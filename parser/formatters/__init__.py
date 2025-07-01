"""
格式化器包

该包包含了用于将解析后的数据结构转换为不同输出格式的格式化器
"""

# 导入基础类
from .base import Formatter, FormattingStrategy, VerboseStrategy, ConciseStrategy

# 导入具体的格式化器
from .graph_formatter import MarkdownEventGraphFormatter, ASTVisitor
from .widget_formatter import WidgetTreeFormatter

# 公共接口
__all__ = [
    # 基础类
    'Formatter',
    'FormattingStrategy', 
    'VerboseStrategy',
    'ConciseStrategy',
    
    # Graph格式化器
    'MarkdownEventGraphFormatter',
    'ASTVisitor',
    
    # Widget格式化器
    'WidgetTreeFormatter',
] 