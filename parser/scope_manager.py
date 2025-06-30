"""
作用域管理器模块
提供精确的词法作用域管理，用于追踪和解析蓝图中的变量引用
特别是在嵌套结构（如循环、分支）中的变量可见性
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .models import Expression


@dataclass
class ScopeManager:
    """
    作用域管理器
    使用栈结构管理多层嵌套的词法作用域
    支持变量注册、查找和作用域生命周期管理
    """
    # 作用域栈：每个作用域是一个字典，映射 pin_id/variable_name -> Expression
    scope_stack: List[Dict[str, Expression]] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化时创建全局作用域"""
        if not self.scope_stack:
            self.scope_stack.append({})  # 全局作用域
    
    def enter_scope(self) -> None:
        """
        进入一个新的作用域
        在处理循环、分支等结构时调用
        """
        self.scope_stack.append({})
    
    def leave_scope(self) -> None:
        """
        离开当前作用域
        在循环、分支结构结束时调用
        """
        if len(self.scope_stack) > 1:  # 保留全局作用域
            self.scope_stack.pop()
    
    def register_variable(self, pin_id: str, expression: Expression) -> None:
        """
        在当前作用域中注册一个变量及其对应的AST表达式
        
        Args:
            pin_id: 引脚ID或变量名，用作查找键
            expression: 对应的AST表达式节点
        """
        if not self.scope_stack:
            self.scope_stack.append({})
        
        current_scope = self.scope_stack[-1]
        current_scope[pin_id] = expression
    
    def lookup_variable(self, pin_id: str) -> Optional[Expression]:
        """
        从当前作用域开始，逐层向上查找变量
        
        Args:
            pin_id: 要查找的引脚ID或变量名
            
        Returns:
            找到的表达式节点，如果未找到则返回None
        """
        # 从最内层作用域开始查找
        for scope in reversed(self.scope_stack):
            if pin_id in scope:
                return scope[pin_id]
        
        return None
    
    def get_current_scope_variables(self) -> Dict[str, Expression]:
        """
        获取当前作用域中的所有变量
        主要用于调试和测试
        """
        if not self.scope_stack:
            return {}
        return self.scope_stack[-1].copy()
    
    def get_all_visible_variables(self) -> Dict[str, Expression]:
        """
        获取当前可见的所有变量（从所有作用域层级）
        变量名冲突时，内层作用域优先
        """
        visible_vars = {}
        
        # 从外层到内层合并，内层覆盖外层
        for scope in self.scope_stack:
            visible_vars.update(scope)
        
        return visible_vars
    
    def get_scope_depth(self) -> int:
        """获取当前作用域深度"""
        return len(self.scope_stack)
    
    def clear_all_scopes(self) -> None:
        """清空所有作用域，重新初始化为只有全局作用域"""
        self.scope_stack = [{}] 