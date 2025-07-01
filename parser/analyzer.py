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
    NodeProcessingResult,
    # 新增的AST节点
    GenericCallNode, FallbackNode
)
from .symbol_table import SymbolTable, Symbol
from .scope_manager import ScopeManager
from .common import (
    find_pin, create_source_location, get_pin_default_value, extract_pin_type,
    extract_variable_reference, extract_function_reference, extract_event_name,
    should_create_temp_variable_for_node, generate_temp_variable_name,
    has_execution_pins, node_processor_registry, extract_macro_name, parse_object_path
)

# 导入处理器模块以触发装饰器注册
from . import processors


# 节点处理器类型定义
NodeProcessor = Callable[['AnalysisContext', GraphNode], Optional[ASTNode]]


@dataclass
class AnalysisContext:
    """
    分析上下文，包含多遍分析所需的所有状态信息
    """
    graph: BlueprintGraph
    symbol_table: SymbolTable = field(default_factory=SymbolTable)  # 符号表，管理作用域和变量
    scope_manager: ScopeManager = field(default_factory=ScopeManager)  # 新增：作用域管理器，精确管理变量可见性
    pin_usage_counts: Dict[str, int] = field(default_factory=dict)  # pin_key -> usage_count
    scope_prelude: List[Statement] = field(default_factory=list)  # 当前作用域的前置语句（临时变量声明等）
    memoization_cache: Dict[str, Expression] = field(default_factory=dict)  # pin_key -> cached_expression
    visited_nodes: Set[str] = field(default_factory=set)  # 已访问的节点GUID
    pin_ast_map: Dict[str, Expression] = field(default_factory=dict)  # pin_id -> AST表达式映射，用于循环变量等特殊节点
    # 新增：支持 NodeProcessingResult 的 continuation_pin 处理
    pending_continuation_pin: Optional['GraphPin'] = None  # 来自复杂节点（如 ForEachLoop）的延续执行引脚


