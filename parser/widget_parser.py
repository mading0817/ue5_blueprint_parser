"""widget_parser.py
UI蓝图解析器

该模块直接将UE5 UserWidget蓝图文本解析为 `WidgetNode` AST 树，
弃用旧的 BlueprintNode / Blueprint 中间层，减少冗余。"""

# ================================================================
# 依赖导入
# ================================================================

import re
from collections import deque
from typing import Dict, List, Optional

from .models import WidgetNode, SourceLocation
from .common.graph_utils import parse_object_path


# ================================================================
# 内部辅助数据结构
# ================================================================

class _RawObject:
    """内部使用的临时对象结构，用于解析阶段收集属性"""

    def __init__(self, name: str, class_type: Optional[str]):
        self.name: str = name
        self.class_type: str = class_type or ""
        self.properties: Dict[str, str] = {}

    def add_property(self, key: str, value: str):
        self.properties[key] = value

    # 调试输出
    def __repr__(self):
        return f"<_RawObject {self.name} ({self.class_type})>"


# ================================================================
# 主解析函数
# ================================================================

def parse(blueprint_text: str) -> List[WidgetNode]:
    """解析UE5 UserWidget蓝图文本为 `WidgetNode` 根节点列表。

    :param blueprint_text: 蓝图原始文本
    :return: `WidgetNode` 根节点列表，如果解析失败返回空列表
    """
    if not blueprint_text or not blueprint_text.strip():
        return []

    # 正则表达式准备
    begin_obj_re = re.compile(r"Begin Object(?: Class=(?P<class>[\w./_]+))? Name=\"(?P<name>[\w_]+)\"")
    prop_re = re.compile(r"([\w_()]+)=(.*)")

    # 遍历文本并构建原始对象集合
    objects_by_name: Dict[str, _RawObject] = {}
    slot_objects: List[_RawObject] = []
    object_stack: deque[_RawObject] = deque()

    for raw_line in blueprint_text.strip().splitlines():
        line = raw_line.strip()

        # 开始对象块
        begin_match = begin_obj_re.search(line)
        if begin_match:
            obj_name = begin_match.group("name")
            obj_class = begin_match.group("class")
            obj = _RawObject(obj_name, obj_class)
            objects_by_name[obj_name] = obj
            object_stack.append(obj)
            # 记录Slot对象以便稍后建立层级关系
            if obj_class and "Slot" in obj_class:
                slot_objects.append(obj)
            continue

        # 结束对象块
        if line.startswith("End Object"):
            if object_stack:
                object_stack.pop()
            continue

        # 属性行
        if object_stack:
            current_obj = object_stack[-1]
            prop_match = prop_re.match(line)
            if prop_match:
                key, value = prop_match.groups()
                current_obj.add_property(key.strip(), value.strip())

    # ============================================================
    # 构建 WidgetNode 实例
    # ============================================================
    widget_nodes: Dict[str, WidgetNode] = {}

    for obj in objects_by_name.values():
        # 跳过 Slot 与其他辅助对象
        if "Slot" in obj.class_type or "WidgetSlotPair" in obj.class_type:
            continue

        widget_nodes[obj.name] = WidgetNode(
            widget_name=obj.name,
            widget_type=obj.class_type,
            properties=obj.properties.copy(),
            source_location=SourceLocation(node_name=obj.name, file_path="Blueprint")
        )

    # ============================================================
    # 建立父子关系
    # ============================================================
    for slot_obj in slot_objects:
        parent_path = slot_obj.properties.get("Parent")
        content_path = slot_obj.properties.get("Content")
        if not parent_path or not content_path:
            continue

        parent_name = parse_object_path(parent_path)
        child_name = parse_object_path(content_path)

        parent_widget = widget_nodes.get(parent_name)
        child_widget = widget_nodes.get(child_name)

        if parent_widget and child_widget:
            parent_widget.add_child(child_widget)

    # ============================================================
    # 识别根节点
    # ============================================================
    all_children: set[str] = set()
    for widget in widget_nodes.values():
        for child in widget.children:
            all_children.add(child.widget_name)

    root_widgets = [w for w in widget_nodes.values() if w.widget_name not in all_children]

    return root_widgets


# ================================================================
# 向后兼容API
# ================================================================

# 旧API别名，供性能测试和遗留代码使用
parse_ue_blueprint_to_widget_ast = parse  # noqa: E305, E501

__all__ = [
    "parse",
    "parse_ue_blueprint_to_widget_ast",
] 