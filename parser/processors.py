"""
节点处理器模块
包含所有蓝图节点的处理器，使用装饰器注册模式
"""

from typing import Optional, List, Tuple, Any, Set

from .models import (
    ASTNode, Expression, Statement,
    EventNode, AssignmentNode, FunctionCallNode, FunctionCallExpression,
    VariableGetExpression, LiteralExpression, TemporaryVariableExpression,
    PropertyAccessNode, UnsupportedNode, ExecutionBlock, BranchNode,
    LoopNode, LoopType, LatentActionNode, TemporaryVariableDeclaration,
    VariableDeclaration, CallbackBlock, CastExpression,
    EventReferenceExpression, LoopVariableExpression, NodeProcessingResult,
    EventSubscriptionNode
)
from .common import (
    register_processor, find_pin, create_source_location,
    extract_event_name, extract_event_parameters, find_execution_output_pin,
    extract_variable_reference, extract_function_reference, 
    find_then_pin, find_else_pin, find_pin_by_aliases,
    has_execution_pins, extract_macro_name, node_processor_registry,
    parse_object_path
)


# ============================================================================
# 事件节点处理器
# ============================================================================

@register_processor(
    "K2Node_Event", 
    "K2Node_CustomEvent", 
    "K2Node_ComponentBoundEvent"
)
def process_generic_event_node(analyzer, context, node) -> Optional[EventNode]:
    """
    通用事件节点处理器 - 支持多种事件节点类型
    支持: K2Node_Event, K2Node_CustomEvent, K2Node_ComponentBoundEvent
    """
    # 使用统一工具函数提取事件信息
    event_name = extract_event_name(node)
    parameters = extract_event_parameters(node)
    
    # 创建事件节点
    event_node = EventNode(
        event_name=event_name,
        parameters=parameters,
        body=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    
    # 查找执行输出引脚并跟随执行流
    exec_pin = find_execution_output_pin(node)
    if exec_pin:
        analyzer._follow_execution_flow(context, exec_pin, event_node.body.statements)
    
    # 将临时变量声明添加到事件体的开头
    if context.scope_prelude:
        event_node.body.statements = context.scope_prelude + event_node.body.statements
    
    return event_node


# ============================================================================
# 变量操作处理器
# ============================================================================

@register_processor(
    "K2Node_VariableSet"
)
def process_variable_set(analyzer, context, node) -> Optional[AssignmentNode]:
    """
    处理变量赋值节点
    K2Node_VariableSet -> AssignmentNode
    增强：智能识别cast-and-assign模式，抑制冗余赋值
    """
    # 使用统一工具函数提取变量信息
    var_name, is_self_context = extract_variable_reference(node)
    
    # 查找值引脚
    value_pin = find_pin(node, var_name, "input")
    if not value_pin:
        # 尝试查找任何非exec的输入引脚
        for pin in node.pins:
            if pin.direction == "input" and pin.pin_type != "exec":
                value_pin = pin
                break
    
    # 解析值表达式
    value_expr = analyzer._resolve_data_expression(context, value_pin) if value_pin else LiteralExpression(
        value="null", literal_type="null"
    )
    
    # 智能抑制逻辑：检查是否为cast-and-assign模式的冗余赋值
    if isinstance(value_expr, CastExpression):
        # 检查符号表中是否已存在该变量，且其初始值为相同的CastExpression
        symbol = context.symbol_table.lookup(var_name)
        
        if (symbol and 
            hasattr(symbol.declaration, 'initial_value') and
            isinstance(symbol.declaration.initial_value, CastExpression)):
            
            # 比较两个CastExpression是否来自同一个蓝图节点
            # 通过比较source_location的node_guid来精确判断
            current_cast_location = value_expr.source_location
            existing_cast_location = symbol.declaration.initial_value.source_location
            
            if (current_cast_location and existing_cast_location and
                hasattr(current_cast_location, 'node_guid') and
                hasattr(existing_cast_location, 'node_guid') and
                current_cast_location.node_guid == existing_cast_location.node_guid):
                
                # 这是一个冗余的cast-and-assign赋值，抑制AssignmentNode的生成
                # 抑制冗余的cast赋值，因为变量已在cast成功分支中声明并初始化
                return None
    
    # 解析目标对象
    self_pin = find_pin(node, "self", "input")
    
    if self_pin and self_pin.linked_to and not is_self_context:
        # 有 self 引脚连接且不是 SelfContext，这是对其他对象的属性赋值
        target_object_expr = analyzer._resolve_data_expression(context, self_pin)
        
        # 创建属性访问表达式作为赋值目标
        target_expr = PropertyAccessNode(
            target=target_object_expr,
            property_name=var_name,
            source_location=create_source_location(node)
        )
    else:
        # 这是对当前对象变量的赋值
        target_expr = VariableGetExpression(
            variable_name=var_name,
            is_self_variable=is_self_context,
            source_location=create_source_location(node)
        )
    
    # 创建赋值节点
    is_property_access = isinstance(target_expr, PropertyAccessNode)
    assignment = AssignmentNode(
        target=target_expr,
        value_expression=value_expr,
        is_local_variable=not is_self_context and not is_property_access,
        source_location=create_source_location(node)
    )
    
    return assignment


# ============================================================================
# 函数调用处理器
# ============================================================================




# ============================================================================
# 控制流处理器
# ============================================================================

@register_processor(
    "K2Node_IfThenElse"
)
def process_if_then_else(analyzer, context, node) -> Optional[BranchNode]:
    """
    处理条件分支节点
    """
    # 解析条件表达式
    condition_pin = find_pin(node, "Condition", "input")
    condition_expr = analyzer._resolve_data_expression(context, condition_pin) if condition_pin else LiteralExpression(
        value="false", literal_type="bool"
    )
    
    # 创建分支节点
    branch_node = BranchNode(
        condition=condition_expr,
        true_branch=ExecutionBlock(),
        false_branch=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    
    # 跟随true分支
    true_pin = find_then_pin(node)
    if true_pin and true_pin.linked_to:
        analyzer._follow_execution_flow(context, true_pin, branch_node.true_branch.statements)
    
    # 跟随false分支
    false_pin = find_else_pin(node)
    if false_pin and false_pin.linked_to:
        analyzer._follow_execution_flow(context, false_pin, branch_node.false_branch.statements)
    
    return branch_node


@register_processor(
    "K2Node_ExecutionSequence"
)
def process_execution_sequence(analyzer, context, node) -> Optional[ExecutionBlock]:
    """
    处理执行序列节点
    """
    sequence_block = ExecutionBlock()
    
    # 查找所有输出执行引脚并按顺序处理
    output_pins = []
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type == "exec":
            output_pins.append(pin)
    
    # 按引脚名称排序（then, then_1, then_2...）
    output_pins.sort(key=lambda p: (p.pin_name.replace("then", "0").replace("_", "")))
    
    # 跟随每个输出引脚的执行流
    for pin in output_pins:
        if pin.linked_to:
            analyzer._follow_execution_flow(context, pin, sequence_block.statements)
    
    return sequence_block


# ============================================================================
# 特殊节点处理器
# ============================================================================

@register_processor(
    "K2Node_Knot"
)
def process_knot_node(analyzer, context, node) -> Optional[ASTNode]:
    """
    处理连接节点 - 透传数据
    """
    # Knot节点只是透传，不产生任何AST节点
    return None


@register_processor(
    "K2Node_DynamicCast"
)
def process_dynamic_cast(analyzer, context, node) -> Optional[BranchNode]:
    """
    处理动态类型转换节点
    """
    # 解析要转换的对象
    object_pin = find_pin(node, "Object", "input")
    object_expr = analyzer._resolve_data_expression(context, object_pin) if object_pin else LiteralExpression(
        value="null", literal_type="null"
    )
    
    # 提取目标类型（使用增强的 parse_object_path 函数）
    target_type = node.properties.get("TargetType", "UnknownType")
    target_type_name = parse_object_path(target_type) or "UnknownType"
    
    # 动态获取正确的变量名（从输出引脚获取，保留空格）
    as_pin = next((p for p in node.pins if p.direction == "output" and p.pin_type != "exec" and p.pin_name.startswith("As")), None)
    cast_var_name = as_pin.pin_name if as_pin else f"As {target_type_name}"
    
    # 修正变量名：将"AsAbilities Equipped Panel Controller"转换为"As Abilities Equipped Panel Controller"
    # 这是为了匹配K2Node_VariableSet中VariableReference.MemberName的格式
    if cast_var_name.startswith("As") and not cast_var_name.startswith("As "):
        # 在"As"后插入空格，将"AsAbilities"变为"As Abilities"
        cast_var_name = "As " + cast_var_name[2:]
    
    # 创建转换表达式
    cast_expr = CastExpression(
        source_expression=object_expr,
        target_type=target_type_name,
        source_location=create_source_location(node)
    )
    
    # 创建分支节点（转换成功/失败）
    branch_node = BranchNode(
        condition=cast_expr,
        true_branch=ExecutionBlock(),
        false_branch=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    cast_declaration = VariableDeclaration(
        variable_name=cast_var_name,
        variable_type=target_type_name,
        initial_value=cast_expr,
        is_loop_variable=False,
        is_callback_parameter=False,
        source_location=create_source_location(node)
    )
    branch_node.true_branch.statements.append(cast_declaration)
    
    # 将转换成功后的变量注册到符号表中
    context.symbol_table.define(
        name=cast_var_name,
        symbol_type=target_type_name,
        declaration=cast_declaration
    )
    
    # 跟随转换成功分支
    then_pin = find_then_pin(node)
    if then_pin and then_pin.linked_to:
        analyzer._follow_execution_flow(context, then_pin, branch_node.true_branch.statements)
    
    # 跟随转换失败分支
    cast_failed_pin = find_pin(node, "CastFailed", "output")
    if cast_failed_pin and cast_failed_pin.linked_to:
        analyzer._follow_execution_flow(context, cast_failed_pin, branch_node.false_branch.statements)
    
    return branch_node


# ============================================================================
# 简单表达式处理器
# ============================================================================

@register_processor("K2Node_Literal")
def process_literal_node(analyzer, context, node) -> Optional[LiteralExpression]:
    """
    处理字面量节点
    """
    literal_value = node.properties.get("ObjectRef", "")
    return LiteralExpression(
        value=literal_value,
        literal_type="literal",
        source_location=create_source_location(node)
    )


@register_processor("K2Node_MathExpression")
def process_math_expression_node(analyzer, context, node) -> Optional[FunctionCallExpression]:
    """
    处理数学表达式节点
    """
    expression = node.properties.get("Expression", "")
    
    # 解析参数
    arguments = analyzer._parse_function_arguments(context, node)
    
    return FunctionCallExpression(
        target=None,
        function_name=f"MathExpression({expression})",
        arguments=arguments,
        source_location=create_source_location(node)
    )


@register_processor("K2Node_ArrayGet")
def process_array_access_node(analyzer, context, node) -> Optional[FunctionCallExpression]:
    """
    处理数组访问节点
    """
    # 查找数组和索引引脚
    array_pin = find_pin(node, "TargetArray", "input")
    index_pin = find_pin(node, "Index", "input")
    
    array_expr = analyzer._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression("null", "array")
    index_expr = analyzer._resolve_data_expression(context, index_pin) if index_pin else LiteralExpression("0", "int")
    
    return FunctionCallExpression(
        target=array_expr,
        function_name="Get",
        arguments=[("Index", index_expr)],
        source_location=create_source_location(node)
    )


# ============================================================================
# 宏处理器
# ============================================================================

@register_processor("K2Node_MacroInstance:ForEachLoop")
def process_foreach_macro(analyzer, context, node) -> NodeProcessingResult:
    """
    处理ForEach宏 - 使用ScopeManager精确管理循环变量作用域
    """
    # 解析数组表达式
    array_pin = find_pin(node, "Array", "input")
    array_expr = analyzer._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression(
        value="[]", literal_type="array"
    )
    
    # 获取循环输出引脚
    element_pin = find_pin(node, "Array Element", "output")
    index_pin = find_pin(node, "Array Index", "output")
    
    # 创建循环变量表达式
    loop_id = node.node_guid
    element_expr = LoopVariableExpression(
        variable_name="ArrayElement",
        is_index=False,
        loop_id=loop_id
    )
    index_expr = LoopVariableExpression(
        variable_name="ArrayIndex", 
        is_index=True,
        loop_id=loop_id
    )
    
    # 新架构：进入新的作用域
    context.scope_manager.enter_scope()
    
    # 注册循环变量到ScopeManager（解决UnknownExpression的核心）
    if element_pin:
        context.scope_manager.register_variable(element_pin.pin_id, element_expr)
        # 向后兼容：同时添加到pin_ast_map
        context.pin_ast_map[element_pin.pin_id] = element_expr
    
    if index_pin:
        context.scope_manager.register_variable(index_pin.pin_id, index_expr)
        # 向后兼容：同时添加到pin_ast_map
        context.pin_ast_map[index_pin.pin_id] = index_expr
    
    # 创建循环变量声明
    item_declaration = VariableDeclaration(
        variable_name="ArrayElement",
        variable_type="auto",
        is_loop_variable=True
    )
    
    index_declaration = VariableDeclaration(
        variable_name="ArrayIndex",
        variable_type="int",
        is_loop_variable=True
    )
    
    # 添加到符号表（向后兼容）
    context.symbol_table.define("ArrayElement", "auto", item_declaration, is_loop_variable=True)
    context.symbol_table.define("ArrayIndex", "int", index_declaration, is_loop_variable=True)
    
    # 创建循环节点
    loop_node = LoopNode(
        loop_type=LoopType.FOR_EACH,
        collection_expression=array_expr,
        item_declaration=item_declaration,
        index_declaration=index_declaration,
        body=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    
    # 跟随循环体执行流
    loop_body_pin = find_pin(node, "LoopBody", "output")
    if loop_body_pin:
        analyzer._follow_execution_flow(context, loop_body_pin, loop_node.body.statements)
    
    # 离开作用域（关键：这将在analyzer中处理，通过NodeProcessingResult传递信息）
    # 注意：实际的scope_manager.leave_scope()将在analyzer中调用
    
    # 查找完成后的执行引脚
    completed_pin = find_pin(node, "Completed", "output")
    
    return NodeProcessingResult(node=loop_node, continuation_pin=completed_pin)


@register_processor("K2Node_MacroInstance:WhileLoop")
def process_while_macro(analyzer, context, node) -> Optional[LoopNode]:
    """
    处理While宏
    """
    # 解析条件表达式
    condition_pin = find_pin(node, "Condition", "input")
    condition_expr = analyzer._resolve_data_expression(context, condition_pin) if condition_pin else LiteralExpression(
        value="true", literal_type="bool"
    )
    
    # 创建While循环节点
    loop_node = LoopNode(
        loop_type=LoopType.WHILE,
        condition_expression=condition_expr,
        body=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    
    # 跟随循环体执行流
    loop_body_pin = find_pin(node, "LoopBody", "output")
    if loop_body_pin:
        analyzer._follow_execution_flow(context, loop_body_pin, loop_node.body.statements)
    
    return loop_node


@register_processor("K2Node_MacroInstance")
def process_generic_macro(analyzer, context, node) -> Optional[FunctionCallNode]:
    """
    处理通用宏（作为函数调用）
    增强的警告机制：检测是否存在本应被调用但未被调用的专用处理器
    """
    # 注释：专用处理器的调度由analyzer.py中的_process_node方法处理
    # 如果到达这里，说明没有找到专用处理器，或者专用处理器处理失败
    macro_name = extract_macro_name(node)
    specific_key = f"{node.class_type}:{macro_name}"
    
    macro_ref = node.properties.get("MacroGraphReference", "")
    
    # 提取宏名称
    if isinstance(macro_ref, dict):
        display_macro_name = macro_ref.get("MacroGraph", "UnknownMacro")
    elif isinstance(macro_ref, str):
        display_macro_name = macro_ref if macro_ref else "UnknownMacro"
    else:
        display_macro_name = "UnknownMacro"
    
    # 简化宏名称用于显示
    if isinstance(display_macro_name, str) and "'" in display_macro_name:
        display_macro_name = display_macro_name.split("'")[-2].split(".")[-1] if "." in display_macro_name else display_macro_name
    
    # 解析参数
    arguments = analyzer._parse_function_arguments(context, node, {"self"})
    
    return FunctionCallNode(
        target=None,
        function_name=f"Macro_{display_macro_name}",
        arguments=arguments,
        source_location=create_source_location(node)
    )


# ============================================================================
# 委托处理器 - 统一事件订阅处理
# ============================================================================

@register_processor(
    "K2Node_AddDelegate",
    "K2Node_AssignDelegate"
)
def process_delegate_subscription(analyzer, context, node) -> Optional[EventSubscriptionNode]:
    """
    统一委托处理器 - 处理事件订阅节点
    支持: K2Node_AddDelegate, K2Node_AssignDelegate
    将委托绑定转换为新的事件订阅模型
    """
    # 解析事件源对象 (source_object)
    # 通过解析连接到节点 "self" 输入引脚的对象来获取
    self_pin = find_pin(node, "self", "input")
    if self_pin and self_pin.linked_to:
        source_object = analyzer._resolve_data_expression(context, self_pin)
    else:
        # 如果没有连接的self引脚，使用默认的self引用
        source_object = VariableGetExpression(
            variable_name="self",
            is_self_variable=True,
            source_location=create_source_location(node)
        )
    
    # 解析事件名 (event_name)
    # 从节点的 DelegateReference.MemberName 属性中提取
    event_name = "UnknownEvent"
    delegate_reference = node.properties.get("DelegateReference", {})
    if isinstance(delegate_reference, dict):
        event_name = delegate_reference.get("MemberName", "UnknownEvent")
    elif isinstance(delegate_reference, str):
        # 处理字符串格式的委托引用
        # 例如: "(MemberParent=Class'/Script/UMG.Button',MemberName=OnClicked)"
        if "MemberName=" in delegate_reference:
            # 提取 MemberName= 后面的值
            parts = delegate_reference.split("MemberName=")
            if len(parts) > 1:
                # 获取MemberName后的值，去掉结尾的括号
                member_name = parts[1].split(")")[0].split(",")[0].strip('"').strip("'")
                if member_name:
                    event_name = member_name
    
    # 解析处理器 (handler)
    # 通过解析连接到节点 "Delegate" 输入引脚的 K2Node_CustomEvent 来获取
    delegate_pin = find_pin(node, "Delegate", "input")
    if delegate_pin and delegate_pin.linked_to:
        handler = analyzer._resolve_data_expression(context, delegate_pin)
    else:
        # 如果没有连接的委托引脚，查找其他可能的引脚名称
        handler_pin = None
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type != "exec" and 
                pin.pin_name.lower() in ["delegate", "value", "event"]):
                handler_pin = pin
                break
        
        if handler_pin and handler_pin.linked_to:
            handler = analyzer._resolve_data_expression(context, handler_pin)
        else:
            # 使用默认的事件引用
            handler = EventReferenceExpression(
                event_name="UnknownHandler",
                source_location=create_source_location(node)
            )
    
    # 构建并返回新的事件订阅节点
    return EventSubscriptionNode(
        source_object=source_object,
        event_name=event_name,
        handler=handler,
        source_location=create_source_location(node)
    )


# ============================================================================
# 特殊能力调用处理器 - Inject-and-Delegate 模式实现
# ============================================================================




# ============================================================================
# Widget创建处理器
# ============================================================================




# ============================================================================
# 统一通用可调用处理器 - 消除重复逻辑
# ============================================================================

@register_processor(
    "K2Node_CallFunction",
    "K2Node_CallArrayFunction", 
    "K2Node_LatentAbilityCall",
    "K2Node_CreateWidget"
)
def process_generic_callable(analyzer, context, node) -> Optional[ASTNode]:
    """
    统一通用可调用处理器 - 处理所有类似函数调用的节点
    消除 process_call_function, process_call_array_function, process_latent_ability_call, process_create_widget 的重复逻辑
    """
    # 第一步：提取函数名称，根据节点类型使用不同策略
    if "CreateWidget" in node.class_type:
        func_name = "CreateWidget"
    elif "LatentAbilityCall" in node.class_type:
        func_name = node.properties.get("ProxyFactoryFunctionName", "LatentAbilityCall")
    else:
        func_name = extract_function_reference(node)
    
    # 第二步：解析目标对象，根据节点类型使用不同的引脚别名
    target_expr = None
    
    if "CallArrayFunction" in node.class_type:
        # 数组函数使用 target 别名查找
        target_pin = find_pin_by_aliases(node, "target", "input")
        if target_pin:
            target_expr = analyzer._resolve_data_expression(context, target_pin)
    else:
        # 其他函数使用 self 引脚
        self_pin = find_pin(node, "self", "input")
        if self_pin and self_pin.linked_to:
            target_expr = analyzer._resolve_data_expression(context, self_pin)
    
    # 第三步：特殊处理 - LatentAbilityCall 的 Inject-and-Delegate 模式
    if "LatentAbilityCall" in node.class_type:
        # Phase 1: 参数注入 (Inject)
        # 检查是否存在 OwningAbility 引脚，如果没有连接则注入 self 上下文
        owning_ability_pin = find_pin(node, "OwningAbility", "input")
        
        if owning_ability_pin and not owning_ability_pin.linked_to:
            # 注入 self 上下文到 OwningAbility 参数
            self_expr = VariableGetExpression(
                variable_name="self",
                is_self_variable=True,
                source_location=create_source_location(node)
            )
            # 将注入的表达式添加到 pin_ast_map 中
            context.pin_ast_map[owning_ability_pin.pin_id] = self_expr
    
    # 第四步：解析参数，根据节点类型排除不同的特殊引脚
    exclude_pins = {"self"}  # 默认排除 self
    
    if "CallArrayFunction" in node.class_type:
        exclude_pins.update({"TargetArray", "Array"})
    elif "LatentAbilityCall" in node.class_type:
        exclude_pins.update({"OwningAbility"})
    
    # 第五步：特殊处理 CreateWidget 的 Class 参数
    if "CreateWidget" in node.class_type:
        # CreateWidget 需要特殊处理 Class 参数
        arguments = []
        
        # 解析Class参数（Widget类型）
        class_pin = find_pin(node, "Class", "input")
        class_expr = None
        
        if class_pin:
            if class_pin.default_object:
                # 从default_object中提取类名
                class_name = parse_object_path(class_pin.default_object)
                if class_name:
                    class_expr = LiteralExpression(
                        value=f'"{class_name}"',
                        literal_type="string",
                        source_location=create_source_location(node)
                    )
            
            # 如果default_object解析失败，尝试从连接的引脚获取
            if not class_expr and class_pin.linked_to:
                class_expr = analyzer._resolve_data_expression(context, class_pin)
        
        # 如果仍然没有找到类信息，使用默认值
        if not class_expr:
            class_expr = LiteralExpression(
                value='"UnknownWidget"',
                literal_type="string",
                source_location=create_source_location(node)
            )
        
        arguments.append(("Class", class_expr))
        
        # 查找并解析OwningPlayer参数（如果存在）
        owning_player_pin = find_pin(node, "OwningPlayer", "input")
        if owning_player_pin and owning_player_pin.linked_to:
            owning_player_expr = analyzer._resolve_data_expression(context, owning_player_pin)
            arguments.append(("OwningPlayer", owning_player_expr))
    else:
        # 其他节点使用通用参数解析
        arguments = analyzer._parse_function_arguments(context, node, exclude_pins)
    
    # 第六步：创建函数调用节点，根据执行引脚决定类型
    # CreateWidget 特殊处理：即使有执行引脚也返回表达式，以便后续节点引用其返回值
    if "CreateWidget" in node.class_type:
        return FunctionCallExpression(
            target=target_expr,
            function_name=func_name,
            arguments=arguments,
            source_location=create_source_location(node)
        )
    elif has_execution_pins(node):
        return FunctionCallNode(
            target=target_expr,
            function_name=func_name,
            arguments=arguments,
            source_location=create_source_location(node)
        )
    else:
        return FunctionCallExpression(
            target=target_expr,
            function_name=func_name,
            arguments=arguments,
            source_location=create_source_location(node)
        ) 