class GraphAnalyzer:
    """
    蓝图图分析器
    负责将BlueprintGraph转换为逻辑AST
    新架构：支持统一解析模型和装饰器注册
    """
    
    def __init__(self):
        # 使用全局注册表，不再维护私有注册表
        pass
    
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
        简化版本：依赖 GraphBuilder 提供的完整入口节点列表
        """
        # Pass 1: 符号与依赖分析
        pin_usage_counts = self._perform_symbol_analysis(graph)
        
        # Pass 2: 上下文感知AST生成
        context = AnalysisContext(
            graph=graph,
            symbol_table=SymbolTable(),  # 初始化符号表
            pin_usage_counts=pin_usage_counts
        )
        
        # 简化的入口点处理：直接使用 GraphBuilder 提供的 entry_nodes
        # GraphBuilder 已经负责识别所有事件节点和其他入口点
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
        处理单个节点，使用全局注册表查找处理器
        增强的分发器逻辑：支持宏节点的专用-通用两阶段查找
        """
        if node.node_guid in context.visited_nodes:
            return None
        
        # 标记为已访问
        context.visited_nodes.add(node.node_guid)
        
        processor_key = node.class_type
        
        # 阶段一：宏节点特殊处理
        if node.class_type in ["K2Node_MacroInstance", "/Script/BlueprintGraph.K2Node_MacroInstance"]:
            macro_name = extract_macro_name(node)
            specific_key = f"{node.class_type}:{macro_name}"
            
            # 尝试使用专用键查找
            specific_processor = node_processor_registry.get_processor(specific_key)
            if specific_processor:
                result = specific_processor(self, context, node)
                # 处理 NodeProcessingResult 类型
                if hasattr(result, 'node') and hasattr(result, 'continuation_pin'):
                    # 这是 NodeProcessingResult，设置延续引脚
                    if result.continuation_pin:
                        context.pending_continuation_pin = result.continuation_pin
                    return result.node
                return result
            # 如果没有专用处理器，则 processor_key 保持原样，自然进入通用处理流程
        
        # 阶段二：专用处理器查找
        processor = node_processor_registry.get_processor(processor_key)
        if processor:
            result = processor(self, context, node)
            # 处理 NodeProcessingResult 类型
            if hasattr(result, 'node') and hasattr(result, 'continuation_pin'):
                # 这是 NodeProcessingResult，设置延续引脚
                if result.continuation_pin:
                    context.pending_continuation_pin = result.continuation_pin
                return result.node
            return result
        

        
        # 阶段三：备用处理器（Fallback Processor）- 确保永不失败
        return self._create_fallback_node(context, node)
    

    
    def _create_fallback_node(self, context: AnalysisContext, node: GraphNode) -> FallbackNode:
        """
        备用处理器 - 三层梯度处理器策略的最后一层
        创建FallbackNode确保解析过程永不中断
        """
        # 收集节点的关键属性
        key_properties = {}
        for key, value in node.properties.items():
            # 只保留关键属性，避免输出过于冗长
            if key in ["FunctionReference", "TargetType", "MacroGraphReference", "DelegatePropertyName"]:
                key_properties[key] = str(value)[:100]  # 限制长度
        
        # 收集引脚信息
        pin_info = []
        for pin in node.pins[:10]:  # 限制引脚数量
            pin_info.append((pin.pin_name, pin.direction, pin.pin_type))
        
        return FallbackNode(
            class_name=node.class_type,
            node_name=node.node_name,
            properties=key_properties,
            pin_info=pin_info,
            source_location=create_source_location(node)
        )
    
    def _try_build_data_flow_expression(self, context: AnalysisContext, node: GraphNode) -> Optional[Expression]:
        """
        专门处理数据流中的特殊节点类型
        解决剩余的UnsupportedExpression问题
        """
        # K2Node_Self: 返回self引用
        if node.class_type in ["K2Node_Self", "/Script/BlueprintGraph.K2Node_Self"]:
            return VariableGetExpression(
                variable_name="self",
                is_self_variable=True,
                source_location=create_source_location(node)
            )
        
        # K2Node_Knot: 透明传递连接的值
        elif node.class_type in ["K2Node_Knot", "/Script/BlueprintGraph.K2Node_Knot"]:
            # 查找输入引脚并递归解析
            for pin in node.pins:
                if pin.direction == "input" and pin.linked_to:
                    return self._resolve_data_expression(context, pin)
            # 如果没有输入连接，返回null
            return LiteralExpression(value="null", literal_type="null")
        
        # K2Node_GetArrayItem: 数组元素访问
        elif node.class_type in ["K2Node_GetArrayItem", "/Script/BlueprintGraph.K2Node_GetArrayItem"]:
            array_pin = find_pin(node, "Array", "input")
            index_pin = find_pin(node, "Index", "input")
            
            array_expr = self._resolve_data_expression(context, array_pin) if array_pin else LiteralExpression(value="[]", literal_type="array")
            index_expr = self._resolve_data_expression(context, index_pin) if index_pin else LiteralExpression(value="0", literal_type="int")
            
            return FunctionCallExpression(
                target=array_expr,
                function_name="Array_Get",
                arguments=[("Index", index_expr)],
                source_location=create_source_location(node)
            )
        
        # K2Node_PromotableOperator: 操作符调用
        elif node.class_type in ["K2Node_PromotableOperator", "/Script/BlueprintGraph.K2Node_PromotableOperator"]:
            # 从节点属性中提取操作符名称
            func_ref = node.properties.get("FunctionReference", {})
            if isinstance(func_ref, dict):
                func_name = func_ref.get("MemberName", "UnknownOperator")
            else:
                func_name = "UnknownOperator"
            
            # 解析操作数
            arguments = self._parse_function_arguments(context, node, exclude_pins={"self"})
            
            return FunctionCallExpression(
                target=None,
                function_name=str(func_name),
                arguments=arguments,
                source_location=create_source_location(node)
            )
        
        # K2Node_MacroInstance: 在数据流中作为宏调用结果
        elif node.class_type in ["K2Node_MacroInstance", "/Script/BlueprintGraph.K2Node_MacroInstance"]:
            macro_name = extract_macro_name(node)
            
            # 特殊情况：ForEachLoop在数据流中应该返回循环变量而不是宏调用
            if "ForEachLoop" in macro_name or "ForEach" in macro_name:
                # 查找输出引脚，如果是循环变量输出，直接返回循环变量表达式
                for pin in node.pins:
                    if pin.direction == "output" and pin.pin_name in ["Array Element", "Array Index"]:
                        # 检查ScopeManager中是否有对应的变量
                        scope_expr = context.scope_manager.lookup_variable(pin.pin_id)
                        if scope_expr:
                            return scope_expr
                        # 如果ScopeManager中没有，创建循环变量表达式
                        is_index = "Index" in pin.pin_name
                        return LoopVariableExpression(
                            variable_name="ArrayIndex" if is_index else "ArrayElement",
                            is_index=is_index,
                            loop_id=node.node_guid,
                            source_location=create_source_location(node)
                        )
            
            # 其他宏实例：解析为宏调用
            arguments = self._parse_function_arguments(context, node, exclude_pins={"self"})
            
            return FunctionCallExpression(
                target=None,
                function_name=f"Macro_{macro_name}",
                arguments=arguments,
                source_location=create_source_location(node)
            )
        
        return None



    # ========================================================================
    # 核心遍历方法
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
            
            # 处理目标节点
            ast_node = self._process_node(context, target_node)
            if isinstance(ast_node, Statement):
                statements.append(ast_node)
            
            # 关键修复：检查是否有 pending_continuation_pin（来自 ForEachLoop 等复杂节点）
            if context.pending_continuation_pin:
                # 对于ForEachLoop等需要作用域管理的节点，在这里离开作用域
                if isinstance(ast_node, LoopNode) and ast_node.loop_type == LoopType.FOR_EACH:
                    context.scope_manager.leave_scope()
                
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
        
        # 第一优先级：检查 ScopeManager 中的变量（解决 UnknownExpression 的核心）
        scope_expression = context.scope_manager.lookup_variable(pin.pin_id)
        if scope_expression:
            return scope_expression
        
        # 第二优先级：检查 pin_ast_map（向后兼容）
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
        
        # 查找源节点
        source_node = None
        if source_node_id:
            source_node = self._find_node_by_id(context, source_node_id)
        elif source_pin_id:
            source_node = self._find_node_by_pin_id(context, source_pin_id)
        
        if not source_node:
            return LiteralExpression(value="null", literal_type="null")
        
        # 循环检测
        source_key = f"{source_node.node_guid}:{source_pin_id}"
        if source_key in visited_path:
            return LiteralExpression(value="circular_ref", literal_type="error")
        
        visited_path.add(source_key)
        
        try:
            # 解析源节点表达式
            result = self._resolve_node_expression(context, source_node, source_pin_id, visited_path)
            return result
        finally:
            visited_path.remove(source_key)
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _find_node_by_id(self, context: AnalysisContext, node_id: str) -> Optional[GraphNode]:
        """
        通过节点ID查找节点
        """
        # 先尝试直接查找
        if node_id in context.graph.nodes:
            return context.graph.nodes[node_id]
        
        # 如果直接查找失败，遍历所有节点查找匹配的GUID或名称
        for node in context.graph.nodes.values():
            if node.node_guid == node_id or node.node_name == node_id:
                return node
        
        return None
    
    def _find_node_by_pin_id(self, context: AnalysisContext, pin_id: str) -> Optional[GraphNode]:
        """
        通过引脚ID查找包含该引脚的节点
        """
        for node in context.graph.nodes.values():
            for pin in node.pins:
                if pin.pin_id == pin_id:
                    return node
        return None
    
    def _resolve_node_expression(self, context: AnalysisContext, node: GraphNode, pin_id: str, visited_path: Optional[Set[str]] = None) -> Expression:
        """
        解析节点的表达式
        """
        # 优先检查符号表解析
        symbol_expr = self._try_resolve_from_symbol_table(context, node, pin_id)
        if symbol_expr:
            return symbol_expr
        
        # 检查是否需要创建临时变量
        pin_key = f"{node.node_guid}:{pin_id}"
        usage_count = context.pin_usage_counts.get(pin_key, 0)
        
        if usage_count > 1 and should_create_temp_variable_for_node(node):
            # 创建临时变量
            temp_var_name = generate_temp_variable_name(node, pin_id)
            
            # 检查是否已经创建过这个临时变量
            if pin_key not in context.memoization_cache:
                # 解析原始表达式
                original_expr = self._resolve_node_expression_direct(context, node, pin_id, visited_path)
                
                # 创建临时变量声明
                temp_decl = TemporaryVariableDeclaration(
                    variable_name=temp_var_name,
                    value_expression=original_expr,
                    source_location=create_source_location(node)
                )
                
                # 添加到作用域前置语句
                context.scope_prelude.append(temp_decl)
                
                # 创建临时变量表达式
                temp_expr = TemporaryVariableExpression(
                    temp_var_name=temp_var_name,
                    source_location=create_source_location(node)
                )
                
                # 缓存结果
                context.memoization_cache[pin_key] = temp_expr
            
            return context.memoization_cache[pin_key]
        else:
            # 直接解析表达式
            return self._resolve_node_expression_direct(context, node, pin_id, visited_path)
    
    def _resolve_node_expression_direct(self, context: AnalysisContext, node: GraphNode, pin_id: str, visited_path: Optional[Set[str]] = None) -> Expression:
        """
        直接解析节点表达式，不使用临时变量
        """
        # 根据节点类型进行特殊处理
        if "K2Node_VariableGet" in node.class_type:
            return self._build_property_access_expression(context, node)
        elif "K2Node_DynamicCast" in node.class_type:
            return self._build_cast_expression(context, node)
        elif "K2Node_CallFunction" in node.class_type:
            return self._process_call_function_as_expression(context, node)
        elif "K2Node_Literal" in node.class_type:
            # 字面量节点
            default_value = node.properties.get("ObjectRef", "")
            return LiteralExpression(value=default_value, literal_type="literal")
        else:
            # 特殊处理：事件节点作为表达式的情况
            if node.class_type in ["K2Node_Event", "K2Node_CustomEvent", "K2Node_ComponentBoundEvent",
                                   "/Script/BlueprintGraph.K2Node_Event", 
                                   "/Script/BlueprintGraph.K2Node_CustomEvent",
                                   "/Script/BlueprintGraph.K2Node_ComponentBoundEvent"]:
                # 事件节点作为数据源时，返回EventReferenceExpression
                event_name = extract_event_name(node)
                return EventReferenceExpression(
                    event_name=event_name,
                    source_location=create_source_location(node)
                )
            
            # 专门的数据流表达式处理
            data_flow_expression = self._try_build_data_flow_expression(context, node)
            if data_flow_expression:
                return data_flow_expression
            
            # 通用处理：尝试使用处理器
            processor = node_processor_registry.get_processor(node.class_type)
            if processor:
                result = processor(self, context, node)
                if isinstance(result, Expression):
                    return result
                # 删除了对Statement的处理，如果处理器错误地返回了Statement，让它直接失败
            
            # 新架构：不再产生 UnknownExpression，使用 FallbackNode 策略
            # 如果到达这里，说明该节点无法作为表达式解析，返回一个描述性的字面量
            return LiteralExpression(
                value=f"UnsupportedExpression({node.class_type})", 
                literal_type="unsupported",
                source_location=create_source_location(node)
            )
    
    def _process_call_function_as_expression(self, context: AnalysisContext, node: GraphNode) -> FunctionCallExpression:
        """
        将函数调用节点处理为表达式
        """
        # 提取函数信息
        func_name = extract_function_reference(node)
        
        # 解析目标对象
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
    
    def _parse_function_arguments(self, context: AnalysisContext, node: GraphNode, exclude_pins: set = None) -> List[Tuple[str, Expression]]:
        """
        解析函数参数，返回带表达式的参数列表
        """
        if exclude_pins is None:
            exclude_pins = {"self"}
        
        arguments = []
        
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec"] and
                pin.pin_name not in exclude_pins):
                arg_expr = self._resolve_data_expression(context, pin)
                arguments.append((pin.pin_name, arg_expr))
        
        return arguments
    
    def _build_property_access_expression(self, context: AnalysisContext, node: GraphNode) -> Expression:
        """
        构建属性访问表达式，支持递归解析嵌套访问链
        """
        # 提取当前节点的变量名
        var_name, is_self_context = extract_variable_reference(node)
        
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
    
    def _build_cast_expression(self, context: AnalysisContext, node: GraphNode) -> Expression:
        """
        从 K2Node_DynamicCast 节点构建 CastExpression
        专门用于数据流解析，与控制流的 process_dynamic_cast 分离
        """
        # 1. 解析作为转换来源的输入表达式
        # DynamicCast 节点的输入通常是 "Object" 引脚
        object_pin = find_pin(node, "Object", "input")
        if not object_pin:
            # 如果找不到 "Object" 引脚，尝试其他可能的名称
            object_pin = find_pin(node, "Target", "input")
        
        source_expr = self._resolve_data_expression(context, object_pin) if object_pin else LiteralExpression(
            value="null", literal_type="null"
        )
        
        # 2. 从节点属性中提取目标类型名称
        target_type_str = node.properties.get("TargetType", "UnknownType")
        target_type_name = parse_object_path(target_type_str) or "UnknownType"
        
        # 3. 构建并返回 CastExpression AST 节点
        return CastExpression(
            source_expression=source_expr,
            target_type=target_type_name,
            source_location=create_source_location(node),
            ue_type='cast_expression'
        )
    
    def _try_resolve_from_symbol_table(self, context: AnalysisContext, source_node: GraphNode, source_pin_id: str) -> Optional[Expression]:
        """
        尝试从符号表解析表达式
        """
        # 提取变量名
        var_name = self._extract_variable_name_from_node(source_node)
        if not var_name:
            return None
        
        # 检查符号表
        symbol = context.symbol_table.lookup(var_name)
        if symbol:
            return self._create_expression_from_symbol(context, var_name)
        
        # 检查输出引脚符号
        return self._check_output_pin_symbols(context, source_node, source_pin_id)
    
    def _extract_variable_name_from_node(self, node: GraphNode) -> str:
        """
        从节点中提取变量名
        """
        if "K2Node_VariableGet" in node.class_type or "K2Node_VariableSet" in node.class_type:
            var_name, _ = extract_variable_reference(node)
            return var_name
        return ""
    
    def _create_expression_from_symbol(self, context: AnalysisContext, var_name: str) -> Optional[Expression]:
        """
        从符号创建表达式
        """
        symbol = context.symbol_table.lookup(var_name)
        if symbol:
            return VariableGetExpression(
                variable_name=var_name,
                is_self_variable=not (symbol.is_loop_variable or symbol.is_callback_parameter)
            )
        return None
    
    def _check_output_pin_symbols(self, context: AnalysisContext, node: GraphNode, pin_id: str) -> Optional[Expression]:
        """
        检查输出引脚符号
        """
        # 查找对应的输出引脚
        for pin in node.pins:
            if pin.pin_id == pin_id and pin.direction == "output":
                symbol = context.symbol_table.lookup(pin.pin_name)
                if symbol:
                    return VariableGetExpression(
                        variable_name=pin.pin_name,
                        is_self_variable=not (symbol.is_loop_variable or symbol.is_callback_parameter)
                    )
        return None


    



    

    
    def _process_macro_instance(self, context: AnalysisContext, node: GraphNode) -> Optional[ASTNode]:
        """
        处理宏实例节点 - 现在通过注册表系统处理
        K2Node_MacroInstance -> 根据宏类型返回不同的AST节点
        """
        # 获取宏图引用信息
        macro_ref = node.properties.get("MacroGraphReference", {})
        if isinstance(macro_ref, dict):
            macro_graph = macro_ref.get("MacroGraph", "")
        elif isinstance(macro_ref, str):
            macro_graph = macro_ref
        else:
            macro_graph = ""
        
        # 构建特殊的处理器键来处理特定的宏类型
        if "ForEachLoop" in macro_graph or "ForEach" in macro_graph:
            # 使用特殊的注册键处理 ForEachLoop
            from .common.decorators import get_processor
            processor = get_processor("K2Node_MacroInstance:ForEachLoop")
            if processor:
                result = processor(self, context, node)
                if hasattr(result, 'continuation_pin'):
                    # NodeProcessingResult 类型，需要特殊处理
                    context.pending_continuation_pin = result.continuation_pin
                    return result.ast_node
                return result
        elif "WhileLoop" in macro_graph or "While" in macro_graph:
            # 使用特殊的注册键处理 WhileLoop
            from .common.decorators import get_processor
            processor = get_processor("K2Node_MacroInstance:WhileLoop")
            if processor:
                return processor(self, context, node)
        
        # 通用宏处理
        from .common.decorators import get_processor
        processor = get_processor("K2Node_MacroInstance")
        if processor:
            return processor(self, context, node)
        
        return None
    

    

    

    
    # ========================================================================
    # 新增节点处理器实现
    # ========================================================================
    

    

    

    
