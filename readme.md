# UE5 Blueprint Parser: Refactoring Guide

This document outlines the architectural principles for the UE5 Blueprint Parser. The primary goal is to create a robust, extensible, and high-fidelity system for converting `.uasset` blueprint text into a human-readable, logical pseudo-code format.

The system is architected as a **three-stage pipeline**, inspired by modern compiler design.

## Guiding Philosophy: Fidelity First

Based on extensive analysis, the parser's core philosophy has been refined to prioritize **high fidelity** over semantic interpretation. The parser's primary responsibility is to be a "recorder" that accurately mirrors the structure and information present in the source blueprint, not an "interpreter" that beautifies or transforms the logic.

This means:
- **No Automatic Simplification**: The parser will **not** automatically convert low-level function calls into high-level operators (e.g., `Not_PreBool(EqualEqual_ObjectObject(...))` will be preserved, not converted to `!=`). This ensures that the raw information from the blueprint is never lost.
- **No Automatic Expansion**: The parser will **not** automatically expand macros. A macro node in the blueprint will be represented as a macro call in the output, preserving the original level of abstraction.
- **Optional Transformations**: Any "beautification" or logic expansion is delegated to optional, post-processing transformation passes, keeping the core parser pure and faithful to the source.

## Core Architecture: A Three-Stage Pipeline

### 1. Stage One: Graph Construction

- **Module**: `parser/graph_parser.py`
- **Input**: Raw Blueprint graph text.
- **Output**: A `BlueprintGraph` object.
- **Responsibility**: This stage performs a lossless conversion of the raw text into a foundational graph data structure (`BlueprintGraph`). It parses all nodes, pins, and their explicit `LinkedTo` connections without interpreting their logical meaning.

### 2. Stage Two: High-Fidelity AST Generation

- **Module**: `parser/analyzer.py`
- **Input**: The `BlueprintGraph` object from Stage One.
- **Output**: A **structurally accurate Abstract Syntax Tree (AST)**.
- **Responsibility**: This is the heart of the parser. It traverses the `BlueprintGraph` to produce an AST that is a direct logical equivalent of the blueprint's structure.

#### Key Architectural Features:

1.  **Execution-Flow-Driven Traversal**:
    *   The parser's `analyzer` operates by strictly following the execution pins (`exec`) from an entry point (e.g., an Event node). This ensures the resulting AST's control flow (sequences, branches, loops) perfectly matches the blueprint's execution order.

2.  **Context-Aware Structural Handlers**:
    *   As the traverser encounters nodes, it uses specific handlers to build the AST. The key is how it handles complex structures:
    *   **Asynchronous Nodes (`LatentActionNode`)**: Instead of flattening the logic, the parser creates a dedicated `ASTAwaitBlock` (represented by `LatentActionNode`). This block contains the initial async call and a collection of **callback blocks**. Each callback block (e.g., `on ValidData:`, `on Cancelled:`) contains the complete sub-graph of logic that executes when that specific callback delegate is fired. This preserves the essential asynchronous structure.

3.  **Generic Fallback Handler for Extensibility**:
    *   To ensure robustness and support for custom or unknown nodes, the analyzer includes a **Generic Fallback Handler**.
    *   If the parser encounters a node type it doesn't have a specific handler for (like a custom `K2Node_Message`), it does not fail. Instead, the fallback handler inspects the node's pin structure. If the pins match a standard pattern (e.g., `execute` in, `then` out), it infers the node to be a function call and creates a corresponding `ASTFunctionCall` node. This allows the parser to gracefully handle new or project-specific nodes without modification.

### 3. Stage Three: AST Rendering

- **Module**: `parser/formatters.py`
- **Input**: An AST (typically the high-fidelity raw AST from Stage Two).
- **Output**: A formatted string (e.g., Markdown pseudo-code).
- **Responsibility**: This stage is a straightforward "printer" that traverses the AST and renders it into a human-readable format. It correctly formats all structural nodes, including the nested blocks for asynchronous callbacks, to produce a clear and accurate representation of the blueprint's logic.
