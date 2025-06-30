# UE5 Blueprint Parser: 代码精简与高保真重构指南

## 重构概览

本文档记录了UE5蓝图解析器在"高保真AST生成"阶段的核心重构工作，旨在通过引入**严格契约**、**统一节点身份**，彻底解决解析器输出中存在的`stmt_result_...`临时变量问题和事件逻辑丢失问题，同时提升对蓝图语义的还原度（如委托绑定从`=`变为`+=`）。

## 重构目标

-   **消除临时变量**：彻底废除`parser/analyzer.py`中因处理器返回类型不匹配而产生的`stmt_result_...`临时变量，确保表达式解析的精确命名。
-   **修复逻辑丢失**：确保所有`K2Node_Event`、`K2Node_CustomEvent`和`K2Node_ComponentBoundEvent`等事件节点所连接的执行流能够被完整解析，不再出现事件体下方为空的情况。
-   **提升语义保真度**：将`K2Node_AssignDelegate`（委托分配）的解析输出从简单的赋值`=`优化为更符合UE蓝图行为的`+=`（事件绑定）。
-   **强化契约**：在`analyzer`和`processors`之间建立严格的交互契约，明确处理器在不同解析模式下（执行流 vs. 数据流）应返回的AST节点类型。

## 核心架构变更与任务分解

### 1. 模型层增强 (`parser/models.py`)

-   **背景/目的**: 为事件引用和委托赋值提供更精确的AST表示。
-   **任务**: 
    1.  新增`@dataclass class EventReferenceExpression(Expression)`：包含`event_name: str`和`source_location: SourceLocation`字段，用于数据流中表示事件名。
    2.  修改`AssignmentNode`：增加`operator: str = "="`字段，支持`+=`等操作符。
-   **状态**: 已完成。

### 2. 格式化层适配 (`parser/formatters.py`)

-   **背景/目的**: 支持新的AST节点和操作符的正确渲染。
-   **任务**: 
    1.  更新`MarkdownEventGraphFormatter._format_expression`：增加对`EventReferenceExpression`的处理，直接输出`event_name`。
    2.  修改`_format_assignment`：使用`node.operator`字段来构建赋值语句。
-   **状态**: 已完成。

### 3. 处理器逻辑重构 (`parser/processors.py`)

-   **背景/目的**: 遵循严格契约，确保处理器在被要求提供表达式时返回`Expression`，在构建执行流时返回`Statement`。
-   **任务**: 
    1.  **修改`process_generic_event_node`**: 其主要职责仍是返回`EventNode`（`Statement`），用于构建顶级执行流。但在`analyzer`中将确保其作为数据源被引用时，会得到一个`EventReferenceExpression`。
    2.  **重构`process_assign_delegate`**: 
        *   当解析`Delegate`输入引脚时，期望其连接的事件节点（如`K2Node_CustomEvent`）解析为`EventReferenceExpression`。
        *   生成的`AssignmentNode`的`operator`字段应设置为`"+\="`。
-   **状态**: 已完成。

### 4. 分析器核心重构 (`parser/analyzer.py`)

-   **背景/目的**: 彻底废除`stmt_result_`生成逻辑，并确保执行流的完整遍历。这是本次重构最核心的部分。
-   **任务**: 
    1.  **废除临时变量生成**: 在`_resolve_node_expression_direct`中，完全移除处理`isinstance(result, Statement)`的分支，从而杜绝`stmt_result_...`的产生。如果处理器返回`Statement`而期望`Expression`，则应明确表示错误或返回`UnsupportedExpression`。
    2.  **重构主分析流程(`analyze`方法)**: 
        *   在`analyze`方法开始时，首先识别所有事件入口节点（`K2Node_Event`、`K2Node_CustomEvent`等）。
        *   对每个识别出的事件入口节点，独立调用`_process_node`，确保其完整执行流被解析并添加到AST中。这解决了之前事件逻辑丢失的问题。
-   **状态**: 已完成。

## 维护指南更新

本次重构后的维护指南更加清晰：

-   **添加新节点处理器**: 
    *   需明确处理器在两种上下文（执行流或数据流）中应返回的AST类型（`Statement`或`Expression`）。
    *   如果节点既可以作为执行流的起点，又可以作为数据源（如事件节点），则在`analyzer`中调用其处理器时需根据上下文正确引导。

-   **数据流解析**: 当需要获取一个节点作为"值"的表达式时，`analyzer`会期望处理器返回一个`
