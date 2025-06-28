"""
节点处理器模块
包含所有蓝图节点的处理器，使用装饰器注册模式
"""

from typing import Optional, List, Tuple, Any, Set
import re

from .models import (
    ASTNode, Expression, Statement,
    EventNode, AssignmentNode, FunctionCallNode, FunctionCallExpression,
    VariableGetExpression, LiteralExpression, TemporaryVariableExpression,
    PropertyAccessNode, UnsupportedNode, ExecutionBlock, BranchNode,
    LoopNode, LoopType, LatentActionNode, TemporaryVariableDeclaration,
    VariableDeclaration, CallbackBlock, CastExpression,
    EventReferenceExpression, LoopVariableExpression, NodeProcessingResult
)
from .common import register_processor, find_pin, create_source_location


# ============================================================================
# 事件节点处理器
# ============================================================================

@register_processor(
    "K2Node_Event", 
    "K2Node_CustomEvent", 
    "K2Node_ComponentBoundEvent",
    "/Script/BlueprintGraph.K2Node_Event",
    "/Script/BlueprintGraph.K2Node_CustomEvent",
    "/Script/BlueprintGraph.K2Node_ComponentBoundEvent"
)
def process_generic_event_node(analyzer, context, node) -> Optional[EventNode]:
    """
    通用事件节点处理器 - 支持多种事件节点类型
    支持: K2Node_Event, K2Node_CustomEvent, K2Node_ComponentBoundEvent
    """
    # 根据节点类型提取事件名称
    event_name = _extract_event_name(node)
    
    # 自动提取事件参数
    parameters = _extract_event_parameters(node)
    
    # 创建事件节点
    event_node = EventNode(
        event_name=event_name,
        parameters=parameters,
        body=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    
    # 查找执行输出引脚并跟随执行流
    exec_pin = _find_execution_output_pin(node)
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
    "K2Node_VariableSet",
    "/Script/BlueprintGraph.K2Node_VariableSet"
)
def process_variable_set(analyzer, context, node) -> Optional[AssignmentNode]:
    """
    处理变量赋值节点 - 增强版本
    K2Node_VariableSet -> AssignmentNode
    实现完整的数据流解析以正确识别目标对象
    """
    # 提取变量名
    var_name, is_self_context = analyzer._extract_variable_reference(node)
    
    # 查找值引脚（通常是和变量同名的输入引脚）
    value_pin = find_pin(node, var_name, "input")
    if not value_pin:
        # 尝试查找任何非exec的输入引脚
        for pin in node.pins:
            if pin.direction == "input" and pin.pin_type != "exec":
                value_pin = pin
                break
    
    # 解析值表达式
    value_expr = analyzer._resolve_data_expression(context, value_pin) if value_pin else LiteralExpression(
        value="null",
        literal_type="null"
    )
    
    # 关键修复：解析目标对象
    # 检查 self 引脚以确定操作的真正目标
    self_pin = find_pin(node, "self", "input")
    
    if self_pin and self_pin.linked_to and not is_self_context:
        # 有 self 引脚连接且不是 SelfContext，说明这是对其他对象的属性赋值
        # 使用数据流解析来找到真正的目标对象
        target_object_expr = analyzer._resolve_data_expression(context, self_pin)
        
        # 创建属性访问表达式作为赋值目标
        target_expr = PropertyAccessNode(
            target=target_object_expr,
            property_name=var_name,
            source_location=create_source_location(node)
        )
    else:
        # 没有 self 引脚连接或是 SelfContext，这是对当前对象变量的赋值
        target_expr = VariableGetExpression(
            variable_name=var_name,
            is_self_variable=is_self_context,
            source_location=create_source_location(node)
        )
    
    # 创建赋值节点
    # 对于属性访问，不应该是本地变量声明
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

