from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
from abc import ABC, abstractmethod
from enum import Enum


@dataclass
class BlueprintNode:
    """
    代表一个UE蓝图中的节点，例如一个Widget控件或一个Slot。
    这是一个通用的数据结构，用于构建解析后的层级树。
    """
    name: str
    class_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List['BlueprintNode'] = field(default_factory=list)
    has_parent: bool = False


@dataclass
class GraphPin:
    """
    代表蓝图Graph节点的引脚信息
    用于存储引脚的连接关系和数据流向
    """
    pin_id: str
    pin_name: str
    direction: str  # "input" 或 "output"
    pin_type: str   # 引脚的数据类型
    linked_to: List[Dict[str, str]] = field(default_factory=list)  # 连接到的其他引脚信息 [{"node_guid": "", "pin_id": ""}]
    default_value: Optional[str] = None  # 引脚的默认值


@dataclass
class GraphNode:
    """
    代表蓝图Graph中的单个节点
    专门用于处理Graph逻辑的节点结构
    """
    node_guid: str
    node_name: str
    class_type: str
    pins: List[GraphPin] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    node_pos_x: float = 0.0
    node_pos_y: float = 0.0
    # 用于图遍历的连接引用
    input_connections: Dict[str, 'GraphNode'] = field(default_factory=dict)  # pin_id -> 连接的源节点
    output_connections: Dict[str, List['GraphNode']] = field(default_factory=dict)  # pin_id -> 连接的目标节点列表


@dataclass
class BlueprintGraph:
    """
    代表完整的蓝图图结构
    包含所有节点和它们之间的连接关系
    """
    graph_name: str
    nodes: Dict[str, GraphNode] = field(default_factory=dict)  # node_guid -> GraphNode
    entry_nodes: List[GraphNode] = field(default_factory=list)  # 入口节点（如事件节点）


@dataclass
class Blueprint:
    """代表一个完整的蓝图资源，包含其层级结构和元数据。"""
    name: str
    root_nodes: List[BlueprintNode]
    graphs: Dict[str, BlueprintGraph] = field(default_factory=dict)  # graph_name -> BlueprintGraph


# ============================================================================
# AST (Abstract Syntax Tree) Node Definitions
# ============================================================================
# 这些类定义了逻辑抽象语法树的节点，用于表示蓝图的程序逻辑
# 而不是原始的图结构

@dataclass
class SourceLocation:
    """
    追踪AST节点的源位置信息
    用于调试和错误报告
    """
    node_guid: Optional[str] = None
    node_name: Optional[str] = None
    pin_id: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class ASTNode(ABC):
    """
    所有AST节点的抽象基类
    提供通用的功能和访问者模式支持
    """
    source_location: Optional[SourceLocation] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    def accept(self, visitor):
        """访问者模式的accept方法"""
        pass


@dataclass
class Expression(ASTNode):
    """
    表达式节点的基类
    表达式产生值但不改变执行流
    """
    # 表达式的类型信息（可选，用于未来扩展）
    expression_type: Optional[str] = None


@dataclass
class Statement(ASTNode):
    """
    语句节点的基类
    语句执行动作并可能改变执行流
    """
    pass


# ============================================================================
# 表达式节点 (Expression Nodes)
# ============================================================================

@dataclass
class LiteralExpression(Expression):
    """
    字面量表达式
    例如: 42, "hello", true
    """
    value: Any = None
    literal_type: str = "unknown"  # "int", "float", "string", "bool", etc.
    
    def accept(self, visitor):
        return visitor.visit_literal_expression(self)


@dataclass
class VariableGetExpression(Expression):
    """
    变量读取表达式
    例如: PlayerHealth, CurrentWeapon
    """
    variable_name: str = ""
    is_self_variable: bool = True  # 是否是self的成员变量
    
    def accept(self, visitor):
        return visitor.visit_variable_get_expression(self)


