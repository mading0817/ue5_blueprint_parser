# UE5 Blueprint Parser – Tasks Guide

> This document tracks the project's overall tasks, milestone progress, and to-do items.
>
> **Rules:**
> 1. The total number of milestones is fixed at **10**.
> 2. Each milestone contains **3–5** clearly defined tasks.
> 3. Completed tasks are marked with `✅ Completed`, in-progress tasks with `🚧 In-Progress`, and pending tasks with `🕒 Pending`.

---

## Milestone 1–6 – Previous Work ✅ Completed
> These milestones represent the foundational work completed prior to the latest architectural refactoring, including the initial three-stage pipeline, loop/delegate semantics, and basic widget parsing.

---

## Milestone 7 – Structural Fidelity & Resilience 🚧 In-Progress

> **Context:** This milestone addresses fundamental architectural issues discovered during the analysis of complex blueprints. The goal is to refactor the parser into a **"High-Fidelity Structural Parsing Engine"** that accurately records the blueprint's original logic, including complex control flows and unknown custom nodes, without making interpretive transformations.

1.  **Refactor Async Node Handling** (`analyzer.py`)
    *   **Task**: Rework the `_process_latent_ability_call` handler to correctly create a `LatentActionNode` that models asynchronous operations. The node must contain distinct `CallbackBlock`s for each output execution pin (e.g., `ValidData`), with each block containing the complete AST of its corresponding sub-graph.
    *   **Status**: `🕒 Pending`

2.  **Implement Generic Fallback Handler** (`analyzer.py`)
    *   **Task**: Implement a new `_process_generic_node` function. This handler will act as a fallback when no specific processor is found for a node. It will analyze the node's pin structure to infer its function (e.g., a standard function call) and create the appropriate AST node, ensuring custom nodes like `K2Node_Message` are parsed structurally.
    *   **Status**: `🕒 Pending`

3.  **Update Formatter for Async Structures** (`formatters.py`)
    *   **Task**: Modify the `visit_latent_action_node` method in the `MarkdownFormatter` to render the `LatentActionNode` into a human-readable, nested structure. The output must clearly distinguish the `await` call from its named callback blocks (e.g., `on ValidData: { ... }`).
    *   **Status**: `🕒 Pending`

4.  **Add End-to-End Verification Test** (`tests/`)
    *   **Task**: Create a new test file (`test_structural_parser.py`) that uses `example_1.txt` as input and asserts that the final output precisely matches the expected high-fidelity, structurally correct format.
    *   **Status**: `🕒 Pending`

5.  **Deprecate Obsolete Code**
    *   **Task**: Formally mark any functions from the old parsing model that are made obsolete by the new engine. Use Python's `warnings` module and docstring annotations (`.. deprecated::`) to flag them for future removal.
    *   **Status**: `🕒 Pending`

## Milestone 8 – Advanced Macros & Control Flow 🕒 Pending
1. Support `ForLoopWithBreak` macro.
2. Support `WhileLoop` macro.
3. Introduce a generic macro handler registry for easy extension.
4. Refactor duplicate macro code into utility helpers.

## Milestone 9 – Parser Robustness & Debugging 🕒 Pending
1. Implement graceful skip for malformed links instead of aborting parse.
2. Add diagnostic messages with source location for unresolved pins.
3. Provide "debug mode" formatter for verbose troubleshooting.
4. Implement basic error reporting in the web UI.

## Milestone 10 – Output Formats & UI 🕒 Pending
1. Implement a JSON serializer for the AST (for machine consumption).
2. Implement a Mermaid sequence/flow diagram renderer.
3. Add file upload & drag-drop support to the web UI.
4. Complete user/developer documentation with examples.
