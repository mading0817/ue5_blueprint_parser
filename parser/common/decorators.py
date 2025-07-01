"""
装饰器工具模块
包含用于节点处理器注册等功能的装饰器
"""

from typing import Dict, Callable, List, Any


class ProcessorRegistry:
    """节点处理器注册表"""
    
    def __init__(self):
        self._processors: Dict[str, Callable] = {}
    
    def register(self, *node_types: str):
        """
        注册节点处理器的装饰器
        增强版本：自动处理名称变体，减少样板代码
        
        :param node_types: 要处理的节点类型列表
        :return: 装饰器函数
        """
        def decorator(processor_func: Callable):
            # 为每个节点类型注册处理器
            for node_type in node_types:
                self._processors[node_type] = processor_func
                
                # 智能名称变体生成
                if node_type.startswith("/Script/"):
                    # 提取简短名称，如 "/Script/BlueprintGraph.K2Node_Event" -> "K2Node_Event"
                    short_name = node_type.split('.')[-1]
                    if short_name != node_type:  # 避免重复注册
                        self._processors[short_name] = processor_func
                
                elif node_type.startswith("K2Node_"):
                    # 为 K2Node_ 开头的节点自动生成完整路径变体
                    # 根据节点类型推断正确的前缀
                    full_path = self._generate_full_path(node_type)
                    if full_path and full_path != node_type:
                        self._processors[full_path] = processor_func
            
            return processor_func
        return decorator
    
    def _generate_full_path(self, short_name: str) -> str:
        """
        为简短节点名称生成完整路径
        根据节点类型智能推断正确的命名空间前缀
        
        :param short_name: 简短名称，如 "K2Node_Event"
        :return: 完整路径，如 "/Script/BlueprintGraph.K2Node_Event"
        """
        # 特殊节点类型的命名空间映射
        special_namespaces = {
            "K2Node_CreateWidget": "/Script/UMGEditor",
            "K2Node_LatentAbilityCall": "/Script/GameplayAbilitiesEditor",
        }
        
        # 检查是否有特殊的命名空间映射
        if short_name in special_namespaces:
            return f"{special_namespaces[short_name]}.{short_name}"
        
        # 默认使用 BlueprintGraph 命名空间
        return f"/Script/BlueprintGraph.{short_name}"
    
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