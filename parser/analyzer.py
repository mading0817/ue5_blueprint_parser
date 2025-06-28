"""
Blueprint Graph Analyzer
将原始的BlueprintGraph转换为逻辑抽象语法树(AST)
支持新的统一解析模型架构
"""

from typing import Dict, List, Optional, Callable, Set, Tuple, Any
from dataclasses import dataclass, field

from .models import (
    BlueprintGraph, GraphNode, GraphPin,
    # AST节点
    ASTNode, Expression, Statement,
    SourceLocation, ExecutionBlock, EventNode, AssignmentNode,
    FunctionCallNode, FunctionCallExpression, VariableGetExpression,
    LiteralExpression, TemporaryVariableExpression, CastExpression,
    TemporaryVariableDeclaration, PropertyAccessNode, UnsupportedNode,
    # 控制流节点
    BranchNode, LoopNode, LoopType, LatentActionNode,
    # 新的语义节点
    VariableDeclaration, CallbackBlock,
    # 新架构核心数据结构
    ResolutionResult, EventReferenceExpression, LoopVariableExpression,
    NodeProcessingResult
)
from .symbol_table import SymbolTable, Symbol
from .utils import find_pin, create_source_location, get_pin_default_value, extract_pin_type


# 节点处理器类型定义
NodeProcessor = Callable[['AnalysisContext', GraphNode], Optional[ASTNode]]


@dataclass
class AnalysisContext:
    """
    分析上下文，包含多遍分析所需的所有状态信息
    """
    graph: BlueprintGraph
    symbol_table: SymbolTable = field(default_factory=SymbolTable)  # 符号表，管理作用域和变量
    pin_usage_counts: Dict[str, int] = field(default_factory=dict)  # pin_key -> usage_count
    scope_prelude: List[Statement] = field(default_factory=list)  # 当前作用域的前置语句（临时变量声明等）
    memoization_cache: Dict[str, Expression] = field(default_factory=dict)  # pin_key -> cached_expression
    visited_nodes: Set[str] = field(default_factory=set)  # 已访问的节点GUID
    pin_ast_map: Dict[str, Expression] = field(default_factory=dict)  # pin_id -> AST表达式映射，用于循环变量等特殊节点
    # 新增：支持 NodeProcessingResult 的 continuation_pin 处理
    pending_continuation_pin: Optional['GraphPin'] = None  # 来自复杂节点（如 ForEachLoop）的延续执行引脚


# 旧的AnalysisState类已被AnalysisContext替代


