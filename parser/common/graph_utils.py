"""
图操作相关的工具函数
包含与GraphNode、GraphPin操作相关的无状态辅助函数
"""

import re
from typing import Optional, Any, List, Tuple, Set
from ..models import GraphNode, GraphPin, SourceLocation, Expression, LiteralExpression


# ================================================================
# 原有的基础工具函数
# ================================================================

def find_pin(node: GraphNode, pin_name: str, direction: str) -> Optional[GraphPin]:
    """
    在节点中查找指定名称和方向的引脚
    
    :param node: 要搜索的图节点
    :param pin_name: 引脚名称
    :param direction: 引脚方向 ("input" 或 "output")
    :return: 找到的引脚，如果没找到则返回None
    """
    return next((pin for pin in node.pins 
                if pin.pin_name == pin_name and pin.direction == direction), None)


def create_source_location(node: GraphNode) -> SourceLocation:
    """
    创建源位置信息
    
    :param node: 图节点
    :return: 源位置对象
    """
    return SourceLocation(node_guid=node.node_guid, node_name=node.node_name)


def get_pin_default_value(pin: GraphPin) -> Any:
    """
    获取引脚的默认值
    
    :param pin: 图引脚
    :return: 引脚的默认值，如果没有则返回None
    """
    return pin.default_value if pin and pin.default_value is not None else None


def extract_pin_type(pin: GraphPin) -> str:
    """
    从引脚中提取 UE 类型信息
    用于为 AST 节点附加类型信息
    
    :param pin: 图引脚
    :return: 引脚的类型字符串
    """
    if not pin:
        return "unknown"
    
    # 基本类型映射
    type_mapping = {
        "exec": "exec",
        "bool": "bool", 
        "int": "int",
        "float": "float",
        "string": "string",
        "object": "object",
        "struct": "struct",
        "delegate": "delegate"
    }
    
    base_type = type_mapping.get(pin.pin_type, pin.pin_type)
    
    # 对于结构体类型，尝试从 PinSubCategoryObject 中提取更具体的类型
    # 这需要从原始引脚数据中解析，目前返回基本类型
    return base_type 


def parse_object_path(path_string: str) -> Optional[str]:
    """
    从UE对象路径字符串中解析对象名称。
    增强版本，能够处理多种UE路径格式，包括TargetType等复杂情况。

    示例:
        "/Script/UMG.Border'Border_0'"  ->  "Border_0"
        "/Game/BPs/UI/WBP_Foo.WBP_Foo_C'WidgetTree.CanvasPanel_0'" -> "CanvasPanel_0"
        "Class'/Script/UMG.UserWidget'" -> "UserWidget"
        "/Script/UMG.UserWidget" -> "UserWidget"

    :param path_string: UE对象路径字符串
    :return: 提取的对象名称，如果解析失败则返回None
    """
    if not path_string:
        return None

    # 清理字符串，移除前后的双引号和空格，但保留单引号
    cleaned_path = path_string.strip().strip('"').strip()
    
    # 处理 "/Script/UMG.Border'Border_0'" 格式：提取单引号内的内容
    quote_match = re.search(r"'([^']+)'?$", cleaned_path)
    if quote_match:
        # 如果找到单引号，提取单引号内的内容作为对象名
        object_name = quote_match.group(1)
        
        # 处理可能的点分隔路径，如 "WidgetTree.CanvasPanel_0"
        if '.' in object_name:
            # 取最后一个点后的部分
            return object_name.rsplit('.', 1)[-1]
        else:
            # 直接返回单引号内的内容
            return object_name
    
    # 如果没有单引号，按原来的逻辑处理
    path_to_parse = cleaned_path
    
    # 从路径中提取最后的类名或对象名
    # 处理 /Script/UMG.UserWidget 或 /Game/Path.ClassName 格式
    if '.' in path_to_parse:
        # 按点分割，取最后一部分
        name = path_to_parse.rsplit('.', 1)[-1]
    elif '/' in path_to_parse:
        # 按斜杠分割，取最后一部分
        name = path_to_parse.rsplit('/', 1)[-1]
    else:
        # 如果既没有点也没有斜杠，直接使用整个字符串
        name = path_to_parse
    
    # 进一步处理冒号分割的情况（如某些宏或特殊节点）
    if ':' in name:
        name = name.rsplit(':', 1)[-1]
    
    return name if name else None 


