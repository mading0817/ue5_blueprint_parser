from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


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
class GraphPin:
    """
    代表蓝图Graph节点的引脚信息
    用于存储引脚的连接关系和数据流向
    """
    pin_id: str
    pin_name: str
    direction: str  # "input" 或 "output"
    pin_type: str   # 引脚的数据类型
    linked_to: List[Dict[str, str]] = field(default_factory=list)  # 连接到的其他引脚信息 [{"node_guid": "", "pin_id": ""}]


@dataclass
class GraphNode:
    """
    代表蓝图Graph中的单个节点
    专门用于处理Graph逻辑的节点结构
    """
    node_guid: str
    node_name: str
    class_type: str
    pins: List[GraphPin] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    node_pos_x: float = 0.0
    node_pos_y: float = 0.0
    # 用于图遍历的连接引用
    input_connections: Dict[str, 'GraphNode'] = field(default_factory=dict)  # pin_id -> 连接的源节点
    output_connections: Dict[str, List['GraphNode']] = field(default_factory=dict)  # pin_id -> 连接的目标节点列表


@dataclass
class BlueprintGraph:
    """
    代表完整的蓝图图结构
    包含所有节点和它们之间的连接关系
    """
    graph_name: str
    nodes: Dict[str, GraphNode] = field(default_factory=dict)  # node_guid -> GraphNode
    entry_nodes: List[GraphNode] = field(default_factory=list)  # 入口节点（如事件节点）


@dataclass
class Blueprint:
    """代表一个完整的蓝图资源，包含其层级结构和元数据。"""
    name: str
    root_nodes: List[BlueprintNode]
    graphs: Dict[str, BlueprintGraph] = field(default_factory=dict)  # graph_name -> BlueprintGraph