class GraphAnalyzer:
    """
    蓝图图分析器
    负责将BlueprintGraph转换为逻辑AST
    新架构：支持统一解析模型
    """
    
    def __init__(self):
        # 初始化节点处理器注册表
        self._node_processors: Dict[str, NodeProcessor] = {}
        self._register_default_processors()
    
    def _register_default_processors(self):
        """注册默认的节点处理器"""
        # 使用简化的注册方式
        processors = {
            "K2Node_Event": self._process_generic_event_node,
            "K2Node_CustomEvent": self._process_generic_event_node,
            "K2Node_ComponentBoundEvent": self._process_generic_event_node,
            "K2Node_VariableSet": self._process_variable_set,
            "K2Node_CallFunction": self._process_call_function,
            "K2Node_IfThenElse": self._process_if_then_else,
            "K2Node_ExecutionSequence": self._process_execution_sequence,
            "K2Node_MacroInstance": self._process_macro_instance,
            "K2Node_LatentAbilityCall": self._process_latent_ability_call,
            "K2Node_Knot": self._process_knot_node,
            "K2Node_DynamicCast": self._process_dynamic_cast,
            "K2Node_AssignDelegate": self._process_assign_delegate,
            "K2Node_CallArrayFunction": self._process_call_array_function,
        }
        
        # 注册简短名称和完整路径
        for short_name, processor in processors.items():
            self.register_processor(short_name, processor)
            # 自动生成完整路径
            if short_name.startswith("K2Node_"):
                full_path = f"/Script/BlueprintGraph.{short_name}"
                self.register_processor(full_path, processor)
                    
        # 特殊路径注册
        self.register_processor("/Script/GameplayAbilitiesEditor.K2Node_LatentAbilityCall", 
                               self._process_latent_ability_call)
    
    def register_processor(self, node_type: str, processor: NodeProcessor):
        """
        注册节点处理器
        """
        self._node_processors[node_type] = processor
    
    # ========================================================================
    # 新架构核心方法：统一解析模型
    # ========================================================================
    
    def resolve(self, context: AnalysisContext, pin: GraphPin) -> ResolutionResult:
        """
        统一解析方法 - 新架构的核心
        解析一个引脚，返回其触发的语句和/或产生的表达式
        
        :param context: 分析上下文
        :param pin: 要解析的引脚
        :return: 解析结果，包含语句和表达式
        """
        # 如果是执行引脚，解析后续的执行流
        if pin.pin_type == "exec" and pin.direction == "output":
            statements = []
            self._follow_execution_flow(context, pin, statements)
            return ResolutionResult(statements=statements, expression=None)
        
        # 如果是数据引脚，解析数据表达式
        elif pin.pin_type != "exec":
            expression = self._resolve_data_expression(context, pin)
            return ResolutionResult(statements=[], expression=expression)
        
        # 其他情况返回空结果
        return ResolutionResult(statements=[], expression=None)
    
    # ========================================================================
    # 分析入口方法（已更新为使用新架构）
    # ========================================================================
    
    def analyze(self, graph: BlueprintGraph) -> List[ASTNode]:
        """
        分析蓝图图并返回AST节点列表
        主入口方法 - 使用统一解析模型架构
        """
        # Pass 1: 符号与依赖分析
        pin_usage_counts = self._perform_symbol_analysis(graph)
        
        # Pass 2: 上下文感知AST生成
        context = AnalysisContext(
            graph=graph,
            symbol_table=SymbolTable(),  # 初始化符号表
            pin_usage_counts=pin_usage_counts
        )
        
        # 处理所有入口节点
        ast_nodes = []
        for entry_node in graph.entry_nodes:
            if entry_node.node_guid not in context.visited_nodes:
                ast_node = self._process_node(context, entry_node)
                if ast_node:
                    ast_nodes.append(ast_node)
        
        return ast_nodes
    
    def _perform_symbol_analysis(self, graph: BlueprintGraph) -> Dict[str, int]:
        """
        Pass 1: 符号与依赖分析
        遍历图中所有节点和连接，构建pin使用计数表
        """
        pin_usage_counts = {}
        
        for node in graph.nodes.values():
            for pin in node.pins:
                # 统计每个输出引脚被连接的次数
                if pin.direction == "output" and pin.linked_to:
                    pin_key = f"{node.node_guid}:{pin.pin_id}"
                    pin_usage_counts[pin_key] = len(pin.linked_to)
        
        return pin_usage_counts
    
    def _process_node(self, context: AnalysisContext, node: GraphNode) -> Optional[ASTNode]:
        """
        处理单个节点，调用相应的处理器
        """
        if node.node_guid in context.visited_nodes:
            return None
        
        # 标记为已访问
        context.visited_nodes.add(node.node_guid)
        
        # 查找对应的处理器
        processor = self._node_processors.get(node.class_type)
        if processor:
            return processor(context, node)
        else:
            # 未知节点类型，创建UnsupportedNode
            return UnsupportedNode(
                class_name=node.class_type,
                node_name=node.node_name,
                source_location=create_source_location(node)
            )
    
    # ========================================================================
    # 节点处理器实现
    # ========================================================================
    
    def _process_generic_event_node(self, context: AnalysisContext, node: GraphNode) -> Optional[EventNode]:
        """
        通用事件节点处理器 - 支持多种事件节点类型
        支持: K2Node_Event, K2Node_CustomEvent, K2Node_ComponentBoundEvent
        """
        # 根据节点类型提取事件名称
        event_name = self._extract_event_name(node)
        
        # 自动提取事件参数
        parameters = self._extract_event_parameters(node)
        
        # 创建事件节点
        event_node = EventNode(
            event_name=event_name,
            parameters=parameters,
            body=ExecutionBlock(),
            source_location=create_source_location(node)
        )
        
        # 查找执行输出引脚并跟随执行流
        exec_pin = self._find_execution_output_pin(node)
        if exec_pin:
            self._follow_execution_flow(context, exec_pin, event_node.body.statements)
        
        # 将临时变量声明添加到事件体的开头
        if context.scope_prelude:
            event_node.body.statements = context.scope_prelude + event_node.body.statements
        
        return event_node
    
    def _extract_event_name(self, node: GraphNode) -> str:
        """
        根据节点类型提取事件名称
        """
        if 'K2Node_Event' in node.class_type:
            # 标准事件节点：从EventReference.MemberName提取
            event_ref = node.properties.get("EventReference", "")
            if isinstance(event_ref, dict):
                return event_ref.get("MemberName", node.node_name)
            elif isinstance(event_ref, str) and "MemberName=" in event_ref:
                import re
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
    
    def _extract_event_parameters(self, node: GraphNode) -> List[Tuple[str, str]]:
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
    
    def _find_execution_output_pin(self, node: GraphNode) -> Optional['GraphPin']:
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
    

    
    def _extract_variable_reference(self, node: GraphNode) -> Tuple[str, bool]:
        """提取变量引用信息的公共方法 - 修复版本"""
        var_reference = node.properties.get("VariableReference", "")
        var_name = "UnknownVariable"
        is_self_context = True  # 默认值
        
        # 提取变量名
        if isinstance(var_reference, dict):
            var_name = var_reference.get("MemberName", "UnknownVariable")
            is_self_context = var_reference.get("bSelfContext", True)
        elif isinstance(var_reference, str) and "MemberName=" in var_reference:
            import re
            match = re.search(r'MemberName="([^"]+)"', var_reference)
            var_name = match.group(1) if match else "UnknownVariable"
            
            # 检查 VariableReference 中的 bSelfContext
            if "bSelfContext=True" in var_reference:
                is_self_context = True
            elif "bSelfContext=False" in var_reference:
                is_self_context = False
            else:
                # 如果 VariableReference 中没有 bSelfContext，检查 SelfContextInfo
                self_context_info = node.properties.get("SelfContextInfo", "")
                is_self_context = self_context_info != "NotSelfContext"
        else:
            # 如果没有 VariableReference，检查 SelfContextInfo
            self_context_info = node.properties.get("SelfContextInfo", "")
            is_self_context = self_context_info != "NotSelfContext"
        
        return var_name, is_self_context

    def _extract_function_reference(self, node: GraphNode) -> str:
        """
        从节点中提取函数引用信息
        支持多种函数引用格式
        """
        # 尝试从 FunctionReference 属性获取
        func_ref = node.properties.get("FunctionReference", "")
        if isinstance(func_ref, dict):
            member_name = func_ref.get("MemberName", "")
            if member_name:
                return member_name
        elif isinstance(func_ref, str) and "MemberName=" in func_ref:
            import re
            match = re.search(r'MemberName="([^"]+)"', func_ref)
            if match:
                return match.group(1)
        
        # 回退到其他可能的属性
        return (node.properties.get("FunctionName", "") or 
                node.properties.get("ArrayFunction", "") or 
                "UnknownFunction")

    def _parse_function_arguments(self, context: AnalysisContext, node: GraphNode, 
                                  exclude_pins: set = None) -> List[Tuple[str, Expression]]:
        """
        解析函数参数
        排除执行引脚和指定的特殊引脚
        
        :param exclude_pins: 要排除的引脚名称集合，如果为None则使用默认排除列表
        """
        if exclude_pins is None:
            exclude_pins = {"self"}  # 默认只排除self引脚
        
        arguments = []
        
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec"] and
                pin.pin_name not in exclude_pins):
                arg_expr = self._resolve_data_expression(context, pin)
                arguments.append((pin.pin_name, arg_expr))
        
        return arguments

    def _create_function_call_node(self, context: AnalysisContext, node: GraphNode, 
                                   function_name: str, target_expr: Expression, 
                                   arguments: List[Tuple[str, Expression]]) -> ASTNode:
        """
        创建函数调用节点的公共逻辑
        根据是否有执行引脚决定返回FunctionCallNode还是FunctionCallExpression
        """
        # 检查是否有执行引脚（决定是语句还是表达式）
        has_exec_pins = any(pin.pin_type == "exec" for pin in node.pins)
        
        if has_exec_pins:
            # 有执行引脚，生成FunctionCallNode
            return FunctionCallNode(
                target=target_expr,
                function_name=function_name,
                arguments=arguments,
                source_location=create_source_location(node)
            )
        else:
            # 纯函数调用，生成FunctionCallExpression
            return FunctionCallExpression(
                target=target_expr,
                function_name=function_name,
                arguments=arguments,
                source_location=create_source_location(node)
            )

    def _process_variable_set(self, context: AnalysisContext, node: GraphNode) -> Optional[AssignmentNode]:
        """
        处理变量赋值节点 - 增强版本
        K2Node_VariableSet -> AssignmentNode
        实现完整的数据流解析以正确识别目标对象
        """
        # 提取变量名
        var_name, is_self_context = self._extract_variable_reference(node)
        
        # 查找值引脚（通常是和变量同名的输入引脚）
        value_pin = find_pin(node, var_name, "input")
        if not value_pin:
            # 尝试查找任何非exec的输入引脚
            for pin in node.pins:
                if pin.direction == "input" and pin.pin_type != "exec":
                    value_pin = pin
                    break
        
        # 解析值表达式
        value_expr = self._resolve_data_expression(context, value_pin) if value_pin else LiteralExpression(
            value="null",
            literal_type="null"
        )
        
        # 关键修复：解析目标对象
        # 检查 self 引脚以确定操作的真正目标
        self_pin = find_pin(node, "self", "input")
        
        if self_pin and self_pin.linked_to and not is_self_context:
            # 有 self 引脚连接且不是 SelfContext，说明这是对其他对象的属性赋值
            # 使用数据流解析来找到真正的目标对象
            target_object_expr = self._resolve_data_expression(context, self_pin)
            
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
    
    def _process_call_array_function(self, context: AnalysisContext, node: GraphNode) -> Optional[ASTNode]:
        """
        处理数组函数调用节点
        K2Node_CallArrayFunction -> FunctionCallNode or FunctionCallExpression
        使用重构后的公共逻辑减少代码重复
        """
        # 提取函数名称（数组函数的特殊处理）
        function_name = self._extract_function_reference(node)
        
        # 查找目标数组引脚（数组函数的特殊目标引脚）
        target_pin = find_pin(node, "TargetArray", "input")
        if not target_pin:
            target_pin = find_pin(node, "Array", "input")
        
        target_expr = None
        if target_pin:
            target_expr = self._resolve_data_expression(context, target_pin)
        
        # 解析函数参数（使用公共逻辑，排除数组函数的特殊引脚）
        exclude_pins = {"TargetArray", "Array"}
        arguments = self._parse_function_arguments(context, node, exclude_pins)
        
        # 使用公共逻辑创建函数调用节点
        return self._create_function_call_node(context, node, function_name, target_expr, arguments)

    def _build_property_access_expression(self, context: AnalysisContext, node: GraphNode) -> Expression:
        """
        构建属性访问表达式，支持递归解析嵌套访问链
        K2Node_VariableGet -> VariableGetExpression 或 PropertyAccessNode
        """
        # 提取当前节点的变量名
        var_name, is_self_context = self._extract_variable_reference(node)
        
        # 检查是否有 self 引脚连接（表示这是一个属性访问）
        self_pin = find_pin(node, "self", "input")
        
        if self_pin and self_pin.linked_to:
            # 有 self 引脚连接，递归解析基础对象
            base_expression = self._resolve_data_expression(context, self_pin)
            
            # 创建属性访问节点
            return PropertyAccessNode(
                target=base_expression,
                property_name=var_name,
                source_location=create_source_location(node),
                ue_type="property_access"
            )
        else:
            # 没有 self 引脚连接，这是一个顶级变量
            return VariableGetExpression(
                variable_name=var_name,
                is_self_variable=is_self_context,
                source_location=create_source_location(node),
                ue_type="variable_reference"
            )
    
    def _process_call_function(self, context: AnalysisContext, node: GraphNode) -> Optional[ASTNode]:
        """
        处理函数调用节点
        使用重构后的公共逻辑减少代码重复
        """
        # 提取函数信息（使用公共逻辑）
        func_name = self._extract_function_reference(node)
        
        # 解析目标对象（self引脚，普通函数调用的特殊处理）
        target_expr = None
        self_pin = find_pin(node, "self", "input")
        if self_pin and self_pin.linked_to:
            target_expr = self._resolve_data_expression(context, self_pin)
        
        # 解析参数（使用公共逻辑）
        arguments = self._parse_function_arguments(context, node)
        
        # 使用公共逻辑创建函数调用节点
        call_node = self._create_function_call_node(context, node, func_name, target_expr, arguments)
        
        # 处理返回值赋值（保留原有的特殊逻辑）
        if isinstance(call_node, FunctionCallNode):
            for pin in node.pins:
                if pin.direction == "output" and pin.pin_type != "exec":
                    # 返回值处理暂未实现
                    pass
        
        return call_node
    
    def _process_if_then_else(self, context: AnalysisContext, node: GraphNode) -> Optional[BranchNode]:
        """
        处理分支节点
        K2Node_IfThenElse -> BranchNode
        """
        # 查找条件引脚
        condition_pin = find_pin(node, "Condition", "input")
        condition_expr = self._resolve_data_expression(context, condition_pin) if condition_pin else LiteralExpression(
            value="true",
            literal_type="bool"
        )
        
        # 创建分支节点
        branch_node = BranchNode(
            condition=condition_expr,
            true_branch=ExecutionBlock(),
            false_branch=ExecutionBlock(),
            source_location=create_source_location(node)
        )
        
        # 处理true分支
        true_pin = find_pin(node, "then", "output")
        if not true_pin:
            true_pin = find_pin(node, "true", "output")
        if true_pin:
            self._follow_execution_flow(context, true_pin, branch_node.true_branch.statements)
        
        # 处理false分支
        false_pin = find_pin(node, "else", "output")
        if not false_pin:
            false_pin = find_pin(node, "false", "output")
        if false_pin:
            self._follow_execution_flow(context, false_pin, branch_node.false_branch.statements)
        
        return branch_node
    
    def _process_execution_sequence(self, context: AnalysisContext, node: GraphNode) -> Optional[ExecutionBlock]:
        """
        处理执行序列节点
        K2Node_ExecutionSequence -> ExecutionBlock (包含多个执行流)
        """
        # 执行序列节点会有多个输出执行引脚，按顺序执行
        sequence_block = ExecutionBlock(source_location=create_source_location(node))
        
        # 查找所有输出执行引脚，按名称排序
        output_exec_pins = []
        for pin in node.pins:
            if pin.direction == "output" and pin.pin_type == "exec":
                output_exec_pins.append(pin)
        
        # 按引脚名称排序（通常是 "then 0", "then 1", "then 2" 等）
        output_exec_pins.sort(key=lambda p: p.pin_name)
        
        # 依次处理每个输出执行流
        for pin in output_exec_pins:
            if pin.linked_to:
                self._follow_execution_flow(context, pin, sequence_block.statements)
        
        return sequence_block
    
    def _process_macro_instance(self, context: AnalysisContext, node: GraphNode) -> Optional[ASTNode]:
        """
        处理宏实例节点 - 适配新架构
        K2Node_MacroInstance -> 根据宏类型返回不同的AST节点
        
        !WARNING! 这是一个临时的适配器方法。由于 _process_foreach_macro 现在返回 NodeProcessingResult，
        而其他处理器仍然返回 ASTNode，我们需要在这里进行适配。
        """
        # 获取宏图引用信息
        macro_ref = node.properties.get("MacroGraphReference", {})
        if isinstance(macro_ref, dict):
            macro_graph = macro_ref.get("MacroGraph", "")
        elif isinstance(macro_ref, str):
            macro_graph = macro_ref
        else:
            macro_graph = ""
        
        # 根据宏类型处理
        if "ForEachLoop" in macro_graph or "ForEach" in macro_graph:
            # ForEachLoop 返回 NodeProcessingResult，需要特殊处理
            result = self._process_foreach_macro(context, node)
            # 将 continuation_pin 存储到上下文中，稍后在 _follow_execution_flow 中处理
            context.pending_continuation_pin = result.continuation_pin
            return result.node
        elif "WhileLoop" in macro_graph or "While" in macro_graph:
            return self._process_while_macro(context, node)
        else:
            # 未知宏类型，作为函数调用处理
            return self._process_generic_macro(context, node)
    
    def _process_foreach_macro(self, context: AnalysisContext, node: GraphNode) -> NodeProcessingResult:
        """
        处理ForEach循环宏 - 重构版本
        返回 NodeProcessingResult 以支持完整的执行流追踪
        """
        # 查找数组输入引脚
        array_pin = find_pin(node, "Array", "input")
        collection_expr = self._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression(
            value="[]",
            literal_type="array"
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
            variable_type="auto",  # 类型从集合元素推断
            is_loop_variable=True
        )
        
        index_declaration = VariableDeclaration(
            variable_name="ArrayIndex",
            variable_type="int",
            is_loop_variable=True
        )
        
        # 创建循环节点
        loop_node = LoopNode(
            loop_type=LoopType.FOR_EACH,
            collection_expression=collection_expr,
            item_declaration=item_declaration,
            index_declaration=index_declaration,
            body=ExecutionBlock(),
            source_location=create_source_location(node)
        )
        
        # 在新作用域中处理循环体
        with context.symbol_table.scoped():
            # 定义循环变量，关联 LoopVariableExpression 作为值
            context.symbol_table.define(
                "ArrayElement", "auto", 
                declaration=item_declaration,
                value=element_expr,
                is_loop_variable=True
            )
            context.symbol_table.define(
                "ArrayIndex", "int", 
                declaration=index_declaration,
                value=index_expr,
                is_loop_variable=True
            )
            
            # 处理循环体
            loop_body_pin = find_pin(node, "LoopBody", "output")
            if loop_body_pin:
                self._follow_execution_flow(context, loop_body_pin, loop_node.body.statements)
        
        # 关键修复：查找并返回 Completed 引脚，以便主执行流可以继续
        completed_pin = find_pin(node, "Completed", "output")
        
        return NodeProcessingResult(
            node=loop_node,
            continuation_pin=completed_pin  # 这是解决执行流不完整问题的关键
        )
    
    def _process_while_macro(self, context: AnalysisContext, node: GraphNode) -> Optional[LoopNode]:
        """
        处理While循环宏
        """
        # 查找条件引脚
        condition_pin = find_pin(node, "Condition", "input")
        condition_expr = self._resolve_data_expression(context, condition_pin) if condition_pin else LiteralExpression(
            value="true",
            literal_type="bool"
        )
        
        # 创建循环节点
        loop_node = LoopNode(
            loop_type=LoopType.WHILE,
            condition_expression=condition_expr,
            body=ExecutionBlock(),
            source_location=create_source_location(node)
        )
        
        # 处理循环体
        loop_body_pin = find_pin(node, "LoopBody", "output")
        if loop_body_pin:
            self._follow_execution_flow(context, loop_body_pin, loop_node.body.statements)
        
        return loop_node
    
    def _process_generic_macro(self, context: AnalysisContext, node: GraphNode) -> Optional[FunctionCallNode]:
        """
        处理通用宏实例（作为函数调用）
        """
        # 提取宏名称
        macro_ref = node.properties.get("MacroGraphReference", {})
        if isinstance(macro_ref, dict):
            macro_name = macro_ref.get("MacroGraph", "UnknownMacro")
        else:
            macro_name = str(macro_ref)
        
        # 简化宏名称
        if "/" in macro_name:
            macro_name = macro_name.split("/")[-1]
        
        # 解析参数
        arguments = []
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec", "delegate"]):
                arg_expr = self._resolve_data_expression(context, pin)
                arguments.append((pin.pin_name, arg_expr))
        
        return FunctionCallNode(
            target=None,
            function_name=f"macro_{macro_name}",
            arguments=arguments,
            source_location=create_source_location(node)
        )
    
    def _process_latent_ability_call(self, context: AnalysisContext, node: GraphNode) -> Optional[LatentActionNode]:
        """
        处理潜在动作节点 - 修复版本
        K2Node_LatentAbilityCall -> LatentActionNode
        正确处理回调的数据输出引脚，解决 UnknownFunction 问题
        """
        # 提取动作名称
        proxy_factory_func = node.properties.get("ProxyFactoryFunctionName", "UnknownAction")
        # 移除可能存在的引号
        if isinstance(proxy_factory_func, str):
            proxy_factory_func = proxy_factory_func.strip('"')
        
        # 解析目标对象（self引脚）
        target_expr = None
        self_pin = find_pin(node, "self", "input")
        if self_pin and self_pin.linked_to:
            target_expr = self._resolve_data_expression(context, self_pin)
        
        # 解析参数
        arguments = []
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec", "delegate"] and
                pin.pin_name not in ["self", "OwningAbility"]):
                arg_expr = self._resolve_data_expression(context, pin)
                arguments.append((pin.pin_name, arg_expr))
        
        # 创建函数调用节点
        call_node = FunctionCallNode(
            target=target_expr,
            function_name=proxy_factory_func,
            arguments=arguments,
            source_location=create_source_location(node)
        )
        
        # 创建回调执行引脚字典
        callback_exec_pins = {}
        for pin in node.pins:
            if pin.direction == "output" and pin.pin_type == "exec":
                if pin.pin_name != "then":  # "then"是主执行流，不算回调
                    # 关键修复：识别与该回调执行引脚一同输出的数据引脚
                    callback_data_pins = []
                    for data_pin in node.pins:
                        if (data_pin.direction == "output" and 
                            data_pin.pin_type not in ["exec"] and
                            data_pin.pin_name not in ["AsyncTaskProxy"]):  # 排除异步任务代理引脚
                            callback_data_pins.append(data_pin)
                    
                    # 为每个数据引脚创建变量声明
                    callback_declarations = []
                    for data_pin in callback_data_pins:
                        var_declaration = VariableDeclaration(
                            variable_name=data_pin.pin_name,
                            variable_type=data_pin.pin_type,
                            is_callback_parameter=True,
                            source_location=create_source_location(node)
                        )
                        callback_declarations.append(var_declaration)
                        
                        # 关键修复：将数据引脚注册到 pin_ast_map 中
                        # 创建对应的变量获取表达式
                        var_expr = VariableGetExpression(
                            variable_name=data_pin.pin_name,
                            is_self_variable=False,  # 回调参数不是self变量
                            source_location=create_source_location(node)
                        )
                        context.pin_ast_map[data_pin.pin_id] = var_expr
                    
                    # 创建CallbackBlock
                    callback_block = CallbackBlock(declarations=callback_declarations)
                    
                    # 在新作用域中处理回调体
                    with context.symbol_table.scoped():
                        # 定义回调参数到符号表
                        for declaration in callback_declarations:
                            context.symbol_table.define(
                                declaration.variable_name,
                                declaration.variable_type,
                                declaration=declaration,
                                is_callback_parameter=True
                            )
                        
                        # 处理回调执行流
                        self._follow_execution_flow(context, pin, callback_block.statements)
                    
                    callback_exec_pins[pin.pin_name] = callback_block
        
        # 创建潜在动作节点
        latent_node = LatentActionNode(
            call=call_node,
            callback_exec_pins=callback_exec_pins,
            source_location=create_source_location(node)
        )
        
        return latent_node
    
    def _process_knot_node(self, context: AnalysisContext, node: GraphNode) -> Optional[ASTNode]:
        """
        处理连接节点（透传节点）
        K2Node_Knot 只是传递数据，不产生AST节点
        """
        # Knot节点不产生AST，只是数据的透传
        # 在_resolve_data_expression中会正确处理连接关系
        return None
    
    # ========================================================================
    # 新增节点处理器实现
    # ========================================================================
    
    def _process_custom_event(self, context: AnalysisContext, node: GraphNode) -> Optional[EventNode]:
        """
        处理自定义事件节点
        K2Node_CustomEvent -> EventNode
        """
        # 提取自定义事件名称
        custom_function_name = node.properties.get("CustomFunctionName", "")
        if isinstance(custom_function_name, str):
            event_name = custom_function_name.strip('"') if custom_function_name else node.node_name
        else:
            event_name = node.node_name
        
        # 如果事件名称为空，使用节点名称
        if not event_name or event_name == "K2Node_CustomEvent":
            event_name = "CustomEvent"
        
                    # 自定义事件参数解析暂未实现
        # 自定义事件可能有输入参数，需要从输入引脚中提取
        parameters = []
        for pin in node.pins:
            if pin.direction == "input" and pin.pin_type not in ["exec"]:
                # 跳过执行引脚，其他输入引脚作为参数
                parameters.append((pin.pin_name, pin.pin_type))
        
        # 创建事件节点
        event_node = EventNode(
            event_name=event_name,
            parameters=parameters,
            body=ExecutionBlock(),
            source_location=create_source_location(node)
        )
        
        # 跟随执行流构建事件体
        exec_pin = find_pin(node, "then", "output")
        if not exec_pin:
            # 某些自定义事件可能使用不同的执行输出引脚名称
            for pin in node.pins:
                if pin.direction == "output" and pin.pin_type == "exec":
                    exec_pin = pin
                    break
        
        if exec_pin:
            self._follow_execution_flow(context, exec_pin, event_node.body.statements)
        
        # 将临时变量声明添加到事件体的开头
        if context.scope_prelude:
            event_node.body.statements = context.scope_prelude + event_node.body.statements
        
        return event_node
    
    def _process_dynamic_cast(self, context: AnalysisContext, node: GraphNode) -> Optional[BranchNode]:
        """
        处理动态类型转换节点 - 战略重构版本
        K2Node_DynamicCast -> BranchNode (条件分支节点，正确反映其本质逻辑)
        
        Dynamic Cast本质上是一个条件分支：
        if (cast successful) {
            // 声明转换后的变量并执行then分支
            AsTargetType = cast(source)
            // 后续执行流...
        } else {
            // 执行CastFailed分支
        }
        """
        # 第一步：提取目标类型信息
        target_type = node.properties.get("TargetType", "")
        if isinstance(target_type, dict):
            # 如果是复杂对象，尝试提取类型名称
            target_type_name = target_type.get("ObjectName", "") or target_type.get("ClassName", "")
        elif isinstance(target_type, str):
            # 如果是字符串，可能包含类型路径，提取类名
            if "'" in target_type:
                # 格式如: /Script/CoreUObject.Class'/Script/XiangYang.AttributesMenuController'
                parts = target_type.split("'")
                if len(parts) >= 2:
                    class_path = parts[-2]  # 取倒数第二个部分
                    target_type_name = class_path.split(".")[-1]  # 取最后一个点后的部分
                else:
                    target_type_name = target_type
            else:
                target_type_name = target_type
        else:
            target_type_name = "UnknownType"
        
        # 第二步：查找输入对象引脚并解析源表达式
        object_pin = find_pin(node, "Object", "input")
        if not object_pin:
            # 尝试查找任何非exec的输入引脚
            for pin in node.pins:
                if pin.direction == "input" and pin.pin_type not in ["exec"]:
                    object_pin = pin
                    break
        
        # 解析输入对象表达式
        source_expr = self._resolve_data_expression(context, object_pin) if object_pin else LiteralExpression(
            value="null", literal_type="null"
        )
        
        # 第三步：创建类型转换表达式作为条件
        cast_expr = CastExpression(
            source_expression=source_expr,
            target_type=target_type_name,
            source_location=create_source_location(node)
        )
        
        # 第四步：构建true分支（转换成功）
        true_branch = ExecutionBlock(source_location=create_source_location(node))
        
        # 在true分支中，首先声明转换后的变量
        output_var_name = f"As{target_type_name}"  # 遵循UE蓝图的命名约定
        var_declaration = VariableDeclaration(
            variable_name=output_var_name,
            variable_type=target_type_name,
            initial_value=cast_expr,  # 变量的初始值就是转换表达式
            is_loop_variable=False,
            is_callback_parameter=False,
            source_location=create_source_location(node)
        )
        true_branch.statements.append(var_declaration)
        
        # 然后跟随then引脚的执行流
        then_pin = find_pin(node, "then", "output")
        if then_pin and then_pin.linked_to:
            self._follow_execution_flow(context, then_pin, true_branch.statements)
        
        # 第五步：构建false分支（转换失败）
        false_branch = ExecutionBlock(source_location=create_source_location(node))
        
        # 跟随CastFailed引脚的执行流
        cast_failed_pin = find_pin(node, "CastFailed", "output")
        if cast_failed_pin and cast_failed_pin.linked_to:
            self._follow_execution_flow(context, cast_failed_pin, false_branch.statements)
        
        # 第六步：创建分支节点
        branch_node = BranchNode(
            condition=cast_expr,  # 转换表达式本身作为条件
            true_branch=true_branch,
            false_branch=false_branch if false_branch.statements else None,  # 如果false分支为空则设为None
            source_location=create_source_location(node)
        )
        
        return branch_node
    
    def _process_assign_delegate(self, context: AnalysisContext, node: GraphNode) -> Optional[AssignmentNode]:
        """
        处理委托赋值节点 - 新架构版本
        K2Node_AssignDelegate -> AssignmentNode (delegate assignment)
        支持复杂的委托目标表达式，如 CloseButton.Button.OnClicked = MyEvent
        """
        # 第一步：解析委托属性信息
        delegate_reference = node.properties.get("DelegateReference", "")
        delegate_name = "UnknownDelegate"
        
        if isinstance(delegate_reference, str) and "MemberName=" in delegate_reference:
            import re
            match = re.search(r'MemberName="([^"]+)"', delegate_reference)
            if match:
                delegate_name = match.group(1)
        
        # 第二步：解析赋值目标（左值）- 通过self引脚
        self_pin = find_pin(node, "self", "input")
        if not self_pin:
            # 兼容性：尝试查找Target引脚
            self_pin = find_pin(node, "Target", "input")
        
        if self_pin:
            # 解析目标对象表达式
            target_object_expr = self._resolve_data_expression(context, self_pin)
            # 创建属性访问表达式：TargetObject.DelegateName
            target_expr = PropertyAccessNode(
                target=target_object_expr,
                property_name=delegate_name,
                source_location=create_source_location(node)
            )
        else:
            # 如果没有self引脚，假设是简单变量赋值
            target_expr = VariableGetExpression(
                variable_name=delegate_name,
                source_location=create_source_location(node)
            )
        
        # 第三步：解析赋值源（右值）- 通过Delegate引脚
        delegate_pin = find_pin(node, "Delegate", "input")
        if not delegate_pin:
            # 尝试查找Event引脚
            delegate_pin = find_pin(node, "Event", "input")
        
        if delegate_pin:
            # 解析委托源表达式
            value_expr = self._resolve_data_expression(context, delegate_pin)
        else:
            # 如果没有找到委托引脚，创建一个未知表达式
            value_expr = LiteralExpression(
                value="UnknownDelegate",
                literal_type="delegate",
                source_location=create_source_location(node)
            )
        
        # 第四步：创建增强的赋值节点
        assignment = AssignmentNode(
            target=target_expr,  # 使用新的target字段
            value_expression=value_expr,
            is_local_variable=False,  # 委托通常是成员变量
            source_location=create_source_location(node)
        )
        
        return assignment
    

    
    def _infer_callback_parameters(self, callback_name: str, node: GraphNode) -> List[VariableDeclaration]:
        """
        根据回调名称推断可能的参数声明
        """
        declarations = []
        
        # 基于常见的回调模式推断参数
        if "EventReceived" in callback_name:
            # WaitGameplayEvent的EventReceived回调通常有Payload参数
            # 首先声明主Payload变量
            declarations.append(VariableDeclaration(
                variable_name="Payload",
                variable_type="GameplayEventData",
                is_callback_parameter=True
            ))
            
            # 然后声明Payload的所有子字段作为独立变量
            for pin in node.pins:
                if (pin.direction == "output" and 
                    pin.pin_type not in ["exec"] and
                    pin.pin_name.startswith("Payload_")):
                    # 提取字段名（移除"Payload_"前缀）
                    field_name = pin.pin_name[8:]  # 移除"Payload_"
                    # 创建完整的变量名（保持原始格式以便查找）
                    var_name = f"Payload {field_name.replace('_', ' ')}"
                    declarations.append(VariableDeclaration(
                        variable_name=var_name,
                        variable_type="auto",
                        is_callback_parameter=True
                    ))
        elif "Completed" in callback_name:
            # 完成回调通常没有额外参数
            pass
        elif "Cancelled" in callback_name:
            # 取消回调通常没有额外参数
            pass
        else:
            # 对于未知回调类型，检查是否有相关的输出数据引脚
            for pin in node.pins:
                if (pin.direction == "output" and 
                    pin.pin_type not in ["exec"] and
                    callback_name.lower() in pin.pin_name.lower()):
                    declarations.append(VariableDeclaration(
                        variable_name=pin.pin_name,
                        variable_type="auto",
                        is_callback_parameter=True
                    ))
        
        return declarations
    
    def _try_resolve_from_symbol_table(self, context: AnalysisContext, source_node: GraphNode, source_pin_id: str) -> Optional[Expression]:
        """
        尝试从符号表解析表达式
        检查源节点是否对应符号表中的变量
        """
        # 如果是变量获取节点，检查变量名是否在符号表中
        if 'K2Node_VariableGet' in source_node.class_type:
            var_reference = source_node.properties.get("VariableReference", "")
            var_name = ""
            
            if isinstance(var_reference, dict):
                var_name = var_reference.get("MemberName", "")
            elif isinstance(var_reference, str) and "MemberName=" in var_reference:
                import re
                match = re.search(r'MemberName="([^"]+)"', var_reference)
                var_name = match.group(1) if match else ""
            
            if var_name:
                symbol = context.symbol_table.lookup(var_name)
                if symbol:
                    return VariableGetExpression(
                        variable_name=symbol.name,
                        is_self_variable=not (symbol.is_loop_variable or symbol.is_callback_parameter)
                    )
        
        # 检查是否有输出引脚名称匹配符号表中的变量
        for pin in source_node.pins:
            if pin.direction == "output" and pin.pin_id == source_pin_id:
                # 直接匹配引脚名称
                symbol = context.symbol_table.lookup(pin.pin_name)
                if symbol:
                    return VariableGetExpression(
                        variable_name=symbol.name,
                        is_self_variable=not (symbol.is_loop_variable or symbol.is_callback_parameter)
                    )
                
                # 特殊处理：如果是Payload_字段，尝试转换为"Payload FieldName"格式
                if pin.pin_name.startswith("Payload_"):
                    field_name = pin.pin_name[8:]  # 移除"Payload_"
                    var_name = f"Payload {field_name.replace('_', ' ')}"
                    symbol = context.symbol_table.lookup(var_name)
                    if symbol:
                        return VariableGetExpression(
                            variable_name=symbol.name,
                            is_self_variable=not (symbol.is_loop_variable or symbol.is_callback_parameter)
                        )
                
                # 特殊处理：ForEach循环的Array Element
                if pin.pin_name == "Array Element" and 'K2Node_MacroInstance' in source_node.class_type:
                    # 检查是否在ForEach循环的作用域中
                    symbol = context.symbol_table.lookup("ArrayElement")
                    if symbol:
                        return VariableGetExpression(
                            variable_name=symbol.name,
                            is_self_variable=False
                        )
        
        return None
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _follow_execution_flow(self, context: AnalysisContext, start_pin: GraphPin, statements: List[Statement]):
        """
        跟随执行流，构建语句序列 - 增强版本
        支持 NodeProcessingResult 的 continuation_pin 处理
        """
        current_pin = start_pin
        
        while current_pin and current_pin.linked_to:
            # 获取连接的第一个目标节点
            target_link = current_pin.linked_to[0]
            target_node_id = target_link.get("node_guid") or target_link.get("node_name")
            target_pin_id = target_link.get("pin_id")
            
            # 查找目标节点
            target_node = None
            if target_node_id:
                target_node = self._find_node_by_id(context, target_node_id)
            elif target_pin_id:
                # 通过pin_id查找目标节点
                target_node = self._find_node_by_pin_id(context, target_pin_id)
            
            if not target_node:
                break
            
            # 注意：不在这里检查visited_nodes，因为_process_node会处理这个逻辑
            
            # 处理目标节点
            ast_node = self._process_node(context, target_node)
            if isinstance(ast_node, Statement):
                statements.append(ast_node)
            
            # 关键修复：检查是否有 pending_continuation_pin（来自 ForEachLoop 等复杂节点）
            if context.pending_continuation_pin:
                # 使用 continuation_pin 作为下一个执行点
                current_pin = context.pending_continuation_pin
                # 清除 pending_continuation_pin 以避免重复使用
                context.pending_continuation_pin = None
                continue
            
            # 查找下一个执行输出引脚
            current_pin = find_pin(target_node, "then", "output")
            if not current_pin:
                # 某些节点可能有不同名称的执行输出
                for pin in target_node.pins:
                    if pin.direction == "output" and pin.pin_type == "exec":
                        current_pin = pin
                        break
    
    def _resolve_data_expression(self, context: AnalysisContext, pin: Optional[GraphPin], visited_path: Optional[Set[str]] = None) -> Expression:
        """
        解析数据引脚连接，构建表达式树 - 增强版本
        实现数据流递归解析，支持循环检测和类型信息提取
        """
        if not pin:
            return LiteralExpression(value="null", literal_type="null")
        
        # 初始化访问路径（用于循环检测）
        if visited_path is None:
            visited_path = set()
        
        # 优先检查 pin_ast_map：如果该引脚已有预定义的 AST 表达式（如循环变量），直接返回
        if pin.pin_id in context.pin_ast_map:
            return context.pin_ast_map[pin.pin_id]
        
        # 如果引脚没有连接，检查是否为符号表中的变量名或使用默认值
        if not pin.linked_to:
            # 尝试将pin名称作为变量名在符号表中查找
            symbol = context.symbol_table.lookup(pin.pin_name)
            if symbol:
                return VariableGetExpression(
                    variable_name=symbol.name,
                    is_self_variable=not (symbol.is_loop_variable or symbol.is_callback_parameter)
                )
            
            # 没有找到符号，使用默认值并提取类型信息
            default_value = get_pin_default_value(pin)
            ue_type = extract_pin_type(pin)
            return LiteralExpression(
                value=default_value, 
                literal_type="auto",
                expression_type=ue_type
            )
        
        # 获取连接的源节点
        source_link = pin.linked_to[0]
        source_node_id = source_link.get("node_guid") or source_link.get("node_name")
        source_pin_id = source_link.get("pin_id")
        
        # 循环检测：检查是否已经在访问路径中
        path_key = f"{source_node_id}:{source_pin_id}"
        if path_key in visited_path:
            # 检测到循环引用，返回特殊节点
            return LiteralExpression(
                value="<circular_reference>",
                literal_type="error",
                expression_type="circular_ref"
            )
        
        # 关键修复：检查源引脚是否在 pin_ast_map 中（循环变量等特殊引脚）
        if source_pin_id and source_pin_id in context.pin_ast_map:
            return context.pin_ast_map[source_pin_id]
        
        # 生成缓存键
        cache_key = f"{source_node_id}:{source_pin_id}"
        
        # 检查缓存
        if cache_key in context.memoization_cache:
            return context.memoization_cache[cache_key]
        
        # 查找源节点
        source_node = self._find_node_by_id(context, source_node_id)
        if not source_node:
            return LiteralExpression(value="<node_not_found>", literal_type="error")
        
        # 将当前路径添加到访问路径中
        visited_path.add(path_key)
        
        # 首先检查源节点是否产生符号表中的变量
        result_expr = self._try_resolve_from_symbol_table(context, source_node, source_pin_id)
        if result_expr:
            # 从访问路径中移除当前路径
            visited_path.remove(path_key)
            context.memoization_cache[cache_key] = result_expr
            return result_expr
        
        # 检查是否需要创建临时变量
        pin_usage_count = context.pin_usage_counts.get(cache_key, 0)
        if pin_usage_count > 1 and self._should_create_temp_variable_for_node(source_node):
            # 创建临时变量
            temp_var_name = self._generate_temp_variable_name(context, source_node, source_pin_id)
            
            # 解析源表达式（传递访问路径）
            source_expr = self._resolve_node_expression(context, source_node, source_pin_id, visited_path)
            
            # 创建临时变量声明并添加到scope_prelude
            temp_var_decl = TemporaryVariableDeclaration(
                variable_name=temp_var_name,
                value_expression=source_expr,
                source_location=create_source_location(source_node)
            )
            context.scope_prelude.append(temp_var_decl)
            
            # 创建临时变量引用表达式
            result = TemporaryVariableExpression(
                temp_var_name=temp_var_name,
                source_location=create_source_location(source_node)
            )
        else:
            # 直接解析表达式（传递访问路径）
            result = self._resolve_node_expression(context, source_node, source_pin_id, visited_path)
        
        # 从访问路径中移除当前路径
        visited_path.remove(path_key)
        
        # 缓存结果
        context.memoization_cache[cache_key] = result
        return result
    
    def _find_node_by_id(self, context: AnalysisContext, node_id: str) -> Optional[GraphNode]:
        """
        根据节点ID查找节点
        """
        # 先从graph的nodes字典中查找
        node = context.graph.nodes.get(node_id)
        if node:
            return node
        
        # 尝试通过节点名查找
        for node in context.graph.nodes.values():
            if node.node_name == node_id:
                return node
        
        return None
    
    def _find_node_by_pin_id(self, context: AnalysisContext, pin_id: str) -> Optional[GraphNode]:
        """
        根据引脚ID查找拥有该引脚的节点
        """
        for node in context.graph.nodes.values():
            for pin in node.pins:
                if pin.pin_id == pin_id:
                    return node
        return None
    
    def _should_create_temp_variable_for_node(self, source_node: GraphNode) -> bool:
        """
        判断是否需要为节点创建临时变量
        """
        # 简单的变量获取不需要临时变量
        if 'K2Node_VariableGet' in source_node.class_type:
            return False
        # 字面量节点也不需要临时变量
        if 'K2Node_Literal' in source_node.class_type:
            return False
        return True
    
