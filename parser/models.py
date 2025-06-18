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
