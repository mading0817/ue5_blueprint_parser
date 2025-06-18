from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class BlueprintNode:
    """
    代表一个UE蓝图中的节点，例如一个Widget控件或一个Slot。
    这是一个通用的数据结构，用于构建解析后的层级树。
    """
    name: str
    class_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List['BlueprintNode'] = field(default_factory=list)
    has_parent: bool = False


@dataclass
class Blueprint:
    """代表一个完整的蓝图资源，包含其层级结构和元数据。"""
    name: str
    root_nodes: List[BlueprintNode]
