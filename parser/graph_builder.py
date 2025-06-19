from typing import List, Dict, Optional, Set
from .models import GraphNode, BlueprintGraph


class GraphTraverser:
    """
    图遍历器，用于分析蓝图Graph的执行流程和数据流
    """
    
    def __init__(self, graph: BlueprintGraph):
        self.graph = graph
        self.visited_nodes: Set[str] = set()
        self.execution_sequence: List[GraphNode] = []
    
    def find_execution_path(self, start_node: GraphNode) -> List[GraphNode]:
        """
        从指定节点开始，沿着exec引脚遍历执行路径
        返回按执行顺序排列的节点列表
        """
        self.visited_nodes.clear()
        self.execution_sequence.clear()
        
        self._traverse_execution(start_node)
        return self.execution_sequence.copy()
    
    def _traverse_execution(self, node: GraphNode):
        """
        递归遍历执行路径
        主要沿着exec类型的引脚进行遍历
        """
        if not node or node.node_guid in self.visited_nodes:
            return
        
        self.visited_nodes.add(node.node_guid)
        self.execution_sequence.append(node)
        
        # 查找执行输出引脚
        exec_pins = self._find_exec_output_pins(node)
        
        # 按引脚名称排序，确保then_0, then_1, then_2...的顺序
        exec_pins.sort(key=lambda pin: self._get_pin_order(pin.pin_name))
        
        # 遍历所有执行输出引脚
        for pin in exec_pins:
            if pin.pin_id in node.output_connections:
                connected_nodes = node.output_connections[pin.pin_id]
                for connected_node in connected_nodes:
                    self._traverse_execution(connected_node)
    
    def _find_exec_output_pins(self, node: GraphNode) -> List:
        """
        找到节点的所有执行输出引脚
        """
        exec_pins = []
        for pin in node.pins:
            if (pin.direction == "output" and 
                (pin.pin_type == "exec" or 
                 pin.pin_name.lower().startswith("exec") or
                 pin.pin_name.lower().startswith("then") or
                 pin.pin_name.lower() == "loopbody")):
                exec_pins.append(pin)
        return exec_pins
    
    def _get_pin_order(self, pin_name: str) -> int:
        """
        获取引脚的排序优先级
        确保then_0在then_1之前执行
        """
        pin_name_lower = pin_name.lower()
        
        # 处理then_X格式的引脚
        if pin_name_lower.startswith("then_"):
            try:
                return int(pin_name_lower.split("_")[1])
            except (IndexError, ValueError):
                pass
        
        # 处理其他特殊引脚
        if pin_name_lower == "exec":
            return -1  # exec引脚优先级最高
        elif pin_name_lower == "loopbody":
            return 100  # 循环体引脚
        elif pin_name_lower == "completed":
            return 200  # 完成引脚
        
        return 1000  # 默认优先级
    
    def resolve_data_flow(self, node: GraphNode, pin_name: str) -> Optional[str]:
        """追溯数据流直到获取可读描述"""
        # 找到目标输入引脚
        target_pin = next((p for p in node.pins if p.pin_name == pin_name and p.direction == "input"), None)
        if not target_pin or target_pin.pin_id not in node.input_connections:
            return None

        source_node = node.input_connections[target_pin.pin_id]
        return self._resolve_recursive_source(source_node, target_pin.pin_name)
    
    def _resolve_recursive_source(self, source_node: GraphNode, via_pin_name: Optional[str] = None) -> Optional[str]:
        desc = self._generate_data_source_description(source_node, via_pin_name)

        if (not desc or desc.startswith("K2Node_")) and source_node.input_connections:
            # 继续递归第一个输入连接
            upstream = next(iter(source_node.input_connections.values()))
            return self._resolve_recursive_source(upstream, via_pin_name)
        return desc
    
    def _generate_data_source_description(self, source_node: GraphNode, via_pin_name: Optional[str]) -> str:
        """
        根据源节点生成数据来源的描述
        """
        node_type = source_node.class_type
        
        # 变量获取节点
        if "K2Node_VariableGet" in node_type:
            var_ref = source_node.properties.get("VariableReference", "")
            var_name = "UnknownVariable"
            
            if "MemberName=" in var_ref:
                import re
                match = re.search(r'MemberName="([^"]+)"', var_ref)
                if match:
                    var_name = match.group(1)
            
            return f"{var_name}"
        
        # 变量设置节点
        elif "K2Node_VariableSet" in node_type:
            var_name = source_node.properties.get("VariableReference.MemberName", "UnknownVariable")
            return f"{var_name}"
        
        # 函数调用节点
        elif "K2Node_CallFunction" in node_type:
            func_ref = source_node.properties.get("FunctionReference", "")
            func_name = "UnknownFunction"
            
            if "MemberName=" in func_ref:
                import re
                match = re.search(r'MemberName="([^"]+)"', func_ref)
                if match:
                    func_name = match.group(1)
            
            return f"{func_name}()"
        
        # 动态转换节点
        elif "K2Node_DynamicCast" in node_type:
            target_class_full = source_node.properties.get("TargetType", "UnknownType")
            import re
            cls_all = re.findall(r"\.([A-Za-z0-9_]+)'", str(target_class_full))
            cls_name = cls_all[-1] if cls_all else str(target_class_full).split('.')[-1].split("'")[0]
            obj_expr = self.resolve_data_flow(source_node, "Object") or "unknown"
            return f"cast({obj_expr} as {cls_name})"
        
        # 字面量节点
        elif "K2Node_Literal" in node_type:
            return f"literal_value"
        
        # ForEachLoop 宏实例
        elif "K2Node_MacroInstance" in node_type:
            if via_pin_name and via_pin_name.lower().startswith("array index"):
                return "index"
            return "item"

        # Knot 重路由节点：跳过再向前解析
        elif "K2Node_Knot" in node_type:
            if source_node.input_connections:
                upstream = next(iter(source_node.input_connections.values()))
                return self._resolve_recursive_source(upstream, via_pin_name)
            return "<unknown>"
        
        # 默认情况
        else:
            return f"<unknown>"
    
    def get_execution_sequence(self) -> List[GraphNode]:
        """
        获取完整的执行序列
        从第一个入口节点开始遍历（通常只有一个事件节点）
        """
        if not self.graph.entry_nodes:
            return []
        
        # 只从第一个入口节点开始遍历
        # 在蓝图Graph中，通常只有一个主要的事件入口点
        entry_node = self.graph.entry_nodes[0]
        return self.find_execution_path(entry_node) 