# 旧的临时变量方法已被新的context-aware方法替代
    
    def _generate_temp_variable_name(self, context: AnalysisContext, source_node: GraphNode, source_pin_id: str) -> str:
        """
        生成临时变量名
        """
        # 基于节点类型和函数名生成有意义的临时变量名
        if 'K2Node_CallFunction' in source_node.class_type:
            func_ref = source_node.properties.get("FunctionReference", "")
            if isinstance(func_ref, dict):
                func_name = func_ref.get("MemberName", "func")
            elif isinstance(func_ref, str) and "MemberName=" in func_ref:
                import re
                match = re.search(r'MemberName="([^"]+)"', func_ref)
                func_name = match.group(1) if match else "func"
            else:
                func_name = "func"
            
            # 简化函数名
            func_name = func_name.replace("BP_", "").replace("K2_", "")
            base_name = f"temp_{func_name.lower()}"
        else:
            # 其他节点类型
            node_type = source_node.class_type.split('.')[-1] if '.' in source_node.class_type else source_node.class_type
            base_name = f"temp_{node_type.lower().replace('k2node_', '')}"
        
        # 确保变量名唯一 - 检查当前作用域的前置语句中的临时变量声明
        counter = 1
        temp_name = base_name
        while any(isinstance(stmt, TemporaryVariableDeclaration) and stmt.variable_name == temp_name 
                  for stmt in context.scope_prelude):
            temp_name = f"{base_name}_{counter}"
            counter += 1
        
        return temp_name
    
    def _resolve_node_expression(self, context: AnalysisContext, node: GraphNode, pin_id: str, visited_path: Optional[Set[str]] = None) -> Expression:
        """
        根据节点类型解析为表达式
        """
        # K2Node_VariableGet - 变量获取（使用新的递归解析）
        if 'K2Node_VariableGet' in node.class_type:
            return self._build_property_access_expression(context, node)
        
        # K2Node_Knot - 连接节点（透传）
        elif 'K2Node_Knot' in node.class_type:
            # Knot节点只是透传数据，查找输入引脚并递归解析
            input_pin = None
            for pin in node.pins:
                if pin.direction == "input" and pin.linked_to:
                    input_pin = pin
                    break
            
            if input_pin:
                return self._resolve_data_expression(context, input_pin, visited_path)
            else:
                return LiteralExpression(value="null", literal_type="null")
        
        # K2Node_CallFunction - 函数调用（纯函数）
        elif 'K2Node_CallFunction' in node.class_type:
            # 检查是否是纯函数
            is_pure = node.properties.get("bIsPureFunc", False)
            if is_pure or not any(pin.pin_type == "exec" for pin in node.pins):
                expr = self._process_call_function_as_expression(context, node)
                if isinstance(expr, FunctionCallExpression):
                    return expr
        
        # K2Node_Literal - 字面量
        elif 'K2Node_Literal' in node.class_type:
            return self._process_literal_node(node)
        
        # K2Node_MathExpression - 数学表达式
        elif 'K2Node_MathExpression' in node.class_type:
            return self._process_math_expression_node(context, node)
        
        # K2Node_GetArrayItem - 数组访问
        elif 'K2Node_GetArrayItem' in node.class_type:
            return self._process_array_access_node(context, node)
        
        # K2Node_DynamicCast - 动态类型转换（返回转换后的变量引用）
        elif 'K2Node_DynamicCast' in node.class_type:
            # 提取目标类型信息
            target_type = node.properties.get("TargetType", "")
            if isinstance(target_type, str) and "'" in target_type:
                # 格式如: /Script/CoreUObject.Class'/Script/XiangYang.AttributesMenuController'
                parts = target_type.split("'")
                if len(parts) >= 2:
                    class_path = parts[-2]  # 取倒数第二个部分
                    target_type_name = class_path.split(".")[-1]  # 取最后一个点后的部分
                else:
                    target_type_name = target_type
            else:
                target_type_name = "UnknownType"
            
            # 返回对转换后变量的引用
            var_name = f"As{target_type_name}"  # 遵循UE蓝图的命名约定
            return VariableGetExpression(
                variable_name=var_name,
                is_self_variable=False,  # 转换后的变量是局部变量
                source_location=create_source_location(node)
            )
        
        # K2Node_CustomEvent - 自定义事件（作为事件引用）
        elif 'K2Node_CustomEvent' in node.class_type:
            event_name = node.properties.get("CustomFunctionName", "UnknownEvent")
            return EventReferenceExpression(
                event_name=event_name,
                source_location=create_source_location(node)
            )
        
        # K2Node_Event - 标准事件（作为事件引用）
        elif 'K2Node_Event' in node.class_type:
            event_ref = node.properties.get("EventReference", "")
            event_name = "UnknownEvent"
            
            if isinstance(event_ref, str) and "MemberName=" in event_ref:
                import re
                match = re.search(r'MemberName="([^"]+)"', event_ref)
                if match:
                    event_name = match.group(1)
            
            return EventReferenceExpression(
                event_name=event_name,
                source_location=create_source_location(node)
            )
        
        # 默认处理：尝试作为函数调用
        return self._process_call_function_as_expression(context, node)
    
    def _process_call_function_as_expression(self, context: AnalysisContext, node: GraphNode) -> FunctionCallExpression:
        """
        将函数调用节点处理为表达式
        """
        # 提取函数信息
        func_name = self._extract_function_reference(node)
        
        # 解析目标对象（self引脚）
        target_expr = None
        self_pin = find_pin(node, "self", "input")
        if self_pin and self_pin.linked_to:
            target_expr = self._resolve_data_expression(context, self_pin)
        
        # 解析参数
        arguments = self._parse_function_arguments(context, node)
        
        return FunctionCallExpression(
            target=target_expr,
            function_name=func_name,
            arguments=arguments,
            source_location=create_source_location(node)
        )
    
    def _process_literal_node(self, node: GraphNode) -> LiteralExpression:
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
    
    def _process_math_expression_node(self, context: AnalysisContext, node: GraphNode) -> FunctionCallExpression:
        """
        处理数学表达式节点
        """
        # 数学表达式节点通常有操作符属性
        op = node.properties.get("Op", "+")
        
        # 查找输入引脚
        inputs = []
        for pin in node.pins:
            if pin.direction == "input" and pin.pin_type not in ["exec"]:
                input_expr = self._resolve_data_expression(context, pin)
                inputs.append((pin.pin_name, input_expr))
        
        return FunctionCallExpression(
            target=None,
            function_name=f"math_{op}",
            arguments=inputs,
            source_location=create_source_location(node)
        )
    
    def _process_array_access_node(self, context: AnalysisContext, node: GraphNode) -> FunctionCallExpression:
        """
        处理数组访问节点
        """
        # 查找数组和索引引脚
        array_pin = find_pin(node, "TargetArray", "input")
        index_pin = find_pin(node, "Index", "input")
        
        array_expr = self._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression("null", "null")
        index_expr = self._resolve_data_expression(context, index_pin) if index_pin else LiteralExpression("0", "int")
        
        return FunctionCallExpression(
            target=array_expr,
            function_name="get_item",
            arguments=[("index", index_expr)],
            source_location=create_source_location(node)
        )
    
