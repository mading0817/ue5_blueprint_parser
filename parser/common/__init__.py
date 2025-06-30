"""
通用工具模块
包含图操作、装饰器、构建器等通用功能
"""

# 基础工具函数
from .graph_utils import (
    find_pin, create_source_location, get_pin_default_value, extract_pin_type, parse_object_path,
    # 引脚别名查找
    find_pin_by_aliases, find_execution_output_pin, find_then_pin, find_else_pin,
    # 节点属性提取
    extract_variable_reference, extract_function_reference, extract_event_name, extract_event_parameters,
    # 参数解析
    parse_function_arguments, should_create_temp_variable_for_node, generate_temp_variable_name,
    # 节点验证
    has_execution_pins, get_output_pins, get_input_pins,
    # 宏节点特殊处理
    extract_macro_name
)

# 装饰器系统
from .decorators import register_processor, node_processor_registry

# 对象解析器
from .object_parser import BlueprintObjectParser

# 构建器工具
from .builder_utils import collect_all_raw_objects

# 为了向后兼容，保留原有的导入方式
__all__ = [
    # 基础工具函数
    'find_pin', 'create_source_location', 'get_pin_default_value', 'extract_pin_type', 'parse_object_path',
    # 引脚别名查找
    'find_pin_by_aliases', 'find_execution_output_pin', 'find_then_pin', 'find_else_pin',
    # 节点属性提取
    'extract_variable_reference', 'extract_function_reference', 'extract_event_name', 'extract_event_parameters',
    # 参数解析
    'parse_function_arguments', 'should_create_temp_variable_for_node', 'generate_temp_variable_name',
    # 节点验证
    'has_execution_pins', 'get_output_pins', 'get_input_pins',
    # 宏节点特殊处理
    'extract_macro_name',
    # 装饰器系统
    'register_processor', 'node_processor_registry',
    # 对象解析器
    'BlueprintObjectParser',
    # 构建器工具
    'collect_all_raw_objects'
] 