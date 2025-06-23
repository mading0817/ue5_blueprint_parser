"""
Blueprint Graph Analyzer
将原始的BlueprintGraph转换为逻辑抽象语法树(AST)
"""

from typing import Dict, List, Optional, Callable, Set, Tuple, Any
from dataclasses import dataclass, field

from .models import (
    BlueprintGraph, GraphNode, GraphPin,
    # AST节点
    ASTNode, Expression, Statement,
    SourceLocation, ExecutionBlock, EventNode, AssignmentNode,
    FunctionCallNode, FunctionCallExpression, VariableGetExpression,
    LiteralExpression, TemporaryVariableExpression,
    TemporaryVariableDeclaration,
    # 控制流节点
    BranchNode, LoopNode, LoopType, MultiBranchNode, LatentActionNode
)


# 节点处理器类型定义
NodeProcessor = Callable[[GraphNode], Optional[ASTNode]]


@dataclass
class AnalysisState:
    """
    分析过程中的状态跟踪
    """
    visited_nodes: Set[str] = field(default_factory=set)  # 已访问的节点GUID
    temp_variables: Dict[str, TemporaryVariableDeclaration] = field(default_factory=dict)  # pin_id -> temp var
    pin_usage_count: Dict[str, int] = field(default_factory=dict)  # 统计每个输出引脚的使用次数
    current_scope: List[Statement] = field(default_factory=list)  # 当前作用域的语句列表


