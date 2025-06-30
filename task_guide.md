# UE5 Blueprint Parser: 代码精简与高保真重构指南

## 重构概览

本文档记录了UE5蓝图解析器在"高保真AST生成"阶段的核心重构工作，旨在通过引入**严格契约**、**统一节点身份**、**三层梯度处理器**和**精确作用域管理**，彻底解决解析器输出中存在的`stmt_result_...`临时变量、事件逻辑丢失、`UnknownExpression`和`Unsupported node`问题，同时提升对蓝图语义的还原度（如委托绑定从`=`变为`+=`）。

## 重构目标

-   **彻底消除`UnknownExpression`**：通过引入**`ScopeManager`**，精确管理变量的词法作用域和生命周期。所有数据流中的引用将首先通过作用域管理器查找，确保即使在嵌套循环或复杂数据流中也能正确解析变量，从而**完全消除`"UnknownExpression"`的产生。**
-   **彻底消除`Unsupported node`**：通过实现**三层梯度节点处理策略**（Specialized, Generic Callable, Fallback Processors），确保所有蓝图节点都能被转换为有意义的AST表示。对于无法识别的节点，将生成`FallbackNode`而非抛弃，确保输出的完整性。
-   **修复逻辑丢失**：确保所有`K2Node_Event`、`K2Node_CustomEvent`和`K2Node_ComponentBoundEvent`等事件节点所连接的执行流能够被完整解析，不再出现事件体下方为空的情况。
-   **提升语义保真度**：将`K2Node_AssignDelegate`（委托分配）的解析输出从简单的赋值`=`优化为更符合UE蓝图行为的`+=`（事件绑定）。
-   **强化契约**：在`analyzer`和`processors`之间建立严格的交互契约，明确处理器在不同解析模式下（执行流 vs. 数据流）应返回的AST节点类型。
-   **优化变量命名与符号管理**：确保`K2Node_DynamicCast`等节点生成的转换后变量（如`As Abilities Equipped Panel Controller`）能够正确保留空格，并被准确注册到符号表中，以支持后续的变量引用。

## 核心架构变更与任务分解

### 1. 模型层增强 (`parser/models.py`)

-   **背景/目的**: 为事件引用、委托赋值以及通用的可调用节点和未识别节点提供更精确、健壮的AST表示。
-   **任务**: 
    1.  新增`@dataclass class EventReferenceExpression(Expression)`：包含`event_name: str`和`source_location: SourceLocation`字段，用于数据流中表示事件名。
    2.  修改`AssignmentNode`：增加`operator: str = "="`字段，支持`+=`等操作符。
    3.  **新增`@dataclass class GenericCallNode(Statement)`**：表示通用的函数或方法调用（例如 `SpawnActorFromClass`, `LatentAbilityCall` 等）。
    4.  **新增`@dataclass class FallbackNode(Statement)`**：作为未知节点的优雅降级表示，包含原始节点的核心信息。
-   **状态**: 已完成。

### 2. 格式化层适配 (`parser/formatters.py`)

-   **背景/目的**: 支持新的AST节点和操作符的正确渲染。
-   **任务**: 
    1.  更新`MarkdownEventGraphFormatter._format_expression`：增加对`EventReferenceExpression`的处理，直接输出`event_name`。
    2.  修改`_format_assignment`：使用`node.operator`字段来构建赋值语句。
    3.  **新增`MarkdownEventGraphFormatter`中`_format_generic_call`方法**：用于渲染`GenericCallNode`，例如 `TargetObject.Function(param: Value)`。
    4.  **新增`MarkdownEventGraphFormatter`中`_format_fallback`方法**：用于渲染`FallbackNode`为信息丰富的注释，例如 `// Fallback: K2Node_Message(Param1=Value1)`。
-   **状态**: 已完成。

### 3. 处理器逻辑重构 (`parser/processors.py`)

-   **背景/目的**: 遵循严格契约，实现三层梯度节点处理策略，确保处理器在被要求提供表达式时返回`Expression`，在构建执行流时返回`Statement`。
-   **任务**: 
    1.  **修改`process_generic_event_node`**: 其主要职责仍是返回`EventNode`（`Statement`），用于构建顶级执行流。但在`analyzer`中将确保其作为数据源被引用时，会得到一个`EventReferenceExpression`。
    2.  **重构`process_assign_delegate`**: 
        *   当解析`Delegate`输入引脚时，期望其连接的事件节点（如`K2Node_CustomEvent`）解析为`EventReferenceExpression`。
        *   生成的`AssignmentNode`的`operator`字段应设置为`"+\="`。
    3.  **修复`process_dynamic_cast`中的变量命名与符号注册**：此处理器现在仅负责处理`DynamicCast`的执行流。它将确保从节点的`As...`输出引脚获取正确的变量名（包含空格），并将其注册到符号表中。
    4.  **新增通用可调用节点处理器(`process_generic_callable_node`)**：该处理器将负责解析 `K2Node_SpawnActorFromClass`, `K2Node_LatentAbilityCall`, `K2Node_AddDelegate` 等通用函数/方法调用类节点，并返回 `GenericCallNode`。
    5.  **新增备用处理器(`process_fallback_node`)**：该处理器将负责捕获所有未识别节点的关键信息，并返回 `FallbackNode`。
    6.  **改造现有特殊处理器以使用`ScopeManager`**: 例如 `process_foreach_loop`，在处理开始时调用 `context.scope_manager.enter_scope()`，并将循环变量（如`Array Element`, `Array Index`）注册到 `ScopeManager`。在逻辑处理结束时，**需要通过返回一个特殊的处理结果（例如包含执行流延续引脚和作用域清理指令的`NodeProcessingResult`）来通知分析器调用`context.scope_manager.leave_scope()`。**
