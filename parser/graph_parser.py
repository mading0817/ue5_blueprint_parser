import re
from typing import List, Dict, Optional
from .models import GraphPin, GraphNode, BlueprintGraph, RawObject
from .common.object_parser import BlueprintObjectParser
import uuid

# 生成唯一 GUID
_defalt_guid_counter = 0

def _generate_temp_guid() -> str:
    global _defalt_guid_counter
    _defalt_guid_counter += 1
    return f"TEMP-{_defalt_guid_counter:08x}"


# ================================================================
# Graph 构建器类
# ================================================================

class GraphBuilder:
    """
    Graph 构建器
    职责：将 RawObject 列表构建为 BlueprintGraph
    """
    
    def __init__(self):
        self.object_parser = BlueprintObjectParser()
    
    def build(self, raw_objects: List[RawObject], graph_name: str = "EventGraph") -> Optional[BlueprintGraph]:
        """
        从 RawObject 列表构建 BlueprintGraph
        
        :param raw_objects: 解析出的原始对象列表
        :param graph_name: 图名称
        :return: BlueprintGraph 对象或 None
        """
        # 收集所有对象（包括嵌套的）
        all_objects = self._collect_all_objects(raw_objects)
        
        # 分类对象：Graph 节点和 Pin 对象
        graph_nodes = []
        pin_objects = []
        
        for obj in all_objects:
            if "Pin" in obj.class_type:
                pin_objects.append(obj)
            elif obj.class_type and obj.class_type != "":  # 有类型的对象才是真正的节点
                graph_nodes.append(obj)
        
        if not graph_nodes:
            return None
        
        # 构建 GraphNode 实例
        nodes = self._build_graph_nodes(graph_nodes, pin_objects)
        
        # 建立连接关系
        nodes_dict = self._build_connections(nodes)
        
        # 找到入口节点
        entry_nodes = self._find_entry_nodes(nodes)
        
        # 提取蓝图名称
        blueprint_name = self._extract_blueprint_name(raw_objects)
        
        # 创建 BlueprintGraph 对象
        return BlueprintGraph(
            graph_name=f"{blueprint_name} {graph_name}",
            nodes=nodes_dict,
            entry_nodes=entry_nodes
        )
    
    def _collect_all_objects(self, raw_objects: List[RawObject]) -> List[RawObject]:
        """递归收集所有对象（包括嵌套的子对象）"""
        all_objects = []
        
        def collect_recursive(objects):
            for obj in objects:
                all_objects.append(obj)
                if obj.children:
                    collect_recursive(obj.children)
        
        collect_recursive(raw_objects)
        return all_objects
    
    def _build_graph_nodes(self, graph_objects: List[RawObject], pin_objects: List[RawObject]) -> List[GraphNode]:
        """从 Graph 对象构建 GraphNode 实例"""
        nodes = []
        
        # 创建节点 ID 到引脚的映射
        node_pins_map = {}
        for pin_obj in pin_objects:
            # 从引脚的父节点关系或属性中推断所属节点
            # 这里简化处理，实际可能需要更复杂的逻辑
            pass
        
        for obj in graph_objects:
            # 创建基本的 GraphNode
            node = GraphNode(
                node_guid=obj.properties.get("NodeGuid", _generate_temp_guid()),
                node_name=obj.name,
                class_type=obj.class_type,
                properties=obj.properties.copy()
            )
            
            # 设置节点位置
            if "NodePosX" in obj.properties:
                try:
                    node.node_pos_x = float(obj.properties["NodePosX"])
                except ValueError:
                    pass
            
            if "NodePosY" in obj.properties:
                try:
                    node.node_pos_y = float(obj.properties["NodePosY"])
                except ValueError:
                    pass
            
            # 解析引脚（从 CustomProperties Pin 或子对象中）
            node.pins = self._extract_pins_for_node(obj)
            
            nodes.append(node)
        
        return nodes
    
    def _extract_pins_for_node(self, node_obj: RawObject) -> List[GraphPin]:
        """为节点提取引脚信息"""
        pins = []
        
        # 处理 CustomProperties Pin 格式的内联引脚
        for prop_name, prop_value in node_obj.properties.items():
            if prop_name.startswith("CustomProperties Pin"):
                pin = self._parse_inline_pin_from_property(prop_value)
                if pin:
                    pins.append(pin)
        
        # 处理子对象中的引脚
        for child in node_obj.children:
            if "Pin" in child.class_type:
                pin = self._build_pin_from_object(child)
                if pin:
                    pins.append(pin)
        
        return pins
    
    def _parse_inline_pin_from_property(self, prop_value: str) -> Optional[GraphPin]:
        """从属性值解析内联引脚"""
        # 提取PinId
        pin_id_match = re.search(r'PinId=([A-F0-9-]+)', prop_value)
        if not pin_id_match:
            return None
        pin_id = pin_id_match.group(1)
        
        # 提取PinName
        pin_name_match = re.search(r'PinName="([^"]+)"', prop_value)
        pin_name = pin_name_match.group(1) if pin_name_match else "unknown"
        
        # 提取引脚方向
        direction = "input"  # 默认为输入
        if 'Direction="EGPD_Output"' in prop_value:
            direction = "output"
        
        # 提取引脚类型
        pin_type_match = re.search(r'PinType\.PinCategory="([^"]+)"', prop_value)
        pin_type = pin_type_match.group(1) if pin_type_match else "unknown"
        
        # 提取默认值
        default_value = None
        default_match = re.search(r'DefaultValue="((?:[^"\\]|\\.)*)"', prop_value)
        if default_match:
            raw_value = default_match.group(1)
            default_value = raw_value.replace('\\"', '"').replace('\\\\', '\\')
        
        # 创建引脚对象
        pin = GraphPin(
            pin_id=pin_id,
            pin_name=pin_name,
            direction=direction,
            pin_type=pin_type,
            default_value=default_value
        )
        
        # 解析连接信息
        linked_match = re.search(r'LinkedTo=\(([^)]+)\)', prop_value)
        if linked_match:
            links_str = linked_match.group(1)
            self._parse_linked_to_inline(pin, links_str)
        
        return pin
    
    def _parse_linked_to_inline(self, pin: GraphPin, links_str: str):
        """解析内联格式的连接信息"""
        # 尝试新格式：K2Node_Event_0 AD580DCB422E368B8945BFBB2B710ECC,
        link_parts = re.findall(r'(\w+)\s+([A-F0-9-]+)', links_str)
        if link_parts:
            for node_name, pin_id in link_parts:
                pin.linked_to.append({
                    "node_name": node_name,
                    "pin_id": pin_id
                })
        else:
            # 回退到旧格式：只有引脚ID
            guid_parts = re.findall(r'([A-F0-9-]+)', links_str)
            for target_pin_id in guid_parts:
                if target_pin_id:  # 确保不是空字符串
                    pin.linked_to.append({
                        "pin_id": target_pin_id
                    })
    
    def _build_pin_from_object(self, pin_obj: RawObject) -> Optional[GraphPin]:
        """从 Pin 对象构建 GraphPin"""
        pin_id = pin_obj.properties.get("PinId", "")
        if not pin_id:
            return None
        
        pin_name = pin_obj.properties.get("PinName", pin_obj.name)
        if pin_name.startswith('"') and pin_name.endswith('"'):
            pin_name = pin_name[1:-1]  # 移除引号
        
        # 确定方向
        direction = "input"
        if pin_obj.properties.get("PinType.bIsOutput") == "True":
            direction = "output"
        
        # 获取类型
        pin_type = pin_obj.properties.get("PinType.PinCategory", "unknown")
        if pin_type.startswith('"') and pin_type.endswith('"'):
            pin_type = pin_type[1:-1]
        
        # 获取默认值
        default_value = pin_obj.properties.get("DefaultValue")
        
        # 创建引脚对象
        pin = GraphPin(
            pin_id=pin_id,
            pin_name=pin_name,
            direction=direction,
            pin_type=pin_type,
            default_value=default_value
        )
        
        # 解析连接信息
        linked_to_str = pin_obj.properties.get("LinkedTo")
        if linked_to_str:
            self._parse_linked_to(pin, linked_to_str)
        
        return pin
    
    def _parse_linked_to(self, pin: GraphPin, linked_to_str: str):
        """解析引脚的连接信息"""
        # 移除外层括号
        if linked_to_str.startswith("(") and linked_to_str.endswith(")"):
            linked_to_str = linked_to_str[1:-1]
        
        # 解析连接信息
        link_parts = re.findall(r'NodeGuid=([A-F0-9-]+),PinId=([A-F0-9-]+)', linked_to_str)
        for node_guid, pin_id in link_parts:
            pin.linked_to.append({
                "node_guid": node_guid,
                "pin_id": pin_id
            })
    
    def _build_connections(self, nodes: List[GraphNode]) -> Dict[str, GraphNode]:
        """建立节点之间的连接关系"""
        nodes_dict = {node.node_guid: node for node in nodes if node.node_guid}
        
        # 建立连接关系
        for node in nodes:
            for pin in node.pins:
                for link in pin.linked_to:
                    if "node_guid" in link:
                        target_node_guid = link["node_guid"]
                        target_pin_id = link["pin_id"]
                        
                        if target_node_guid in nodes_dict:
                            target_node = nodes_dict[target_node_guid]
                            self._establish_connection(node, pin, target_node, target_pin_id)
        
        return nodes_dict
    
    def _establish_connection(self, source_node: GraphNode, source_pin: GraphPin, target_node: GraphNode, target_pin_id: str):
        """建立两个节点间的连接关系"""
        if source_pin.direction == "output":
            if source_pin.pin_id not in source_node.output_connections:
                source_node.output_connections[source_pin.pin_id] = []
            source_node.output_connections[source_pin.pin_id].append(target_node)
            target_node.input_connections[target_pin_id] = source_node
        elif source_pin.direction == "input":
            source_node.input_connections[source_pin.pin_id] = target_node
            if target_pin_id not in target_node.output_connections:
                target_node.output_connections[target_pin_id] = []
            target_node.output_connections[target_pin_id].append(source_node)
    
    def _find_entry_nodes(self, nodes: List[GraphNode]) -> List[GraphNode]:
        """识别图的入口节点"""
        entry_nodes = []
        
        for node in nodes:
            # 检查是否有输出执行引脚
            has_output_exec = any(
                pin.pin_type == "exec" and pin.direction == "output"
                for pin in node.pins
            )
            
            if not has_output_exec:
                continue
            
            # 检查是否所有输入执行引脚都未被连接
            has_connected_input_exec = any(
                pin.pin_type == "exec" and pin.direction == "input" and pin.linked_to
                for pin in node.pins
            )
            
            if not has_connected_input_exec:
                entry_nodes.append(node)
        
        # 按位置排序
        entry_nodes.sort(key=lambda node: float(node.properties.get("NodePosY", 0)))
        return entry_nodes
    
    def _extract_blueprint_name(self, raw_objects: List[RawObject]) -> str:
        """从原始对象中提取蓝图名称"""
        # 从第一个对象的属性中查找
        for obj in raw_objects:
            for prop_key, prop_value in obj.properties.items():
                # 跳过 CustomProperties Pin 属性
                if prop_key.startswith("CustomProperties Pin"):
                    continue
                    
                # 查找包含路径信息的属性
                if isinstance(prop_value, str):
                    name_match = re.search(r"/Game/.*(?:/|')(?P<asset_name>[^/.]+)\.", prop_value)
                    if name_match:
                        return name_match.group("asset_name")
        return "UnknownBlueprint"

