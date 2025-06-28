"""
通用构建器工具函数
包含各种Builder类之间共享的通用逻辑
"""

from typing import List
from ..models import RawObject


def collect_all_raw_objects(raw_objects: List[RawObject]) -> List[RawObject]:
    """
    递归收集所有对象（包括嵌套的子对象）
    
    该函数被WidgetBuilder和GraphBuilder共同使用, 用于扁平化RawObject树结构
    
    :param raw_objects: 根级别的RawObject列表
    :return: 包含所有对象（根对象和所有子对象）的扁平化列表
    """
    all_objects = []
    
    def collect_recursive(objects):
        for obj in objects:
            all_objects.append(obj)
            if obj.children:
                collect_recursive(obj.children)
    
    collect_recursive(raw_objects)
    return all_objects 