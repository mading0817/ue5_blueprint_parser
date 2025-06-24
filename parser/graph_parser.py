import re
from typing import List, Dict, Optional
from .models import GraphPin, GraphNode, BlueprintGraph
import uuid

# 生成唯一 GUID
_defalt_guid_counter = 0

def _generate_temp_guid() -> str:
    global _defalt_guid_counter
    _defalt_guid_counter += 1
    return f"TEMP-{_defalt_guid_counter:08x}"

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
    
    # 提取默认值
    default_value = None
    default_match = re.search(r'DefaultValue="([^"]*)"', line)
    if default_match:
        default_value = default_match.group(1)

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
    识别图的入口节点
    包括所有事件节点和自定义事件节点
    """
    entry_nodes = []
    potential_entries = []
    
    for node in nodes:
        # 优先级 1: 事件节点和自定义事件节点 (都是独立的入口点)
        if 'K2Node_Event' in node.class_type or 'K2Node_CustomEvent' in node.class_type:
            entry_nodes.append(node)
        
        # 优先级 2: 其他潜在入口节点
        elif any(entry_type in node.class_type for entry_type in [
            'K2Node_FunctionEntry', 
            'K2Node_CallFunction',
            'K2Node_MacroInstance'
        ]):
            potential_entries.append(node)
    
    # 如果没有找到事件节点，使用备选入口
    if not entry_nodes and potential_entries:
        # 进一步筛选: 查找没有执行输入连接的节点
        for node in potential_entries:
            has_exec_input = False
            for pin in node.pins:
                if pin.pin_type == "exec" and pin.direction == "input" and pin.linked_to:
                    has_exec_input = True
                    break
            
            # 没有执行输入连接的节点可能是入口点
            if not has_exec_input:
                entry_nodes.append(node)
    
    # 如果仍然没有找到入口，返回所有潜在入口
    if not entry_nodes and potential_entries:
        entry_nodes = potential_entries[:1]  # 至少返回一个
    
    return entry_nodes


def parse_blueprint_graph(graph_text: str, graph_name: str = "EventGraph") -> Optional[BlueprintGraph]:
    """
    主函数：解析蓝图Graph文本并返回BlueprintGraph对象
    """
    if not graph_text or not graph_text.strip():
        return None
    
    # 提取蓝图名称 - 新增功能
    blueprint_name = "UnknownBlueprint"
    name_match = re.search(r"/Game/.*(?:/|')(?P<asset_name>[^/.]+)\.", graph_text)
    if name_match:
        blueprint_name = name_match.group("asset_name")
    
    # 解析所有节点
    nodes = parse_graph_nodes(graph_text)
    if not nodes:
        return None
    
    # 建立连接关系
    nodes_dict = build_graph_connections(nodes)
    
    # 找到入口节点
    entry_nodes = find_entry_nodes(nodes)
    
    # 创建BlueprintGraph对象，使用提取的蓝图名称
    blueprint_graph = BlueprintGraph(
        graph_name=f"{blueprint_name} {graph_name}",  # 组合蓝图名称和图类型
        nodes=nodes_dict,
        entry_nodes=entry_nodes
    )
    
    return blueprint_graph 