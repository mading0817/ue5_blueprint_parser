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

*   **Module**: `parser/analyzer.py` (new)
*   **Input**: The `BlueprintGraph` object from Stage One.
*   **Output**: A Logical Abstract Syntax Tree (AST).
*   **Responsibility**: This is the core of the new architecture. A `GraphAnalyzer` traverses the raw `BlueprintGraph` and transforms it into a high-level AST that represents the *program's logic*.
    *   **AST Nodes**: The AST is composed of strong-typed nodes like `EventNode`, `AssignmentNode`, `BranchNode` (for `if/else`), `LoopNode`, and `FunctionCallNode`. This structure naturally handles nested logic and scopes.
    *   **Node Processor Registry**: The analyzer uses a dictionary-based registry to map Blueprint node `class_type` names to specific processing functions, making the system easily extensible.
    *   **Data Flow Analysis**: It recursively resolves data-source pins (even on pure function nodes without `exec` pins) to build nested expression trees.
    *   **Smart Variable Extraction**: To balance readability and accuracy, a pure function's result is extracted into a temporary variable only when its output is consumed by multiple downstream nodes.

### 3. Stage Three: AST Formatting

*   **Module**: `parser/formatters.py` (refactored)
*   **Input**: The Logical AST from Stage Two.
*   **Output**: A formatted string (e.g., Markdown pseudo-code).
*   **Responsibility**: This stage translates the logical AST into a final textual representation.
    *   **Visitor Pattern**: Formatters are implemented as visitors that traverse the AST. This decouples the logical representation from its presentation.
    *   **Formatting Strategies**: Different strategies can be applied to the same AST to produce different outputs (e.g., a `VerboseStrategy` for detailed debugging vs. a `ConciseStrategy` for a high-level overview).
    *   **Diagnostics**: A `MermaidFormatter` will also be implemented to visualize the generated AST, providing a powerful tool for validation and debugging.

This new architecture replaces the previous, fragmented approach, ensuring that the parsing process is robust, maintainable, and correctly interprets the complex interplay of execution and data flow within UE Blueprints.