# ================================================================
# 引脚别名查找 - 支持多种引脚名称别名
# ================================================================

# 引脚名称别名映射表
PIN_ALIAS_MAP = {
    "then": ["then", "True"],
    "else": ["else", "False"],
    "exec": ["exec", "execute"],
    "condition": ["Condition", "condition"],
    "self": ["self", "Self"],
    "target": ["Target", "TargetArray", "Array"],
}

def find_pin_by_aliases(node: GraphNode, primary_name: str, direction: str) -> Optional[GraphPin]:
    """
    通过别名查找引脚，支持多种可能的引脚名称
    
    :param node: 要搜索的图节点
    :param primary_name: 主要引脚名称
    :param direction: 引脚方向 ("input" 或 "output")
    :return: 找到的引脚，如果没找到则返回None
    """
    aliases = PIN_ALIAS_MAP.get(primary_name, [primary_name])
    
    for alias in aliases:
        pin = find_pin(node, alias, direction)
        if pin:
            return pin
    
    return None


def find_execution_output_pin(node: GraphNode) -> Optional[GraphPin]:
    """
    查找节点的执行输出引脚
    """
    # 优先查找标准的执行输出引脚
    for pin_name in ["then", "exec"]:
        pin = find_pin(node, pin_name, "output")
        if pin:
            return pin
    
    # 如果没找到，查找任何执行类型的输出引脚
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type == "exec":
            return pin
    
    return None


def find_then_pin(node: GraphNode) -> Optional[GraphPin]:
    """查找then输出引脚的便捷函数"""
    return find_pin_by_aliases(node, "then", "output")


def find_else_pin(node: GraphNode) -> Optional[GraphPin]:
    """查找else输出引脚的便捷函数"""
    return find_pin_by_aliases(node, "else", "output")


# ================================================================
# 节点属性提取工具函数 - 从analyzer.py迁移
# ================================================================

def extract_variable_reference(node: GraphNode) -> Tuple[str, bool]:
    """
    提取变量引用信息的公共方法
    
    :param node: 图节点
    :return: (变量名, 是否为self上下文)
    """
    var_reference = node.properties.get("VariableReference", "")
    var_name = "UnknownVariable"
    is_self_context = True  # 默认值
    
    # 提取变量名
    if isinstance(var_reference, dict):
        var_name = var_reference.get("MemberName", "UnknownVariable")
        is_self_context = var_reference.get("bSelfContext", True)
    elif isinstance(var_reference, str) and "MemberName=" in var_reference:
        match = re.search(r'MemberName="([^"]+)"', var_reference)
        var_name = match.group(1) if match else "UnknownVariable"
        
        # 检查 VariableReference 中的 bSelfContext
        if "bSelfContext=True" in var_reference:
            is_self_context = True
        elif "bSelfContext=False" in var_reference:
            is_self_context = False
        else:
            # 如果 VariableReference 中没有 bSelfContext，检查 SelfContextInfo
            self_context_info = node.properties.get("SelfContextInfo", "")
            is_self_context = self_context_info != "NotSelfContext"
    else:
        # 如果没有 VariableReference，检查 SelfContextInfo
        self_context_info = node.properties.get("SelfContextInfo", "")
        is_self_context = self_context_info != "NotSelfContext"
    
    return var_name, is_self_context


