# Task Guide: Blueprint Parser Refactoring

This document outlines the concrete tasks required to implement the new three-stage parsing architecture.

---

### Milestone 1: Core AST Framework & Basic Execution Flow

*Goal: Establish the foundational data structures for the AST and implement a basic analyzer capable of parsing simple, linear execution chains.*

-   [x] **Task 1.1: Define Core AST Nodes**: In `parser/models.py`, define the new dataclasses for the Abstract Syntax Tree. This includes a base `ASTNode` and specific nodes for fundamental operations: `ExecutionBlock`, `EventNode`, `AssignmentNode`, and `FunctionCallNode`.

-   [x] **Task 1.2: Define Control Flow AST Nodes**: In `parser/models.py`, add dataclasses for control flow logic: `BranchNode` (for if/else), `LoopNode` (for loops), `MultiBranchNode` (for switches), and `LatentActionNode` (for async tasks).

-   [x] **Task 1.3: Create Graph Analyzer Stub**: Create a new file `parser/analyzer.py` and define the `GraphAnalyzer` class. Implement the node processor registry (dictionary) and the main `analyze` method stub.

-   [x] **Task 1.4: Implement Basic Node Processors**: In `parser/analyzer.py`, implement the initial set of processor functions for basic nodes (`K2Node_Event`, `K2Node_VariableSet`, `K2Node_CallFunction`) and register them. These processors will convert a `GraphNode` into its corresponding `ASTNode`.

---

### Milestone 2: Advanced Flow Analysis

*Goal: Enhance the analyzer to fully support complex control structures and data flow, including nested logic and expression trees.*

-   [x] **Task 2.1: Implement Data Flow Resolution**: In `parser/analyzer.py`, implement the recursive logic to resolve data input pins. This function will traverse data connections to build nested `ASTNode` expressions.

-   [x] **Task 2.2: Implement Smart Variable Extraction**: Enhance the data flow resolution to include the logic for smart temporary variable extraction. A variable should be created only when an output pin's value is used by more than one downstream node.

-   [x] **Task 2.3: Implement Control Flow Processors**: In `parser/analyzer.py`, implement the processors for control flow nodes like `K2Node_IfThenElse` and `K2Node_MacroInstance[ForEachLoop]`. These processors will recursively call the main analyzer for each execution branch (`Then`, `Else`, `LoopBody`) and populate the `true_branch`, `false_branch`, etc., fields of the corresponding AST node.

---

### Milestone 3: Formatter Refactoring & Integration

*Goal: Replace the old formatting logic with a new, AST-based formatter and integrate the full pipeline.*

-   [x] **Task 3.1: Refactor Formatter with Visitor Pattern**: Overhaul `parser/formatters.py`. Create a `MarkdownFormatter` class that traverses the AST using the visitor pattern. Implement `visit_*` methods for each `ASTNode` type to generate the final pseudo-code with correct indentation and structure.

-   [x] **Task 3.2: Implement Formatter Strategies**: Design the formatter to accept different formatting strategies (`VerboseStrategy`, `ConciseStrategy`) to control the level of detail in the output.

-   [x] **Task 3.3: Implement Diagnostic Formatter**: Create a `MermaidFormatter` that also visits the AST but generates a Mermaid graph definition. This will be crucial for debugging and verifying the correctness of the AST.

-   [x] **Task 3.4: Integrate the New Pipeline**: Modify the application's entry point (e.g., in `app.py`) to chain the new components together: `graph_parser -> GraphAnalyzer -> MarkdownFormatter`.

-   [x] **Task 3.5: Cleanup**: Once the new pipeline is fully functional and validated, remove the obsolete `parser/graph_builder.py` file and any legacy code from `parser/formatters.py`.

---

### Milestone 4: Analyzer Refactoring to Multi-Pass Architecture

*Goal: Overhaul the `GraphAnalyzer` to use a robust, two-pass analysis method. This will fix systemic data-flow resolution issues and correctly model complex Blueprint patterns like latent actions and smart temporary variables.*

-   [x] **Task 4.1: Enhance AST Model**: In `parser/models.py`, define the new `PropertyAccessNode`, `LatentActionNode`, and `UnsupportedNode` dataclasses to provide a richer, more accurate representation of Blueprint logic.

-   [x] **Task 4.2: Implement Pass 1 (Symbol & Dependency Analysis)**: In `parser/analyzer.py`, implement the first pass. This involves creating a new method that traverses the graph once to build a `pin_usage_counts` map (the symbol table).

-   [x] **Task 4.3: Implement `AnalysisContext` and Pass 2 Orchestration**: Define the `AnalysisContext` dataclass. Refactor the main `GraphAnalyzer.analyze` method to orchestrate the two passes, first calling the symbol analysis and then feeding its results into the main AST generation pass.

-   [x] **Task 4.4: Refactor `_resolve_data_expression` for Context-Awareness**: Rework the core data resolution logic to accept the `AnalysisContext`. It will now use the `pin_usage_counts` to decide when to extract temporary variables and inject the corresponding `AssignmentNode` into the correct scope prelude (`AnalysisContext.scope_prelude`).

-   [x] **Task 4.5: Implement Latent & Unsupported Node Processors**: Add a dedicated processor for `K2Node_LatentAbilityCall` that generates the new `LatentActionNode`. Also, improve the fallback mechanism to create an `UnsupportedNode` for unknown node types.

-   [x] **Task 4.6: Update Formatters**: In `parser/formatters.py`, add `visit_*` methods to the `MarkdownFormatter` for the new `PropertyAccessNode`, `LatentActionNode`, and `UnsupportedNode` to ensure they are rendered correctly.

-   [x] **Task 4.7: Enhance Integration Tests**: In `tests/test_pipeline_integration.py`, create a comprehensive new test case that uses a complex blueprint (like the one from our discussion) to validate that the new multi-pass analyzer correctly handles temporary variables, branches, and latent actions simultaneously.
