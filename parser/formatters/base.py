"""
格式化器基础模块

该模块定义了格式化器的基础接口和策略模式实现
"""

from abc import ABC, abstractmethod
from typing import Any


# ============================================================================
# 格式化器基础接口
# ============================================================================

class Formatter(ABC):
    """
    格式化器基础接口
    所有具体的格式化器都应该继承此接口
    """
    
    @abstractmethod
    def format(self, data: Any) -> str:
        """
        格式化数据为字符串
        
        :param data: 要格式化的数据
        :return: 格式化后的字符串
        """
        pass


# ============================================================================
# 格式化策略模式
# ============================================================================

class FormattingStrategy(ABC):
    """
    格式化策略基类
    定义格式化的通用行为接口
    """
    
    @abstractmethod
    def get_indent_string(self) -> str:
        """
        获取缩进字符串
        
        :return: 缩进字符串
        """
        pass
    
    @abstractmethod
    def should_show_details(self) -> bool:
        """
        是否显示详细信息
        
        :return: True表示显示详细信息，False表示简洁模式
        """
        pass
    
    @abstractmethod
    def should_show_type_info(self) -> bool:
        """
        是否显示类型信息
        
        :return: True表示显示类型信息，False表示不显示
        """
        pass


class ConciseStrategy(FormattingStrategy):
    """
    简洁格式化策略
    使用较少的缩进和简洁的输出格式
    """
    
    def get_indent_string(self) -> str:
        """返回简洁的缩进字符串"""
        return "  "  # 2个空格
    
    def should_show_details(self) -> bool:
        """简洁模式不显示详细信息"""
        return False
    
    def should_show_type_info(self) -> bool:
        """简洁模式不显示类型信息"""
        return False


class VerboseStrategy(FormattingStrategy):
    """
    详细格式化策略
    使用更多的缩进和详细的输出格式
    """
    
    def get_indent_string(self) -> str:
        """返回详细的缩进字符串"""
        return "    "  # 4个空格
    
    def should_show_details(self) -> bool:
        """详细模式显示详细信息"""
        return True
    
    def should_show_type_info(self) -> bool:
        """详细模式显示类型信息"""
        return True 