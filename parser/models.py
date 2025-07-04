from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union, TYPE_CHECKING
from abc import ABC, abstractmethod
from enum import Enum
import weakref

# 避免循环导入
if TYPE_CHECKING:
    from .symbol_table import Scope


# ============================================================================
# 通用解析中间结构 (Common Parsing Intermediate Structure)
# ============================================================================

@dataclass
class RawObject:
    """
    通用蓝图对象的中间表示
    用于在原始文本解析和领域模型构建之间提供统一的数据结构
    """
    name: str                                           # 对象名称
    class_type: str                                     # 对象类型
    properties: Dict[str, str] = field(default_factory=dict)  # 属性键值对
    children: List['RawObject'] = field(default_factory=list)  # 子对象列表


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
    default_object: Optional[str] = None  # 引脚的默认对象路径（用于K2Node_CreateWidget等节点）


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
# 新架构核心数据结构 (New Architecture Core Data Structures)
# ============================================================================

@dataclass
class ResolutionResult:
    """
    统一解析结果
    包含执行语句和数据表达式，支持统一解析模型
    """
    statements: List['Statement'] = field(default_factory=list)  # 由该pin触发的所有后续执行语句
    expression: Optional['Expression'] = None  # 该pin自身产生的数据值表达式（如果它是数据引脚）


@dataclass
class NodeProcessingResult:
    """
    节点处理结果 - 控制流结果对象
    用于封装节点处理器的所有输出，解决复杂节点的执行流追踪问题
    
    这个类是解决 ForEachLoop 等复杂宏节点执行流不完整问题的核心方案。
    它允许节点处理器同时返回生成的 AST 节点和主执行流应该继续的引脚。
    """
    # 主要生成的AST节点 (例如 LoopNode, BranchNode, FunctionCallNode)
    node: Optional['ASTNode'] = None
    # 主执行流应从哪个引脚继续 (例如 ForEachLoop 的 "Completed" 引脚)
    continuation_pin: Optional['GraphPin'] = None
    # 可选：需要添加到当前作用域的前置语句（例如临时变量声明）
    prelude_statements: List['Statement'] = field(default_factory=list)


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
    新架构：支持双向链接到作用域
    """
    source_location: Optional[SourceLocation] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 新增：指向该节点所在作用域的弱引用（避免循环引用）
    scope: Optional[weakref.ReferenceType] = None
    
    @abstractmethod
    def accept(self, visitor):
        """访问者模式的accept方法"""
        pass
    
    def get_scope(self) -> Optional['Scope']:
        """获取该节点所在的作用域"""
        if self.scope:
            return self.scope()
        return None
    
    def set_scope(self, scope: 'Scope') -> None:
        """设置该节点所在的作用域"""
        if scope:
            self.scope = weakref.ref(scope)


@dataclass
class Expression(ASTNode):
    """
    表达式节点的基类
    表达式产生值但不改变执行流
    """
    # 表达式的类型信息（可选，用于未来扩展）
    expression_type: Optional[str] = None
    # UE 类型信息（从 PinType 提取的完整类型信息）
    ue_type: Optional[str] = None


@dataclass
class Statement(ASTNode):
    """
    语句节点的基类
    语句执行动作并可能改变执行流
    """
    pass


@dataclass
class WidgetNode(ASTNode):
    """
    Widget节点 - 新架构UI AST节点
    用于表示UE5 UserWidget的UI元素层级结构
    继承自ASTNode以统一架构，替代遗留的BlueprintNode
    """
    widget_name: str = ""  # Widget实例名称
    widget_type: str = ""  # Widget类型（如Button, TextBlock等）
    properties: Dict[str, Any] = field(default_factory=dict)  # Widget属性
    children: List['WidgetNode'] = field(default_factory=list)  # 子Widget节点
    
    def accept(self, visitor):
        """访问者模式的accept方法"""
        return visitor.visit_widget_node(self)
    
    def add_child(self, child: 'WidgetNode'):
        """添加子Widget节点"""
        if child not in self.children:
            self.children.append(child)
    
    def find_child_by_name(self, name: str) -> Optional['WidgetNode']:
        """根据名称查找子Widget节点"""
        for child in self.children:
            if child.widget_name == name:
                return child
        return None


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
    属性访问节点 - 增强版
    例如: CloseButton.Button.OnClicked, Actor.Health
    用于表示对对象或结构体属性的访问，支持链式访问
    """
    target: Optional[Expression] = None  # 目标对象或表达式
    property_name: str = ""  # 属性名称
    
    def accept(self, visitor):
        return visitor.visit_property_access(self)


