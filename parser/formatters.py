from parser.models import BlueprintNode, Blueprint, BlueprintGraph, GraphNode
from parser.graph_builder import GraphTraverser
from typing import List


def _to_markdown_tree_recursive(node: BlueprintNode, indent_level: int = 0) -> str:
    """
    将单个BlueprintNode及其子节点递归地转换为Markdown格式的无序列表字符串。

    :param node: 要格式化的根节点。
    :param indent_level: 当前的缩进级别。
    :return: Markdown格式的层级字符串。
    """
    # 移除 'FString' 等可能的前缀
    class_type_simple = node.class_type.split('.')[-1]

    # 根据缩进级别生成前缀
    indent_str = "  " * indent_level

    # 格式化当前节点
    result_string = f"{indent_str}- **{node.name}** (`{class_type_simple}`)\n"

    # 递归格式化所有子节点
    for child in node.children:
        result_string += _to_markdown_tree_recursive(child, indent_level + 1)

    return result_string


def format_blueprint_to_markdown(blueprint: Blueprint) -> str:
    """
    将一个BlueprintNode的列表格式化为完整的Markdown层级树。

    :param blueprint: 根节点的列表。
    :return: 完整的Markdown格式字符串。
    """
    if not blueprint or not blueprint.root_nodes:
        return "没有找到可显示的节点。(No displayable nodes found.)"

    final_output = f"#### {blueprint.name} Blueprint Hierarchy\n\n"
    for root in blueprint.root_nodes:
        final_output += _to_markdown_tree_recursive(root)

    return final_output


def format_graph_to_pseudocode(graph: BlueprintGraph) -> str:
    """
    将BlueprintGraph转换为伪代码格式
    
    :param graph: 要格式化的蓝图图
    :return: 伪代码字符串
    """
    if not graph or not graph.entry_nodes:
        return "// 没有找到可执行的Graph节点 (No executable graph nodes found)"
    
    # 创建图遍历器
    traverser = GraphTraverser(graph)
    
    # 获取执行序列
    execution_sequence = traverser.get_execution_sequence()
    
    if not execution_sequence:
        return "// 无法确定执行序列 (Unable to determine execution sequence)"
    
    # 生成伪代码
    pseudocode_lines = []
    pseudocode_lines.append(f"// === {graph.graph_name} 伪代码 ===")
    pseudocode_lines.append("")
    
    indent_level = 0
    
    for i, node in enumerate(execution_sequence):
        # 生成当前节点的伪代码
        node_pseudocode = _generate_node_pseudocode(node, traverser, indent_level)
        
        if node_pseudocode:
            # 处理缩进
            for line in node_pseudocode.split('\n'):
                if line.strip():
                    pseudocode_lines.append("    " * indent_level + line.strip())
                else:
                    pseudocode_lines.append("")
            
            # 根据节点类型调整缩进级别
            indent_level = _adjust_indent_level(node, indent_level)
    
    return '\n'.join(pseudocode_lines)


