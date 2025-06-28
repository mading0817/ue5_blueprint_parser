"""
图操作相关的工具函数
包含与GraphNode、GraphPin操作相关的无状态辅助函数
"""

from typing import Optional, Any
from ..models import GraphNode, GraphPin, SourceLocation


def find_pin(node: GraphNode, pin_name: str, direction: str) -> Optional[GraphPin]:
    """
    在节点中查找指定名称和方向的引脚
    
    :param node: 要搜索的图节点
    :param pin_name: 引脚名称
    :param direction: 引脚方向 ("input" 或 "output")
    :return: 找到的引脚，如果没找到则返回None
    """
    return next((pin for pin in node.pins 
                if pin.pin_name == pin_name and pin.direction == direction), None)


def create_source_location(node: GraphNode) -> SourceLocation:
    """
    创建源位置信息
    
    :param node: 图节点
    :return: 源位置对象
    """
    return SourceLocation(node_guid=node.node_guid, node_name=node.node_name)


def get_pin_default_value(pin: GraphPin) -> Any:
    """
    获取引脚的默认值
    
    :param pin: 图引脚
    :return: 引脚的默认值，如果没有则返回None
    """
    return pin.default_value if pin and pin.default_value is not None else None


def extract_pin_type(pin: GraphPin) -> str:
    """
    从引脚中提取 UE 类型信息
    用于为 AST 节点附加类型信息
    
    :param pin: 图引脚
    :return: 引脚的类型字符串
    """
    if not pin:
        return "unknown"
    
    # 基本类型映射
    type_mapping = {
        "exec": "exec",
        "bool": "bool", 
        "int": "int",
        "float": "float",
        "string": "string",
        "object": "object",
        "struct": "struct",
        "delegate": "delegate"
    }
    
    base_type = type_mapping.get(pin.pin_type, pin.pin_type)
    
    # 对于结构体类型，尝试从 PinSubCategoryObject 中提取更具体的类型
    # 这需要从原始引脚数据中解析，目前返回基本类型
    return base_type 


# ================================================================
# 通用函数: 解析UE对象路径 -> 提取对象名称
# ================================================================

def parse_object_path(path_string: str) -> Optional[str]:
    """
    从UE对象路径字符串中解析对象名称。

    示例:
        "/Script/UMG.Border'Border_0'"  ->  "Border_0"
        "/Game/BPs/UI/WBP_Foo.WBP_Foo_C'WidgetTree.CanvasPanel_0'" -> "CanvasPanel_0"

    :param path_string: UE对象路径字符串
    :return: 提取的对象名称，如果解析失败则返回None
    """
    if not path_string:
        return None

    # 使用正则提取单引号内的内容，然后切分出末尾的对象名
    import re

    match = re.search(r"'([^']*)'", path_string)
    if not match:
        return None

    full_path = match.group(1)

    # 对路径进行分割以提取最后的对象名（处理形如 A.B 或 A:B 的情况）
    name = full_path.rsplit('.', 1)[-1].rsplit(':', 1)[-1]
    return name 