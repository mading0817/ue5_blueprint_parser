"""
通用蓝图对象解析器
使用基于栈的策略解析任何蓝图文本中的 Begin Object...End Object 块
输出统一的 RawObject 中间表示，供各领域构建器使用
"""

import re
from collections import deque
from typing import List, Dict, Optional
from ..models import RawObject


class BlueprintObjectParser:
    """
    通用蓝图对象解析器
    职责：将蓝图文本解析为 RawObject 树状结构
    不包含任何业务逻辑，纯粹的文本结构解析
    """
    
    def __init__(self):
        # 预编译正则表达式以提高性能
        self.begin_obj_with_class_re = re.compile(
            r"Begin Object Class=(?P<class>[\w./_]+) Name=\"(?P<name>[\w_]+)\""
        )
        self.begin_obj_name_only_re = re.compile(
            r"Begin Object Name=\"(?P<name>[\w_]+)\""
        )
        self.property_re = re.compile(r"([\w_()]+)=(.*)")
    
    def parse(self, blueprint_text: str) -> List[RawObject]:
        """
        解析蓝图文本为 RawObject 列表
        
        :param blueprint_text: 蓝图原始文本
        :return: RawObject 根节点列表
        """
        if not blueprint_text or not blueprint_text.strip():
            return []
        
        # 初始化解析状态
        objects_by_name: Dict[str, RawObject] = {}
        object_stack: deque[RawObject] = deque()
        root_objects: List[RawObject] = []
        
        # 逐行解析
        for line_num, raw_line in enumerate(blueprint_text.strip().splitlines(), 1):
            line = raw_line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith("//"):
                continue
            
            # 移除可能的BOM字符
            if line.startswith('\ufeff'):
                line = line[1:]
            
            try:
                # 检查是否是 Begin Object 行
                if self._is_begin_object(line):
                    obj, is_new_object = self._parse_begin_object(line, objects_by_name)
                    if obj:
                        # 只有新对象才需要添加到父对象或根对象列表
                        if is_new_object:
                            if object_stack:
                                object_stack[-1].children.append(obj)
                            else:
                                root_objects.append(obj)
                        object_stack.append(obj)
                
                # 检查是否是 End Object 行
                elif line.startswith("End Object"):
                    if object_stack:
                        object_stack.pop()
                
                # 解析属性行
                elif object_stack:
                    self._parse_property_line(line, object_stack[-1])
                    
            except Exception as e:
                # 解析错误时继续处理下一行，不中断整个解析过程
                print(f"Warning: Failed to parse line {line_num}: {line} - {e}")
                continue
        
        return root_objects
    
    def _is_begin_object(self, line: str) -> bool:
        """检查是否是 Begin Object 行"""
        return line.startswith("Begin Object")
    
    def _parse_begin_object(self, line: str, objects_by_name: Dict[str, RawObject]) -> tuple[Optional[RawObject], bool]:
        """
        解析 Begin Object 行，创建或获取 RawObject
        
        :param line: Begin Object 行文本
        :param objects_by_name: 已创建的对象字典
        :return: (解析出的 RawObject 或 None, 是否为新对象)
        """
        # 尝试匹配 "Begin Object Class=... Name=..." 格式
        class_match = self.begin_obj_with_class_re.search(line)
        if class_match:
            obj_name = class_match.group("name")
            obj_class = class_match.group("class")
            obj = RawObject(name=obj_name, class_type=obj_class)
            
            # 检查是否有 ExportPath 属性
            export_path_match = re.search(r'ExportPath="([^"]+)"', line)
            if export_path_match:
                obj.properties["ExportPath"] = export_path_match.group(1)
            
            objects_by_name[obj_name] = obj
            return obj, True  # 新对象
        
        # 尝试匹配 "Begin Object Name=..." 格式（重新引用已存在的对象）
        name_match = self.begin_obj_name_only_re.search(line)
        if name_match:
            obj_name = name_match.group("name")
            if obj_name in objects_by_name:
                # 返回已存在的对象，用于设置其属性
                return objects_by_name[obj_name], False  # 已存在的对象
            else:
                # 如果对象不存在，创建一个新的空对象
                obj = RawObject(name=obj_name, class_type="")
                objects_by_name[obj_name] = obj
                return obj, True  # 新对象
        
        return None, False
    
    def _parse_property_line(self, line: str, current_obj: RawObject) -> None:
        """
        解析属性行并添加到当前对象
        
        :param line: 属性行文本
        :param current_obj: 当前正在处理的对象
        """
        # 特殊处理 CustomProperties Pin 格式
        if line.startswith("CustomProperties Pin"):
            # 为每个 Pin 创建唯一的键名
            pin_count = len([k for k in current_obj.properties.keys() if k.startswith("CustomProperties Pin")])
            key = f"CustomProperties Pin {pin_count + 1}"
            # 提取括号内的内容作为值
            if '(' in line and ')' in line:
                start = line.find('(')
                end = line.rfind(')')
                value = line[start+1:end]
                current_obj.properties[key] = value
            return
        
        # 处理多行属性（如 LinkedTo）
        if 'LinkedTo=(' in line and ')' not in line:
            # 这是多行属性的开始，暂时存储
            # 注意：这里简化处理，实际项目中可能需要更复杂的多行处理
            pass
        
        # 解析单行属性
        prop_match = self.property_re.match(line)
        if prop_match:
            key, value = prop_match.groups()
            current_obj.properties[key.strip()] = value.strip() 