def _generate_node_pseudocode(node: GraphNode, traverser: GraphTraverser, current_indent: int) -> str:
    """
    为单个节点生成伪代码
    """
    node_type = node.class_type
    node_name = node.node_name
    
    # 事件节点
    if "K2Node_Event" in node_type:
        # 从EventReference中提取事件名称
        event_ref = node.properties.get("EventReference", "")
        if "MemberName=" in event_ref:
            # 提取MemberName的值
            import re
            match = re.search(r'MemberName="([^"]+)"', event_ref)
            if match:
                event_name = match.group(1)
            else:
                # 尝试提取不带引号的MemberName
                match = re.search(r'MemberName=([^,)]+)', event_ref)
                event_name = match.group(1) if match else node_name
        else:
            event_name = node.properties.get("EventReference.MemberName", node_name)
        
        return f"event {event_name}:"
    
    # 执行序列节点
    elif "K2Node_ExecutionSequence" in node_type:
        return f"// --- 执行序列: {node_name} ---"
    
    # 函数调用节点
    elif "K2Node_CallFunction" in node_type:
        # 从FunctionReference中提取函数名称
        func_ref = node.properties.get("FunctionReference", "")
        func_name = "UnknownFunction"
        
        if "MemberName=" in func_ref:
            # 提取MemberName的值
            import re
            match = re.search(r'MemberName="([^"]+)"', func_ref)
            if match:
                func_name = match.group(1)
            else:
                # 尝试提取不带引号的MemberName
                match = re.search(r'MemberName=([^,)]+)', func_ref)
                func_name = match.group(1) if match else "UnknownFunction"
        
        # 获取函数调用的目标对象
        target_obj = traverser.resolve_data_flow(node, "self")
        if not target_obj or target_obj == "unknown_object":
            target_obj = "self"
        
        # 获取函数参数
        params = _extract_function_parameters(node, traverser)
        param_str = ", ".join(params) if params else ""
        
        return f"{target_obj}.{func_name}({param_str})"
    
    # 变量设置节点
    elif "K2Node_VariableSet" in node_type:
        # 从VariableReference中提取变量名称
        var_ref = node.properties.get("VariableReference", "")
        var_name = "UnknownVariable"
        
        if "MemberName=" in var_ref:
            import re
            match = re.search(r'MemberName="([^"]+)"', var_ref)
            if match:
                var_name = match.group(1)
        
        value_source = traverser.resolve_data_flow(node, "Value")
        if value_source:
            return f"{var_name} = {value_source}"
        else:
            return f"{var_name} = <未知值>"
    
    # 变量获取节点（通常不需要单独的伪代码行）
    elif "K2Node_VariableGet" in node_type:
        return ""  # 变量获取通常作为其他节点的参数
    
    # 动态转换节点
    elif "K2Node_DynamicCast" in node_type:
        target_class = node.properties.get("TargetType", "UnknownType")
        source_obj = traverser.resolve_data_flow(node, "Object")
        result_var = f"As_{target_class.replace('C', '').replace('_', '_')}"
        
        if source_obj:
            return f"{result_var} = cast<{target_class}>({source_obj})"
        else:
            return f"{result_var} = cast<{target_class}>(unknown_object)"
    
    # 宏实例节点（如ForEachLoop）
    elif "K2Node_MacroInstance" in node_type:
        macro_name = node.properties.get("MacroGraphReference.MacroGraph.GraphName", "UnknownMacro")
        
        if "ForEachLoop" in macro_name:
            array_source = traverser.resolve_data_flow(node, "Array")
            if array_source:
                return f"for (index, item) in enumerate({array_source}):"
            else:
                return "for (index, item) in enumerate(unknown_array):"
        else:
            return f"// 宏调用: {macro_name}"
    
    # 注释节点
    elif "EdGraphNode_Comment" in node_type:
        comment_text = node.properties.get("NodeComment", "")
        if comment_text:
            return f"// {comment_text}"
        return ""
    
    # Knot节点（重路由节点）- 通常不需要生成代码
    elif "K2Node_Knot" in node_type:
        return ""
    
    # 默认情况
    else:
        return f"// 节点: {node_name} (类型: {node_type.split('.')[-1]})"


def _extract_function_parameters(node: GraphNode, traverser: GraphTraverser) -> List[str]:
    """
    提取函数调用节点的参数
    """
    params = []
    
    # 遍历输入引脚，找到参数
    for pin in node.pins:
        if (pin.direction == "input" and 
            pin.pin_type != "exec" and 
            pin.pin_name not in ["self", "Target"]):
            
            param_value = traverser.resolve_data_flow(node, pin.pin_name)
            if param_value:
                params.append(f"{pin.pin_name}={param_value}")
    
    return params


def _adjust_indent_level(node: GraphNode, current_level: int) -> int:
    """
    根据节点类型调整缩进级别
    """
    node_type = node.class_type
    
    # 事件节点和循环节点增加缩进
    if ("K2Node_Event" in node_type or 
        ("K2Node_MacroInstance" in node_type and "ForEachLoop" in str(node.properties))):
        return current_level + 1
    
    return current_level
