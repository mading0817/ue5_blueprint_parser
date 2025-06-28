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
from .common import find_pin, create_source_location, get_pin_default_value, extract_pin_type
from .common import register_processor, node_processor_registry

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
        处理单个节点，使用全局注册表查找处理器
        """
        if node.node_guid in context.visited_nodes:
            return None
        
        # 标记为已访问
        context.visited_nodes.add(node.node_guid)
        
        # 从全局注册表查找处理器
        processor = node_processor_registry.get_processor(node.class_type)
        if processor:
            return processor(self, context, node)
        else:
            # 未知节点类型，创建UnsupportedNode
            return UnsupportedNode(
                class_name=node.class_type,
                node_name=node.node_name,
                source_location=create_source_location(node)
            )
    
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
        
        # K2Node_Literal, K2Node_MathExpression, K2Node_GetArrayItem 现在通过注册表处理
        elif ('K2Node_Literal' in node.class_type or 
              'K2Node_MathExpression' in node.class_type or 
              'K2Node_GetArrayItem' in node.class_type):
            # 尝试通过注册表处理
            result = self._process_node(context, node)
            if result and hasattr(result, 'accept'):  # 检查是否是表达式
                return result
        
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
    

    

    

    