@register_processor(
    "K2Node_CallFunction",
    "/Script/BlueprintGraph.K2Node_CallFunction"
)
def process_call_function(analyzer, context, node) -> Optional[ASTNode]:
    """
    处理函数调用节点
    使用重构后的公共逻辑减少代码重复
    """
    # 提取函数信息（使用公共逻辑）
    func_name = analyzer._extract_function_reference(node)
    
    # 解析目标对象（self引脚，普通函数调用的特殊处理）
    target_expr = None
    self_pin = find_pin(node, "self", "input")
    if self_pin and self_pin.linked_to:
        target_expr = analyzer._resolve_data_expression(context, self_pin)
    
    # 解析参数（使用公共逻辑）
    arguments = analyzer._parse_function_arguments(context, node)
    
    # 使用公共逻辑创建函数调用节点
    call_node = analyzer._create_function_call_node(context, node, func_name, target_expr, arguments)
    
    # 处理返回值赋值（保留原有的特殊逻辑）
    if isinstance(call_node, FunctionCallNode):
        for pin in node.pins:
            if pin.direction == "output" and pin.pin_type != "exec":
                # 返回值处理暂未实现
                pass
    
    return call_node


@register_processor(
    "K2Node_CallArrayFunction",
    "/Script/BlueprintGraph.K2Node_CallArrayFunction"
)
def process_call_array_function(analyzer, context, node) -> Optional[ASTNode]:
    """
    处理数组函数调用节点
    K2Node_CallArrayFunction -> FunctionCallNode or FunctionCallExpression
    使用重构后的公共逻辑减少代码重复
    """
    # 提取函数名称（数组函数的特殊处理）
    function_name = analyzer._extract_function_reference(node)
    
    # 查找目标数组引脚（数组函数的特殊目标引脚）
    target_pin = find_pin(node, "TargetArray", "input")
    if not target_pin:
        target_pin = find_pin(node, "Array", "input")
    
    target_expr = None
    if target_pin:
        target_expr = analyzer._resolve_data_expression(context, target_pin)
    
    # 解析函数参数（使用公共逻辑，排除数组函数的特殊引脚）
    exclude_pins = {"TargetArray", "Array"}
    arguments = analyzer._parse_function_arguments(context, node, exclude_pins)
    
    # 使用公共逻辑创建函数调用节点
    return analyzer._create_function_call_node(context, node, function_name, target_expr, arguments)


# ============================================================================
# 控制流处理器
# ============================================================================

