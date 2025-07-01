# Task Guide: UE5 Blueprint Parser

This document tracks the major development tasks, their status, and the context behind them.

## Milestone 1: Foundational Parser Refactoring (Completed)

This milestone focused on refactoring the core parsing engine to be more robust, extensible, and high-fidelity.

### Completed Tasks

- [x] **Refactor Widget Parser**:
    - **Context**: The original Widget parser produced a flat list, making it impossible to understand the UI's hierarchical structure. It also outputted raw, unhelpful property values like `NSLOCTEXT`.
    - **Resolution**:
        1.  Fixed the `parse_object_path` utility in `parser/common/graph_utils.py` to correctly establish parent-child relationships from `Slot` data.
        2.  Refactored the `WidgetTreeFormatter` to use a recursive approach, correctly rendering the UI tree with proper indentation.
        3.  Implemented an extensible property cleaner within the `WidgetTreeFormatter` to convert `NSLOCTEXT` into readable text.

- [x] **Decouple Formatters**:
    - **Context**: The `graph_formatter` and `widget_formatter` were tightly coupled in a single `parser/formatters.py` file, violating the Single Responsibility Principle and creating maintenance risks.
    - **Resolution**: The `formatters.py` file was split into a dedicated `parser/formatters/` package with clear separation of concerns (`base.py`, `graph_formatter.py`, `widget_formatter.py`).

## Milestone 2: Future Enhancements (To-Do)

This milestone outlines potential next steps for improving the parser.

### Potential Tasks

- [ ] **Enhance Property Filtering**: Allow the `WidgetTreeFormatter` to accept a configurable list of properties to display, giving the user more control over the output verbosity.
- [ ] **Refactor Tests for Modularity**: Create separate test files (`test_graph_formatter.py`, `test_widget_formatter.py`) to mirror the new modular structure of the `formatters` package.
- [ ] **Support more `FText` variants**: Extend the property cleaner to handle other localization macros like `LOCTEXT`.
- [ ] **Add Layout Property Support**: Optionally display layout-specific properties from `Slot` objects (e.g., `Padding`, `Alignment`) to provide a more complete UI picture.