def parse_graph_nodes(graph_text: str) -> List[GraphNode]:
    """
    解析Graph文本中的所有节点
    提取节点的基础信息和引脚数据
    """
    nodes = []
    lines = graph_text.strip().splitlines()
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 移除可能的BOM字符（通常出现在第一行）
        if line.startswith('\ufeff'):
            line = line[1:]
        
        # 检测主节点开始（不是引脚节点）
        if line.startswith('Begin Object Class=') and 'Pin' not in line:
            # 解析单个节点及其所有内容
            node, next_i = _parse_single_node(lines, i)
            if node:
                nodes.append(node)
            i = next_i
        else:
            i += 1
    
    return nodes


def _parse_single_node(lines: List[str], start_index: int) -> tuple[Optional[GraphNode], int]:
    """
    解析单个节点及其所有内容（包括引脚）
    返回解析的节点和下一个要处理的行索引
    """
    i = start_index
    line = lines[i].strip()
    
    # 移除可能的BOM字符（通常出现在第一行）
    if line.startswith('\ufeff'):
        line = line[1:]
    
    # 解析节点开始行
    begin_match = re.search(r'Begin Object Class=(?P<class>[\w./_]+) Name="(?P<name>[\w_]+)"', line)
    if not begin_match:
        return None, i + 1
    
    node_name = begin_match.group('name')
    node_class = begin_match.group('class')
    
    node = GraphNode(
        node_guid="",
        node_name=node_name,
        class_type=node_class
    )
    
    i += 1  # 移到下一行
    
    # 解析节点内容
    while i < len(lines):
        line = lines[i].strip()
        
        # 检测节点结束
        if line == 'End Object':
            # 在函数 _parse_single_node 结束前, 若 node_guid 为空则填充
            if not node.node_guid:
                node.node_guid = _generate_temp_guid()
            return node, i + 1
        
        # 检测嵌套引脚开始
        if line.startswith('Begin Object Class=') and 'Pin' in line:
            pin, next_i = _parse_single_pin(lines, i)
            if pin:
                node.pins.append(pin)
            i = next_i
            continue
        
        # 检测内联引脚定义（CustomProperties Pin格式）
        if line.startswith('CustomProperties Pin'):
            pin = _parse_inline_pin(line)
            if pin:
                node.pins.append(pin)
            i += 1
            continue
        
        # 解析节点属性
        _parse_node_property(line, node)
        i += 1
    
    return node, i


