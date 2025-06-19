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
        """
        追溯数据引脚的连接，确定变量和参数的来源
        返回数据来源的描述字符串
        """
        # 找到指定的输入引脚
        target_pin = None
        for pin in node.pins:
            if pin.pin_name == pin_name and pin.direction == "input":
                target_pin = pin
                break
        
        if not target_pin or target_pin.pin_id not in node.input_connections:
            return None
        
        # 获取连接的源节点
        source_node = node.input_connections[target_pin.pin_id]
        
        # 根据源节点类型生成描述
        return self._generate_data_source_description(source_node, target_pin)
    
    def _generate_data_source_description(self, source_node: GraphNode, target_pin) -> str:
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
            target_class = source_node.properties.get("TargetType", "UnknownType")
            return f"cast<{target_class}>"
        
        # 字面量节点
        elif "K2Node_Literal" in node_type:
            return source_node.properties.get("LiteralValue", "literal_value")
        
        # 默认情况
        else:
            return f"{source_node.node_name}"
    
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