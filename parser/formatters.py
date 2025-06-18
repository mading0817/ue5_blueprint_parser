from parser.models import BlueprintNode, Blueprint
from typing import List


def _to_markdown_tree_recursive(node: BlueprintNode, indent_level: int = 0) -> str:
    """
    将单个BlueprintNode及其子节点递归地转换为Markdown格式的无序列表字符串。

    :param node: 要格式化的根节点。
    :param indent_level: 当前的缩进级别。
    :return: Markdown格式的层级字符串。
    """
    # 移除 'FString' 等可能的前缀
    class_type_simple = node.class_type.split('.')[-1]

    # 根据缩进级别生成前缀
    indent_str = "  " * indent_level

    # 格式化当前节点
    result_string = f"{indent_str}- **{node.name}** (`{class_type_simple}`)\n"

    # 递归格式化所有子节点
    for child in node.children:
        result_string += _to_markdown_tree_recursive(child, indent_level + 1)

    return result_string


def format_blueprint_to_markdown(blueprint: Blueprint) -> str:
    """
    将一个BlueprintNode的列表格式化为完整的Markdown层级树。

    :param blueprint: 根节点的列表。
    :return: 完整的Markdown格式字符串。
    """
    if not blueprint or not blueprint.root_nodes:
        return "没有找到可显示的节点。(No displayable nodes found.)"

    final_output = f"#### {blueprint.name} Blueprint Hierarchy\n\n"
    for root in blueprint.root_nodes:
        final_output += _to_markdown_tree_recursive(root)

    return final_output
