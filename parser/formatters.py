"""
格式化器模块：使用访问者模式将AST转换为不同的输出格式

该模块实现了新的三阶段解析架构中的第三阶段：AST格式化
支持多种输出格式和格式化策略
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from parser.models import (
    ASTNode, Expression, Statement,
    LiteralExpression, VariableGetExpression, FunctionCallExpression,
    CastExpression, MemberAccessExpression, TemporaryVariableExpression,
    PropertyAccessNode, UnsupportedNode,
    ExecutionBlock, EventNode, AssignmentNode, FunctionCallNode,
    BranchNode, LoopNode, LoopType, MultiBranchNode, LatentActionNode,
    ReturnNode, TemporaryVariableDeclaration,
    BlueprintNode, Blueprint, BlueprintGraph, GraphNode,
    # 新的语义节点
    VariableDeclaration, CallbackBlock
)


# ============================================================================
# 访问者模式基类
# ============================================================================

class ASTVisitor(ABC):
    """
    AST访问者模式的抽象基类
    所有格式化器都应该继承此类并实现相应的visit方法
    """
    
    @abstractmethod
    def visit_literal_expression(self, node: LiteralExpression) -> str:
        pass
    
    @abstractmethod
    def visit_variable_get_expression(self, node: VariableGetExpression) -> str:
        pass
    
    @abstractmethod
    def visit_function_call_expression(self, node: FunctionCallExpression) -> str:
        pass
    
    @abstractmethod
    def visit_cast_expression(self, node: CastExpression) -> str:
        pass
    
    @abstractmethod
    def visit_member_access_expression(self, node: MemberAccessExpression) -> str:
        pass
    
    @abstractmethod
    def visit_temporary_variable_expression(self, node: TemporaryVariableExpression) -> str:
        pass
    
    @abstractmethod
    def visit_property_access(self, node: PropertyAccessNode) -> str:
        pass
    
    @abstractmethod
    def visit_unsupported_node(self, node: UnsupportedNode) -> str:
        pass
    
    @abstractmethod
    def visit_execution_block(self, node: ExecutionBlock) -> str:
        pass
    
    @abstractmethod
    def visit_event_node(self, node: EventNode) -> str:
        pass
    
    @abstractmethod
    def visit_assignment_node(self, node: AssignmentNode) -> str:
        pass
    
    @abstractmethod
    def visit_function_call_node(self, node: FunctionCallNode) -> str:
        pass
    
    @abstractmethod
    def visit_branch_node(self, node: BranchNode) -> str:
        pass
    
    @abstractmethod
    def visit_loop_node(self, node: LoopNode) -> str:
        pass
    
    @abstractmethod
    def visit_multi_branch_node(self, node: MultiBranchNode) -> str:
        pass
    
    @abstractmethod
    def visit_latent_action_node(self, node: LatentActionNode) -> str:
        pass
    
    @abstractmethod
    def visit_return_node(self, node: ReturnNode) -> str:
        pass
    
    @abstractmethod
    def visit_temporary_variable_declaration(self, node: TemporaryVariableDeclaration) -> str:
        pass
    
    @abstractmethod
    def visit_variable_declaration(self, node: VariableDeclaration) -> str:
        pass
    
    @abstractmethod
    def visit_callback_block(self, node: CallbackBlock) -> str:
        pass


# ============================================================================
# 格式化策略模式
# ============================================================================

class FormattingStrategy(ABC):
    """格式化策略的抽象基类"""
    
    @abstractmethod
    def should_show_node_comments(self) -> bool:
        """是否显示节点注释"""
        pass
    
    @abstractmethod
    def should_show_type_info(self) -> bool:
        """是否显示类型信息"""
        pass
    
    @abstractmethod
    def should_inline_simple_expressions(self) -> bool:
        """是否内联简单表达式"""
        pass
    
    @abstractmethod
    def get_indent_string(self) -> str:
        """获取缩进字符串"""
        pass


class VerboseStrategy(FormattingStrategy):
    """详细输出策略"""
    
    def should_show_node_comments(self) -> bool:
        return True
    
    def should_show_type_info(self) -> bool:
        return True
    
    def should_inline_simple_expressions(self) -> bool:
        return False
    
    def get_indent_string(self) -> str:
        return "    "  # 4个空格


class ConciseStrategy(FormattingStrategy):
    """简洁输出策略"""
    
    def should_show_node_comments(self) -> bool:
        return False
    
    def should_show_type_info(self) -> bool:
        return False
    
    def should_inline_simple_expressions(self) -> bool:
        return True
    
    def get_indent_string(self) -> str:
        return "  "  # 2个空格


# ============================================================================
# Markdown格式化器
# ============================================================================

class MarkdownFormatter(ASTVisitor):
    """
    将AST转换为Markdown格式伪代码的格式化器
    使用访问者模式遍历AST并生成结构化的伪代码输出
    """
    
    def __init__(self, strategy: FormattingStrategy = None):
        self.strategy = strategy or ConciseStrategy()
        self.current_indent = 0
        self.output_lines = []
    
    def format_ast(self, ast_node: ASTNode) -> str:
        """
        格式化AST节点为Markdown字符串
        
        :param ast_node: 要格式化的AST根节点
        :return: 格式化后的Markdown字符串
        """
        self.current_indent = 0
        self.output_lines = []
        
        # 访问AST节点
        result = ast_node.accept(self)
        
        if self.output_lines:
            return '\n'.join(self.output_lines)
        else:
            return result or ""
    
    def _add_line(self, content: str, extra_indent: int = 0):
        """添加一行内容到输出"""
        indent = self.strategy.get_indent_string() * (self.current_indent + extra_indent)
        self.output_lines.append(f"{indent}{content}")
    
    def _get_indent(self, extra_indent: int = 0) -> str:
        """获取当前缩进字符串"""
        return self.strategy.get_indent_string() * (self.current_indent + extra_indent)
    
    # ========================================================================
    # 表达式节点访问方法
    # ========================================================================
    
    def visit_literal_expression(self, node: LiteralExpression) -> str:
        """访问字面量表达式"""
        if node.literal_type == "string":
            return f'"{node.value}"'
        elif node.literal_type == "bool":
            return str(node.value).lower()
        else:
            return str(node.value)
    
    def visit_variable_get_expression(self, node: VariableGetExpression) -> str:
        """访问变量获取表达式"""
        return node.variable_name
    
    def visit_function_call_expression(self, node: FunctionCallExpression) -> str:
        """访问函数调用表达式"""
        # 构建参数列表
        args = []
        for param_name, arg_expr in node.arguments:
            if arg_expr:
                arg_value = arg_expr.accept(self)
                if param_name and param_name.lower() != "value":
                    args.append(f"{param_name}: {arg_value}")
                else:
                    args.append(arg_value)
        
        args_str = ", ".join(args)
        
        # 构建函数调用
        if node.target:
            target_str = node.target.accept(self)
            return f"{target_str}.{node.function_name}({args_str})"
        else:
            return f"{node.function_name}({args_str})"
    
    def visit_cast_expression(self, node: CastExpression) -> str:
        """访问类型转换表达式"""
        if node.source_expression:
            source_str = node.source_expression.accept(self)
            return f"cast({source_str} as {node.target_type})"
        else:
            return f"cast(<unknown> as {node.target_type})"
    
    def visit_member_access_expression(self, node: MemberAccessExpression) -> str:
        """访问成员访问表达式"""
        if node.object_expression:
            obj_str = node.object_expression.accept(self)
            return f"{obj_str}.{node.member_name}"
        else:
            return node.member_name
    
    def visit_temporary_variable_expression(self, node: TemporaryVariableExpression) -> str:
        """访问临时变量表达式"""
        return node.temp_var_name
    
    def visit_property_access(self, node: PropertyAccessNode) -> str:
        """格式化属性访问表达式"""
        if node.target:
            target_str = node.target.accept(self)
            return f"{target_str}.{node.property_name}"
        else:
            return node.property_name
    
    def visit_unsupported_node(self, node: UnsupportedNode) -> str:
        """格式化不支持的节点"""
        self._add_line(f"// Unsupported node: {node.class_name} ({node.node_name})")
        return ""
    
    # ========================================================================
    # 语句节点访问方法
    # ========================================================================
    
    def visit_execution_block(self, node: ExecutionBlock) -> str:
        """访问执行块"""
        for statement in node.statements:
            statement.accept(self)
        return ""
    
    def visit_event_node(self, node: EventNode) -> str:
        """访问事件节点"""
        # 构建参数列表
        params_str = ""
        if node.parameters:
            param_parts = []
            for param_name, param_type in node.parameters:
                if self.strategy.should_show_type_info():
                    param_parts.append(f"{param_name}: {param_type}")
                else:
                    param_parts.append(param_name)
            params_str = f"({', '.join(param_parts)})"
        
        # 添加事件声明
        self._add_line(f"#### Event: {node.event_name}{params_str}")
        self._add_line("")
        
        # 处理事件体
        if node.body and node.body.statements:
            self.current_indent += 1
            self.visit_execution_block(node.body)
            self.current_indent -= 1
        
        return ""
    
    def visit_assignment_node(self, node: AssignmentNode) -> str:
        """访问赋值节点"""
        if node.value_expression:
            value_str = node.value_expression.accept(self)
            if node.is_local_variable:
                self._add_line(f"let {node.variable_name} = {value_str}")
            else:
                self._add_line(f"{node.variable_name} = {value_str}")
        else:
            self._add_line(f"{node.variable_name} = <unknown>")
        
        return ""
    
    def visit_function_call_node(self, node: FunctionCallNode) -> str:
        """访问函数调用节点"""
        # 构建参数列表
        args = []
        for param_name, arg_expr in node.arguments:
            if arg_expr:
                arg_value = arg_expr.accept(self)
                if param_name and param_name.lower() != "value":
                    args.append(f"{param_name}: {arg_value}")
                else:
                    args.append(arg_value)
        
        args_str = ", ".join(args)
        
        # 构建函数调用
        if node.target:
            target_str = node.target.accept(self)
            call_str = f"{target_str}.{node.function_name}({args_str})"
        else:
            call_str = f"{node.function_name}({args_str})"
        
        # 处理返回值赋值
        if node.return_assignments:
            for var_name, output_pin in node.return_assignments:
                self._add_line(f"{var_name} = {call_str}")
        else:
            self._add_line(call_str)
        
        return ""
    
    def visit_branch_node(self, node: BranchNode) -> str:
        """访问分支节点"""
        if node.condition:
            condition_str = node.condition.accept(self)
            self._add_line(f"if ({condition_str}):")
        else:
            self._add_line("if (<unknown condition>):")
        
        # 处理true分支
        if node.true_branch and node.true_branch.statements:
            self.current_indent += 1
            self.visit_execution_block(node.true_branch)
            self.current_indent -= 1
        else:
            self._add_line("// 空分支", 1)
        
        # 处理false分支
        if node.false_branch and node.false_branch.statements:
            self._add_line("else:")
            self.current_indent += 1
            self.visit_execution_block(node.false_branch)
            self.current_indent -= 1
        
        return ""
    
    def visit_loop_node(self, node: LoopNode) -> str:
        """访问循环节点"""
        if node.loop_type == LoopType.FOR_EACH:
            if node.collection_expression:
                collection_str = node.collection_expression.accept(self)
            else:
                collection_str = "<unknown collection>"
            
            # 构建循环变量（使用新的声明结构）
            loop_vars = []
            if node.item_declaration:
                loop_vars.append(node.item_declaration.variable_name)
            if node.index_declaration:
                loop_vars.append(node.index_declaration.variable_name)
            
            # 向后兼容：如果没有声明但有旧的变量名，使用旧的变量名
            if not loop_vars:
                if node.item_variable_name:
                    loop_vars.append(node.item_variable_name)
                if node.index_variable_name:
                    loop_vars.append(node.index_variable_name)
            
            if loop_vars:
                vars_str = ", ".join(loop_vars)
            else:
                vars_str = "item, index"
            
            self._add_line(f"for each ({vars_str}) in {collection_str}:")
        
        elif node.loop_type == LoopType.WHILE:
            if node.condition_expression:
                condition_str = node.condition_expression.accept(self)
                self._add_line(f"while ({condition_str}):")
            else:
                self._add_line("while (<unknown condition>):")
        
        # 处理循环体
        if node.body and node.body.statements:
            self.current_indent += 1
            self.visit_execution_block(node.body)
            self.current_indent -= 1
        else:
            self._add_line("// 空循环体", 1)
        
        return ""
    
    def visit_multi_branch_node(self, node: MultiBranchNode) -> str:
        """访问多分支节点"""
        if node.switch_expression:
            switch_str = node.switch_expression.accept(self)
            self._add_line(f"switch ({switch_str}):")
        else:
            self._add_line("switch (<unknown>):")
        
        # 处理各个分支
        for case_value, case_body in node.branches:
            self._add_line(f"case {case_value}:", 1)
            if case_body and case_body.statements:
                self.current_indent += 2
                self.visit_execution_block(case_body)
                self.current_indent -= 2
        
        # 处理默认分支
        if node.default_branch and node.default_branch.statements:
            self._add_line("default:", 1)
            self.current_indent += 2
            self.visit_execution_block(node.default_branch)
            self.current_indent -= 2
        
        return ""
    
    def visit_latent_action_node(self, node: LatentActionNode) -> str:
        """访问延迟动作节点"""
        if node.call:
            # 格式化异步函数调用
            call_str = node.call.accept(self)
            self._add_line(f"await {call_str}")
        else:
            self._add_line("await <unknown_latent_action>()")
        
        # 处理回调执行流
        for callback_name, callback_block in node.callback_exec_pins.items():
            if callback_block and callback_block.statements:
                # 显示回调参数（如果有的话）
                if hasattr(callback_block, 'declarations') and callback_block.declarations:
                    param_names = [decl.variable_name for decl in callback_block.declarations]
                    param_str = f"({', '.join(param_names)})"
                    self._add_line(f"// {callback_name}{param_str}:")
                else:
                    self._add_line(f"// {callback_name}:")
                
                self.current_indent += 1
                # 使用CallbackBlock的访问方法
                if hasattr(callback_block, 'accept'):
                    callback_block.accept(self)
                else:
                    # 向后兼容：直接访问statements
                    self.visit_execution_block(callback_block)
                self.current_indent -= 1
        
        return ""
    
    def visit_return_node(self, node: ReturnNode) -> str:
        """访问返回节点"""
        if node.return_values:
            return_parts = []
            for output_name, value_expr in node.return_values:
                if value_expr:
                    value_str = value_expr.accept(self)
                    return_parts.append(f"{output_name}: {value_str}")
                else:
                    return_parts.append(f"{output_name}: <unknown>")
            
            self._add_line(f"return ({', '.join(return_parts)})")
        else:
            self._add_line("return")
        
        return ""
    
    def visit_temporary_variable_declaration(self, node: TemporaryVariableDeclaration) -> str:
        """访问临时变量声明"""
        if node.value_expression:
            value_str = node.value_expression.accept(self)
            if self.strategy.should_show_type_info() and node.variable_type:
                self._add_line(f"let {node.variable_name}: {node.variable_type} = {value_str}")
            else:
                self._add_line(f"let {node.variable_name} = {value_str}")
        else:
            self._add_line(f"let {node.variable_name} = <unknown>")
        
        return ""
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> str:
        """访问变量声明节点"""
        if self.strategy.should_show_type_info():
            type_info = f": {node.variable_type}" if node.variable_type != "unknown" else ""
        else:
            type_info = ""
        
        if node.initial_value:
            value_str = node.initial_value.accept(self)
            self._add_line(f"declare {node.variable_name}{type_info} = {value_str}")
        else:
            self._add_line(f"declare {node.variable_name}{type_info}")
        
        return ""
    
    def visit_callback_block(self, node: CallbackBlock) -> str:
        """访问回调块节点"""
        # 首先处理变量声明
        for declaration in node.declarations:
            declaration.accept(self)
        
        # 然后处理语句
        for statement in node.statements:
            statement.accept(self)
        
        return ""


# ============================================================================
# Mermaid图格式化器（用于调试和可视化）
# ============================================================================

class MermaidFormatter(ASTVisitor):
    """
    将AST转换为Mermaid图定义的格式化器
    用于调试和验证AST结构的正确性
    """
    
    def __init__(self):
        self.node_counter = 0
        self.nodes = []
        self.edges = []
        self.node_map = {}  # AST节点 -> Mermaid节点ID
    
    def format_ast(self, ast_node: ASTNode) -> str:
        """
        格式化AST为Mermaid图定义
        
        :param ast_node: 要格式化的AST根节点
        :return: Mermaid图定义字符串
        """
        self.node_counter = 0
        self.nodes = []
        self.edges = []
        self.node_map = {}
        
        # 访问AST生成图定义
        root_id = self._visit_node(ast_node)
        
        # 构建Mermaid图定义
        lines = ["graph TD"]
        
        # 添加节点定义
        for node_def in self.nodes:
            lines.append(f"    {node_def}")
        
        # 添加边定义
        for edge_def in self.edges:
            lines.append(f"    {edge_def}")
        
        return '\n'.join(lines)
    
    def _visit_node(self, node: ASTNode) -> str:
        """访问节点并返回其Mermaid ID"""
        node_key = id(node)  # 使用对象ID作为键
        if node_key in self.node_map:
            return self.node_map[node_key]
        
        node_id = f"N{self.node_counter}"
        self.node_counter += 1
        self.node_map[node_key] = node_id
        
        # 让节点接受访问并获取标签
        label = node.accept(self)
        self.nodes.append(f'{node_id}["{label}"]')
        
        return node_id
    
    def _add_edge(self, from_node: ASTNode, to_node: ASTNode, label: str = ""):
        """添加边连接"""
        from_id = self._visit_node(from_node)
        to_id = self._visit_node(to_node)
        
        if label:
            self.edges.append(f"{from_id} -->|{label}| {to_id}")
        else:
            self.edges.append(f"{from_id} --> {to_id}")
    
    # ========================================================================
    # 实现访问方法（返回节点标签）
    # ========================================================================
    
    def visit_literal_expression(self, node: LiteralExpression) -> str:
        return f"Literal: {node.value}"
    
    def visit_variable_get_expression(self, node: VariableGetExpression) -> str:
        return f"Get: {node.variable_name}"
    
    def visit_function_call_expression(self, node: FunctionCallExpression) -> str:
        # 处理参数连接
        for param_name, arg_expr in node.arguments:
            if arg_expr:
                self._add_edge(node, arg_expr, param_name)
        
        # 处理目标连接
        if node.target:
            self._add_edge(node, node.target, "target")
        
        return f"Call: {node.function_name}"
    
    def visit_cast_expression(self, node: CastExpression) -> str:
        if node.source_expression:
            self._add_edge(node, node.source_expression, "source")
        return f"Cast: {node.target_type}"
    
    def visit_member_access_expression(self, node: MemberAccessExpression) -> str:
        if node.object_expression:
            self._add_edge(node, node.object_expression, "object")
        return f"Member: {node.member_name}"
    
    def visit_temporary_variable_expression(self, node: TemporaryVariableExpression) -> str:
        return f"TempVar: {node.temp_var_name}"
    
    def visit_property_access(self, node: PropertyAccessNode) -> str:
        if node.target:
            self._add_edge(node, node.target, "target")
        return f"Property: {node.property_name}"
    
    def visit_unsupported_node(self, node: UnsupportedNode) -> str:
        return f"Unsupported: {node.class_name}"
    
    def visit_execution_block(self, node: ExecutionBlock) -> str:
        for i, stmt in enumerate(node.statements):
            self._add_edge(node, stmt, f"stmt{i}")
        return "ExecutionBlock"
    
    def visit_event_node(self, node: EventNode) -> str:
        if node.body:
            self._add_edge(node, node.body, "body")
        return f"Event: {node.event_name}"
    
    def visit_assignment_node(self, node: AssignmentNode) -> str:
        if node.value_expression:
            self._add_edge(node, node.value_expression, "value")
        return f"Assign: {node.variable_name}"
    
    def visit_function_call_node(self, node: FunctionCallNode) -> str:
        # 处理参数连接
        for param_name, arg_expr in node.arguments:
            if arg_expr:
                self._add_edge(node, arg_expr, param_name)
        
        # 处理目标连接
        if node.target:
            self._add_edge(node, node.target, "target")
        
        return f"CallStmt: {node.function_name}"
    
    def visit_branch_node(self, node: BranchNode) -> str:
        if node.condition:
            self._add_edge(node, node.condition, "condition")
        if node.true_branch:
            self._add_edge(node, node.true_branch, "then")
        if node.false_branch:
            self._add_edge(node, node.false_branch, "else")
        return "Branch"
    
    def visit_loop_node(self, node: LoopNode) -> str:
        if node.collection_expression:
            self._add_edge(node, node.collection_expression, "collection")
        if node.condition_expression:
            self._add_edge(node, node.condition_expression, "condition")
        if node.body:
            self._add_edge(node, node.body, "body")
        return f"Loop: {node.loop_type.value}"
    
    def visit_multi_branch_node(self, node: MultiBranchNode) -> str:
        if node.switch_expression:
            self._add_edge(node, node.switch_expression, "switch")
        
        for i, (case_value, case_body) in enumerate(node.branches):
            if case_body:
                self._add_edge(node, case_body, f"case_{case_value}")
        
        if node.default_branch:
            self._add_edge(node, node.default_branch, "default")
        
        return "MultiBranch"
    
    def visit_latent_action_node(self, node: LatentActionNode) -> str:
        # 处理函数调用连接
        if node.call:
            self._add_edge(node, node.call, "call")
        
        # 处理回调执行流连接
        for callback_name, callback_body in node.callback_exec_pins.items():
            if callback_body:
                self._add_edge(node, callback_body, callback_name)
        
        call_name = node.call.function_name if node.call else "LatentAction"
        return f"LatentAction: {call_name}"
    
    def visit_return_node(self, node: ReturnNode) -> str:
        for output_name, value_expr in node.return_values:
            if value_expr:
                self._add_edge(node, value_expr, output_name)
        return "Return"
    
    def visit_temporary_variable_declaration(self, node: TemporaryVariableDeclaration) -> str:
        if node.value_expression:
            self._add_edge(node, node.value_expression, "value")
        return f"TempVarDecl: {node.variable_name}"
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> str:
        if node.initial_value:
            self._add_edge(node, node.initial_value, "initial_value")
        return f"VarDecl: {node.variable_name}"
    
    def visit_callback_block(self, node: CallbackBlock) -> str:
        # 处理变量声明连接
        for i, declaration in enumerate(node.declarations):
            self._add_edge(node, declaration, f"decl{i}")
        
        # 处理语句连接
        for i, stmt in enumerate(node.statements):
            self._add_edge(node, stmt, f"stmt{i}")
        
        return "CallbackBlock"


# ============================================================================
# 向后兼容的遗留格式化函数
# ============================================================================

def format_blueprint_to_markdown(blueprint: Blueprint) -> str:
    """
    向后兼容的蓝图格式化函数
    将一个BlueprintNode的列表格式化为完整的Markdown层级树
    """
    if not blueprint or not blueprint.root_nodes:
        return "没有找到可显示的节点。(No displayable nodes found.)"
    
    def _to_markdown_tree_recursive(node: BlueprintNode, indent_level: int = 0) -> str:
        # 移除 'FString' 等可能的前缀
        class_type_simple = node.class_type.split('.')[-1]
        
        # 根据缩进级别生成前缀
        indent_str = "  " * indent_level
        
        # 格式化当前节点
        result_string = f"{indent_str}- **{node.name}** (`{class_type_simple}`)\n"
        
        # 递归格式化所有子节点
        for child in node.children:
            result_string += _to_markdown_tree_recursive(child, indent_level + 1)
        
        return result_string
    
    final_output = f"#### {blueprint.name} Blueprint Hierarchy\n\n"
    for root in blueprint.root_nodes:
        final_output += _to_markdown_tree_recursive(root)
    
    return final_output


 