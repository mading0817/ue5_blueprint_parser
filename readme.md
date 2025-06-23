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

*   **Module**: `parser/analyzer.py`
*   **Input**: The `BlueprintGraph` object from Stage One.
*   **Output**: A Logical Abstract Syntax Tree (AST).
*   **Responsibility**: This stage is the heart of the parser, transforming the raw graph into a semantically rich AST. It employs a **multi-pass analysis** approach inspired by modern compilers to ensure accuracy and robustness.
    *   **Pass 1: Symbol & Dependency Analysis**: The analyzer first traverses the graph to build a `SymbolTable`. This table primarily calculates the usage count for every output pin, which is critical for the "Smart Variable Extraction" logic.
    *   **Pass 2: Context-Aware AST Generation**: In the second pass, the analyzer generates the AST. It carries an `AnalysisContext` object that holds the `SymbolTable`, a memoization cache, and the current execution scope. This context allows the analyzer to make informed decisions.
    *   **AST Nodes**: The tree is built from expressive nodes like `EventNode`, `AssignmentNode`, `BranchNode`, and `FunctionCallNode`. Crucially, it also uses specialized nodes like `LatentActionNode` (to model asynchronous operations like `WaitGameplayEvent` and their callbacks) and `PropertyAccessNode` (to represent accessing a property of an object or struct, like `Payload.EventMagnitude`).
    *   **Smart Variable Extraction**: With the `SymbolTable`, this process is now precise. If a pure function's output pin has a usage count greater than one, an `AssignmentNode` is injected into the correct scope's "prelude," and all subsequent uses are replaced with a `VariableAccessNode`. This prevents logic duplication and maintains readability.
    *   **Extensible Node Processors**: A registry maps blueprint node types to dedicated processing functions, allowing the system to be easily extended to support new kinds of blueprint nodes.

### 3. Stage Three: AST Formatting

*   **Module**: `parser/formatters.py` (refactored)
*   **Input**: The Logical AST from Stage Two.
*   **Output**: A formatted string (e.g., Markdown pseudo-code).
*   **Responsibility**: This stage translates the logical AST into a final textual representation.
    *   **Visitor Pattern**: Formatters are implemented as visitors that traverse the AST. This decouples the logical representation from its presentation.
    *   **Formatting Strategies**: Different strategies can be applied to the same AST to produce different outputs (e.g., a `VerboseStrategy` for detailed debugging vs. a `ConciseStrategy` for a high-level overview).
    *   **Diagnostics**: A `MermaidFormatter` will also be implemented to visualize the generated AST, providing a powerful tool for validation and debugging.

This new architecture replaces the previous, fragmented approach, ensuring that the parsing process is robust, maintainable, and correctly interprets the complex interplay of execution and data flow within UE Blueprints.