@dataclass
class FunctionCallExpression(Expression):
    """
    纯函数调用表达式（无exec引脚）
    例如: GetActorLocation(), Add(X, Y)
    """
    target: Optional[Expression] = None  # 调用目标（如果是成员函数）
    function_name: str = ""
    arguments: List[Tuple[str, Expression]] = field(default_factory=list)  # [(param_name, value), ...]
    
    def accept(self, visitor):
        return visitor.visit_function_call_expression(self)


@dataclass
class CastExpression(Expression):
    """
    类型转换表达式
    例如: Cast<PlayerCharacter>(Actor)
    """
    source_expression: Optional[Expression] = None
    target_type: str = ""
    
    def accept(self, visitor):
        return visitor.visit_cast_expression(self)


@dataclass
class MemberAccessExpression(Expression):
    """
    成员访问表达式
    例如: Player.Health, Vector.X
    """
    object_expression: Optional[Expression] = None
    member_name: str = ""
    
    def accept(self, visitor):
        return visitor.visit_member_access_expression(self)


@dataclass
class TemporaryVariableExpression(Expression):
    """
    临时变量引用表达式
    用于引用之前提取的临时变量
    """
    temp_var_name: str = ""
    
    def accept(self, visitor):
        return visitor.visit_temporary_variable_expression(self)


@dataclass
class PropertyAccessNode(Expression):
    """
    属性访问节点
    例如: Payload.EventTag, Actor.Health
    用于表示对对象或结构体属性的访问
    """
    target: Optional[Expression] = None  # 目标对象或表达式
    property_name: str = ""  # 属性名称
    
    def accept(self, visitor):
        return visitor.visit_property_access(self)


@dataclass
class VariableDeclaration(Statement):
    """
    变量声明节点
    用于声明局部变量，包括循环变量和回调参数等
    例如: Item (from ForEach), Index (from ForEach), EventData (from callback)
    """
    variable_name: str = ""
    variable_type: str = "unknown"  # 变量的数据类型
    initial_value: Optional[Expression] = None  # 初始值表达式（可选）
    is_loop_variable: bool = False  # 是否是循环变量
    is_callback_parameter: bool = False  # 是否是回调参数
    
    def accept(self, visitor):
        return visitor.visit_variable_declaration(self)


# ============================================================================
# 语句节点 (Statement Nodes)
# ============================================================================

@dataclass
class ExecutionBlock(Statement):
    """
    执行块，包含一系列顺序执行的语句
    用于表示线性执行流
    """
    statements: List[Statement] = field(default_factory=list)
    
    def accept(self, visitor):
        return visitor.visit_execution_block(self)


@dataclass
class CallbackBlock(ExecutionBlock):
    """
    回调执行块，扩展ExecutionBlock以包含变量声明
    用于表示异步操作的回调，包含回调参数的声明
    """
    declarations: List[VariableDeclaration] = field(default_factory=list)  # 回调参数声明
    
    def accept(self, visitor):
        return visitor.visit_callback_block(self)


@dataclass
class EventNode(Statement):
    """
    事件节点，表示事件处理程序的入口点
    例如: EventBeginPlay, EventTick
    """
    event_name: str = ""
    parameters: List[Tuple[str, str]] = field(default_factory=list)  # [(param_name, param_type), ...]
    body: ExecutionBlock = field(default_factory=ExecutionBlock)
    
    def accept(self, visitor):
        return visitor.visit_event_node(self)


@dataclass
class AssignmentNode(Statement):
    """
    赋值语句节点
    例如: Health = 100, Position = GetActorLocation()
    """
    variable_name: str = ""
    value_expression: Optional[Expression] = None
    is_local_variable: bool = False  # 是否是局部变量声明
    
    def accept(self, visitor):
        return visitor.visit_assignment_node(self)


@dataclass
class FunctionCallNode(Statement):
    """
    函数调用语句（有exec引脚）
    例如: PrintString("Hello"), SetActorLocation(NewPos)
    """
    target: Optional[Expression] = None  # 调用目标
    function_name: str = ""
    arguments: List[Tuple[str, Expression]] = field(default_factory=list)  # [(param_name, value), ...]
    # 返回值赋值（如果有）
    return_assignments: List[Tuple[str, str]] = field(default_factory=list)  # [(var_name, output_pin_name), ...]
    
    def accept(self, visitor):
        return visitor.visit_function_call_node(self)


