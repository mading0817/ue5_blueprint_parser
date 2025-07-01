import re
from typing import List, Dict, Optional
from .models import GraphPin, GraphNode, BlueprintGraph, RawObject
from .common.object_parser import BlueprintObjectParser
from .common.builder_utils import collect_all_raw_objects
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
        all_objects = collect_all_raw_objects(raw_objects)
        
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
        
        # 提取默认对象路径（用于K2Node_CreateWidget等节点）
        default_object = None
        default_object_match = re.search(r'DefaultObject="([^"]*)"', prop_value)
        if default_object_match:
            default_object = default_object_match.group(1)
        
        # 创建引脚对象
        pin = GraphPin(
            pin_id=pin_id,
            pin_name=pin_name,
            direction=direction,
            pin_type=pin_type,
            default_value=default_value,
            default_object=default_object
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
        
        # 获取默认对象路径
        default_object = pin_obj.properties.get("DefaultObject")
        
        # 创建引脚对象
        pin = GraphPin(
            pin_id=pin_id,
            pin_name=pin_name,
            direction=direction,
            pin_type=pin_type,
            default_value=default_value,
            default_object=default_object
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
        """
        识别图的入口节点
        增强版本：优先识别事件节点，确保所有事件都被包含
        """
        entry_nodes = []
        
        # 第一优先级：识别所有事件节点
        event_node_types = {
            "K2Node_Event", "K2Node_CustomEvent", "K2Node_ComponentBoundEvent",
            "/Script/BlueprintGraph.K2Node_Event", 
            "/Script/BlueprintGraph.K2Node_CustomEvent",
            "/Script/BlueprintGraph.K2Node_ComponentBoundEvent"
        }
        
        for node in nodes:
            # 检查是否为事件节点
            if node.class_type in event_node_types:
                entry_nodes.append(node)
                continue
            
            # 第二优先级：其他有输出执行引脚且无连接输入执行引脚的节点
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
        
        # 去重（避免事件节点被重复添加）
        seen_guids = set()
        unique_entry_nodes = []
        for node in entry_nodes:
            if node.node_guid not in seen_guids:
                seen_guids.add(node.node_guid)
                unique_entry_nodes.append(node)
        
        # 按位置排序
        unique_entry_nodes.sort(key=lambda node: float(node.properties.get("NodePosY", 0)))
        return unique_entry_nodes
    
    def _extract_blueprint_name(self, raw_objects: List[RawObject]) -> str:
        """从原始对象中提取蓝图名称 - 多源瀑布式策略"""
        # 优先级1: 从ExportPath提取
        name = self._extract_from_export_path(raw_objects)
        if name and name != "UnknownBlueprint":
            return name
        
        # 优先级2: 从WidgetTree提取（仅Widget蓝图）
        name = self._extract_from_widget_tree(raw_objects)
        if name and name != "UnknownBlueprint":
            return name
        
        # 优先级3: 基于频率分析的智能提取
        name = self._extract_by_frequency(raw_objects)
        if name and name != "UnknownBlueprint":
            return name
        
        return "UnknownBlueprint"
    
    def _extract_from_export_path(self, raw_objects: List[RawObject]) -> str:
        """从ExportPath属性提取蓝图名称（最可靠）"""
        for obj in raw_objects:
            export_path = obj.properties.get("ExportPath", "")
            if not export_path or ":" not in export_path:
                continue
            
            # ExportPath格式: ".../WBP_AbilitiesMenu.WBP_AbilitiesMenu:EventGraph.K2Node_Event_0'"
            # 提取冒号前的部分
            blueprint_part = export_path.split(":")[0]
            
            # 提取最后一个路径段中的资产名
            match = re.search(r"/([^/]+)\.([^'\"]+)$", blueprint_part)
            if match:
                folder_name = match.group(1)
                asset_name = match.group(2)
                # 通常folder_name和asset_name相同，表示这是主蓝图
                if folder_name == asset_name:
                    return asset_name.replace("_C", "")
        
        return "UnknownBlueprint"
    
    def _extract_from_widget_tree(self, raw_objects: List[RawObject]) -> str:
        """从WidgetTree根节点提取蓝图名称（Widget专用）"""
        for obj in raw_objects:
            if obj.class_type == "WidgetTree":
                root_widget = obj.properties.get("RootWidget", "")
                if root_widget:
                    # 格式: "WidgetBlueprint'WBP_Name_C'"
                    match = re.search(r"'([^']+)_C'", root_widget)
                    if match:
                        return match.group(1)
        
        return "UnknownBlueprint"
    
    def _extract_by_frequency(self, raw_objects: List[RawObject]) -> str:
        """基于频率分析的智能名称提取"""
        from collections import Counter
        
        # 收集所有可能的蓝图名称
        candidates = []
        
        for obj in raw_objects:
            for prop_key, prop_value in obj.properties.items():
                # 跳过Pin属性，避免捕获引用的外部类型
                if prop_key.startswith("CustomProperties Pin"):
                    continue
                
                if isinstance(prop_value, str):
                    # 查找所有路径格式的资产引用
                    matches = re.findall(r"/Game/[^'\"]*?/([^/'\"]+)\.([^'\"]+)", prop_value)
                    for folder_name, asset_name in matches:
                        # 清理后缀
                        clean_name = asset_name.replace("_C", "")
                        
                        # 过滤明显的外部引用
                        if self._is_likely_external_reference(clean_name):
                            continue
                        
                        # 如果文件夹名和资产名相似，很可能是主蓝图
                        if self._names_are_similar(folder_name, clean_name):
                            candidates.append(clean_name)
        
        # 返回出现频率最高的名称
        if candidates:
            counter = Counter(candidates)
            most_common = counter.most_common(1)[0]
            return most_common[0]
        
        return "UnknownBlueprint"
    
    def _is_likely_external_reference(self, name: str) -> bool:
        """判断是否可能是外部引用的资产"""
        # 常见的UI控件类型
        ui_widget_patterns = [
            r"^(Button|Panel|Text|Image|Border|Canvas|Overlay|Grid|Spacer)$",
            r"^WBP_.*?(Button|Panel|Icon|Item|Slot)s?$",  # 复数形式
            r"^BP_.*?(Component|Actor|Controller)$"
        ]
        
        for pattern in ui_widget_patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return True
        
        return False
    
    def _names_are_similar(self, name1: str, name2: str) -> bool:
        """判断两个名称是否相似（忽略大小写和下划线）"""
        # 标准化名称：转小写，移除下划线
        norm1 = name1.lower().replace("_", "")
        norm2 = name2.lower().replace("_", "")
        
        # 完全匹配或互相包含
        return norm1 == norm2 or norm1 in norm2 or norm2 in norm1













# ================================================================
# 主解析函数（保持向后兼容）
# ================================================================

def parse_blueprint_graph(graph_text: str, graph_name: str = "EventGraph") -> Optional[BlueprintGraph]:
    """
    主函数：解析蓝图Graph文本并返回BlueprintGraph对象
    
    注意：此函数保持向后兼容，返回BlueprintGraph对象
    新代码应使用 parse_blueprint_graph_v2 获取完整的解析结果
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


def parse_blueprint_graph_v2(graph_text: str, graph_name: str = "EventGraph") -> 'BlueprintParseResult':
    """
    新版本：解析蓝图Graph文本并返回统一的解析结果
    """
    from .models import BlueprintParseResult
    
    if not graph_text or not graph_text.strip():
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
        raw_objects = object_parser.parse(graph_text)
        
        if not raw_objects:
            return BlueprintParseResult(
                blueprint_name="UnknownBlueprint",
                blueprint_path="",
                content=None,
                success=False,
                error_message="无法解析蓝图文本格式"
            )
        
        # 第二阶段：使用 Graph 构建器构建 BlueprintGraph
        graph_builder = GraphBuilder()
        graph = graph_builder.build(raw_objects, graph_name)
        
        if not graph:
            return BlueprintParseResult(
                blueprint_name="UnknownBlueprint",
                blueprint_path="",
                content=None,
                success=False,
                error_message="无法构建蓝图图结构"
            )
        
        # 提取蓝图名称和路径
        blueprint_name = graph.graph_name.split(" ")[0] if " " in graph.graph_name else graph.graph_name
        
        # 尝试提取完整路径
        blueprint_path = ""
        path_match = re.search(r"/Game/[^'\"]+\.([^'\"]+)", graph_text)
        if path_match:
            blueprint_path = path_match.group(0)
        
        return BlueprintParseResult(
            blueprint_name=blueprint_name,
            blueprint_path=blueprint_path,
            content=graph,
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