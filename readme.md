# Refactoring Guide: UE5 Blueprint Graph Parser

This document outlines the architectural principles for refactoring the UE5 Blueprint Graph Parser. The primary goal is to create a robust, extensible, and accurate system for converting `.uasset` blueprint text into a human-readable, logical pseudo-code format, primarily for consumption by Large Language Models (LLMs) and developers.

The system is architected as a three-stage pipeline, inspired by modern compiler front-end design.

## Core Architecture: A Three-Stage Pipeline

### 1. Stage One: Graph Construction

*   **Module**: `parser/graph_parser.py`
*   **Input**: Raw Blueprint graph text.
*   **Output**: A `BlueprintGraph` object.
*   **Responsibility**: This stage is responsible for a high-fidelity, lossless conversion of the raw text into a foundational graph data structure. It parses all nodes, pins, and their explicit `LinkedTo` connections without interpreting their logical meaning. The output is a complete, raw representation of the blueprint's structure.

### 2. Stage Two: Logical AST Generation

*   **Module**: `parser/analyzer.py` (with new `parser/symbol_table.py`)
*   **Input**: The `BlueprintGraph` object from Stage One.
*   **Output**: A **Semantically-Rich Logical Abstract Syntax Tree (AST)**.
*   **Responsibility**: This stage is the heart of the parser, transforming the raw graph into a semantically complete AST. It abandons fragile, stateful tracking in favor of producing a self-descriptive AST, inspired by modern compiler theory.
    *   **AST-Driven Semantics**: Instead of relying on the analyzer to "remember" the context of a loop or an async callback, the AST nodes themselves are enhanced to declare their own context. For example, a `LoopNode` now contains `VariableDeclaration` objects for its `item` and `index`, and a `LatentActionNode` explicitly lists the variables provided by its callbacks. This makes the AST a standalone, unambiguous representation of the blueprint's logic.
    *   **Formal Symbol Table**: A dedicated `SymbolTable` class manages scopes. As the analyzer traverses the graph, it pushes and pops scopes on the symbol table (e.g., upon entering/leaving a loop body). When resolving a variable, it queries the symbol table directly, which correctly handles scope-based visibility and shadowing.
    *   **Decoupled Data Flow Resolution**: The logic for resolving data (`_resolve_data_expression`) is simplified. Its primary responsibility is to query the `SymbolTable` for variables or to trace connections for direct function call results. This has successfully eliminated the `UnknownFunction` errors caused by the old model's inability to distinguish between a value-providing node and a context-providing node, and now correctly handles complex data structures and intermediate connection nodes like `K2Node_Knot`.
    *   **Extensible Node Processors**: A registry maps blueprint node types to dedicated processing functions. This remains a key feature, allowing the system to be easily extended to support new kinds of blueprint nodes, including those that create new lexical scopes. Recently added support for `K2Node_CustomEvent`, `K2Node_DynamicCast`, `K2Node_AssignDelegate`, and `K2Node_CallArrayFunction` nodes.

### 3. Stage Three: AST Formatting

*   **Module**: `parser/formatters.py` (refactored)
*   **Input**: The Logical AST from Stage Two.
*   **Output**: A formatted string (e.g., Markdown pseudo-code).
*   **Responsibility**: This stage translates the logical AST into a final textual representation.
    *   **Visitor Pattern**: Formatters are implemented as visitors that traverse the AST. This decouples the logical representation from its presentation.
    *   **Formatting Strategies**: Different strategies can be applied to the same AST to produce different outputs (e.g., a `VerboseStrategy` for detailed debugging vs. a `ConciseStrategy` for a high-level overview).
    *   **Diagnostics**: A `MermaidFormatter` will also be implemented to visualize the generated AST, providing a powerful tool for validation and debugging.

This new architecture replaces the previous, fragmented approach, ensuring that the parsing process is robust, maintainable, and correctly interprets the complex interplay of execution and data flow within UE Blueprints.