# ============================================================================
# 控制流节点 (Control Flow Nodes)
# ============================================================================

@dataclass
class BranchNode(Statement):
    """
    分支节点（if/else）
    例如: if (Health > 0) { ... } else { ... }
    """
    condition: Optional[Expression] = None
    true_branch: ExecutionBlock = field(default_factory=ExecutionBlock)
    false_branch: Optional[ExecutionBlock] = None
    
    def accept(self, visitor):
        return visitor.visit_branch_node(self)


class LoopType(Enum):
    """循环类型枚举"""
    FOR_EACH = "foreach"
    FOR_EACH_WITH_BREAK = "foreach_with_break"
    WHILE = "while"
    FOR = "for"


@dataclass
class LoopNode(Statement):
    """
    循环节点
    支持多种循环类型：ForEach, While, For
    """
    loop_type: LoopType = LoopType.FOR_EACH
    # ForEach循环特定
    collection_expression: Optional[Expression] = None
    item_declaration: Optional[VariableDeclaration] = None  # 循环项变量声明
    index_declaration: Optional[VariableDeclaration] = None  # 索引变量声明（可选）
    # While/For循环特定
    condition_expression: Optional[Expression] = None
    # 循环体
    body: ExecutionBlock = field(default_factory=ExecutionBlock)
    
    # 向后兼容的属性（已弃用，但保留以避免破坏现有代码）
    @property
    def item_variable_name(self) -> Optional[str]:
        return self.item_declaration.variable_name if self.item_declaration else None
    
    @property
    def index_variable_name(self) -> Optional[str]:
        return self.index_declaration.variable_name if self.index_declaration else None
    
    def accept(self, visitor):
        return visitor.visit_loop_node(self)


@dataclass
class MultiBranchNode(Statement):
    """
    多分支节点（switch/select）
    例如: switch (State) { case Idle: ..., case Running: ... }
    """
    switch_expression: Optional[Expression] = None
    branches: List[Tuple[str, ExecutionBlock]] = field(default_factory=list)  # [(case_value, body), ...]
    default_branch: Optional[ExecutionBlock] = None
    
    def accept(self, visitor):
        return visitor.visit_multi_branch_node(self)


@dataclass
class LatentActionNode(Statement):
    """
    延迟/异步动作节点
    例如: WaitGameplayEvent, Delay, AsyncLoadAsset
    用于表示异步操作及其回调执行流
    """
    call: Optional['FunctionCallNode'] = None  # 异步函数调用
    callback_exec_pins: Dict[str, 'CallbackBlock'] = field(default_factory=dict)  # 回调执行引脚 {"EventReceived": CallbackBlock, ...}
    
    def accept(self, visitor):
        return visitor.visit_latent_action_node(self)


@dataclass
class ReturnNode(Statement):
    """
    返回语句节点
    用于函数返回值
    """
    return_values: List[Tuple[str, Expression]] = field(default_factory=list)  # [(output_name, value), ...]
    
    def accept(self, visitor):
        return visitor.visit_return_node(self)


# ============================================================================
# 临时变量声明节点
# ============================================================================

@dataclass
class TemporaryVariableDeclaration(Statement):
    """
    临时变量声明
    用于智能变量提取：当纯函数输出被多处使用时创建
    """
    variable_name: str = ""
    value_expression: Optional[Expression] = None
    variable_type: Optional[str] = None
    
    def accept(self, visitor):
        return visitor.visit_temporary_variable_declaration(self)


@dataclass
class UnsupportedNode(Statement):
    """
    不支持的节点类型
    用于表示解析器尚未支持的蓝图节点类型
    """
    class_name: str = ""  # 节点的类名
    node_name: str = ""   # 节点的名称
    
    def accept(self, visitor):
        return visitor.visit_unsupported_node(self)


# Type aliases for convenience
ASTNodeType = Union[Expression, Statement]