@register_processor(
    "K2Node_IfThenElse",
    "/Script/BlueprintGraph.K2Node_IfThenElse"
)
def process_if_then_else(analyzer, context, node) -> Optional[BranchNode]:
    """
    处理条件分支节点 - 增强版本
    K2Node_IfThenElse -> BranchNode
    正确处理只有else分支的情况
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
    
    # 跟随true分支（then引脚）
    true_pin = find_pin(node, "then", "output")
    if not true_pin:
        true_pin = find_pin(node, "True", "output")
    
    if true_pin and true_pin.linked_to:
        analyzer._follow_execution_flow(context, true_pin, branch_node.true_branch.statements)
    
    # 跟随false分支（else引脚）
    false_pin = find_pin(node, "else", "output")
    if not false_pin:
        false_pin = find_pin(node, "False", "output")
    
    if false_pin and false_pin.linked_to:
        analyzer._follow_execution_flow(context, false_pin, branch_node.false_branch.statements)
    
    return branch_node


@register_processor(
    "K2Node_ExecutionSequence",
    "/Script/BlueprintGraph.K2Node_ExecutionSequence"
)
def process_execution_sequence(analyzer, context, node) -> Optional[ExecutionBlock]:
    """
    处理执行序列节点
    K2Node_ExecutionSequence -> ExecutionBlock with numbered outputs
    """
    sequence_block = ExecutionBlock()
    
    # 查找所有数字编号的输出引脚并按顺序处理
    output_pins = []
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type == "exec":
            # 提取引脚的数字编号
            try:
                pin_number = int(pin.pin_name.replace("then_", "").replace("Then ", ""))
                output_pins.append((pin_number, pin))
            except ValueError:
                # 如果不是数字编号，按原顺序添加
                output_pins.append((999, pin))  # 给非数字引脚一个很大的排序值
    
    # 按编号排序
    output_pins.sort(key=lambda x: x[0])
    
    # 按顺序跟随每个输出引脚
    for _, pin in output_pins:
        analyzer._follow_execution_flow(context, pin, sequence_block.statements)
    
    return sequence_block


# ============================================================================
# 宏和特殊节点处理器
# ============================================================================

@register_processor(
    "K2Node_MacroInstance",
    "/Script/BlueprintGraph.K2Node_MacroInstance"
)
def process_macro_instance(analyzer, context, node) -> Optional[ASTNode]:
    """
    处理宏实例节点 - 增强版本
    支持ForEach, While等常见宏，改进宏名称提取逻辑
    正确处理NodeProcessingResult以支持continuation_pin
    """
    macro_ref = node.properties.get("MacroGraphReference", "")
    
    # 提取宏名称的简短形式
    if isinstance(macro_ref, dict):
        macro_name = macro_ref.get("MacroGraph", "")
    elif isinstance(macro_ref, str):
        # MacroGraphReference 是字符串格式，提取宏名称
        macro_name = macro_ref
    else:
        macro_name = ""
    
    # 改进的宏名称提取逻辑
    if isinstance(macro_name, str):
        # 处理格式: "/Script/Engine.EdGraph'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'"
        if ":" in macro_name:
            macro_name = macro_name.split(":")[-1].rstrip("'")
        elif "/" in macro_name and "." in macro_name:
            # 提取最后一个路径部分
            macro_name = macro_name.split("'")[-2].split(".")[-1] if "'" in macro_name else macro_name.split(".")[-1]
    
    # 根据宏类型分发到特定处理器
    if "ForEach" in macro_name or "ForEachLoop" in macro_name:
        result = _process_foreach_macro(analyzer, context, node)
        # 关键修复：正确处理 NodeProcessingResult
        if hasattr(result, 'node') and hasattr(result, 'continuation_pin'):
            # 设置 continuation_pin 到 context 中
            if result.continuation_pin:
                context.pending_continuation_pin = result.continuation_pin
            return result.node
        return result
    elif "While" in macro_name:
        return _process_while_macro(analyzer, context, node)
    else:
        return _process_generic_macro(analyzer, context, node)


@register_processor(
    "K2Node_LatentAbilityCall",
    "/Script/GameplayAbilitiesEditor.K2Node_LatentAbilityCall"
)
def process_latent_ability_call(analyzer, context, node) -> Optional[LatentActionNode]:
    """
    处理延迟能力调用节点
    K2Node_LatentAbilityCall -> LatentActionNode
    """
    # 提取函数名
    func_name = analyzer._extract_function_reference(node)
    
    # 解析目标对象
    target_expr = None
    self_pin = find_pin(node, "self", "input")
    if self_pin and self_pin.linked_to:
        target_expr = analyzer._resolve_data_expression(context, self_pin)
    
    # 解析参数
    arguments = analyzer._parse_function_arguments(context, node, {"self"})
    
    # 创建函数调用
    call_node = FunctionCallNode(
        target=target_expr,
        function_name=func_name,
        arguments=arguments,
        source_location=create_source_location(node)
    )
    
    # 创建延迟动作节点
    latent_node = LatentActionNode(
        call=call_node,
        callback_exec_pins={},
        source_location=create_source_location(node)
    )
    
    # 处理回调执行引脚
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type == "exec" and pin.pin_name != "then":
            callback_block = ExecutionBlock()
            
            # 推断回调参数并添加到符号表
            callback_declarations = analyzer._infer_callback_parameters(pin.pin_name, node)
            for decl in callback_declarations:
                context.symbol_table.declare(decl.variable_name, decl)
            
            # 跟随回调执行流
            analyzer._follow_execution_flow(context, pin, callback_block.statements)
            
            # 创建CallbackBlock并设置声明
            callback_block_node = CallbackBlock(
                declarations=callback_declarations,
                statements=callback_block.statements
            )
            
            latent_node.callback_exec_pins[pin.pin_name] = callback_block_node
    
    return latent_node


# ============================================================================
# 其他节点处理器
# ============================================================================

@register_processor(
    "K2Node_Knot",
    "/Script/BlueprintGraph.K2Node_Knot"
)
def process_knot_node(analyzer, context, node) -> Optional[ASTNode]:
    """
    处理连接节点（Knot节点）
    这些节点只是透传数据/执行流，不产生AST节点
    """
    # Knot节点不产生AST节点，只是透传
    return None


@register_processor(
    "K2Node_DynamicCast",
    "/Script/BlueprintGraph.K2Node_DynamicCast"
)
def process_dynamic_cast(analyzer, context, node) -> Optional[BranchNode]:
    """
    处理动态类型转换节点
    K2Node_DynamicCast -> BranchNode with cast assignment
    """
    # 解析输入对象
    object_pin = find_pin(node, "Object", "input")
    object_expr = analyzer._resolve_data_expression(context, object_pin) if object_pin else VariableGetExpression(
        variable_name="self", is_self_variable=True
    )
    
    # 提取目标类型
    target_type = node.properties.get("TargetType", "")
    if isinstance(target_type, str) and "'" in target_type:
        parts = target_type.split("'")
        if len(parts) >= 2:
            class_path = parts[-2]
            target_type_name = class_path.split(".")[-1]
        else:
            target_type_name = target_type
    else:
        target_type_name = "UnknownType"
    
    # 创建类型转换表达式
    cast_expr = CastExpression(
        source_expression=object_expr,
        target_type=target_type_name,
        source_location=create_source_location(node)
    )
    
    # 创建分支节点
    branch_node = BranchNode(
        condition=cast_expr,
        true_branch=ExecutionBlock(),
        false_branch=ExecutionBlock(),
        source_location=create_source_location(node)
    )
    
    # 在true分支中添加转换后变量的声明
    cast_var_name = f"As{target_type_name}"
    cast_declaration = VariableDeclaration(
        variable_name=cast_var_name,
        variable_type=target_type_name,
        initial_value=cast_expr,
        is_loop_variable=False,
        is_callback_parameter=False,
        source_location=create_source_location(node)
    )
    branch_node.true_branch.statements.append(cast_declaration)
    
    # 跟随执行流
    then_pin = find_pin(node, "then", "output")
    if then_pin:
        analyzer._follow_execution_flow(context, then_pin, branch_node.true_branch.statements)
    
    cast_failed_pin = find_pin(node, "CastFailed", "output")
    if cast_failed_pin:
        analyzer._follow_execution_flow(context, cast_failed_pin, branch_node.false_branch.statements)
    
    return branch_node


@register_processor(
    "K2Node_AssignDelegate",
    "/Script/BlueprintGraph.K2Node_AssignDelegate"
)
def process_assign_delegate(analyzer, context, node) -> Optional[AssignmentNode]:
    """
    处理委托赋值节点 - 增强版本
    K2Node_AssignDelegate -> AssignmentNode
    支持解析复杂的属性访问链作为委托赋值目标
    """
    # 从DelegateReference中提取委托属性名
    delegate_ref = node.properties.get("DelegateReference", {})
    if isinstance(delegate_ref, dict):
        delegate_prop = delegate_ref.get("MemberName", "UnknownDelegate")
    elif isinstance(delegate_ref, str) and "MemberName=" in delegate_ref:
        import re
        match = re.search(r'MemberName="([^"]+)"', delegate_ref)
        delegate_prop = match.group(1) if match else "UnknownDelegate"
    else:
        delegate_prop = node.properties.get("DelegatePropertyName", "UnknownDelegate")
    
    # 查找委托值引脚
    delegate_pin = find_pin(node, "Delegate", "input")
    delegate_expr = analyzer._resolve_data_expression(context, delegate_pin) if delegate_pin else LiteralExpression(
        value="null", literal_type="delegate"
    )
    
    # 关键修复：解析目标对象的完整属性访问链
    self_pin = find_pin(node, "self", "input")
    
    if self_pin and self_pin.linked_to:
        # 递归解析self引脚连接的属性访问链
        target_object_expr = analyzer._resolve_data_expression(context, self_pin)
        
        # 创建属性访问表达式作为赋值目标
        target_expr = PropertyAccessNode(
            target=target_object_expr,
            property_name=delegate_prop,
            source_location=create_source_location(node)
        )
    else:
        # 没有self引脚连接，这是对当前对象委托的赋值
        target_expr = VariableGetExpression(
            variable_name=delegate_prop,
            is_self_variable=True,
            source_location=create_source_location(node)
        )
    
    # 创建赋值节点
    assignment = AssignmentNode(
        target=target_expr,
        value_expression=delegate_expr,
        is_local_variable=False,  # 委托赋值不是本地变量声明
        source_location=create_source_location(node)
    )
    
    return assignment


# ============================================================================
# 新迁移的处理器 - 从 analyzer.py 移过来
# ============================================================================

@register_processor("K2Node_Literal")
def process_literal_node(analyzer, context, node) -> Optional[LiteralExpression]:
    """
    处理字面量节点
    """
    # 尝试从节点属性中提取字面量值
    literal_value = node.properties.get("Value", node.properties.get("DefaultValue", "null"))
    literal_type = "unknown"  # 基于引脚类型的类型推断暂未实现
    
    return LiteralExpression(
        value=str(literal_value),
        literal_type=literal_type
    )


@register_processor("K2Node_MathExpression")
def process_math_expression_node(analyzer, context, node) -> Optional[FunctionCallExpression]:
    """
    处理数学表达式节点
    """
    # 数学表达式节点通常有操作符属性
    op = node.properties.get("Op", "+")
    
    # 查找输入引脚
    inputs = []
    for pin in node.pins:
        if pin.direction == "input" and pin.pin_type not in ["exec"]:
            input_expr = analyzer._resolve_data_expression(context, pin)
            inputs.append((pin.pin_name, input_expr))
    
    return FunctionCallExpression(
        target=None,
        function_name=f"math_{op}",
        arguments=inputs,
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
    
    array_expr = analyzer._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression("null", "null")
    index_expr = analyzer._resolve_data_expression(context, index_pin) if index_pin else LiteralExpression("0", "int")
    
    return FunctionCallExpression(
        target=array_expr,
        function_name="get_item",
        arguments=[("index", index_expr)],
        source_location=create_source_location(node)
    )


@register_processor("K2Node_MacroInstance:ForEachLoop")
def process_foreach_macro(analyzer, context, node) -> NodeProcessingResult:
    """
    处理 ForEach 循环宏
    """
    # 查找输入引脚
    array_pin = find_pin(node, "Array", "input")
    
    # 解析数组表达式
    array_expr = analyzer._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression("[]", "array")
    
    # 创建循环变量
    element_var = VariableDeclaration(
        variable_name="ArrayElement",
        variable_type="auto",
        is_loop_variable=True
    )
    
    index_var = VariableDeclaration(
        variable_name="ArrayIndex",
        variable_type="int",
        is_loop_variable=True
    )
    
    # 注册循环变量到符号表
    context.symbol_table.declare_variable(element_var.variable_name, element_var)
    context.symbol_table.declare_variable(index_var.variable_name, index_var)
    
    # 创建循环体
    loop_body_statements = []
    
    # 查找循环体的执行引脚
    loop_body_pin = find_pin(node, "Loop Body", "output")
    if loop_body_pin:
        analyzer._follow_execution_flow(context, loop_body_pin, loop_body_statements)
    
    # 创建循环体执行块
    loop_body = ExecutionBlock(
        statements=loop_body_statements,
        declarations=[element_var, index_var]
    )
    
    # 创建循环节点
    loop_node = LoopNode(
        loop_type="foreach",
        condition=array_expr,
        body=loop_body,
        source_location=create_source_location(node)
    )
    
    # 查找完成后的执行引脚
    completed_pin = find_pin(node, "Completed", "output")
    
    return NodeProcessingResult(
        ast_node=loop_node,
        continuation_pin=completed_pin
    )


@register_processor("K2Node_MacroInstance:WhileLoop")
def process_while_macro(analyzer, context, node) -> Optional[LoopNode]:
    """
    处理 While 循环宏
    """
    # 查找条件引脚
    condition_pin = find_pin(node, "Condition", "input")
    condition_expr = analyzer._resolve_data_expression(context, condition_pin) if condition_pin else LiteralExpression("true", "bool")
    
    # 创建循环体
    loop_body_statements = []
    
    # 查找循环体的执行引脚
    loop_body_pin = find_pin(node, "Loop Body", "output")
    if loop_body_pin:
        analyzer._follow_execution_flow(context, loop_body_pin, loop_body_statements)
    
    # 创建循环体执行块
    loop_body = ExecutionBlock(statements=loop_body_statements)
    
    return LoopNode(
        loop_type="while",
        condition=condition_expr,
        body=loop_body,
        source_location=create_source_location(node)
    )


@register_processor("K2Node_MacroInstance")
def process_generic_macro(analyzer, context, node) -> Optional[FunctionCallNode]:
    """
    处理通用宏实例（不是特殊循环的宏）
    """
    # 提取宏名称
    macro_name = node.properties.get("MacroGraphReference", {}).get("MacroGraph", "UnknownMacro")
    if isinstance(macro_name, str) and "." in macro_name:
        macro_name = macro_name.split(".")[-1]
    
    # 解析参数
    arguments = analyzer._parse_function_arguments(context, node, exclude_pins={"exec"})
    
    return FunctionCallNode(
        target=None,
        function_name=f"Macro_{macro_name}",
        arguments=arguments,
        source_location=create_source_location(node)
    )


@register_processor("K2Node_CustomEvent")
def process_custom_event(analyzer, context, node) -> Optional[EventNode]:
    """
    处理自定义事件节点
    """
    # 提取事件名称
    event_name = node.properties.get("CustomFunctionName", "UnknownEvent")
    
    # 解析事件参数（输出引脚）
    event_params = []
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type != "exec":
            event_params.append(pin.pin_name)
    
    # 查找事件执行引脚
    exec_pin = find_pin(node, "then", "output")
    
    # 创建事件体
    event_body_statements = []
    if exec_pin:
        analyzer._follow_execution_flow(context, exec_pin, event_body_statements)
    
    event_body = ExecutionBlock(statements=event_body_statements)
    
    return EventNode(
        event_name=event_name,
        parameters=event_params,
        body=event_body,
        source_location=create_source_location(node)
    )


# ============================================================================
# 辅助函数
# ============================================================================

def _extract_event_name(node) -> str:
    """
    根据节点类型提取事件名称
    """
    if 'K2Node_Event' in node.class_type:
        # 标准事件节点：从EventReference.MemberName提取
        event_ref = node.properties.get("EventReference", "")
        if isinstance(event_ref, dict):
            return event_ref.get("MemberName", node.node_name)
        elif isinstance(event_ref, str) and "MemberName=" in event_ref:
            match = re.search(r'MemberName="([^"]+)"', event_ref)
            return match.group(1) if match else node.node_name
        else:
            return node.node_name
            
    elif 'K2Node_CustomEvent' in node.class_type:
        # 自定义事件节点：从CustomFunctionName提取
        custom_function_name = node.properties.get("CustomFunctionName", "")
        if isinstance(custom_function_name, str):
            event_name = custom_function_name.strip('"') if custom_function_name else node.node_name
        else:
            event_name = node.node_name
        
        # 如果事件名称为空，使用节点名称
        if not event_name or event_name == "K2Node_CustomEvent":
            event_name = "CustomEvent"
        return event_name
        
    elif 'K2Node_ComponentBoundEvent' in node.class_type:
        # 组件绑定事件：组合ComponentPropertyName.DelegatePropertyName
        component_name = node.properties.get("ComponentPropertyName", "")
        delegate_name = node.properties.get("DelegatePropertyName", "")
        
        if component_name and delegate_name:
            return f"{component_name}.{delegate_name}"
        elif delegate_name:
            return delegate_name
        else:
            return node.node_name
    
    # 默认情况
    return node.node_name


def _extract_event_parameters(node) -> List[Tuple[str, str]]:
    """
    自动提取事件参数 - 从非执行的输出引脚中提取
    """
    parameters = []
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type != "exec":
            # 跳过隐藏的引脚和特殊引脚
            if not getattr(pin, 'bHidden', False) and pin.pin_name not in ["OutputDelegate"]:
                parameters.append((pin.pin_name, pin.pin_type))
    return parameters


def _find_execution_output_pin(node) -> Optional:
    """
    查找节点的执行输出引脚
    """
    # 优先查找标准的执行输出引脚
    for pin_name in ["then", "exec"]:
        pin = find_pin(node, pin_name, "output")
        if pin:
            return pin
    
    # 如果没找到，查找任何执行类型的输出引脚
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type == "exec":
            return pin
    
    return None


def _process_foreach_macro(analyzer, context, node) -> NodeProcessingResult:
    """
    处理ForEach宏的特殊逻辑
    """
    # 解析数组表达式
    array_pin = find_pin(node, "Array", "input")
    array_expr = analyzer._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression(
        value="[]", literal_type="array"
    )
    
    # 获取循环输出引脚，用于建立 pin→AST 映射
    element_pin = find_pin(node, "Array Element", "output")
    index_pin = find_pin(node, "Array Index", "output")
    
    # 创建 LoopVariableExpression 实例
    loop_id = node.node_guid  # 使用节点 GUID 作为循环 ID
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
    
    # 建立 pin→AST 映射，解决 UnknownFunction 问题
    if element_pin:
        context.pin_ast_map[element_pin.pin_id] = element_expr
    if index_pin:
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
    
    # 将循环变量添加到符号表
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
    
    # 查找完成后的执行引脚
    completed_pin = find_pin(node, "Completed", "output")
    if completed_pin:
        # 设置continuation_pin以便在循环完成后继续执行
        context.pending_continuation_pin = completed_pin
    
    return NodeProcessingResult(node=loop_node, continuation_pin=completed_pin)


def _process_while_macro(analyzer, context, node) -> Optional[LoopNode]:
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


def _process_generic_macro(analyzer, context, node) -> Optional[FunctionCallNode]:
    """
    处理通用宏（作为函数调用）
    """
    macro_ref = node.properties.get("MacroGraphReference", "")
    
    # 提取宏名称的简短形式
    if isinstance(macro_ref, dict):
        macro_name = macro_ref.get("MacroGraph", "UnknownMacro")
    elif isinstance(macro_ref, str):
        macro_name = macro_ref if macro_ref else "UnknownMacro"
    else:
        macro_name = "UnknownMacro"
    
    # 进一步提取简短名称
    if isinstance(macro_name, str) and "'" in macro_name:
        macro_name = macro_name.split("'")[-2].split(".")[-1] if "." in macro_name else macro_name
    
    # 解析参数
    arguments = analyzer._parse_function_arguments(context, node, {"self"})
    
    return FunctionCallNode(
        target=None,
        function_name=f"Macro_{macro_name}",
        arguments=arguments,
        source_location=create_source_location(node)
    ) 