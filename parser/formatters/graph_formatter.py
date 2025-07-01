"""
Graph格式化器模块

该模块实现了EventGraph专用的Markdown格式化器，使用访问者模式将AST转换为结构化的伪代码输出
"""

from abc import ABC, abstractmethod
from typing import Any
from .base import Formatter, FormattingStrategy, ConciseStrategy
from parser.models import (
    ASTNode, Expression, Statement,
    LiteralExpression, VariableGetExpression, FunctionCallExpression,
    CastExpression, TemporaryVariableExpression,
    PropertyAccessNode, UnsupportedNode,
    ExecutionBlock, EventNode, AssignmentNode, FunctionCallNode,
    BranchNode, LoopNode, LoopType, LatentActionNode,
    TemporaryVariableDeclaration,
    # 新的语义节点
    VariableDeclaration, CallbackBlock,
    # 新增的AST节点
    GenericCallNode, FallbackNode, EventSubscriptionNode
)


# ============================================================================
# 访问者模式基类（专用于EventGraph AST）
# ============================================================================

class ASTVisitor(ABC):
    """
    AST访问者模式的抽象基类
    专门用于EventGraph AST的格式化，不再包含Widget相关方法
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
    def visit_latent_action_node(self, node: LatentActionNode) -> str:
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
    
    @abstractmethod
    def visit_event_reference_expression(self, node) -> str:
        pass

    @abstractmethod
    def visit_loop_variable_expression(self, node) -> str:
        pass
    
    @abstractmethod
    def visit_generic_call_node(self, node: GenericCallNode) -> str:
        pass
    
    @abstractmethod
    def visit_fallback_node(self, node: FallbackNode) -> str:
        pass
    
    @abstractmethod
    def visit_event_subscription_node(self, node: EventSubscriptionNode) -> str:
        pass


# ============================================================================
# EventGraph Markdown格式化器
# ============================================================================

class MarkdownEventGraphFormatter(ASTVisitor, Formatter):
    """
    EventGraph专用的Markdown格式化器
    使用访问者模式遍历AST并生成结构化的伪代码输出
    """
    
    def __init__(self, strategy: FormattingStrategy = None):
        self.strategy = strategy or ConciseStrategy()
        self.current_indent = 0
        self.output_lines = []
    
    def format(self, data: Any) -> str:
        """
        实现Formatter接口：格式化AST节点为Markdown字符串
        
        :param data: AST节点
        :return: 格式化后的Markdown字符串
        """
        if isinstance(data, ASTNode):
            return self.format_ast(data)
        else:
            raise ValueError(f"MarkdownEventGraphFormatter只能格式化ASTNode，收到: {type(data)}")
    
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

    def _format_value(self, value: Any) -> str:
        """
        通用值格式化辅助函数
        - 格式化None, bool
        - 格式化UE资源路径为简洁名称
        - 格式化普通字符串并加引号
        """
        if value is None:
            return "None"
        if isinstance(value, bool):
            return str(value).lower()
        if not isinstance(value, str):
            return str(value)

        # 检查是否是UE资源路径
        # e.g., /Game/BPs/UI/WBP_MyWidget.WBP_MyWidget_C
        if value.startswith('/Game/') and '.' in value and value.endswith('_C'):
            # 提取文件名部分并移除_C后缀
            base_name = value.split('.')[-1]
            return base_name.removesuffix('_C')

        # 否则视为普通字符串
        return f'"{value}"'

    # ========================================================================
    # 表达式节点访问方法
    # ========================================================================
    
    def visit_literal_expression(self, node: LiteralExpression) -> str:
        """访问字面量表达式"""
        return self._format_value(node.value)
    
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
        if hasattr(self, '_blueprint_title_added') and not self._blueprint_title_added:
            self._add_line(f"#### Event: {node.event_name}{params_str}")
            self._add_line("")
            self._blueprint_title_added = True
        else:
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
        else:
            value_str = "<unknown>"
        
        # 处理新的target字段或向后兼容的variable_name
        if hasattr(node, 'target') and node.target:
            target_str = node.target.accept(self)
        else:
            target_str = node.variable_name
        
        # 使用新的operator字段，如果没有则默认使用"="
        operator = getattr(node, 'operator', '=')
        
        if node.is_local_variable:
            self._add_line(f"let {target_str} = {value_str}")
        else:
            self._add_line(f"{target_str} {operator} {value_str}")
        
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
    
    def visit_latent_action_node(self, node: LatentActionNode) -> str:
        """访问延迟动作节点"""
        if node.call:
            # 直接构建函数调用字符串，而不是通过 accept 方法（避免重复输出）
            call_str = self._format_function_call_inline(node.call)
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
    
    def _format_function_call_inline(self, node: FunctionCallNode) -> str:
        """内联格式化函数调用（不添加到输出行）"""
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
    
    def visit_temporary_variable_declaration(self, node: TemporaryVariableDeclaration) -> str:
        """访问临时变量声明"""
        if node.value_expression:
            value_str = node.value_expression.accept(self)
            if self.strategy.should_show_type_info() and node.variable_type:
                self._add_line(f"declare {node.variable_name}: {node.variable_type} = {value_str}")
            else:
                self._add_line(f"declare {node.variable_name} = {value_str}")
        else:
            type_info = f": {node.variable_type}" if self.strategy.should_show_type_info() and node.variable_type else ""
            self._add_line(f"declare {node.variable_name}{type_info}")
        
        return ""
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> str:
        """访问变量声明 - 移除declare关键字以简化输出"""
        if self.strategy.should_show_type_info():
            type_info = f": {node.variable_type}" if node.variable_type and node.variable_type != "unknown" else ""
        else:
            type_info = ""
        
        if node.initial_value:
            initial_value_str = node.initial_value.accept(self)
            # 移除declare关键字，直接使用赋值格式
            self._add_line(f"{node.variable_name}{type_info} = {initial_value_str}")
        else:
            # 对于没有初始值的声明，保留declare关键字以明确这是声明
            self._add_line(f"declare {node.variable_name}{type_info}")
        
        return ""
    
    def visit_callback_block(self, node: CallbackBlock) -> str:
        """访问回调块"""
        # 首先处理变量声明
        for declaration in node.declarations:
            declaration.accept(self)
        
        # 然后处理语句
        for statement in node.statements:
            statement.accept(self)
        
        return ""
    
    def visit_event_reference_expression(self, node) -> str:
        """访问事件引用表达式"""
        return node.event_name if hasattr(node, 'event_name') else "UnknownEvent"

    def visit_loop_variable_expression(self, node) -> str:
        """访问循环变量表达式"""
        return node.variable_name
    
    def visit_generic_call_node(self, node: GenericCallNode) -> str:
        """格式化通用可调用节点"""
        # 构建函数调用格式：TargetObject.Function(param: Value)
        target_str = ""
        if node.target:
            target_str = node.target.accept(self) + "."
        
        # 构建参数列表
        args_str = ""
        if node.arguments:
            arg_parts = []
            for param_name, param_expr in node.arguments:
                param_value = param_expr.accept(self) if param_expr else "null"
                arg_parts.append(f"{param_name}: {param_value}")
            args_str = ", ".join(arg_parts)
        
        function_call = f"{target_str}{node.function_name}({args_str})"
        self._add_line(function_call)
        return ""
    
    def visit_fallback_node(self, node: FallbackNode) -> str:
        """格式化备用节点为信息丰富的注释"""
        # 构建注释格式：// Fallback: NodeClass(key_property=value)
        comment_parts = [f"// Fallback: {node.class_name}"]
        
        if node.node_name and node.node_name != node.class_name:
            comment_parts.append(f" ({node.node_name})")
        
        # 添加关键属性信息
        if node.properties:
            prop_parts = []
            for key, value in node.properties.items():
                prop_parts.append(f"{key}={value}")
            if prop_parts:
                comment_parts.append(f" [{', '.join(prop_parts)}]")
        
        comment_line = "".join(comment_parts)
        self._add_line(comment_line)
        return ""
    
    def visit_event_subscription_node(self, node: EventSubscriptionNode) -> str:
        """访问事件订阅节点，格式化为 Source.Event += Handler 的形式"""
        # 构建事件源对象字符串
        if node.source_object:
            source_str = node.source_object.accept(self)
        else:
            source_str = "<unknown>"
        
        # 构建事件处理器字符串
        if node.handler:
            handler_str = node.handler.accept(self)
            # 处理特殊情况：如果处理器是 PropertyAccessNode 且属性名为 OutputDelegate，
            # 则只使用目标对象名称（即事件名称）
            if hasattr(node.handler, 'property_name') and node.handler.property_name == "OutputDelegate":
                if hasattr(node.handler, 'target'):
                    handler_str = node.handler.target.accept(self)
        else:
            handler_str = "<unknown>"
        
        # 格式化事件订阅：Source.Event += Handler
        event_subscription = f"{source_str}.{node.event_name} += {handler_str}"
        self._add_line(event_subscription)
        
        return "" 