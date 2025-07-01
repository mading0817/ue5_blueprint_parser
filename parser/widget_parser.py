"""widget_parser.py
UI蓝图构建器

该模块使用通用的 BlueprintObjectParser 解析蓝图文本，
然后将 RawObject 构建为 WidgetNode AST 树。
重构后消除了与 graph_parser 的代码重复。"""

# ================================================================
# 依赖导入
# ================================================================

from typing import Dict, List, Set

from .models import WidgetNode, SourceLocation, RawObject
from .common.graph_utils import parse_object_path
from .common.object_parser import BlueprintObjectParser
from .common.builder_utils import collect_all_raw_objects


# ================================================================
# Widget 构建器类
# ================================================================

class WidgetBuilder:
    """
    Widget 构建器
    职责：将 RawObject 列表构建为 WidgetNode 树
    """
    
    def __init__(self):
        self.object_parser = BlueprintObjectParser()
    
    def build(self, raw_objects: List[RawObject]) -> List[WidgetNode]:
        """
        从 RawObject 列表构建 WidgetNode 树
        
        :param raw_objects: 解析出的原始对象列表
        :return: WidgetNode 根节点列表
        """
        # 收集所有对象（包括嵌套的）
        all_objects = collect_all_raw_objects(raw_objects)
        
        # 分类对象：Widget 对象和 Slot 对象
        widget_objects = []
        slot_objects = []
        
        for obj in all_objects:
            if "Slot" in obj.class_type or "WidgetSlotPair" in obj.class_type:
                slot_objects.append(obj)
            elif obj.class_type:  # 有类型的对象才是真正的 Widget
                widget_objects.append(obj)
        
        # 构建 WidgetNode 实例
        widget_nodes = self._build_widget_nodes(widget_objects)
        
        # 建立父子关系
        self._establish_relationships(widget_nodes, slot_objects)
        
        # 识别并返回根节点
        return self._find_root_nodes(widget_nodes)
    

    
    def _build_widget_nodes(self, widget_objects: List[RawObject]) -> Dict[str, WidgetNode]:
        """从 Widget 对象构建 WidgetNode 实例"""
        widget_nodes = {}
        
        for obj in widget_objects:
            widget_nodes[obj.name] = WidgetNode(
                widget_name=obj.name,
                widget_type=obj.class_type,
                properties=obj.properties.copy(),
                source_location=SourceLocation(node_name=obj.name, file_path="Blueprint")
            )
        
        return widget_nodes
    
    def _establish_relationships(self, widget_nodes: Dict[str, WidgetNode], slot_objects: List[RawObject]):
        """通过 Slot 对象建立 Widget 之间的父子关系"""
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
    
    def _find_root_nodes(self, widget_nodes: Dict[str, WidgetNode]) -> List[WidgetNode]:
        """识别根节点（没有父节点的 Widget）"""
        all_children: Set[str] = set()
        
        # 收集所有子节点的名称
        for widget in widget_nodes.values():
            for child in widget.children:
                all_children.add(child.widget_name)
        
        # 不在子节点列表中的就是根节点
        root_widgets = [
            widget for widget in widget_nodes.values() 
            if widget.widget_name not in all_children
        ]
        
        return root_widgets


# ================================================================
# 主解析函数（保持向后兼容）
# ================================================================

def parse(blueprint_text: str) -> List[WidgetNode]:
    """解析UE5 UserWidget蓝图文本为 WidgetNode 根节点列表。

    :param blueprint_text: 蓝图原始文本
    :return: WidgetNode 根节点列表，如果解析失败返回空列表
    """
    if not blueprint_text or not blueprint_text.strip():
        return []

    # 第一阶段：使用通用解析器解析文本
    object_parser = BlueprintObjectParser()
    raw_objects = object_parser.parse(blueprint_text)
    
    if not raw_objects:
        return []
    
    # 第二阶段：使用 Widget 构建器构建 WidgetNode 树
    widget_builder = WidgetBuilder()
    return widget_builder.build(raw_objects)


def parse_v2(blueprint_text: str) -> 'BlueprintParseResult':
    """
    新版本：解析UE5 UserWidget蓝图文本并返回统一的解析结果
    """
    from .models import BlueprintParseResult
    import re
    
    if not blueprint_text or not blueprint_text.strip():
        return BlueprintParseResult(
            blueprint_name="UnknownBlueprint",
            blueprint_path="",
            content=None,
            success=False,
            error_message="输入文本为空"
        )
    
    try:
        # 第一阶段：使用通用解析器解析文本
        object_parser = BlueprintObjectParser()
        raw_objects = object_parser.parse(blueprint_text)
        
        if not raw_objects:
            return BlueprintParseResult(
                blueprint_name="UnknownBlueprint",
                blueprint_path="",
                content=None,
                success=False,
                error_message="无法解析蓝图文本格式"
            )
        
        # 使用与graph_parser相同的名称提取逻辑
        # 创建临时的GraphBuilder实例来复用名称提取逻辑
        from .graph_parser import GraphBuilder
        temp_builder = GraphBuilder()
        blueprint_name = temp_builder._extract_blueprint_name(raw_objects)
        
        # 尝试提取完整路径
        blueprint_path = ""
        path_match = re.search(r"/Game/[^'\"]+\.([^'\"]+)", blueprint_text)
        if path_match:
            blueprint_path = path_match.group(0)
        
        # 第二阶段：使用 Widget 构建器构建 WidgetNode 树
        widget_builder = WidgetBuilder()
        widget_nodes = widget_builder.build(raw_objects)
        
        if not widget_nodes:
            return BlueprintParseResult(
                blueprint_name=blueprint_name,
                blueprint_path=blueprint_path,
                content=None,
                success=False,
                error_message="无法构建Widget树结构"
            )
        
        return BlueprintParseResult(
            blueprint_name=blueprint_name,
            blueprint_path=blueprint_path,
            content=widget_nodes,
            success=True,
            error_message=None
        )
        
    except Exception as e:
        return BlueprintParseResult(
            blueprint_name="UnknownBlueprint",
            blueprint_path="",
            content=None,
            success=False,
            error_message=f"解析过程中发生错误: {str(e)}"
        )


# ================================================================
# 向后兼容API
# ================================================================

# 旧API别名，供性能测试和遗留代码使用
parse_ue_blueprint_to_widget_ast = parse  # noqa: E305, E501

__all__ = [
    "parse",
    "parse_ue_blueprint_to_widget_ast",
] 