# UE5 Blueprint Parser: Architecture Guide

This document outlines the architectural principles for the UE5 Blueprint Parser. The system has been successfully refactored to be a **robust, extensible, and high-fidelity system** for converting `.uasset` blueprint text into a human-readable, logical pseudo-code format, focusing on **surgical precision in optimization and future-proofing the architecture**.

The system is architected as a **multi-stage pipeline**, inspired by modern compiler design.

## Guiding Philosophy: Fidelity First

The parser's core philosophy prioritizes **high fidelity** over semantic interpretation. The parser's primary responsibility is to be a "recorder" that accurately mirrors the structure and information present in the source blueprint, not an "interpreter" that beautifies or transforms the logic.

This means:
- **No Automatic Simplification**: The parser does **not** automatically convert low-level function calls into high-level operators (e.g., `Not_PreBool(EqualEqual_ObjectObject(...))` is preserved, not converted to `!=`).
- **No Automatic Expansion**: The parser does **not** automatically expand macros. A macro node in the blueprint is represented as a macro call in the output, preserving the original level of abstraction.
- **Optional Transformations**: Any "beautification" or logic expansion is delegated to optional, post-processing transformation passes, keeping the core parser pure and faithful to the source.

## Core Architecture: A Multi-Stage Pipeline

The parser operates through distinct stages, primarily focusing on **EventGraph (Logic) Parsing** and a specialized path for **UI Widget Parsing**.

### 1. Stage One: EventGraph Construction (Logic Parsing - Initial Phase)
- **Module**: `parser/graph_parser.py`
- **Responsibility**: This stage performs a lossless conversion of the raw text into a foundational graph data structure (`BlueprintGraph`). It parses all nodes, pins, and their explicit `LinkedTo` connections without interpreting their logical meaning.

### 2. Stage Two: High-Fidelity AST Generation (Logic Parsing - Semantic Phase)
- **Module**: `parser/analyzer.py` (orchestrates the process) and `parser/processors.py` (contains specific handlers for each blueprint node type).
- **Responsibility**: This is the heart of the parser. The `analyzer` traverses the `BlueprintGraph`, dispatching to the appropriate handlers in `processors.py` to produce an AST that is a direct logical equivalent of the blueprint's structure.

#### Key Architectural Features:

1.  **Execution-Flow-Driven Traversal**:
    *   The parser's `analyzer` operates by strictly following the execution pins (`exec`) from an entry point (e.g., an Event node). This ensures the resulting AST's control flow perfectly matches the blueprint's execution order.

2.  **Unified Node Identity & Strict Processor Contract**:
    *   Processors are explicitly designed to return either a `Statement` (for execution flow) or an `Expression` (for data flow/value resolution). This contract ensures that any node, when referenced as a data source, provides a meaningful `Expression`, preventing the generation of temporary variables and enabling high-fidelity representation of delegate assignments (e.g., `Button.OnClicked += OnClicked_Event`).

3.  **Three-Tier Processing Strategy for Robustness and Extensibility**:
    *   The parser employs a **three-tier processing strategy** for blueprint nodes, ensuring comprehensive and robust AST generation:
        *   **Specialized Processors**: For nodes with unique execution flow, scope management, or domain-specific context. A key pattern here is the lightweight **"Inject-and-Delegate"** processor (e.g., for `K2Node_LatentAbilityCall`), which handles specific pre-processing (like injecting an implicit parameter) before delegating to the generic processor for the actual function call logic.
        *   **Generic Callable Processor**: A single, intelligent, and fortified processor handles the vast majority of "function-call-like" nodes (e.g., `K2Node_CallFunction`, `K2Node_SpawnActorFromClass`, and interface calls like `K2Node_Message`). Its logic is hardened to **prioritize the `FunctionReference` property** as the single source of truth for the function's name, ensuring high-fidelity parsing.
        *   **Fallback Processor**: For any truly unknown or unhandled node type, a `FallbackNode` is generated. This ensures the parsing process never halts, **eliminating all "Unsupported node" errors**.

