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
    *   The parser's `analyzer` operates by strictly following the execution pins (`exec`) from an entry point (e.g., an Event node). This ensures the resulting AST's control flow (sequences, branches, loops) perfectly matches the blueprint's execution order. It now correctly traverses all execution paths originating from event nodes, resolving the previously missing logic.

2.  **Unified Node Identity & Strict Processor Contract**:
    *   As the traverser encounters nodes, it uses specific handlers to build the AST. A key enhancement is the implementation of a **Strict Processor Contract**. Processors are now explicitly designed to return either a `Statement` (for execution flow) or an `Expression` (for data flow/value resolution).
    *   This ensures that any node, when referenced as a data source, provides a meaningful `Expression` (e.g., `EventReferenceExpression` for event names) rather than a generic `Statement` that would lead to temporary variable generation (`stmt_result_...`).
    *   This also enables high-fidelity representation of delegate assignments, such as `Button.OnClicked += OnClicked_Event`.

3.  **Refined Fallback Handling for Extensibility**:
    *   The analyzer's fallback mechanism has been refined. It no longer generates generic temporary variables (`stmt_result_...`) for known node types whose processors fail to return an `Expression` when one is expected. Instead, this indicates a design flaw in the processor or an `UnsupportedExpression` is explicitly returned.
    *   The generic fallback is now strictly reserved for truly unknown or unhandled node types, maintaining robustness while enforcing a cleaner AST generation for recognized patterns.

### 3. Stage Three: AST Rendering & UI Tree Formatting

- **Module**: `parser/formatters.py`
- **Input**:
    - For EventGraph: A structurally accurate Abstract Syntax Tree (AST) from Stage Two.
    - For UI Widgets: A `WidgetNode` hierarchy (as detailed below).
- **Output**: A formatted string (e.g., Markdown pseudo-code for EventGraph, hierarchical Markdown for UI).
- **Responsibility**: This stage acts as a a "printer" that traverses the provided data structure (either an AST or a Widget tree) and renders it into a human-readable format. It is implemented by specialized formatter classes, such as `MarkdownEventGraphFormatter` and `WidgetTreeFormatter`, which inherit from the `Formatter` abstract base class to handle different data types. It has been updated to correctly interpret and display new AST nodes like `EventReferenceExpression` and enhanced `AssignmentNode` operators (e.g., `+=`).

### 4. UI Widget Parsing Pipeline (Parallel Path for User Interfaces)

- **Module**: `parser/blueprint_parser.py` (to be refactored into `parser/widget/parser.py`)
- **Input**: Raw Blueprint text for User Widgets.
- **Output**: A hierarchical `WidgetNode` tree.
- **Responsibility**: This dedicated pipeline parses the raw UI blueprint text, builds an indexed representation of UI elements, resolves their parent-child relationships, and constructs a clean `WidgetNode` tree. This tree is then passed to Stage Three for formatting. This stage also focuses on performance optimization, specifically by addressing O(n^2) lookups.

### 5. Common Utilities & Shared Components (`parser/common/`)

- **Module**: `parser/common/` (new directory)
- **Responsibility**: This directory houses high-cohesion, stateless utility functions and shared components used across different parsing stages or domains. Key sub-modules include `graph_utils.py` for common graph traversal and node/pin interaction logic, and `builder_utils.py` for AST node construction helpers. This promotes better code organization and reusability, moving away from a monolithic `utils.py`.

## Current Refactoring & Optimization Focus

Based on the latest analysis, the primary refactoring effort centered on establishing a **Strict Contract** between the `analyzer` and `processors` for handling Statement and Expression types. This involved:

1.  **Elimination of Implicit Temporary Variable Generation**: The problematic `stmt_result_...` fallback in `analyzer.py` has been removed. Processors are now strictly required to return the expected AST type (`Statement` for execution, `Expression` for data/value). If a processor returns a `Statement` when an `Expression` is expected, it now explicitly signifies an error, enforcing better design.
2.  **Enhanced Event & Delegate Handling**: Custom Events (`K2Node_CustomEvent`) and other event nodes now provide a distinct `EventReferenceExpression` when used as data sources (e.g., in `AssignDelegate` nodes).
3.  **High-Fidelity Delegate Assignment**: The `AssignDelegate` processor and `AssignmentNode` now support `+=` operator semantics, accurately reflecting the blueprint's event binding behavior.

This surgical approach aims to enhance code clarity, maintainability, and reusability without altering the established pipeline or core functionality.

## Testing and Snapshot Workflow

To ensure consistency and ease of development, the testing workflow has been refined:

1.  **Manual Snapshot Generation**: When blueprint parsing logic changes and new expected outputs are desired, you can manually generate or update snapshots by running the `tests/generate_snapshots.py` script. This script processes all fixture files in `tests/fixtures/` and saves their parsed output as `.snap` files in `tests/snapshots/`.
    ```bash
    .venv/Scripts/python tests/generate_snapshots.py
    ```

2.  **Automated Snapshot Consistency Test**: The `tests/test_snapshots.py` script is used for automated testing (e.g., via `pytest` or CI/CD pipelines). It verifies that the current parser output for all fixtures matches the existing snapshots. If any discrepancies are found, the test will fail.
    ```bash
    .venv/Scripts/python -m pytest tests/test_snapshots.py
    ```

This separation ensures a clear distinction between updating expected results and verifying code correctness.