@dataclass
class EventReferenceExpression(Expression):
    """
    事件引用表达式 - 新增
    用于表示对一个可绑定事件的引用
    例如: CloseAttributesMenu, OnMenuOpenChanged_Event
    区别于函数调用，这是对事件本身的引用
    """
    event_name: str = ""
    
    def accept(self, visitor):
        return visitor.visit_event_reference_expression(self)


@dataclass
class LoopVariableExpression(Expression):
    """
    循环变量表达式 - 新增
    用于表示由循环宏（如 ForEachLoop）生成的迭代器变量
    例如: ArrayElement, ArrayIndex, LoopCounter
    通过显式 AST 节点避免降级为 UnknownFunction 占位符
    """
    variable_name: str = ""
    is_index: bool = False  # True 表示索引变量（如 ArrayIndex），False 表示元素变量（如 ArrayElement）
    loop_id: str = ""  # 关联的循环节点 ID，用于区分嵌套循环中的同名变量
    
    def accept(self, visitor):
        return visitor.visit_loop_variable_expression(self)


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
    赋值语句节点 - 增强版
    支持复杂的左值表达式，如属性访问链
    例如: Health = 100, CloseButton.Button.OnClicked = MyEvent
    """
    target: Expression = None  # 赋值目标（左值表达式）
    value_expression: Optional[Expression] = None  # 赋值源（右值表达式）
    is_local_variable: bool = False  # 是否是局部变量声明
    operator: str = "="  # 赋值操作符，支持 "=" 和 "+=" 等
    
    # 向后兼容性属性
    @property
    def variable_name(self) -> str:
        """向后兼容：提取简单变量名"""
        if isinstance(self.target, VariableGetExpression):
            return self.target.variable_name
        elif isinstance(self.target, PropertyAccessNode):
            return self.target.property_name
        else:
            return "UnknownTarget"
    
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


@dataclass
class EventSubscriptionNode(Statement):
    """
    事件订阅节点 - 新增
    用于表示将事件处理器绑定到对象事件的操作
    例如: Button.OnClicked += OnButtonClicked_Event
    用于处理 K2Node_AddDelegate 和 K2Node_AssignDelegate 节点
    """
    source_object: Optional[Expression] = None  # 事件源对象，例如 Button 实例
    event_name: str = ""  # 被订阅的事件名，例如 OnClicked
    handler: Optional[Expression] = None  # 处理事件的函数或自定义事件
    
    def accept(self, visitor):
        return visitor.visit_event_subscription_node(self)


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
    
    # 简化的属性访问器
    @property
    def item_variable_name(self) -> Optional[str]:
        return self.item_declaration.variable_name if self.item_declaration else None
    
    @property
    def index_variable_name(self) -> Optional[str]:
        return self.index_declaration.variable_name if self.index_declaration else None
    
    def accept(self, visitor):
        return visitor.visit_loop_node(self)


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
class GenericCallNode(Statement):
    """
    通用可调用节点 - 新增
    用于表示通用的函数或方法调用（例如 SpawnActorFromClass, LatentAbilityCall 等）
    支持三层梯度处理器策略中的Generic Callable Processor
    """
    target: Optional[Expression] = None  # 调用目标对象
    function_name: str = ""  # 函数或方法名称
    arguments: List[Tuple[str, Expression]] = field(default_factory=list)  # 参数列表
    node_class: str = ""  # 原始节点类型，用于调试
    
    def accept(self, visitor):
        return visitor.visit_generic_call_node(self)


@dataclass
class FallbackNode(Statement):
    """
    备用节点 - 新增
    作为未知节点的优雅降级表示，包含原始节点的核心信息
    确保解析过程永不中断，替代UnsupportedNode异常
    """
    class_name: str = ""  # 节点的类名
    node_name: str = ""   # 节点的名称
    properties: Dict[str, Any] = field(default_factory=dict)  # 节点的关键属性
    pin_info: List[Tuple[str, str, str]] = field(default_factory=list)  # (pin_name, direction, pin_type)
    
    def accept(self, visitor):
        return visitor.visit_fallback_node(self)


@dataclass
class UnsupportedNode(Statement):
    """
    不支持的节点类型 - 保留用于向后兼容
    用于表示解析器尚未支持的蓝图节点类型
    注意：新架构中应优先使用FallbackNode
    """
    class_name: str = ""  # 节点的类名
    node_name: str = ""   # 节点的名称
    
    def accept(self, visitor):
        return visitor.visit_unsupported_node(self)


# Type aliases for convenience
ASTNodeType = Union[Expression, Statement]

# ================================================================
# 统一解析结果契约
# ================================================================

@dataclass
class BlueprintParseResult:
    """统一的蓝图解析结果契约"""
    blueprint_name: str
    blueprint_path: str
    content: Any  # 解析后的AST或Widget节点树
    success: bool
    error_message: Optional[str] = None
