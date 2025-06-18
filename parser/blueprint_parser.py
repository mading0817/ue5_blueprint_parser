import re
from collections import deque
from typing import List, Dict, Optional, Tuple

from .models import BlueprintNode, Blueprint


def parse_object_path(path_string: str) -> Optional[str]:
    """
    从UE对象路径字符串中更稳健地解析对象名称。
    示例: "/Script/UMG.Border'Border_0'" -> "Border_0"
    示例: "/Game/BPs/UI/WBP_Foo.WBP_Foo_C'WidgetTree.CanvasPanel_0'" -> "CanvasPanel_0"
    """
    if not path_string:
        return None
    match = re.search(r"'([^']*)'", path_string)
    if match:
        full_path = match.group(1)
        name = full_path.rsplit('.', 1)[-1].rsplit(':', 1)[-1]
        return name
    return None


def find_object_by_name(name: str, objects: List[BlueprintNode]) -> Optional[BlueprintNode]:
    """从后往前搜索列表，找到第一个匹配名称的对象。"""
    for obj in reversed(objects):
        if obj.name == name:
            return obj
    return None


def build_hierarchy(objects: List[BlueprintNode]):
    """根据解析的对象属性构建节点层级。"""
    for obj in objects:
        if obj.class_type and 'Slot' in obj.class_type:
            parent_path = obj.properties.get('Parent')
            content_path = obj.properties.get('Content')

            if parent_path and content_path:
                parent_name = parse_object_path(parent_path)
                content_name = parse_object_path(content_path)

                parent_obj = find_object_by_name(parent_name, objects)
                child_obj = find_object_by_name(content_name, objects)

                if parent_obj and child_obj:
                    if child_obj not in parent_obj.children:
                        parent_obj.children.append(child_obj)
                    child_obj.has_parent = True


def parse_ue_blueprint(blueprint_text: str) -> Optional[Blueprint]:
    """
    主解析函数，将UE蓝图文本转换为Blueprint对象的列表。
    如果解析失败或输入为空，则返回空列表。
    """
    if not blueprint_text or not blueprint_text.strip():
        return None

    # 提取蓝图名称
    blueprint_name = "UnknownBlueprint"
    name_match = re.search(r"/Game/.*(?:/|')(?P<asset_name>[^/.]+)\.", blueprint_text)
    if name_match:
        blueprint_name = name_match.group("asset_name")

    objects: List[BlueprintNode] = []
    object_stack = deque()

    # 用于匹配对象块开始的正则表达式。
    # 它捕获类（可选）和名称。
    begin_obj_re = re.compile(r'Begin Object(?: Class=(?P<class>[\w./_]+))? Name="(?P<name>[\w_]+)"')
    # 用于匹配属性行的正则表达式。
    prop_re = re.compile(r'([\w_()]+)=(.*)')

    for line in blueprint_text.strip().splitlines():
        line = line.strip()
        begin_match = begin_obj_re.search(line)

        if begin_match:
            obj_name = begin_match.group('name')
            obj_class = begin_match.group('class')

            if obj_class:
                # 定义总是创建一个新对象
                node = BlueprintNode(name=obj_name, class_type=obj_class)
                objects.append(node)
                object_stack.append(node)
            else:
                # 引用则查找最近定义的对象
                node = find_object_by_name(obj_name, objects)
                if node:
                    object_stack.append(node)
            continue

        if line.startswith('End Object'):
            if object_stack:
                object_stack.pop()
            continue

        if object_stack:
            current_obj = object_stack[-1]
            prop_match = prop_re.match(line)
            if prop_match:
                key, value = prop_match.groups()
                current_obj.properties[key.strip()] = value.strip()

    build_hierarchy(objects)

    # 根节点是没有父级且不属于辅助对象类型的节点。
    root_nodes = [
        obj for obj in objects
        if not obj.has_parent and 'Slot' not in obj.class_type and 'WidgetSlotPair' not in obj.class_type
    ]

    return Blueprint(name=blueprint_name, root_nodes=root_nodes)
