"""
装饰器工具模块
包含用于节点处理器注册等功能的装饰器
"""

from typing import Dict, Callable, List, Any
from functools import wraps


class ProcessorRegistry:
    """节点处理器注册表"""
    
    def __init__(self):
        self._processors: Dict[str, Callable] = {}
    
    def register(self, *node_types: str):
        """
        注册节点处理器的装饰器
        
        :param node_types: 要处理的节点类型列表
        :return: 装饰器函数
        """
        def decorator(processor_func: Callable):
            # 为每个节点类型注册处理器
            for node_type in node_types:
                self._processors[node_type] = processor_func
                
                # 同时注册简短名称（如果是完整路径）
                if node_type.startswith("/Script/"):
                    # 提取简短名称，如 "/Script/BlueprintGraph.K2Node_Event" -> "K2Node_Event"
                    short_name = node_type.split('.')[-1]
                    if short_name != node_type:  # 避免重复注册
                        self._processors[short_name] = processor_func
            
            return processor_func
        return decorator
    
    def get_processor(self, node_type: str) -> Callable:
        """获取节点类型对应的处理器"""
        return self._processors.get(node_type)
    
    def get_all_processors(self) -> Dict[str, Callable]:
        """获取所有注册的处理器"""
        return self._processors.copy()


# 全局注册表实例
node_processor_registry = ProcessorRegistry()

# 导出装饰器函数
register_processor = node_processor_registry.register 