def extract_function_reference(node: GraphNode) -> str:
    """
    从节点中提取函数引用信息
    支持多种函数引用格式
    
    :param node: 图节点
    :return: 函数名称
    """
    # 尝试从 FunctionReference 属性获取
    func_ref = node.properties.get("FunctionReference", "")
    if isinstance(func_ref, dict):
        member_name = func_ref.get("MemberName", "")
        if member_name:
            return member_name
    elif isinstance(func_ref, str) and "MemberName=" in func_ref:
        match = re.search(r'MemberName="([^"]+)"', func_ref)
        if match:
            return match.group(1)
    
    # 回退到其他可能的属性
    return (node.properties.get("FunctionName", "") or 
            node.properties.get("ArrayFunction", "") or 
            "UnknownFunction")


def extract_event_name(node: GraphNode) -> str:
    """
    根据节点类型提取事件名称
    
    :param node: 图节点
    :return: 事件名称
    """
    if 'K2Node_Event' in node.class_type:
        # 标准事件节点：从EventReference.MemberName提取
        event_ref = node.properties.get("EventReference", "")
        if isinstance(event_ref, dict):
            return event_ref.get("MemberName", node.node_name)
        elif isinstance(event_ref, str) and "MemberName=" in event_ref:
            match = re.search(r'MemberName="([^"]+)"', event_ref)
            return match.group(1) if match else node.node_name
        else:
            return node.node_name
            
    elif 'K2Node_CustomEvent' in node.class_type:
        # 自定义事件节点：从CustomFunctionName提取
        custom_function_name = node.properties.get("CustomFunctionName", "")
        if isinstance(custom_function_name, str):
            event_name = custom_function_name.strip('"') if custom_function_name else node.node_name
        else:
            event_name = node.node_name
        
        # 如果事件名称为空，使用节点名称
        if not event_name or event_name == "K2Node_CustomEvent":
            event_name = "CustomEvent"
        return event_name
        
    elif 'K2Node_ComponentBoundEvent' in node.class_type:
        # 组件绑定事件：组合ComponentPropertyName.DelegatePropertyName
        component_name = node.properties.get("ComponentPropertyName", "")
        delegate_name = node.properties.get("DelegatePropertyName", "")
        
        if component_name and delegate_name:
            return f"{component_name}.{delegate_name}"
        elif delegate_name:
            return delegate_name
        else:
            return node.node_name
    
    # 默认情况
    return node.node_name


def extract_event_parameters(node: GraphNode) -> List[Tuple[str, str]]:
    """
    自动提取事件参数 - 从非执行的输出引脚中提取
    
    :param node: 图节点
    :return: 参数列表 [(参数名, 参数类型), ...]
    """
    parameters = []
    for pin in node.pins:
        if pin.direction == "output" and pin.pin_type != "exec":
            # 跳过隐藏的引脚和特殊引脚
            if not getattr(pin, 'bHidden', False) and pin.pin_name not in ["OutputDelegate"]:
                parameters.append((pin.pin_name, pin.pin_type))
    return parameters


# ================================================================
# 参数解析工具函数
# ================================================================

def parse_function_arguments(node: GraphNode, exclude_pins: Set[str] = None) -> List[Tuple[str, Any]]:
    """
    解析函数参数的基础信息（不包含表达式解析）
    排除执行引脚和指定的特殊引脚
    
    :param node: 图节点
    :param exclude_pins: 要排除的引脚名称集合，如果为None则使用默认排除列表
    :return: 参数信息列表 [(参数名, 默认值), ...]
    """
    if exclude_pins is None:
        exclude_pins = {"self"}  # 默认只排除self引脚
    
    arguments = []
    
    for pin in node.pins:
        if (pin.direction == "input" and 
            pin.pin_type not in ["exec"] and
            pin.pin_name not in exclude_pins):
            default_value = get_pin_default_value(pin)
            arguments.append((pin.pin_name, default_value))
    
    return arguments


def should_create_temp_variable_for_node(source_node: GraphNode) -> bool:
    """
    判断是否应该为节点创建临时变量
    
    :param source_node: 源节点
    :return: 是否应该创建临时变量
    """
    # 对于复杂的函数调用节点，创建临时变量
    complex_node_types = [
        "K2Node_CallFunction",
        "K2Node_CallArrayFunction", 
        "K2Node_DynamicCast",
        "K2Node_MacroInstance"
    ]
    
    return any(node_type in source_node.class_type for node_type in complex_node_types)


