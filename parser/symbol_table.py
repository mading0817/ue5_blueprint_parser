"""
符号表实现
用于管理变量作用域和符号查找
"""

from typing import Dict, List, Optional, Any, Union
from contextlib import contextmanager
from dataclasses import dataclass
from .models import VariableDeclaration, Expression


@dataclass
class Symbol:
    """
    符号表条目
    表示一个已声明的变量或标识符
    """
    name: str
    symbol_type: str  # 变量类型，如 "int", "string", "Actor", etc.
    declaration: Optional[VariableDeclaration] = None  # 关联的声明节点
    value: Optional[Expression] = None  # 当前值表达式（如果已知）
    is_loop_variable: bool = False
    is_callback_parameter: bool = False
    scope_level: int = 0  # 作用域层级


class SymbolTable:
    """
    符号表类
    管理嵌套作用域和符号查找
    """
    
    def __init__(self):
        # 作用域栈：每个作用域是一个符号字典
        self._scopes: List[Dict[str, Symbol]] = []
        self._current_scope_level = 0
        
        # 进入全局作用域
        self.enter_scope()
    
    def enter_scope(self) -> None:
        """进入新的作用域"""
        self._scopes.append({})
        self._current_scope_level += 1
    
    def leave_scope(self) -> None:
        """离开当前作用域"""
        if len(self._scopes) > 1:  # 保持至少一个全局作用域
            self._scopes.pop()
            self._current_scope_level -= 1
    
    def define(self, name: str, symbol_type: str, 
               declaration: Optional[VariableDeclaration] = None,
               value: Optional[Expression] = None,
               is_loop_variable: bool = False,
               is_callback_parameter: bool = False) -> Symbol:
        """
        在当前作用域中定义一个符号
        
        :param name: 符号名称
        :param symbol_type: 符号类型
        :param declaration: 关联的声明节点
        :param value: 当前值表达式
        :param is_loop_variable: 是否是循环变量
        :param is_callback_parameter: 是否是回调参数
        :return: 创建的符号
        """
        if not self._scopes:
            raise RuntimeError("No scope available for symbol definition")
        
        symbol = Symbol(
            name=name,
            symbol_type=symbol_type,
            declaration=declaration,
            value=value,
            is_loop_variable=is_loop_variable,
            is_callback_parameter=is_callback_parameter,
            scope_level=self._current_scope_level
        )
        
        # 在当前作用域中定义符号
        current_scope = self._scopes[-1]
        current_scope[name] = symbol
        
        return symbol
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """
        查找符号，从当前作用域向上搜索
        
        :param name: 符号名称
        :return: 找到的符号，如果不存在则返回None
        """
        # 从最内层作用域开始向外查找
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        
        return None
    
    def lookup_in_current_scope(self, name: str) -> Optional[Symbol]:
        """
        仅在当前作用域中查找符号
        
        :param name: 符号名称
        :return: 找到的符号，如果不存在则返回None
        """
        if not self._scopes:
            return None
        
        current_scope = self._scopes[-1]
        return current_scope.get(name)
    
    def is_defined(self, name: str) -> bool:
        """检查符号是否已定义"""
        return self.lookup(name) is not None
    
    def is_defined_in_current_scope(self, name: str) -> bool:
        """检查符号是否在当前作用域中定义"""
        return self.lookup_in_current_scope(name) is not None
    
    def get_current_scope_level(self) -> int:
        """获取当前作用域层级"""
        return self._current_scope_level
    
    def get_all_symbols_in_scope(self, scope_level: Optional[int] = None) -> Dict[str, Symbol]:
        """
        获取指定作用域中的所有符号
        
        :param scope_level: 作用域层级，None表示当前作用域
        :return: 符号字典
        """
        if scope_level is None:
            scope_level = self._current_scope_level
        
        # 找到对应层级的作用域
        scope_index = scope_level - 1
        if 0 <= scope_index < len(self._scopes):
            return self._scopes[scope_index].copy()
        
        return {}
    
    @contextmanager
    def scoped(self):
        """
        作用域上下文管理器
        用于自动管理作用域的进入和退出
        
        使用方式:
        with symbol_table.scoped():
            symbol_table.define("temp_var", "int")
            # ... 在这个作用域中工作
        # 自动退出作用域
        """
        self.enter_scope()
        try:
            yield self
        finally:
            self.leave_scope()
    
    def debug_print(self) -> str:
        """
        调试用：打印当前符号表状态
        """
        result = []
        result.append(f"SymbolTable (current_level: {self._current_scope_level})")
        
        for i, scope in enumerate(self._scopes):
            level = i + 1
            result.append(f"  Scope {level}:")
            if not scope:
                result.append("    (empty)")
            else:
                for name, symbol in scope.items():
                    result.append(f"    {name}: {symbol.symbol_type} (level: {symbol.scope_level})")
        
        return "\n".join(result) 