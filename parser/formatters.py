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
        target_obj = traverser.resolve_data_flow(node, "self") or "self"
        # 若 target_obj 为 cast(expr as Class) 则取 Class 作为调用者
        import re
        m=re.search(r"cast\([^)]* as ([A-Za-z0-9_]+)\)", str(target_obj))
        if m:
            target_obj = m.group(1)
        
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
        
        value_source = traverser.resolve_data_flow(node, var_name) or traverser.resolve_data_flow(node, "Value") or "<Value>"
        if value_source:
            return f"{var_name} = {value_source}"
        else:
            return f"{var_name} = <未知值>"
    
    # 变量获取节点（通常不需要单独的伪代码行）
    elif "K2Node_VariableGet" in node_type:
        return ""  # 变量获取通常作为其他节点的参数
    
    # 动态转换节点
    elif "K2Node_DynamicCast" in node_type:
        target_class_full = node.properties.get("TargetType", "UnknownType")
        import re
        cls_all = re.findall(r"\.([A-Za-z0-9_]+)'", str(target_class_full))
        cls_name = cls_all[-1] if cls_all else str(target_class_full).split('.')[-1].split("'")[0]
        source_obj = traverser.resolve_data_flow(node, "Object")
        return f"cast({source_obj} as {cls_name})"
    
    # 宏实例节点（如ForEachLoop）
    elif "K2Node_MacroInstance" in node_type:
        macro_ref = node.properties.get("MacroGraphReference", "")
        import re
        macro_name_match = re.search(r":([A-Za-z0-9_]+)\'", macro_ref)
        macro_name = macro_name_match.group(1) if macro_name_match else "UnknownMacro"

        # ForEachLoop 特殊处理
        if "ForEachLoop" in macro_name:
            array_source = traverser.resolve_data_flow(node, "Array") or "ArraySource"
            # 同时保留宏注释满足测试用例对 "// Macro:" 的检查
            comment_line = f"// Macro: {macro_name}()"
            loop_line = f"for each (item, index) in {array_source}:"
            return f"{comment_line}\n{loop_line}"
        # 其他宏仅做注释
        return f"// Macro: {macro_name}()"
    
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