def _parse_single_pin(lines: List[str], start_index: int) -> tuple[Optional[GraphPin], int]:
    """
    解析单个引脚及其所有属性
    返回解析的引脚和下一个要处理的行索引
    """
    i = start_index
    line = lines[i].strip()
    
    # 解析引脚开始行
    pin_match = re.search(r'Begin Object Class=[\w./_]*Pin Name="(?P<name>[\w_]+)"', line)
    if not pin_match:
        return None, i + 1
    
    pin_name = pin_match.group('name')
    pin = GraphPin(
        pin_id="",
        pin_name=pin_name,
        direction="unknown",
        pin_type="unknown"
    )
    
    i += 1  # 移到下一行
    
    # 解析引脚内容
    while i < len(lines):
        line = lines[i].strip()
        
        # 检测引脚结束
        if line == 'End Object':
            return pin, i + 1
        
        # 若发现 LinkedTo 起始但未闭合，合并后续行
        if 'LinkedTo=(' in line and ')' not in line:
            combined = [line]
            j = i + 1
            while j < len(lines):
                combined.append(lines[j].strip())
                if ')' in lines[j]:
                    break
                j += 1
            line = ' '.join(combined)
            i = j  # 跳过已合并的行
        
        # 解析引脚属性（可能是合并后的单行）
        _parse_pin_property(line, pin)
        i += 1
    
    return pin, i


