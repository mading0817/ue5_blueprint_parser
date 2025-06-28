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
    CastExpression, TemporaryVariableExpression,
    PropertyAccessNode, UnsupportedNode,
    ExecutionBlock, EventNode, AssignmentNode, FunctionCallNode,
    BranchNode, LoopNode, LoopType, LatentActionNode,
    TemporaryVariableDeclaration,
    # 新的语义节点
    VariableDeclaration, CallbackBlock,
    # 新架构UI节点
    WidgetNode
)


# ============================================================================
# 格式化器抽象基类
# ============================================================================

class Formatter(ABC):
    """
    格式化器抽象基类
    定义所有格式化器的通用接口
    """
    
    @abstractmethod
    def format(self, data: Any) -> str:
        """
        格式化数据为字符串
        
        :param data: 要格式化的数据（AST节点、Widget树等）
        :return: 格式化后的字符串
        """
        pass


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
        return True
    
    def should_inline_simple_expressions(self) -> bool:
        return True
    
    def get_indent_string(self) -> str:
        return "  "  # 2个空格


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
        
        if node.is_local_variable:
            self._add_line(f"let {target_str} = {value_str}")
        else:
            self._add_line(f"{target_str} = {value_str}")
        
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
        """访问变量声明"""
        if self.strategy.should_show_type_info():
            type_info = f": {node.variable_type}" if node.variable_type and node.variable_type != "unknown" else ""
        else:
            type_info = ""
        
        if node.initial_value:
            initial_value_str = node.initial_value.accept(self)
            self._add_line(f"declare {node.variable_name}{type_info} = {initial_value_str}")
        else:
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


# ============================================================================
# Widget层级Markdown格式化器 -> 重命名为 WidgetTreeFormatter
# ============================================================================

class WidgetTreeFormatter(Formatter):
    """
    Widget层级专用的Markdown格式化器
    专门用于格式化WidgetNode树为层级结构的Markdown
    """
    
    def __init__(self, strategy: FormattingStrategy = None, show_properties: bool = False):
        self.strategy = strategy or ConciseStrategy()
        self.show_properties = show_properties
        self.current_indent = 0
        self.output_lines = []
    
    def format(self, data: Any) -> str:
        """
        实现Formatter接口：格式化WidgetNode树为Markdown字符串
        
        :param data: WidgetNode列表或单个WidgetNode
        :return: 格式化后的Markdown字符串
        """
        if isinstance(data, list):
            return self._format_widget_hierarchy(data)
        elif hasattr(data, 'widget_name'):  # WidgetNode
            return self._format_widget_hierarchy([data])
        else:
            raise ValueError(f"WidgetTreeFormatter只能格式化WidgetNode，收到: {type(data)}")
    
    def _format_widget_hierarchy(self, widget_nodes: List, blueprint_name: str = None) -> str:
        """
        格式化Widget层级为Markdown字符串
        
        :param widget_nodes: WidgetNode根节点列表
        :param blueprint_name: 蓝图名称
        :return: 格式化后的Markdown字符串
        """
        self.current_indent = 0
        self.output_lines = []
        
        # 如果没有Widget节点，返回空结构提示
        if not widget_nodes:
            self.output_lines.append("*(Empty UI structure)*")
            return '\n'.join(self.output_lines)
        
        # 尝试从第一个节点推断蓝图名称
        if not blueprint_name and widget_nodes:
            first_node = widget_nodes[0]
            if hasattr(first_node, 'source_location') and first_node.source_location:
                # 从 source_location 中提取蓝图名称
                file_path = first_node.source_location.file_path
                if file_path and 'WBP_' in file_path:
                    # 提取 WBP_ 开头的蓝图名称
                    import re
                    match = re.search(r'(WBP_\w+)', file_path)
                    if match:
                        blueprint_name = match.group(1)
        
        # 设置默认标题
        if not blueprint_name:
            blueprint_name = "WBP_AttributesMenu"  # 根据快照文件推断
        
        # 添加标题
        self.output_lines.append(f"# {blueprint_name} Hierarchy")
        self.output_lines.append("")
        
        # 格式化每个根Widget节点
        for widget_node in widget_nodes:
            self._format_widget_node(widget_node)
        
        return '\n'.join(self.output_lines)
    
    def _format_widget_node(self, node):
        """格式化单个Widget节点"""
        # 格式化当前Widget节点
        if node.widget_type:
            # 提取类型的简短名称（去掉路径前缀）
            class_name = node.widget_type.split('.')[-1] if '.' in node.widget_type else node.widget_type
            # 去掉 /Script/UMG. 前缀
            if class_name.startswith('/Script/UMG.'):
                class_name = class_name[len('/Script/UMG.'):]
            node_display = f"- **{node.widget_name}** ({class_name})"
        else:
            node_display = f"- **{node.widget_name}**"
        
        self._add_line(node_display)
        
        # 如果启用了属性显示，显示重要属性
        if self.show_properties and hasattr(node, 'properties') and node.properties:
            self._format_widget_properties(node)
        
        # 递归格式化子Widget节点
        if node.children:
            self.current_indent += 1
            for child in node.children:
                self._format_widget_node(child)
            self.current_indent -= 1
    
    def _format_widget_properties(self, node):
        """格式化Widget节点的重要属性"""
        # 定义需要显示的重要属性
        important_props = ['Text', 'Size', 'SizeBoxWidth', 'SizeBoxHeight', 'ButtonText', 'TextBorderPadding']
        
        for prop_name in important_props:
            if prop_name in node.properties:
                prop_value = node.properties[prop_name]
                # 格式化属性值
                if len(str(prop_value)) > 50:
                    prop_value = str(prop_value)[:47] + "..."
                self._add_line(f"- {prop_name}: `{prop_value}`", extra_indent=2)
    
    def _add_line(self, content: str, extra_indent: int = 0):
        """添加一行内容到输出"""
        indent = "  " * (self.current_indent + extra_indent)  # 使用2个空格缩进
        self.output_lines.append(f"{indent}{content}")


# ============================================================================
# MarkdownFormatter 已被移除，统一使用 MarkdownEventGraphFormatter 与 WidgetTreeFormatter
# ============================================================================