class GraphAnalyzer:
    """
    蓝图图分析器
    负责将BlueprintGraph转换为逻辑AST
    """
    
    def __init__(self):
        # 初始化节点处理器注册表
        self._node_processors: Dict[str, NodeProcessor] = {}
        self._register_default_processors()
    
    def _register_default_processors(self):
        """
        注册默认的节点处理器
        """
        # 事件节点
        self.register_processor("K2Node_Event", self._process_event_node)
        self.register_processor("/Script/BlueprintGraph.K2Node_Event", self._process_event_node)
        
        # 变量操作
        self.register_processor("K2Node_VariableSet", self._process_variable_set)
        self.register_processor("/Script/BlueprintGraph.K2Node_VariableSet", self._process_variable_set)
        self.register_processor("K2Node_VariableGet", self._process_variable_get)
        self.register_processor("/Script/BlueprintGraph.K2Node_VariableGet", self._process_variable_get)
        
        # 函数调用
        self.register_processor("K2Node_CallFunction", self._process_call_function)
        self.register_processor("/Script/BlueprintGraph.K2Node_CallFunction", self._process_call_function)
        
        # 控制流节点
        self.register_processor("K2Node_IfThenElse", self._process_if_then_else)
        self.register_processor("/Script/BlueprintGraph.K2Node_IfThenElse", self._process_if_then_else)
        self.register_processor("K2Node_ExecutionSequence", self._process_execution_sequence)
        self.register_processor("/Script/BlueprintGraph.K2Node_ExecutionSequence", self._process_execution_sequence)
        self.register_processor("K2Node_MacroInstance", self._process_macro_instance)
        self.register_processor("/Script/BlueprintGraph.K2Node_MacroInstance", self._process_macro_instance)
        
        # 潜在动作节点
        self.register_processor("K2Node_LatentAbilityCall", self._process_latent_ability_call)
        self.register_processor("/Script/GameplayAbilitiesEditor.K2Node_LatentAbilityCall", self._process_latent_ability_call)
    
    def register_processor(self, node_type: str, processor: NodeProcessor):
        """
        注册节点处理器
        """
        self._node_processors[node_type] = processor
    
    def analyze(self, graph: BlueprintGraph) -> List[ASTNode]:
        """
        分析蓝图图并返回AST节点列表
        主入口方法
        """
        # 初始化分析状态
        self.state = AnalysisState()
        # 保存graph引用，供其他方法使用
        self.graph = graph
        
        # 首先统计引脚使用次数（用于智能变量提取）
        self._analyze_pin_usage(graph)
        
        # 处理所有入口节点
        ast_nodes = []
        for entry_node in graph.entry_nodes:
            if entry_node.node_guid not in self.state.visited_nodes:
                ast_node = self._process_node(entry_node)
                if ast_node:
                    ast_nodes.append(ast_node)
        
        return ast_nodes
    
    def _analyze_pin_usage(self, graph: BlueprintGraph):
        """
        分析所有引脚的使用次数
        用于决定是否需要创建临时变量
        """
        for node in graph.nodes.values():
            for pin in node.pins:
                # 统计每个引脚被连接的次数
                connection_count = len(pin.linked_to)
                if connection_count > 0 and pin.direction == "output":
                    pin_key = f"{node.node_guid}:{pin.pin_id}"
                    self.state.pin_usage_count[pin_key] = connection_count
    
    def _process_node(self, node: GraphNode) -> Optional[ASTNode]:
        """
        处理单个节点，调用相应的处理器
        """
        if node.node_guid in self.state.visited_nodes:
            return None
        
        # 标记为已访问
        self.state.visited_nodes.add(node.node_guid)
        
        # 查找对应的处理器
        processor = self._node_processors.get(node.class_type)
        if processor:
            return processor(node)
        else:
            # 未知节点类型，打印警告但不中断处理
            print(f"Warning: No processor for node type {node.class_type}")
            return None
    
    # ========================================================================
    # 节点处理器实现
    # ========================================================================
    
    def _process_event_node(self, node: GraphNode) -> Optional[EventNode]:
        """
        处理事件节点
        K2Node_Event -> EventNode
        """
        # 提取事件名称
        event_ref = node.properties.get("EventReference", "")
        if isinstance(event_ref, dict):
            event_name = event_ref.get("MemberName", node.node_name)
        elif isinstance(event_ref, str) and "MemberName=" in event_ref:
            # 解析字符串格式的EventReference
            import re
            match = re.search(r'MemberName="([^"]+)"', event_ref)
            event_name = match.group(1) if match else node.node_name
        else:
            event_name = node.node_name
        
        # 创建事件节点
        event_node = EventNode(
            event_name=event_name,
            parameters=[],  # TODO: 解析事件参数
            body=ExecutionBlock(),
            source_location=self._create_source_location(node)
        )
        
        # 跟随执行流构建事件体
        exec_pin = self._find_pin(node, "then", "output")
        if exec_pin:
            self._follow_execution_flow(exec_pin, event_node.body.statements)
        
        return event_node
    
    def _process_variable_set(self, node: GraphNode) -> Optional[AssignmentNode]:
        """
        处理变量赋值节点
        K2Node_VariableSet -> AssignmentNode
        """
        # 提取变量名
        var_reference = node.properties.get("VariableReference", "")
        if isinstance(var_reference, dict):
            var_name = var_reference.get("MemberName", "UnknownVariable")
            is_self_context = var_reference.get("bSelfContext", True)
        elif isinstance(var_reference, str) and "MemberName=" in var_reference:
            import re
            match = re.search(r'MemberName="([^"]+)"', var_reference)
            var_name = match.group(1) if match else "UnknownVariable"
            is_self_context = "bSelfContext=True" in var_reference or "bSelfContext=False" not in var_reference
        else:
            var_name = "UnknownVariable"
            is_self_context = True
        
        # 查找值引脚（通常是和变量同名的输入引脚）
        value_pin = self._find_pin(node, var_name, "input")
        if not value_pin:
            # 尝试查找任何非exec的输入引脚
            for pin in node.pins:
                if pin.direction == "input" and pin.pin_type != "exec":
                    value_pin = pin
                    break
        
        # 解析值表达式
        value_expr = self._resolve_data_expression(value_pin, None, node.node_guid) if value_pin else LiteralExpression(
            value="null",
            literal_type="null"
        )
        
        # 创建赋值节点
        assignment = AssignmentNode(
            variable_name=var_name,
            value_expression=value_expr,
            is_local_variable=not is_self_context,
            source_location=self._create_source_location(node)
        )
        
        return assignment
    
    def _process_variable_get(self, node: GraphNode) -> Optional[VariableGetExpression]:
        """
        处理变量读取节点（作为表达式）
        K2Node_VariableGet -> VariableGetExpression
        """
        # 提取变量名
        var_reference = node.properties.get("VariableReference", "")
        if isinstance(var_reference, dict):
            var_name = var_reference.get("MemberName", "UnknownVariable")
            is_self_context = var_reference.get("bSelfContext", True)
        elif isinstance(var_reference, str) and "MemberName=" in var_reference:
            import re
            match = re.search(r'MemberName="([^"]+)"', var_reference)
            var_name = match.group(1) if match else "UnknownVariable"
            is_self_context = "bSelfContext=True" in var_reference or "bSelfContext=False" not in var_reference
        else:
            var_name = "UnknownVariable"
            is_self_context = True
        
        return VariableGetExpression(
            variable_name=var_name,
            is_self_variable=is_self_context,
            source_location=self._create_source_location(node)
        )
    
    def _process_call_function(self, node: GraphNode) -> Optional[ASTNode]:
        """
        处理函数调用节点
        根据是否有exec引脚决定返回FunctionCallNode还是FunctionCallExpression
        """
        # 提取函数信息
        func_reference = node.properties.get("FunctionReference", "")
        if isinstance(func_reference, dict):
            func_name = func_reference.get("MemberName", "UnknownFunction")
        elif isinstance(func_reference, str) and "MemberName=" in func_reference:
            import re
            match = re.search(r'MemberName="([^"]+)"', func_reference)
            func_name = match.group(1) if match else "UnknownFunction"
        else:
            func_name = "UnknownFunction"
        
        # 检查是否有执行引脚（决定是语句还是表达式）
        has_exec = any(pin.pin_type == "exec" for pin in node.pins)
        
        # 解析目标对象（self引脚）
        target_expr = None
        self_pin = self._find_pin(node, "self", "input")
        if self_pin and self_pin.linked_to:
            target_expr = self._resolve_data_expression(self_pin, None, node.node_guid)
        
        # 解析参数
        arguments = []
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec", "delegate"] and 
                pin.pin_name not in ["self", "then"]):
                arg_expr = self._resolve_data_expression(pin, None, node.node_guid)
                arguments.append((pin.pin_name, arg_expr))
        
        if has_exec:
            # 有执行引脚的函数调用是语句
            call_node = FunctionCallNode(
                target=target_expr,
                function_name=func_name,
                arguments=arguments,
                source_location=self._create_source_location(node)
            )
            
            # 处理返回值赋值
            for pin in node.pins:
                if pin.direction == "output" and pin.pin_type != "exec":
                    # TODO: 实现返回值处理
                    pass
            
            return call_node
        else:
            # 纯函数调用是表达式
            return FunctionCallExpression(
                target=target_expr,
                function_name=func_name,
                arguments=arguments,
                source_location=self._create_source_location(node)
            )
    
    def _process_if_then_else(self, node: GraphNode) -> Optional[BranchNode]:
        """
        处理分支节点
        K2Node_IfThenElse -> BranchNode
        """
        # 查找条件引脚
        condition_pin = self._find_pin(node, "Condition", "input")
        condition_expr = self._resolve_data_expression(condition_pin, None, node.node_guid) if condition_pin else LiteralExpression(
            value="true",
            literal_type="bool"
        )
        
        # 创建分支节点
        branch_node = BranchNode(
            condition=condition_expr,
            true_branch=ExecutionBlock(),
            false_branch=ExecutionBlock(),
            source_location=self._create_source_location(node)
        )
        
        # 处理true分支
        true_pin = self._find_pin(node, "then", "output")
        if not true_pin:
            true_pin = self._find_pin(node, "true", "output")
        if true_pin:
            self._follow_execution_flow(true_pin, branch_node.true_branch.statements)
        
        # 处理false分支
        false_pin = self._find_pin(node, "else", "output")
        if not false_pin:
            false_pin = self._find_pin(node, "false", "output")
        if false_pin:
            self._follow_execution_flow(false_pin, branch_node.false_branch.statements)
        
        return branch_node
    
    def _process_execution_sequence(self, node: GraphNode) -> Optional[ExecutionBlock]:
        """
        处理执行序列节点
        K2Node_ExecutionSequence -> ExecutionBlock (包含多个执行流)
        """
        # 执行序列节点会有多个输出执行引脚，按顺序执行
        sequence_block = ExecutionBlock(source_location=self._create_source_location(node))
        
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
                self._follow_execution_flow(pin, sequence_block.statements)
        
        return sequence_block
    
    def _process_macro_instance(self, node: GraphNode) -> Optional[ASTNode]:
        """
        处理宏实例节点
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
        
        # 根据宏类型处理
        if "ForEachLoop" in macro_graph:
            return self._process_foreach_macro(node)
        elif "WhileLoop" in macro_graph:
            return self._process_while_macro(node)
        else:
            # 未知宏类型，作为函数调用处理
            return self._process_generic_macro(node)
    
    def _process_foreach_macro(self, node: GraphNode) -> Optional[LoopNode]:
        """
        处理ForEach循环宏
        """
        # 查找数组输入引脚
        array_pin = self._find_pin(node, "Array", "input")
        collection_expr = self._resolve_data_expression(array_pin, None, node.node_guid) if array_pin else LiteralExpression(
            value="[]",
            literal_type="array"
        )
        
        # 创建循环节点
        loop_node = LoopNode(
            loop_type=LoopType.FOR_EACH,
            collection_expression=collection_expr,
            item_variable_name="ArrayElement",  # ForEach宏的默认元素变量名
            index_variable_name="ArrayIndex",   # ForEach宏的默认索引变量名
            body=ExecutionBlock(),
            source_location=self._create_source_location(node)
        )
        
        # 处理循环体
        loop_body_pin = self._find_pin(node, "LoopBody", "output")
        if loop_body_pin:
            self._follow_execution_flow(loop_body_pin, loop_node.body.statements)
        
        return loop_node
    
    def _process_while_macro(self, node: GraphNode) -> Optional[LoopNode]:
        """
        处理While循环宏
        """
        # 查找条件引脚
        condition_pin = self._find_pin(node, "Condition", "input")
        condition_expr = self._resolve_data_expression(condition_pin, None, node.node_guid) if condition_pin else LiteralExpression(
            value="true",
            literal_type="bool"
        )
        
        # 创建循环节点
        loop_node = LoopNode(
            loop_type=LoopType.WHILE,
            condition_expression=condition_expr,
            body=ExecutionBlock(),
            source_location=self._create_source_location(node)
        )
        
        # 处理循环体
        loop_body_pin = self._find_pin(node, "LoopBody", "output")
        if loop_body_pin:
            self._follow_execution_flow(loop_body_pin, loop_node.body.statements)
        
        return loop_node
    
    def _process_generic_macro(self, node: GraphNode) -> Optional[FunctionCallNode]:
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
                arg_expr = self._resolve_data_expression(pin, None, node.node_guid)
                arguments.append((pin.pin_name, arg_expr))
        
        return FunctionCallNode(
            target=None,
            function_name=f"macro_{macro_name}",
            arguments=arguments,
            source_location=self._create_source_location(node)
        )
    
    def _process_latent_ability_call(self, node: GraphNode) -> Optional[LatentActionNode]:
        """
        处理潜在动作节点
        K2Node_LatentAbilityCall -> LatentActionNode
        """
        # 提取动作名称
        proxy_factory_func = node.properties.get("ProxyFactoryFunctionName", "UnknownAction")
        
        # 解析参数
        arguments = []
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec", "delegate"] and
                pin.pin_name not in ["self", "OwningAbility"]):
                arg_expr = self._resolve_data_expression(pin, None, node.node_guid)
                arguments.append((pin.pin_name, arg_expr))
        
        # 创建潜在动作节点
        latent_node = LatentActionNode(
            action_name=proxy_factory_func,
            arguments=arguments,
            on_completed=ExecutionBlock(),
            output_flows={},
            source_location=self._create_source_location(node)
        )
        
        # 处理输出执行流
        for pin in node.pins:
            if pin.direction == "output" and pin.pin_type == "exec":
                if pin.pin_name == "then":
                    # 主要完成流
                    self._follow_execution_flow(pin, latent_node.on_completed.statements)
                else:
                    # 其他输出流（如EventReceived等）
                    flow_block = ExecutionBlock()
                    self._follow_execution_flow(pin, flow_block.statements)
                    latent_node.output_flows[pin.pin_name] = flow_block
        
        # 处理输出数据
        for pin in node.pins:
            if pin.direction == "output" and pin.pin_type != "exec":
                latent_node.output_data.append((pin.pin_name, pin.pin_name))
        
        return latent_node
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _follow_execution_flow(self, start_pin: GraphPin, statements: List[Statement]):
        """
        跟随执行流，构建语句序列
        """
        current_pin = start_pin
        
        while current_pin:
            # 查找通过output_connections连接的下一个节点
            next_nodes = []
            
            # 从当前引脚的所属节点查找输出连接
            current_node = None
            for node in self.graph.nodes.values():
                for pin in node.pins:
                    if pin.pin_id == current_pin.pin_id:
                        current_node = node
                        break
                if current_node:
                    break
            
            if current_node and current_pin.pin_id in current_node.output_connections:
                next_nodes = current_node.output_connections[current_pin.pin_id]
            
            if not next_nodes:
                # 没有更多连接，停止执行流跟踪
                break
            
            # 处理下一个节点（执行引脚通常只连接一个节点）
            next_node = next_nodes[0]
            
            # 处理节点
            ast_node = self._process_node(next_node)
            if isinstance(ast_node, Statement):
                statements.append(ast_node)
            
            # 查找下一个执行输出引脚
            current_pin = self._find_pin(next_node, "then", "output")
            if not current_pin:
                # 某些节点可能有不同名称的执行输出
                for pin in next_node.pins:
                    if pin.direction == "output" and pin.pin_type == "exec":
                        current_pin = pin
                        break
    
    def _resolve_data_expression(self, pin: Optional[GraphPin], visited_pins: Optional[Set[str]] = None, current_node_guid: Optional[str] = None) -> Expression:
        """
        解析数据引脚连接，构建表达式树
        支持递归解析和循环检测
        """
        if not pin or not pin.linked_to:
            # 没有连接，返回默认值
            return LiteralExpression(
                value=self._get_pin_default_value(pin) if pin else "null",
                literal_type="unknown"
            )
        
        # 初始化循环检测集合
        if visited_pins is None:
            visited_pins = set()
        
        # 生成当前引脚的唯一标识
        pin_key = f"{current_node_guid}:{pin.pin_id}" if current_node_guid else f"unknown:{pin.pin_id}"
        
        # 检测循环引用
        if pin_key in visited_pins:
            return LiteralExpression(value="<circular_reference>", literal_type="error")
        
        visited_pins.add(pin_key)
        
        try:
            # 获取连接的源节点
            source_link = pin.linked_to[0]
            source_node_id = source_link.get("node_guid") or source_link.get("node_name")
            source_pin_id = source_link.get("pin_id")
            
            # 查找源节点
            source_node = self._find_node_by_id(source_node_id)
            if not source_node:
                return LiteralExpression(value="<node_not_found>", literal_type="error")
            
            # 检查是否需要创建临时变量
            source_pin_key = f"{source_node.node_guid}:{source_pin_id}"
            if self._should_create_temp_variable(source_pin_key, source_node):
                return self._create_or_get_temp_variable(source_pin_key, source_node, source_pin_id, visited_pins.copy())
            
            # 根据源节点类型解析表达式
            return self._resolve_node_expression(source_node, source_pin_id, visited_pins.copy())
            
        finally:
            visited_pins.discard(pin_key)
    
    def _find_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        """
        根据节点ID查找节点
        """
        if not hasattr(self, 'graph') or not self.graph:
            return None
        
        # 先从graph的nodes字典中查找
        node = self.graph.nodes.get(node_id)
        if node:
            return node
        
        # 尝试通过节点名查找
        for node in self.graph.nodes.values():
            if node.node_name == node_id:
                return node
        
        return None
    
    def _should_create_temp_variable(self, pin_key: str, source_node: GraphNode) -> bool:
        """
        判断是否需要为输出引脚创建临时变量
        当输出被多个节点使用时，创建临时变量以避免重复计算
        """
        # 检查引脚使用次数
        usage_count = self.state.pin_usage_count.get(pin_key, 0)
        
        # 如果使用次数大于1，且节点不是简单的变量获取，则创建临时变量
        if usage_count > 1:
            # 简单的变量获取不需要临时变量
            if 'K2Node_VariableGet' in source_node.class_type:
                return False
            # 字面量节点也不需要临时变量
            if 'K2Node_Literal' in source_node.class_type:
                return False
            return True
        
        return False
    
    def _create_or_get_temp_variable(self, pin_key: str, source_node: GraphNode, source_pin_id: str, visited_pins: Set[str]) -> TemporaryVariableExpression:
        """
        创建或获取临时变量
        """
        # 检查是否已经创建了临时变量
        if pin_key in self.state.temp_variables:
            temp_var = self.state.temp_variables[pin_key]
            return TemporaryVariableExpression(
                temp_var_name=temp_var.variable_name,
                source_location=temp_var.source_location
            )
        
        # 创建新的临时变量
        temp_var_name = self._generate_temp_variable_name(source_node, source_pin_id)
        
        # 解析源表达式
        source_expr = self._resolve_node_expression(source_node, source_pin_id, visited_pins)
        
        # 创建临时变量声明
        temp_var_decl = TemporaryVariableDeclaration(
            variable_name=temp_var_name,
            value_expression=source_expr,
            source_location=self._create_source_location(source_node)
        )
        
        # 保存临时变量声明
        self.state.temp_variables[pin_key] = temp_var_decl
        
        # 将临时变量声明添加到当前作用域
        self.state.current_scope.append(temp_var_decl)
        
        # 返回临时变量表达式
        return TemporaryVariableExpression(
            temp_var_name=temp_var_name,
            source_location=temp_var_decl.source_location
        )
    
    def _generate_temp_variable_name(self, source_node: GraphNode, source_pin_id: str) -> str:
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
        
        # 确保变量名唯一
        counter = 1
        temp_name = base_name
        while any(temp_name == var.variable_name for var in self.state.temp_variables.values()):
            temp_name = f"{base_name}_{counter}"
            counter += 1
        
        return temp_name
    
    def _resolve_node_expression(self, node: GraphNode, pin_id: str, visited_pins: Set[str]) -> Expression:
        """
        根据节点类型解析为表达式
        """
        # K2Node_VariableGet - 变量获取
        if 'K2Node_VariableGet' in node.class_type:
            return self._process_variable_get(node)
        
        # K2Node_CallFunction - 函数调用（纯函数）
        elif 'K2Node_CallFunction' in node.class_type:
            # 检查是否是纯函数
            is_pure = node.properties.get("bIsPureFunc", False)
            if is_pure or not any(pin.pin_type == "exec" for pin in node.pins):
                expr = self._process_call_function_as_expression(node, visited_pins)
                if isinstance(expr, FunctionCallExpression):
                    return expr
        
        # K2Node_Literal - 字面量
        elif 'K2Node_Literal' in node.class_type:
            return self._process_literal_node(node)
        
        # K2Node_MathExpression - 数学表达式
        elif 'K2Node_MathExpression' in node.class_type:
            return self._process_math_expression_node(node, visited_pins)
        
        # K2Node_GetArrayItem - 数组访问
        elif 'K2Node_GetArrayItem' in node.class_type:
            return self._process_array_access_node(node, visited_pins)
        
        # 默认处理：尝试作为函数调用
        return self._process_call_function_as_expression(node, visited_pins)
    
    def _process_call_function_as_expression(self, node: GraphNode, visited_pins: Set[str]) -> FunctionCallExpression:
        """
        将函数调用节点处理为表达式
        """
        # 提取函数信息
        func_reference = node.properties.get("FunctionReference", "")
        if isinstance(func_reference, dict):
            func_name = func_reference.get("MemberName", "UnknownFunction")
        elif isinstance(func_reference, str) and "MemberName=" in func_reference:
            import re
            match = re.search(r'MemberName="([^"]+)"', func_reference)
            func_name = match.group(1) if match else "UnknownFunction"
        else:
            func_name = "UnknownFunction"
        
        # 解析目标对象（self引脚）
        target_expr = None
        self_pin = self._find_pin(node, "self", "input")
        if self_pin and self_pin.linked_to:
            target_expr = self._resolve_data_expression(self_pin, visited_pins, node.node_guid)
        
        # 解析参数
        arguments = []
        for pin in node.pins:
            if (pin.direction == "input" and 
                pin.pin_type not in ["exec", "delegate"] and 
                pin.pin_name not in ["self", "then"]):
                arg_expr = self._resolve_data_expression(pin, visited_pins, node.node_guid)
                arguments.append((pin.pin_name, arg_expr))
        
        return FunctionCallExpression(
            target=target_expr,
            function_name=func_name,
            arguments=arguments,
            source_location=self._create_source_location(node)
        )
    
    def _process_literal_node(self, node: GraphNode) -> LiteralExpression:
        """
        处理字面量节点
        """
        # 尝试从节点属性中提取字面量值
        literal_value = node.properties.get("Value", node.properties.get("DefaultValue", "null"))
        literal_type = "unknown"  # TODO: 根据引脚类型确定字面量类型
        
        return LiteralExpression(
            value=str(literal_value),
            literal_type=literal_type
        )
    
    def _process_math_expression_node(self, node: GraphNode, visited_pins: Set[str]) -> FunctionCallExpression:
        """
        处理数学表达式节点
        """
        # 数学表达式节点通常有操作符属性
        op = node.properties.get("Op", "+")
        
        # 查找输入引脚
        inputs = []
        for pin in node.pins:
            if pin.direction == "input" and pin.pin_type not in ["exec"]:
                input_expr = self._resolve_data_expression(pin, visited_pins, node.node_guid)
                inputs.append((pin.pin_name, input_expr))
        
        return FunctionCallExpression(
            target=None,
            function_name=f"math_{op}",
            arguments=inputs,
            source_location=self._create_source_location(node)
        )
    
    def _process_array_access_node(self, node: GraphNode, visited_pins: Set[str]) -> FunctionCallExpression:
        """
        处理数组访问节点
        """
        # 查找数组和索引引脚
        array_pin = self._find_pin(node, "TargetArray", "input")
        index_pin = self._find_pin(node, "Index", "input")
        
        array_expr = self._resolve_data_expression(array_pin, visited_pins, node.node_guid) if array_pin else LiteralExpression("null", "null")
        index_expr = self._resolve_data_expression(index_pin, visited_pins, node.node_guid) if index_pin else LiteralExpression("0", "int")
        
        return FunctionCallExpression(
            target=array_expr,
            function_name="get_item",
            arguments=[("index", index_expr)],
            source_location=self._create_source_location(node)
        )
    
    def _find_pin(self, node: GraphNode, pin_name: str, direction: str) -> Optional[GraphPin]:
        """
        在节点中查找指定名称和方向的引脚
        """
        for pin in node.pins:
            if pin.pin_name == pin_name and pin.direction == direction:
                return pin
        return None
    
    def _create_source_location(self, node: GraphNode) -> SourceLocation:
        """
        创建源位置信息
        """
        return SourceLocation(
            node_guid=node.node_guid,
            node_name=node.node_name
        )
    
    def _get_pin_default_value(self, pin: GraphPin) -> Any:
        """
        获取引脚的默认值
        """
        if pin and pin.default_value is not None:
            return pin.default_value
        return None 