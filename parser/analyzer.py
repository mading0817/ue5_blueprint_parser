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
from .common import (
    find_pin, create_source_location, get_pin_default_value, extract_pin_type,
    extract_variable_reference, extract_function_reference, extract_event_name,
    parse_function_arguments, should_create_temp_variable_for_node, generate_temp_variable_name,
    has_execution_pins, node_processor_registry, extract_macro_name
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
        重构：优先识别事件入口节点，确保事件逻辑完整解析
        """
        # Pass 1: 符号与依赖分析
        pin_usage_counts = self._perform_symbol_analysis(graph)
        
        # Pass 2: 上下文感知AST生成
        context = AnalysisContext(
            graph=graph,
            symbol_table=SymbolTable(),  # 初始化符号表
            pin_usage_counts=pin_usage_counts
        )
        
        # 重构：首先遍历整个图，找出所有事件入口节点
        event_entry_nodes = []
        for node in graph.nodes.values():
            if node.class_type in ["K2Node_Event", "K2Node_CustomEvent", "K2Node_ComponentBoundEvent",
                                   "/Script/BlueprintGraph.K2Node_Event", 
                                   "/Script/BlueprintGraph.K2Node_CustomEvent",
                                   "/Script/BlueprintGraph.K2Node_ComponentBoundEvent"]:
                event_entry_nodes.append(node)
        
        # 处理所有事件入口节点，确保每个事件的完整逻辑都被解析
        ast_nodes = []
        for event_node in event_entry_nodes:
            if event_node.node_guid not in context.visited_nodes:
                ast_node = self._process_node(context, event_node)
                if ast_node:
                    ast_nodes.append(ast_node)
        
        # 处理其他剩余的入口节点（如果有的话）
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
        
        # 阶段二：通用查找
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
        else:
            # 未知节点类型，创建UnsupportedNode
            return UnsupportedNode(
                class_name=node.class_type,
                node_name=node.node_name,
                source_location=create_source_location(node)
            )
    
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
            
            # 通用处理：尝试使用处理器
            processor = node_processor_registry.get_processor(node.class_type)
            if processor:
                result = processor(self, context, node)
                if isinstance(result, Expression):
                    return result
                # 删除了对Statement的处理，如果处理器错误地返回了Statement，让它直接失败
            
            # 默认返回未知表达式
            return LiteralExpression(value="UnknownExpression", literal_type="unknown")
    
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
    

    

    

    
