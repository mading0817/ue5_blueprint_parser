"""
Widget树格式化器模块

该模块实现了用于格式化WidgetNode树的格式化器，支持递归层级展示和属性清理
"""

import re
from typing import List, Any, Tuple, Callable, Pattern
from .base import Formatter, FormattingStrategy, ConciseStrategy
from parser.models import WidgetNode


# ============================================================================
# 属性清理策略
# ============================================================================

# 定义更健壮的正则表达式模式
NSLOCTEXT_RE = re.compile(r'NSLOCTEXT\s*\(\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)', re.DOTALL)
LOCTEXT_RE = re.compile(r'LOCTEXT\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)', re.DOTALL)

# 清理策略表：(pattern, handler_function)
CLEANUP_STRATEGIES: List[Tuple[Pattern, Callable]] = [
    (NSLOCTEXT_RE, lambda m: m.group(1)),
    (LOCTEXT_RE, lambda m: m.group(1)),
    # 未来可在这里添加更多策略
]


# ============================================================================
# Widget树格式化器
# ============================================================================

class WidgetTreeFormatter(Formatter):
    """
    Widget树格式化器
    使用递归遍历生成带层级缩进的Widget树结构
    """
    
    def __init__(self, strategy: FormattingStrategy = None, show_properties: bool = False):
        """
        初始化Widget树格式化器
        
        :param strategy: 格式化策略，默认使用ConciseStrategy
        :param show_properties: 是否显示Widget属性
        """
        self.strategy = strategy or ConciseStrategy()
        self.show_properties = show_properties
        self.output_lines = []
    
    def format(self, data: Any) -> str:
        """
        实现Formatter接口：格式化WidgetNode树为Markdown字符串
        
        :param data: WidgetNode列表或单个WidgetNode
        :return: 格式化后的Markdown字符串
        """
        # 重置输出缓冲区
        self.output_lines = []
        
        # 处理输入数据
        if isinstance(data, list):
            widget_nodes = data
        elif isinstance(data, WidgetNode):
            widget_nodes = [data]
        else:
            raise ValueError(f"WidgetTreeFormatter只能格式化WidgetNode或WidgetNode列表，收到: {type(data)}")
        
        # 生成格式化输出
        return self._format_widget_hierarchy(widget_nodes)
    
    def _format_widget_hierarchy(self, widget_nodes: List[WidgetNode], blueprint_name: str = None) -> str:
        """
        格式化Widget层级结构
        
        :param widget_nodes: Widget节点列表
        :param blueprint_name: 蓝图名称（可选）
        :return: 格式化后的Markdown字符串
        """
        # 添加标题
        if blueprint_name:
            self._add_line(f"# {blueprint_name} Hierarchy")
        elif widget_nodes:
            # 尝试从第一个节点推断蓝图名称
            first_node = widget_nodes[0]
            if hasattr(first_node, 'source_location') and first_node.source_location:
                blueprint_name = getattr(first_node.source_location, 'file_path', 'Widget Blueprint')
                if blueprint_name and blueprint_name != 'Blueprint':
                    self._add_line(f"# {blueprint_name} Hierarchy")
                else:
                    self._add_line("# Widget Hierarchy")
            else:
                self._add_line("# Widget Hierarchy")
        else:
            self._add_line("# Widget Hierarchy")
        
        self._add_line("")  # 空行分隔
        
        # 递归格式化所有根节点
        for root_node in widget_nodes:
            self._format_node_recursive(root_node, 0)
        
        return '\n'.join(self.output_lines)
    
    def _format_node_recursive(self, node: WidgetNode, depth: int):
        """
        递归格式化Widget节点
        
        :param node: 当前Widget节点
        :param depth: 当前缩进深度
        """
        # 生成缩进
        indent = self.strategy.get_indent_string() * depth
        
        # 格式化节点基本信息
        node_line = f"{indent}- **{node.widget_name}** ({node.widget_type})"
        self._add_line(node_line)
        
        # 如果需要显示属性，则格式化属性信息
        if self.show_properties:
            self._format_node_properties(node, depth)
        
        # 递归处理所有子节点
        for child in node.children:
            self._format_node_recursive(child, depth + 1)
    
    def _format_node_properties(self, node: WidgetNode, depth: int):
        """
        格式化节点属性
        
        :param node: Widget节点
        :param depth: 当前缩进深度
        """
        # 定义需要显示的属性
        properties_to_show = {
            "Text": node.properties.get("Text"),
            "Size": node.properties.get("Size"),
            "SizeBoxWidth": node.properties.get("SizeBoxWidth"),
            "SizeBoxHeight": node.properties.get("SizeBoxHeight"),
            "ButtonText": node.properties.get("ButtonText"),
            "TextBorderPadding": node.properties.get("TextBorderPadding"),
        }
        
        # 过滤掉空值并格式化
        formatted_props = []
        for key, value in properties_to_show.items():
            if value is not None and str(value).strip():
                cleaned_value = self._clean_property_value(value)
                if cleaned_value and cleaned_value.strip():  # 只显示有意义的属性值
                    prop_indent = self.strategy.get_indent_string() * (depth + 1)
                    formatted_props.append(f"{prop_indent}- {key}: `{cleaned_value}`")
        
        # 添加属性到输出
        for prop in formatted_props:
            self._add_line(prop)
    
    def _clean_property_value(self, value: Any) -> str:
        """
        清理属性值，处理特殊格式如NSLOCTEXT
        
        :param value: 原始属性值
        :return: 清理后的属性值
        """
        if not isinstance(value, str):
            return str(value)
        
        # 应用所有清理策略
        for pattern, handler in CLEANUP_STRATEGIES:
            match = pattern.search(value)
            if match:
                try:
                    cleaned = handler(match)
                    # 如果清理后的值不为空且有意义，则返回
                    if cleaned and cleaned.strip():
                        return cleaned
                except Exception:
                    # 如果处理失败，继续尝试下一个策略
                    continue
        
        # 如果所有策略都未匹配或处理失败，检查是否是无用的噪音
        # 如果是明显的内部格式（如NSLOCTEXT但未被正则匹配），则返回占位符
        if 'NSLOCTEXT' in value or 'LOCTEXT' in value:
            return "[Localized Text]"
        
        return value
    
    def _add_line(self, content: str):
        """
        添加一行内容到输出缓冲区
        
        :param content: 要添加的内容
        """
        self.output_lines.append(content) 