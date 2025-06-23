# UE5 Blueprint Parser – Tasks Guide

> 本文件用于跟踪项目整体任务、里程碑进度以及待办事项。
> 
> 规则：
> 1. 所有里程碑数目固定为 **10**。
> 2. 每个里程碑包含 **3–5** 颗粒度清晰的任务。
> 3. 已完成任务标注 `✅ Completed`，进行中标注 `🚧 In-Progress`，未启动标注 `🕒 Pending`。

---

## Milestone 1 – Core Architecture Upgrade ✅ Completed
1. Introduce three-stage pipeline (Graph → AST → Formatter). ✅ Completed
2. Implement `Unified Resolution Model` and replace dual-pass logic. ✅ Completed
3. Refactor `SymbolTable` into scoped tree with bidirectional AST links. ✅ Completed
4. Enhance AST with `PropertyAccessNode`, `EventReferenceExpression`, upgraded `AssignmentNode`. ✅ Completed

## Milestone 2 – Loop & Delegate Semantics ✅ Completed
1. Add `LoopVariableExpression` node to models. ✅ Completed
2. Implement pin→AST binding in `_process_foreach_macro`, register iterator/index vars into symbol table. ✅ Completed
3. Extend `_resolve_data_expression` to check `pin_ast_map` before symbol table lookup. ✅ Completed
4. Update formatters to support `visit_loop_variable_expression`. ✅ Completed
5. Test with example_1.txt to verify UnknownFunction elimination. ✅ Completed

**实现详情**：
- 新增 `LoopVariableExpression` AST 节点类，用于表示循环宏生成的迭代器变量
- 在 `AnalysisContext` 中添加 `pin_ast_map` 字段，建立 pin ID → AST 表达式的直接映射
- 修改 `_process_foreach_macro` 方法，为 "Array Element" 和 "Array Index" 输出引脚创建 `LoopVariableExpression` 并注册到 `pin_ast_map`
- 优化 `_resolve_data_expression` 方法，优先检查源引脚的 `pin_ast_map` 映射，避免降级为 `UnknownFunction`
- 在所有格式化器中实现 `visit_loop_variable_expression` 方法
- 测试验证：example_1.txt 解析结果中不再包含 `UnknownFunction`，`ArrayIndex` 正确显示为循环变量

## Milestone 3 – ForEachLoop Execution Flow Fix ✅ Completed
1. Introduce `NodeProcessingResult` data class for complex node processing. ✅ Completed
2. Refactor `_process_foreach_macro` to return `NodeProcessingResult` with `continuation_pin`. ✅ Completed
3. Enhance `_follow_execution_flow` to handle `pending_continuation_pin` from complex nodes. ✅ Completed
4. Add `pending_continuation_pin` field to `AnalysisContext` for proper state management. ✅ Completed
5. Test and verify complete execution flow parsing for example_1.txt (3 loops). ✅ Completed

**实现详情**：
- 新增 `NodeProcessingResult` 类，用于封装复杂节点的处理结果（AST节点 + 延续执行引脚）
- 重构 `_process_foreach_macro` 方法，使其正确处理 `Completed` 引脚并返回 `NodeProcessingResult`
- 增强 `_follow_execution_flow` 方法，支持从 `pending_continuation_pin` 继续执行流追踪
- 在 `AnalysisContext` 中添加 `pending_continuation_pin` 字段，规范化状态管理
- 测试验证：example_1.txt 现在正确解析出所有3个串联的 ForEachLoop，解决了执行流不完整的重大问题

## Milestone 4 – Additional Standard Macros 🕒 Pending
1. Support `ForLoopWithBreak` macro (LoopCounter, ArrayIndex). 🕒 Pending
2. Support `WhileLoop` macro with `LoopConditionResult`. 🕒 Pending
3. Introduce generic macro handler registry for easy extension. 🕒 Pending
4. Refactor duplicate macro code into utility helpers. 🕒 Pending

## Milestone 5 – Latent Actions & Callbacks 🕒 Pending
1. Finalise `LatentActionNode` AST semantics. 🕒 Pending
2. Auto-infer callback parameter declarations. 🕒 Pending
3. Improve formatter to output nested callbacks in readable blocks. 🕒 Pending

## Milestone 6 – Error Recovery & Diagnostics 🕒 Pending
1. Implement graceful skip for malformed links instead of aborting parse. 🕒 Pending
2. Add diagnostic messages with source location for unresolved pins. 🕒 Pending
3. Provide "debug mode" formatter for verbose troubleshooting. 🕒 Pending

## Milestone 7 – Performance Optimisation 🕒 Pending
1. Memoize heavy graph traversals; profile hot-spots. 🕒 Pending
2. Implement incremental parse cache keyed by blueprint hash. 🕒 Pending
3. Parallelise graph parsing where safe. 🕒 Pending

## Milestone 8 – Output Formats Expansion 🕒 Pending
1. JSON serialiser for AST (machine-readable). 🕒 Pending
2. Mermaid sequence/flow diagrams (graphical). 🕒 Pending
3. Switchable verbosity strategies in Markdown formatter. 🕒 Pending

## Milestone 9 – Web UI Enhancements 🕒 Pending
1. Improve Flask templates for dark/light themes. 🕒 Pending
2. Add file upload & drag-drop support. 🕒 Pending
3. Integrate live preview of Mermaid diagrams. 🕒 Pending

## Milestone 10 – Integration & CI/CD 🕒 Pending
1. GitHub Action for test suite & lint. 🕒 Pending
2. Automatic deployment to Vercel on push. 🕒 Pending
3. Release versioning & changelog generator. 🕒 Pending

## Milestone 11 – Documentation & Polishing 🕒 Pending
1. Complete user/developer docs with examples. 🕒 Pending
2. Record architecture decision log (ADR) entries. 🕒 Pending
3. Prepare presentation & demo assets. 🕒 Pending