def _parse_node_property(line: str, node: GraphNode):
    """
    解析节点属性行
    """
    # NodeGuid
    guid_match = re.search(r'NodeGuid=([A-F0-9-]+)', line)
    if guid_match:
        node.node_guid = guid_match.group(1)
        return
    
    # 节点位置
    pos_match = re.search(r'NodePos([XY])=([-\d.]+)', line)
    if pos_match:
        axis = pos_match.group(1)
        value = float(pos_match.group(2))
        if axis == 'X':
            node.node_pos_x = value
        elif axis == 'Y':
            node.node_pos_y = value
        return
    
    # 其他属性
    if '=' in line and not line.startswith('Begin') and not line.startswith('End'):
        key_value = line.split('=', 1)
        if len(key_value) == 2:
            key = key_value[0].strip()
            value = key_value[1].strip()
            node.properties[key] = value


def _parse_pin_property(line: str, pin: GraphPin):
    """
    解析引脚属性行
    """
    # 连接信息 - 支持多行 LinkedTo
    linked_match = re.search(r'LinkedTo=\(([^)]+)\)', line)
    if linked_match:
        links_str = linked_match.group(1)
        link_parts = re.findall(r'NodeGuid=([A-F0-9-]+),PinId=([A-F0-9-]+)', links_str)
        for node_guid, pin_id in link_parts:
            pin.linked_to.append({
                "node_guid": node_guid,
                "pin_id": pin_id
            })
        return
    
    # PinId - 只处理不在LinkedTo中的PinId
    if line.startswith('PinId=') and 'LinkedTo=' not in line:
        pin_id_match = re.search(r'PinId=([A-F0-9-]+)', line)
        if pin_id_match:
            pin.pin_id = pin_id_match.group(1)
            return
    
    # PinName (有些引脚的名称不是从Begin Object行获取，而是从PinName属性获取)
    pin_name_match = re.search(r'PinName="([\w_]+)"', line)
    if pin_name_match:
        pin.pin_name = pin_name_match.group(1)
        return
    
    # 引脚类型
    pin_type_match = re.search(r'PinType\.PinCategory="([\w]+)"', line)
    if pin_type_match:
        pin.pin_type = pin_type_match.group(1)
        return
    
    # 引脚方向
    if 'PinType.bIsOutput=True' in line:
        pin.direction = "output"
        return
    elif 'PinType.bIsOutput=False' in line:
        pin.direction = "input"
        return


