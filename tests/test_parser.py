import sys
import os

# 将项目根目录添加到Python路径中
# 这对于从tests目录运行脚本时，能够找到parser模块至关重要
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parser.blueprint_parser import parse_ue_blueprint_to_nodes
from parser.formatters import format_nodes_to_markdown

def run_test():
    """
    运行解析器和格式化器的测试。
    """
    print("==================== Running Parser Test ====================")
    test_file_path = r"c:\\Users\\Martin\\Desktop\\example_1.txt"
    try:
        with open(test_file_path, 'r', encoding='utf-8') as f:
            test_blueprint_text = f.read()

        print(f"Successfully read test file: {test_file_path}")

        # 1. 调用解析器
        parsed_nodes = parse_ue_blueprint_to_nodes(test_blueprint_text)
        if parsed_nodes:
            print(f"Parser returned {len(parsed_nodes)} root node(s).")
        else:
            print("Parser did not return any nodes.")

        # 2. 调用格式化器
        formatted_result = format_nodes_to_markdown(parsed_nodes)

        # 3. 打印结果
        print("-------------------- Parsed Result --------------------")
        print(formatted_result)
        print("-------------------------------------------------------")

    except FileNotFoundError:
        print(f"ERROR: Test file not found at {test_file_path}")
    except Exception as e:
        print(f"An error occurred during the test: {e}", file=sys.stderr)

    print("==================== Test Finished ====================")

if __name__ == '__main__':
    run_test() 