class MarkdownGraphFormatter:
    """结构化 Markdown 图格式化器（简化版）

    该实现覆盖了事件、执行序列、分支、ForEachLoop、函数调用、变量赋值、动态转换、宏标记等核心节点，
    旨在让测试用例通过（GREEN 阶段前的最小实现）。
    未来可根据 todo.md 中更严格的规范继续迭代。
    """

    # -------------------------------- PUBLIC API --------------------------------

    def format(self, graph: 'BlueprintGraph') -> str:  # noqa: F821
        """将 BlueprintGraph 转换为结构化 Markdown 字符串。"""
        # 空图或无法解析时
        if graph is None or not graph.nodes:
            return "// 空Graph"

        from .graph_builder import GraphTraverser
        traverser = GraphTraverser(graph)
        sequence = traverser.get_execution_sequence()
        if not sequence:
            return "// 无执行序列"

        lines: list[str] = []
        list_counter: int | None = None  # None 表示当前不是有序列表上下文

        # 遍历执行序列
        for idx, node in enumerate(sequence):
            node_type = node.class_type

            # 事件节点 → 标题
            if "K2Node_Event" in node_type:
                event_name = self._extract_event_name(node)
                provides_pin = self._find_first_output_pin_name(node)
                lines.append(f"#### Event: {event_name} (provides: {provides_pin})")
                continue  # 事件节点不参与后续编号

            # ExecutionSequence 节点 → 重置编号
            if "K2Node_ExecutionSequence" in node_type:
                list_counter = 1  # 开启有序列表
                continue  # 不单独生成行

            # 生成节点行文本
            node_line = self._format_node(node, traverser)
            if not node_line:
                continue

            # 前缀处理：有序列表 or 普通行
            if list_counter is not None:
                lines.append(f"{list_counter}. {node_line}")
                list_counter += 1
            else:
                lines.append(f"- {node_line}")

        return "\n".join(lines)

    # ------------------------------ INTERNAL HELPERS -----------------------------

    @staticmethod
    def _extract_event_name(node: 'GraphNode') -> str:  # noqa: F821
        """从 EventReference 中提取事件名称。"""
        import re
        ref = node.properties.get("EventReference", "")
        match = re.search(r'MemberName="?([^",)]+)', ref)
        if match:
            return match.group(1)
        return node.node_name

    @staticmethod
    def _find_first_output_pin_name(node: 'GraphNode') -> str:  # noqa: F821
        """返回第一个输出引脚名称（非 exec）。"""
        for pin in node.pins:
            if pin.direction == "output" and pin.pin_type != "exec":
                return pin.pin_name
        return "<none>"

    def _format_node(self, node: 'GraphNode', traverser: 'GraphTraverser') -> str:  # noqa: F821
        """按节点类型生成单行/多行 Markdown 字符串。"""
        t = node.class_type

        # --- Branch ---
        if "K2Node_Branch" in t or "IfThenElse" in t:
            condition = traverser.resolve_data_flow(node, "Condition") or "<Condition>"
            return f"if ({condition}):\n    ...\nelse:\n    ..."

        # --- ForEachLoop (宏) ---
        if "K2Node_MacroInstance" in t:
            macro_ref = node.properties.get("MacroGraphReference", "")
            import re
            macro_name_match = re.search(r":([A-Za-z0-9_]+)\'", macro_ref)
            macro_name = macro_name_match.group(1) if macro_name_match else "UnknownMacro"

            # ForEachLoop 特殊处理
            if "ForEachLoop" in macro_name:
                array_source = traverser.resolve_data_flow(node, "Array") or "ArraySource"
                # 同时保留宏注释满足测试用例对 "// Macro:" 的检查
                comment_line = f"// Macro: {macro_name}()"
                loop_line = f"for each (item, index) in {array_source}:"
                return f"{comment_line}\n{loop_line}"
            # 其他宏仅做注释
            return f"// Macro: {macro_name}()"

        # --- 函数调用 ---
        if "K2Node_CallFunction" in t:
            func_name = self._extract_member_name(node.properties.get("FunctionReference", ""))
            target_obj = traverser.resolve_data_flow(node, "self") or "self"
            # 提取参数
            params = _extract_function_parameters(node, traverser)
            param_str = (", ".join(params) if params else "")
            return f"{target_obj}.{func_name}({param_str})"

        # --- 变量赋值 ---
        if "K2Node_VariableSet" in t:
            var_name = self._extract_member_name(node.properties.get("VariableReference", ""))
            # UE5 VariableSet 节点待赋值的输入 pin 名称通常与变量同名，或为 "Value"
            value_source = traverser.resolve_data_flow(node, var_name) or traverser.resolve_data_flow(node, "Value") or "<Value>"
            return f"{var_name} = {value_source}"

        # --- 动态转换 ---
        if "K2Node_DynamicCast" in t:
            target_class_full = node.properties.get("TargetType", "UnknownType")
            import re
            cls_all = re.findall(r"\.([A-Za-z0-9_]+)'", str(target_class_full))
            cls_name = cls_all[-1] if cls_all else str(target_class_full).split('.')[-1].split("'")[0]
            source_obj = traverser.resolve_data_flow(node, "Object")
            return f"cast({source_obj} as {cls_name})"

        # 默认：忽略 Knot / VariableGet 等
        if "K2Node_Knot" in t or "K2Node_VariableGet" in t:
            return ""

        return f"// Node: {node.node_name}"

    # Utility to extract MemberName from mixed reference strings
    @staticmethod
    def _extract_member_name(ref: str) -> str:
        import re
        match = re.search(r'MemberName="?([^",)]+)', ref)
        return match.group(1) if match else "UnknownMember"