def _parse_inline_pin(line: str) -> Optional[GraphPin]:
    """
    解析内联引脚定义（CustomProperties Pin格式）
    示例: CustomProperties Pin (PinId=xxx,PinName="then",Direction="EGPD_Output",PinType.PinCategory="exec",...)
    """
    # 提取PinId
    pin_id_match = re.search(r'PinId=([A-F0-9-]+)', line)
    if not pin_id_match:
        return None
    pin_id = pin_id_match.group(1)
    
    # 提取PinName
    pin_name_match = re.search(r'PinName="([^"]+)"', line)
    pin_name = pin_name_match.group(1) if pin_name_match else "unknown"
    
    # 提取引脚方向
    direction = "input"  # 默认为输入
    if 'Direction="EGPD_Output"' in line:
        direction = "output"
    
    # 提取引脚类型
    pin_type_match = re.search(r'PinType\.PinCategory="([^"]+)"', line)
    pin_type = pin_type_match.group(1) if pin_type_match else "unknown"
    
    # 提取默认值 - 修复转义字符处理
    default_value = None
    # 使用更健壮的正则表达式来匹配包含转义字符的字符串
    default_match = re.search(r'DefaultValue="((?:[^"\\]|\\.)*)"', line)
    if default_match:
        # 处理转义字符：将 \" 转换为 "
        raw_value = default_match.group(1)
        default_value = raw_value.replace('\\"', '"')
        # 同时处理其他可能的转义字符
        default_value = default_value.replace('\\\\', '\\')

    # 提取DefaultObject（通常用于对象引用）
    default_object_match = re.search(r'DefaultObject="([^"]*)"', line)
    if default_object_match:
        # 优先使用DefaultObject作为值
        default_value = default_object_match.group(1)

    # 创建引脚对象
    pin = GraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value
    )
    
    # 解析连接信息
    linked_match = re.search(r'LinkedTo=\(([^)]+)\)', line)
    if linked_match:
        links_str = linked_match.group(1)
        
        # 尝试新格式：K2Node_Event_0 AD580DCB422E368B8945BFBB2B710ECC,K2Node_Other_1 1234567890ABCDEF,
        link_parts = re.findall(r'(\w+)\s+([A-F0-9-]+)', links_str)
        if link_parts:
            for node_name, pin_id in link_parts:
                pin.linked_to.append({
                    "node_name": node_name,
                    "pin_id": pin_id
                })
        else:
            # 回退到旧格式：只有引脚ID
            guid_parts = re.findall(r'([A-F0-9-]+)', links_str)
            for target_pin_id in guid_parts:
                if target_pin_id:  # 确保不是空字符串
                    pin.linked_to.append({
                        "pin_id": target_pin_id
                    })
    
    return pin


