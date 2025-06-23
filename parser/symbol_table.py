"""
符号表实现
用于管理变量作用域和符号查找
支持新的统一解析模型架构
"""

from typing import Dict, List, Optional, Any, Union, TYPE_CHECKING
from contextlib import contextmanager
from dataclasses import dataclass, field
import weakref

# 避免循环导入
if TYPE_CHECKING:
    from .models import VariableDeclaration, Expression, ASTNode

# 实际导入
from .models import VariableDeclaration, Expression


@dataclass
class Symbol:
    """
    符号表条目
    表示一个已声明的变量或标识符
    """
    name: str
    symbol_type: str  # 变量类型，如 "int", "string", "Actor", etc.
    declaration: Optional['VariableDeclaration'] = None  # 关联的声明节点
    value: Optional['Expression'] = None  # 当前值表达式（如果已知）
    is_loop_variable: bool = False
    is_callback_parameter: bool = False
    scope_level: int = 0  # 作用域层级


@dataclass
class Scope:
    """
    作用域对象
    表示一个词法作用域，包含符号表和父子关系
    支持与AST节点的双向链接
    """
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    parent: Optional['Scope'] = None
    children: List['Scope'] = field(default_factory=list)
    # 创建此作用域的AST节点的弱引用（避免循环引用）
    owner: Optional[weakref.ReferenceType] = None
    scope_level: int = 0
    
    def define_symbol(self, name: str, symbol_type: str,
                     declaration: Optional['VariableDeclaration'] = None,
                     value: Optional['Expression'] = None,
                     is_loop_variable: bool = False,
                     is_callback_parameter: bool = False) -> Symbol:
        """在此作用域中定义符号"""
        symbol = Symbol(
            name=name,
            symbol_type=symbol_type,
            declaration=declaration,
            value=value,
            is_loop_variable=is_loop_variable,
            is_callback_parameter=is_callback_parameter,
            scope_level=self.scope_level
        )
        self.symbols[name] = symbol
        return symbol
    
    def lookup_local(self, name: str) -> Optional[Symbol]:
        """仅在当前作用域中查找符号"""
        return self.symbols.get(name)
    
    def lookup_recursive(self, name: str) -> Optional[Symbol]:
        """递归向上查找符号"""
        symbol = self.lookup_local(name)
        if symbol:
            return symbol
        if self.parent:
            return self.parent.lookup_recursive(name)
        return None
    
    def get_owner_node(self) -> Optional['ASTNode']:
        """获取创建此作用域的AST节点"""
        if self.owner:
            return self.owner()
        return None


class SymbolTable:
    """
    符号表类
    管理嵌套作用域和符号查找
    新架构：基于Scope对象的树形结构
    """
    
    def __init__(self):
        # 全局作用域
        self._global_scope = Scope(scope_level=1)
        self._current_scope = self._global_scope
        self._scope_counter = 1
    
    @property
    def current_scope(self) -> Scope:
        """获取当前作用域"""
        return self._current_scope
    
    def enter_scope(self, owner_node: Optional['ASTNode'] = None) -> Scope:
        """
        进入新的作用域
        
        :param owner_node: 创建此作用域的AST节点
        :return: 新创建的作用域
        """
        self._scope_counter += 1
        
        # 创建新作用域
        new_scope = Scope(
            parent=self._current_scope,
            scope_level=self._scope_counter
        )
        
        # 设置弱引用到owner节点
        if owner_node:
            new_scope.owner = weakref.ref(owner_node)
        
        # 建立父子关系
        self._current_scope.children.append(new_scope)
        self._current_scope = new_scope
        
        return new_scope
    
    def leave_scope(self) -> Optional[Scope]:
        """
        离开当前作用域
        
        :return: 离开的作用域，如果是全局作用域则返回None
        """
        if self._current_scope.parent:
            old_scope = self._current_scope
            self._current_scope = self._current_scope.parent
            return old_scope
        return None
    
    def define(self, name: str, symbol_type: str, 
               declaration: Optional['VariableDeclaration'] = None,
               value: Optional['Expression'] = None,
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
        return self._current_scope.define_symbol(
            name=name,
            symbol_type=symbol_type,
            declaration=declaration,
            value=value,
            is_loop_variable=is_loop_variable,
            is_callback_parameter=is_callback_parameter
        )
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """
        查找符号，从当前作用域向上搜索
        
        :param name: 符号名称
        :return: 找到的符号，如果不存在则返回None
        """
        return self._current_scope.lookup_recursive(name)
    
    def lookup_in_current_scope(self, name: str) -> Optional[Symbol]:
        """
        仅在当前作用域中查找符号
        
        :param name: 符号名称
        :return: 找到的符号，如果不存在则返回None
        """
        return self._current_scope.lookup_local(name)
    
    def is_defined(self, name: str) -> bool:
        """检查符号是否已定义"""
        return self.lookup(name) is not None
    
    def is_defined_in_current_scope(self, name: str) -> bool:
        """检查符号是否在当前作用域中定义"""
        return self.lookup_in_current_scope(name) is not None
    
    def get_current_scope_level(self) -> int:
        """获取当前作用域层级"""
        return self._current_scope.scope_level
    
    def get_all_symbols_in_scope(self, scope_level: Optional[int] = None) -> Dict[str, Symbol]:
        """
        获取指定作用域中的所有符号
        
        :param scope_level: 作用域层级，None表示当前作用域
        :return: 符号字典
        """
        if scope_level is None:
            return self._current_scope.symbols.copy()
        
        # 递归查找指定层级的作用域
        def find_scope_by_level(scope: Scope, target_level: int) -> Optional[Scope]:
            if scope.scope_level == target_level:
                return scope
            for child in scope.children:
                result = find_scope_by_level(child, target_level)
                if result:
                    return result
            return None
        
        target_scope = find_scope_by_level(self._global_scope, scope_level)
        if target_scope:
            return target_scope.symbols.copy()
        
        return {}
    
    @contextmanager
    def scoped(self, owner_node: Optional['ASTNode'] = None):
        """
        作用域上下文管理器
        用于自动管理作用域的进入和退出
        
        :param owner_node: 创建此作用域的AST节点
        
        使用方式:
        with symbol_table.scoped(some_ast_node):
            symbol_table.define("temp_var", "int")
            # ... 在这个作用域中工作
        # 自动退出作用域
        """
        self.enter_scope(owner_node)
        try:
            yield self
        finally:
            self.leave_scope()
    
    def debug_print(self) -> str:
        """
        调试用：打印当前符号表状态
        """
        def print_scope(scope: Scope, indent: int = 0) -> List[str]:
            lines = []
            prefix = "  " * indent
            owner_info = ""
            if scope.owner and scope.owner():
                owner_node = scope.owner()
                owner_info = f" (owner: {type(owner_node).__name__})"
            
            lines.append(f"{prefix}Scope {scope.scope_level}{owner_info}:")
            
            if not scope.symbols:
                lines.append(f"{prefix}  (empty)")
            else:
                for name, symbol in scope.symbols.items():
                    lines.append(f"{prefix}  {name}: {symbol.symbol_type}")
            
            for child in scope.children:
                lines.extend(print_scope(child, indent + 1))
            
            return lines
        
        result = ["SymbolTable (tree structure):"]
        result.extend(print_scope(self._global_scope))
        result.append(f"Current scope level: {self.get_current_scope_level()}")
        
        return "\n".join(result)

# 保持向后兼容性的别名
# 旧的方法名仍然可用，但内部使用新的实现
# 这样可以确保现有代码在迁移过程中仍能正常工作 