def generate_temp_variable_name(source_node: GraphNode, source_pin_id: str) -> str:
    """
    生成临时变量名称
    
    :param source_node: 源节点
    :param source_pin_id: 源引脚ID
    :return: 临时变量名称
    """
    # 基于节点类型生成有意义的临时变量名
    if "K2Node_CallFunction" in source_node.class_type:
        func_name = extract_function_reference(source_node)
        return f"temp_{func_name}_{source_node.node_guid[:8]}"
    elif "K2Node_DynamicCast" in source_node.class_type:
        return f"temp_cast_{source_node.node_guid[:8]}"
    elif "K2Node_MacroInstance" in source_node.class_type:
        return f"temp_macro_{source_node.node_guid[:8]}"
    else:
        return f"temp_{source_node.node_guid[:8]}"


# ================================================================
# 节点验证工具函数
# ================================================================

def has_execution_pins(node: GraphNode) -> bool:
    """
    检查节点是否有执行引脚
    
    :param node: 图节点
    :return: 是否有执行引脚
    """
    return any(pin.pin_type == "exec" for pin in node.pins)


def get_output_pins(node: GraphNode, exclude_exec: bool = True) -> List[GraphPin]:
    """
    获取节点的输出引脚列表
    
    :param node: 图节点
    :param exclude_exec: 是否排除执行引脚
    :return: 输出引脚列表
    """
    pins = [pin for pin in node.pins if pin.direction == "output"]
    if exclude_exec:
        pins = [pin for pin in pins if pin.pin_type != "exec"]
    return pins


def get_input_pins(node: GraphNode, exclude_exec: bool = True) -> List[GraphPin]:
    """
    获取节点的输入引脚列表
    
    :param node: 图节点
    :param exclude_exec: 是否排除执行引脚
    :return: 输入引脚列表
    """
    pins = [pin for pin in node.pins if pin.direction == "input"]
    if exclude_exec:
        pins = [pin for pin in pins if pin.pin_type != "exec"]
    return pins


# ================================================================
# 宏节点特殊处理工具函数
# ================================================================

def extract_macro_name(node: GraphNode) -> str:
    """
    从宏节点中安全地提取宏名称
    用于支持专用宏处理器的分发逻辑
    
    :param node: 宏节点 (K2Node_MacroInstance)
    :return: 宏名称，如 "ForEachLoop", "WhileLoop" 等，如果无法提取则返回 "Unknown"
    """
    if not node or "K2Node_MacroInstance" not in node.class_type:
        return "Unknown"
    
    # 尝试从 MacroGraphReference 属性中提取宏名称
    macro_ref = node.properties.get("MacroGraphReference", "")
    
    if isinstance(macro_ref, dict):
        # 如果是字典格式，尝试从 MacroGraph 字段提取
        macro_graph = macro_ref.get("MacroGraph", "")
        if isinstance(macro_graph, str) and ":" in macro_graph:
            # 格式通常为: "/Script/Engine.EdGraph'/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'"
            # 提取冒号后的部分，并去除末尾的单引号
            parts = macro_graph.split(":")
            if len(parts) > 1:
                macro_name = parts[-1].rstrip("'")
                return macro_name
    elif isinstance(macro_ref, str):
        # 如果是字符串格式，使用正则表达式提取
        # 匹配形如 MacroGraph="/path/to/macro:MacroName" 的模式
        match = re.search(r'MacroGraph="[^"]*:([^"\']+)', macro_ref)
        if match:
            return match.group(1)
    
    # 如果无法从标准路径提取，尝试其他可能的属性
    # 某些版本的UE可能使用不同的属性名
    for attr_name in ["MacroName", "MacroType", "GraphName"]:
        if attr_name in node.properties:
            value = node.properties[attr_name]
            if isinstance(value, str) and value.strip():
                return value.strip().strip('"')
    
    # 最后的回退：如果所有方法都失败，返回 "Unknown"
    return "Unknown" 