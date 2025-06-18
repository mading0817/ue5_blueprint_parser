# 任务清单 (CHECKLIST)

1.  **【环境】** 创建 `requirements.txt` 文件并添加 `Flask` 依赖。
2.  **【环境】** 创建项目目录结构: `parser`, `templates`, `static`。
3.  **【数据模型】** 在 `parser/models.py` 中创建 `BlueprintNode` 数据类，用于替代旧的 `UeObject`。
4.  **【HTML模板】** 将原脚本中的 `HTML_TEMPLATE` 字符串移动到 `templates/index.html` 文件中。
5.  **【CSS样式】** 从 `index.html` 中分离出 CSS 样式，并保存到 `static/style.css` 文件中。同时在 `index.html` 中链接到此 CSS 文件。
6.  **【格式化器】** 在 `parser/formatters.py` 中创建 `to_markdown_tree` 函数。将原 `format_hierarchy_to_string` 的逻辑移入并改造，使其接受 `BlueprintNode` 对象并返回 Markdown 格式的层级树字符串。
7.  **【解析器】** 创建 `parser/blueprint_parser.py` 文件。将原脚本中的 `parse_ue_blueprint`, `build_hierarchy`, `parse_object_path` 核心逻辑迁移至此。
8.  **【解析器重构】** 修改 `parser/blueprint_parser.py` 中的函数，使其：
    *   依赖并使用 `parser.models.BlueprintNode`。
    *   `parse_ue_blueprint` 函数的返回值是一个 `BlueprintNode` 对象的列表（根节点列表），而不是格式化后的字符串。
9.  **【应用层】** 创建 `app.py`，并将原脚本中的 Flask 相关代码移入。
10. **【应用层重构】** 修改 `app.py`，使其：
    *   从 `flask` 导入 `render_template` 而不是 `render_template_string`。
    *   导入 `parser.blueprint_parser` 和 `parser.formatters`。
    *   在 `index` 路由中，调用解析器得到 `BlueprintNode` 树，然后调用格式化器得到 Markdown 字符串，最后使用 `render_template` 渲染 `index.html` 并传递结果。
11. **【代码迁移】** 创建一个名为 `main.py` 的临时文件，并将原始代码粘贴到其中，以便在重构过程中参考。
12. **【清理】** 在所有代码迁移并验证完毕后，删除临时的 `main.py` 文件。
13. **【验证】** 运行 `app.py`，确保整个应用功能与重构前一致。 