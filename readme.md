# UE5 Blueprint Parser: Refactoring Guide

This document outlines the architectural principles for the UE5 Blueprint Parser. The primary goal of recent refactoring efforts is to achieve a **robust, extensible, and high-fidelity system** for converting `.uasset` blueprint text into a human-readable, logical pseudo-code format, focusing on **surgical precision in optimization and future-proofing the architecture**.

The system is architected as a **multi-stage pipeline**, inspired by modern compiler design.

## Guiding Philosophy: Fidelity First

Based on extensive analysis, the parser's core philosophy has been refined to prioritize **high fidelity** over semantic interpretation. The parser's primary responsibility is to be a "recorder" that accurately mirrors the structure and information present in the source blueprint, not an "interpreter" that beautifies or transforms the logic.

This means:
- **No Automatic Simplification**: The parser will **not** automatically convert low-level function calls into high-level operators (e.g., `Not_PreBool(EqualEqual_ObjectObject(...))` will be preserved, not converted to `!=`). This ensures that the raw information from the blueprint is never lost.
- **No Automatic Expansion**: The parser will **not** automatically expand macros. A macro node in the blueprint will be represented as a macro call in the output, preserving the original level of abstraction.
- **Optional Transformations**: Any "beautification" or logic expansion is delegated to optional, post-processing transformation passes, keeping the core parser pure and faithful to the source.

## Core Architecture: A Multi-Stage Pipeline

The parser operates through distinct stages, primarily focusing on **EventGraph (Logic) Parsing** and a specialized path for **UI Widget Parsing**.

### 1. Stage One: EventGraph Construction (Logic Parsing - Initial Phase)

- **Module**: `parser/graph_parser.py`
- **Input**: Raw Blueprint graph text.
- **Output**: A `BlueprintGraph` object.
- **Responsibility**: This stage performs a lossless conversion of the raw text into a foundational graph data structure (`BlueprintGraph`). It parses all nodes, pins, and their explicit `LinkedTo` connections without interpreting their logical meaning.

### 2. Stage Two: High-Fidelity AST Generation (Logic Parsing - Semantic Phase)

- **Module**: `parser/analyzer.py` (orchestrates the process) and `parser/processors.py` (contains specific handlers for each blueprint node type).
- **Input**: The `BlueprintGraph` object from Stage One.
- **Output**: A **structurally accurate Abstract Syntax Tree (AST)**.
- **Responsibility**: This is the heart of the parser. The `analyzer` traverses the `BlueprintGraph`, dispatching to the appropriate handlers in `processors.py` to produce an AST that is a direct logical equivalent of the blueprint's structure.

#### Key Architectural Features:

1.  **Execution-Flow-Driven Traversal**:
    *   The parser's `analyzer` operates by strictly following the execution pins (`exec`) from an entry point (e.g., an Event node). This ensures the resulting AST's control flow (sequences, branches, loops) perfectly matches the blueprint's execution order.

2.  **Context-Aware Structural Handlers**:
    *   As the traverser encounters nodes, it uses specific handlers to build the AST. The key is how it handles complex structures:
    *   **Asynchronous Nodes (`LatentActionNode`)**: Instead of flattening the logic, the parser creates a dedicated `ASTAwaitBlock` (represented by `LatentActionNode`). This block contains the initial async call and a collection of **callback blocks**. Each callback block (e.g., `on ValidData:`, `on Cancelled:`) contains the complete sub-graph of logic that executes when that specific callback delegate is fired. This preserves the essential asynchronous structure.

3.  **Generic Fallback Handler for Extensibility**:
    *   To ensure robustness and support for custom or unknown nodes, the analyzer includes a **Generic Fallback Handler**.
    *   If the parser encounters a node type it doesn't have a specific handler for (like a custom `K2Node_Message`), it does not fail. Instead, the fallback handler inspects the node's pin structure. If the pins match a standard pattern (e.g., `execute` in, `then` out), it infers the node to be a function call and creates a corresponding `ASTFunctionCall` node. This allows the parser to gracefully handle new or project-specific nodes without modification.

### 3. Stage Three: AST Rendering & UI Tree Formatting

- **Module**: `parser/formatters.py`
- **Input**:
    - For EventGraph: A structurally accurate Abstract Syntax Tree (AST) from Stage Two.
    - For UI Widgets: A `WidgetNode` hierarchy (as detailed below).
- **Output**: A formatted string (e.g., Markdown pseudo-code for EventGraph, hierarchical Markdown for UI).
- **Responsibility**: This stage acts as a "printer" that traverses the provided data structure (either an AST or a Widget tree) and renders it into a human-readable format. It is implemented by specialized formatter classes, such as `MarkdownEventGraphFormatter` and `WidgetTreeFormatter`, which inherit from the `Formatter` abstract base class to handle different data types.

### 4. UI Widget Parsing Pipeline (Parallel Path for User Interfaces)

- **Module**: `parser/blueprint_parser.py` (to be refactored into `parser/widget/parser.py`)
- **Input**: Raw Blueprint text for User Widgets.
- **Output**: A hierarchical `WidgetNode` tree.
- **Responsibility**: This dedicated pipeline parses the raw UI blueprint text, builds an indexed representation of UI elements, resolves their parent-child relationships, and constructs a clean `WidgetNode` tree. This tree is then passed to Stage Three for formatting. This stage also focuses on performance optimization, specifically by addressing O(n^2) lookups.

### 5. Common Utilities & Shared Components (`parser/common/`)

- **Module**: `parser/common/` (new directory)
- **Responsibility**: This directory houses high-cohesion, stateless utility functions and shared components used across different parsing stages or domains. Key sub-modules include `graph_utils.py` for common graph traversal and node/pin interaction logic, and `builder_utils.py` for AST node construction helpers. This promotes better code organization and reusability, moving away from a monolithic `utils.py`.

## Current Refactoring & Optimization Focus

Based on the latest analysis, the primary refactoring effort will center on maximizing code reduction and quality within the existing robust architecture. Key areas include:

1.  **Consolidation of Auxiliary Functions**: Many stateless utility functions (e.g., pin finding, property extraction, argument parsing) are currently distributed across `analyzer.py` and `processors.py`. These will be systematically identified and moved into `parser/common/graph_utils.py` and potentially `parser/common/builder_utils.py` to centralize common graph and AST-building operations.
2.  **Elimination of Redundancy**: Address minor code duplications, such as aliased pin name lookups (e.g., "then" vs. "True"), by creating unified helper functions in `parser/common/graph_utils.py`.
3.  **Code Simplification**: While no significant "dead code" was found due to the dispatcher pattern, functions with complex internal logic (e.g., `_resolve_data_expression` in `analyzer.py`) will be reviewed for opportunities to decompose them into smaller, more manageable private methods within their respective classes, where applicable.

This surgical approach aims to enhance code clarity, maintainability, and reusability without altering the established pipeline or core functionality.