-   **状态**: 已完成。

### 4. 分析器核心重构 (`parser/analyzer.py`)

-   **背景/目的**: 彻底废除`stmt_result_`生成逻辑，确保执行流的完整遍历，并深度集成`ScopeManager`以解决`UnknownExpression`。这是本次重构最核心的部分。
-   **任务**: 
    1.  **废除临时变量生成与处理`DynamicCast`表达式**: 在`_resolve_node_expression_direct`中，完全移除处理`isinstance(result, Statement)`的分支，从而杜绝`stmt_result_...`的产生。同时，在此方法中新增`K2Node_DynamicCast`的专门数据流处理逻辑（`_build_cast_expression`），使其能够直接返回`CastExpression`，而非依赖通用处理器。如果处理器返回`Statement`而期望`Expression`，则应明确表示错误或返回`UnsupportedExpression`（此处的`UnsupportedExpression`最终将被`FallbackNode`策略取代）。
    2.  **重构主分析流程(`analyze`方法)**: 
        *   在`analyze`方法开始时，首先识别所有事件入口节点（`K2Node_Event`、`K2Node_CustomEvent`等）。
        *   对每个识别出的事件入口节点，独立调用`_process_node`，确保其完整执行流被解析并添加到AST中。这解决了之前事件逻辑丢失的问题。
        *   **在`analyze`方法初始化`AnalysisContext`时，实例化并初始化`ScopeManager`。**
    3.  **深度集成`ScopeManager`到数据流解析**: 修改`_resolve_data_expression`方法，使其在解析任何引脚数据时，**首先尝试通过`context.scope_manager.lookup_variable(pin.pin_id)`来查找对应的表达式。**如果找到，则直接返回。这确保了局部变量和循环变量的正确解析。
    4.  **更新节点分发逻辑(`_process_node`)**: 移除`UnsupportedNode`的创建逻辑。如果 `node_processor_registry` 中没有找到特定处理器的节点，则统一调用 `process_fallback_node` 来处理。
    5.  **在执行流中处理作用域生命周期**: 修改 `_follow_execution_flow` 或 `_process_node`，使其能够识别特殊处理器返回的包含作用域管理指令的结果，并据此调用 `context.scope_manager.leave_scope()`。
-   **状态**: 已完成。

### 5. 新增模块：作用域管理器 (`parser/scope_manager.py`)

-   **背景/目的**: 提供一套健壮的词法作用域管理机制，以精确追踪和解析蓝图中的变量引用，特别是在嵌套结构（如循环、分支）中。彻底解决`UnknownExpression`的根源问题。
-   **任务**: 
    1.  **创建`parser/scope_manager.py`文件**。
    2.  在该文件中定义`ScopeManager`类，包含`scope_stack: List[Dict[str, Expression]]`用于存储多层作用域的变量映射。
    3.  实现核心API：
        *   `enter_scope()`: 进入一个新的作用域。
        *   `leave_scope()`: 离开当前作用域。
        *   `register_variable(pin_id: str, expression: Expression)`: 在当前作用域中注册一个变量及其对应的AST表达式。
        *   `lookup_variable(pin_id: str) -> Optional[Expression]`: 从当前作用域开始，逐层向上查找变量。
-   **状态**: 已完成。

### 6. 通用工具函数增强 (`parser/common/graph_utils.py`)

-   **背景/目的**: 提升工具函数的健壮性，以支持更复杂的蓝图数据解析。
-   **任务**: 
    1.  **增强`parse_object_path`函数**：重写此函数，使其能够健壮地从各种UE对象路径字符串中（包括`TargetType`属性中的路径，如`Class\'\/Script\/UMG.UserWidget\'`）正确解析出对象或类型名称。
-   **状态**: 已完成。

## 维护指南更新

本次重构后的维护指南更加清晰：

-   **添加新节点处理器**: 
    *   首先评估节点类型：
        *   如果节点具有独特的控制流、作用域管理需求或复杂内部逻辑（如`ForEachLoop`, `Branch`），则创建**专用处理器（Specialized Processor）**。在处理器内部，务必正确调用 `context.scope_manager.enter_scope()` 和 `leave_scope()`，并使用 `context.scope_manager.register_variable()` 注册其数据输出引脚。
        *   如果节点本质上是"对某个目标调用一个函数并传递参数"，则无需创建新处理器，只需将其类名添加到 **通用可调用处理器（Generic Callable Processor）** 的识别列表中。
        *   对于极少数无法归类的节点，无需额外处理，它将自动由 **备用处理器（Fallback Processor）** 捕获。
    *   需明确处理器在两种上下文（执行流或数据流）中应返回的AST类型（`Statement`或`Expression`）。
    *   如果节点既可以作为执行流的起点，又可以作为数据源（如事件节点），则在`analyzer`中调用其处理器时需根据上下文正确引导。

-   **数据流解析**: 当需要获取一个节点作为"值"的表达式时，`analyzer`会期望处理器返回一个`Expression`。所有变量和数据输出引脚的解析，都将依赖于 `ScopeManager` 进行精确查找。