4.  **Lexical Scope Manager for Precise Data Flow (`parser/scope_manager.py`)**:
    *   The `ScopeManager` component manages variable visibility and lifetime within the blueprint graph.
    *   **Elimination of `UnknownExpression`**: Nodes that output data (e.g., `ForEachLoop`'s Array Element/Index) explicitly register these outputs into the current scope via the `ScopeManager`. Downstream nodes can then perform a reliable lookup. This guarantees accurate data flow resolution, even in complex nested structures, **permanently eradicating "UnknownExpression" errors**.

### 3. Stage Three: AST Rendering & UI Tree Formatting
- **Module**: `parser/formatters/` (Package)
- **Responsibility**: This stage acts as a "printer" that traverses the provided data structure (either an AST or a Widget tree) and renders it into a human-readable format. This has been refactored into a modular package:
    - `widget_formatter.py`: Handles the recursive, hierarchical rendering of the UI Widget tree, including cleaning up property values like `NSLOCTEXT` into readable text.
    - `graph_formatter.py`: Handles the rendering of the logic AST into Markdown pseudo-code.
    - `base.py`: Contains the abstract base classes for formatters and formatting strategies.

### 4. UI Widget Parsing Pipeline (Parallel Path for User Interfaces)
- **Module**: `parser/widget_parser.py`
- **Responsibility**: This dedicated pipeline parses raw UI blueprint text, resolves parent-child relationships using `Slot` objects, and constructs a clean `WidgetNode` tree. The `parser/common/graph_utils.py` module now correctly parses object paths to ensure these relationships are built with high fidelity. The resulting tree is then passed to the `WidgetTreeFormatter` for hierarchical rendering.

### 5. Common Utilities & Shared Components (`parser/common/` and `parser/scope_manager.py`)
- **Responsibility**: This directory houses high-cohesion, stateless utility functions and shared components. The `parser/scope_manager.py` module specifically handles lexical scope management, promoting better code organization and reusability.

## Refactoring & Error Elimination Summary

The primary refactoring effort centered on establishing a **Strict Contract** between the `analyzer` and `processors`, along with comprehensive error elimination through architectural changes. This involved:

1.  **Elimination of `UnknownExpression`**: Achieved by introducing the `ScopeManager` to precisely track variable visibility across lexical scopes.
2.  **Elimination of `Unsupported node`**: Achieved by implementing the **three-tier processing model** (Specialized, Generic Callable, Fallback Processors) that guarantees every node type is processed into a meaningful AST representation.
3.  **High-Fidelity Delegate Assignment**: The `AssignDelegate` processor and `AssignmentNode` now correctly use `+=` operator semantics, accurately reflecting the blueprint's event binding behavior.
4.  **High-Fidelity Function-Like Node Parsing**: Achieved by unifying logic under a fortified generic processor and removing incorrect special cases, ensuring that nodes like `K2Node_Message` are parsed with full fidelity.
5.  **Specialized Data-Flow Handlers**: The analyzer now includes dedicated logic for correctly resolving common data-flow nodes (like `K2Node_Knot`, `K2Node_Self`, `K2Node_GetArrayItem`) into proper expressions.

**Recent Major Improvements (Completed):**
- **`K2Node_DynamicCast` Full Support**: `DynamicCast` nodes are correctly parsed as `CastExpression` objects.
- **Precise Variable Naming for Cast Results**: Variables for cast results preserve spaces and are properly registered in the symbol table.
- **Enhanced Object Path Parsing**: The `parse_object_path` utility function robustly extracts object names.

## Testing and Snapshot Workflow

To ensure consistency and ease of development, the testing workflow has been refined:

1.  **Manual Snapshot Generation**: When blueprint parsing logic changes, run `tests/generate_snapshots.py` to update the expected outputs.
    ```bash
    .venv/Scripts/python tests/generate_snapshots.py
    ```

2.  **Automated Snapshot Consistency Test**: Run `pytest` on `tests/test_snapshots.py` to verify that the current parser output matches the existing snapshots.
    ```bash
    .venv/Scripts/python -m pytest tests/test_snapshots.py
    ```

This separation ensures a clear distinction between updating expected results and verifying code correctness.
