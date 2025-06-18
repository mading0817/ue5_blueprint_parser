import re
from collections import deque
from typing import List, Dict

from .models import BlueprintNode


def parse_object_path(path_string: str) -> str | None:
    """从UE对象路径中提取对象的名称。"""
    if not path_string:
        return None
    match = re.search(r"'(.*?)'", path_string)
    if match:
        full_path = match.group(1)
        # 同时处理冒号和点作为分隔符的情况
        if ':' in full_path:
            return full_path.split(':')[-1]
        return full_path.split('.')[-1]
    return None


def build_hierarchy(objects_map: Dict[str, BlueprintNode]):
    """根据解析出的对象信息构建层级树。"""
    for obj in objects_map.values():
        if 'Slot' in obj.class_type:
            parent_path = obj.properties.get('Parent')
            content_path = obj.properties.get('Content')
            if parent_path and content_path:
                parent_name = parse_object_path(parent_path)
                content_name = parse_object_path(content_path)
                if parent_name and content_name and parent_name in objects_map and content_name in objects_map:
                    parent_obj = objects_map[parent_name]
                    child_obj = objects_map[content_name]
                    if child_obj not in parent_obj.children:
                        parent_obj.children.append(child_obj)
                    child_obj.has_parent = True


def parse_ue_blueprint_to_nodes(blueprint_text: str) -> List[BlueprintNode]:
    """
    主解析函数，将UE蓝图文本解析为BlueprintNode对象的列表。
    如果解析失败或输入为空，返回一个空列表。
    """
    if not blueprint_text or not blueprint_text.strip():
        return []

    objects_map: Dict[str, BlueprintNode] = {}
    object_stack = deque()

    for line in blueprint_text.strip().split('\\n'):
        line = line.strip()
        begin_match = re.search(r'Begin Object(?: Class=(?P<class>[^\\s"]+))? Name="(?P<name>[^"]+)"', line)

        if begin_match:
            obj_name = begin_match.group('name')
            obj_class = begin_match.group('class')

            if obj_name in objects_map:
                object_stack.append(objects_map[obj_name])
            elif obj_class:
                new_obj = BlueprintNode(name=obj_name, class_type=obj_class)
                objects_map[obj_name] = new_obj
                object_stack.append(new_obj)
            continue

        if line.startswith('End Object'):
            if object_stack:
                object_stack.pop()
            continue

        if object_stack:
            current_obj = object_stack[-1]
            prop_match = re.match(r'([\w\(\)]+)=(.+)', line)
            if prop_match:
                key, value = prop_match.groups()
                current_obj.properties[key] = value

    build_hierarchy(objects_map)

    # 确定根节点: 没有父级，且不是辅助性的Slot或WidgetSlotPair。
    root_nodes = [
        obj for obj in objects_map.values()
        if not obj.has_parent and 'Slot' not in obj.class_type and 'WidgetSlotPair' not in obj.class_type
    ]

    return root_nodes