def build_graph_connections(nodes: List[GraphNode]) -> Dict[str, GraphNode]:
    """
    根据引脚的连接信息建立节点之间的引用关系
    返回以node_guid为键的节点字典
    """
    nodes_dict = {node.node_guid: node for node in nodes if node.node_guid}
    nodes_by_name = {node.node_name: node for node in nodes}  # 按名称索引节点
    
    # 建立连接关系
    for node in nodes:
        for pin in node.pins:
            for link in pin.linked_to:
                # 处理基于GUID的连接（嵌套格式）
                if "node_guid" in link:
                    target_node_guid = link["node_guid"]
                    target_pin_id = link["pin_id"]
                    
                    if target_node_guid in nodes_dict:
                        target_node = nodes_dict[target_node_guid]
                        _establish_connection(node, pin, target_node, target_pin_id)
                
                # 处理基于节点名称的连接（内联格式）
                elif "node_name" in link:
                    target_node_name = link["node_name"]
                    target_pin_id = link["pin_id"]
                    
                    if target_node_name in nodes_by_name:
                        target_node = nodes_by_name[target_node_name]
                        _establish_connection(node, pin, target_node, target_pin_id)
                
                # 处理仅有pin_id的连接（通过pin_id查找目标节点）
                elif "pin_id" in link and "node_guid" not in link and "node_name" not in link:
                    target_pin_id = link["pin_id"]
                    # 在所有节点中查找具有此pin_id的节点
                    for target_node in nodes:
                        for target_pin in target_node.pins:
                            if target_pin.pin_id == target_pin_id:
                                _establish_connection(node, pin, target_node, target_pin_id)
                                break
    
    return nodes_dict


def _establish_connection(source_node: GraphNode, source_pin: GraphPin, target_node: GraphNode, target_pin_id: str):
    """
    建立两个节点间的连接关系
    """
    if source_pin.direction == "output":
        # 当前节点的输出引脚连接到目标节点
        if source_pin.pin_id not in source_node.output_connections:
            source_node.output_connections[source_pin.pin_id] = []
        source_node.output_connections[source_pin.pin_id].append(target_node)
        
        # 目标节点的输入连接
        target_node.input_connections[target_pin_id] = source_node
    
    elif source_pin.direction == "input":
        # 当前节点的输入引脚连接到源节点
        source_node.input_connections[source_pin.pin_id] = target_node
        
        # 源节点的输出连接
        if target_pin_id not in target_node.output_connections:
            target_node.output_connections[target_pin_id] = []
        target_node.output_connections[target_pin_id].append(source_node)


def find_entry_nodes(nodes: List[GraphNode]) -> List[GraphNode]:
    """
    识别图的入口节点 - 基于行为特征的动态识别
    入口节点必须满足：
    1. 有至少一个输出执行引脚 (output exec pin)
    2. 所有输入执行引脚都未被连接 (no connected input exec pins)
    """
    entry_nodes = []
    
    for node in nodes:
        # 检查是否有输出执行引脚
        has_output_exec = False
        for pin in node.pins:
            if pin.pin_type == "exec" and pin.direction == "output":
                has_output_exec = True
                break
        
        # 如果没有输出执行引脚，跳过
        if not has_output_exec:
            continue
        
        # 检查是否所有输入执行引脚都未被连接
        has_connected_input_exec = False
        for pin in node.pins:
            if pin.pin_type == "exec" and pin.direction == "input" and pin.linked_to:
                has_connected_input_exec = True
                break
        
        # 如果没有被连接的输入执行引脚，则为入口节点
        if not has_connected_input_exec:
            entry_nodes.append(node)
    
    # 按NodePosY进行确定性排序，确保输出顺序稳定
    entry_nodes.sort(key=lambda node: node.properties.get("NodePosY", 0))
    
    return entry_nodes


# ================================================================
# 主解析函数（保持向后兼容）
# ================================================================

def parse_blueprint_graph(graph_text: str, graph_name: str = "EventGraph") -> Optional[BlueprintGraph]:
    """
    主函数：解析蓝图Graph文本并返回BlueprintGraph对象
    """
    if not graph_text or not graph_text.strip():
        return None
    
    # 第一阶段：使用通用解析器解析文本
    object_parser = BlueprintObjectParser()
    raw_objects = object_parser.parse(graph_text)
    
    if not raw_objects:
        return None
    
    # 第二阶段：使用 Graph 构建器构建 BlueprintGraph
    graph_builder = GraphBuilder()
    return graph_builder.build(raw_objects, graph_name) 