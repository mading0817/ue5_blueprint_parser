"""
快照测试模块
用于确保重构过程中解析器输出的一致性
"""

import os
import pytest
from pathlib import Path
from typing import List, Tuple

# 导入解析器模块
from parser.graph_parser import parse_blueprint_graph
from parser.analyzer import GraphAnalyzer
from parser.formatters import MarkdownEventGraphFormatter, WidgetTreeFormatter
from parser.widget_parser import parse as parse_widget_ast


class SnapshotTester:
    """快照测试器类"""
    
    def __init__(self):
        self.fixtures_dir = Path("tests/fixtures")
        self.snapshots_dir = Path("tests/snapshots")
        self.analyzer = GraphAnalyzer()
        self.graph_formatter = MarkdownEventGraphFormatter()
        self.widget_formatter = WidgetTreeFormatter(show_properties=True)
        
        # 确保快照目录存在
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def get_fixture_files(self) -> List[Path]:
        """获取所有测试文件"""
        return sorted(self.fixtures_dir.glob("*.txt"))
    
    def is_widget_file(self, file_path: Path) -> bool:
        """判断是否为 Widget 文件"""
        return "ui" in file_path.name.lower() or "widget" in file_path.name.lower()
    
    def process_blueprint_file(self, file_path: Path) -> str:
        """处理单个蓝图文件，返回格式化后的Markdown输出"""
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            blueprint_text = f.read()
        
        # 根据文件类型选择不同的处理管道
        if self.is_widget_file(file_path):
            # Widget 解析管道
            widget_nodes = parse_widget_ast(blueprint_text)
            if not widget_nodes:
                return "# 解析失败\n无法解析Widget蓝图文件"
            
            # 格式化为Widget树
            result = self.widget_formatter.format(widget_nodes)
            if not result or result.strip() == "":
                return "# 格式化失败\n无法生成Widget树状结构"
            
            return result
        else:
            # Graph 解析管道
            graph = parse_blueprint_graph(blueprint_text, "EventGraph")
            if not graph:
                return "# 解析失败\n无法解析蓝图文件"
            
            # 分析生成AST
            ast_nodes = self.analyzer.analyze(graph)
            if not ast_nodes:
                return "# 分析失败\n无法生成AST节点"
            
            # 格式化为Markdown
            output_lines = []
            for node in ast_nodes:
                markdown_output = self.graph_formatter.format(node)
                if markdown_output:
                    output_lines.append(markdown_output)
            
            return "\n\n".join(output_lines)
    
    def generate_snapshots(self):
        """生成所有测试文件的快照"""
        fixture_files = self.get_fixture_files()
        
        for fixture_file in fixture_files:
            print(f"正在生成快照: {fixture_file.name}")
            
            try:
                # 处理蓝图文件
                output = self.process_blueprint_file(fixture_file)
                
                # 保存快照
                snapshot_file = self.snapshots_dir / f"{fixture_file.stem}.snap"
                with open(snapshot_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                print(f"快照已保存: {snapshot_file}")
                
            except Exception as e:
                print(f"处理文件 {fixture_file.name} 时出错: {e}")
                # 保存错误信息作为快照
                snapshot_file = self.snapshots_dir / f"{fixture_file.stem}.snap"
                with open(snapshot_file, 'w', encoding='utf-8') as f:
                    f.write(f"# 处理错误\n错误信息: {str(e)}")
    
    def verify_snapshots(self) -> List[Tuple[str, str, str]]:
        """验证当前输出与快照的一致性，返回不一致的文件列表"""
        fixture_files = self.get_fixture_files()
        mismatches = []
        
        for fixture_file in fixture_files:
            snapshot_file = self.snapshots_dir / f"{fixture_file.stem}.snap"
            
            if not snapshot_file.exists():
                mismatches.append((fixture_file.name, "快照文件不存在", ""))
                continue
            
            try:
                # 生成当前输出
                current_output = self.process_blueprint_file(fixture_file)
                
                # 读取快照
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    expected_output = f.read()
                
                # 比较输出
                if current_output != expected_output:
                    mismatches.append((fixture_file.name, expected_output, current_output))
                
            except Exception as e:
                mismatches.append((fixture_file.name, f"处理错误: {str(e)}", ""))
        
        return mismatches


# pytest测试用例
def test_snapshot_consistency():
    """测试快照一致性"""
    tester = SnapshotTester()
    mismatches = tester.verify_snapshots()
    
    if mismatches:
        error_msg = "快照测试失败，以下文件输出不一致:\n"
        for filename, expected, actual in mismatches:
            error_msg += f"\n文件: {filename}\n"
            if expected.startswith("快照文件不存在") or expected.startswith("处理错误"):
                error_msg += f"错误: {expected}\n"
            else:
                error_msg += f"期望输出长度: {len(expected)} 字符\n"
                error_msg += f"实际输出长度: {len(actual)} 字符\n"
                # 显示前100个字符的差异
                if len(expected) > 100:
                    error_msg += f"期望开头: {expected[:100]}...\n"
                else:
                    error_msg += f"期望内容: {expected}\n"
                if len(actual) > 100:
                    error_msg += f"实际开头: {actual[:100]}...\n"
                else:
                    error_msg += f"实际内容: {actual}\n"
        
        pytest.fail(error_msg)


if __name__ == "__main__":
    # 直接运行时生成快照
    tester = SnapshotTester()
    tester.generate_snapshots()
    print("快照生成完成") 