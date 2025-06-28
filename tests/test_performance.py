"""
性能基准测试
用于监控解析器性能，确保重构不会导致性能回退
"""

import pytest
import os
from parser.graph_parser import parse_blueprint_graph
from parser.widget_parser import parse_ue_blueprint_to_widget_ast


class TestPerformanceBenchmarks:
    """解析器性能基准测试"""
    
    @pytest.fixture(scope="class")
    def fixture_dir(self):
        """获取测试用例目录"""
        return os.path.join(os.path.dirname(__file__), "fixtures")
    
    @pytest.fixture(scope="class")
    def largest_eventgraph_file(self, fixture_dir):
        """获取最大的EventGraph测试文件"""
        # 选择 example_5.txt 作为最复杂的EventGraph测试用例
        filepath = os.path.join(fixture_dir, "example_5.txt")
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    @pytest.fixture(scope="class")
    def ui_widget_file(self, fixture_dir):
        """获取UI Widget测试文件"""
        filepath = os.path.join(fixture_dir, "example_ui.txt")
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_eventgraph_parsing_performance(self, benchmark, largest_eventgraph_file):
        """EventGraph解析性能基准测试"""
        # 使用最复杂的EventGraph文件进行性能测试
        result = benchmark(parse_blueprint_graph, largest_eventgraph_file, "EventGraph")
        
        # 确保解析成功
        assert result is not None
        assert result.nodes is not None
        assert len(result.nodes) > 0
    
    def test_widget_parsing_performance(self, benchmark, ui_widget_file):
        """Widget解析性能基准测试"""
        # 使用UI Widget文件进行性能测试
        result = benchmark(parse_ue_blueprint_to_widget_ast, ui_widget_file)
        
        # 确保解析成功
        assert result is not None
        assert len(result) > 0
    
    def test_eventgraph_parsing_with_analyzer_performance(self, benchmark, largest_eventgraph_file):
        """EventGraph完整解析流程性能基准测试（包含analyzer）"""
        from parser.analyzer import GraphAnalyzer
        
        def full_eventgraph_pipeline(text):
            """完整的EventGraph解析流程"""
            # 第一阶段：文本 -> BlueprintGraph
            blueprint_graph = parse_blueprint_graph(text, "EventGraph")
            if blueprint_graph is None:
                return None
            
            # 第二阶段：BlueprintGraph -> AST
            analyzer = GraphAnalyzer()
            ast_nodes = analyzer.analyze(blueprint_graph)
            return ast_nodes
        
        result = benchmark(full_eventgraph_pipeline, largest_eventgraph_file)
        
        # 确保解析成功
        assert result is not None
        assert len(result) > 0


if __name__ == "__main__":
    # 可以直接运行此文件进行基准测试
    pytest.main([__file__, "--benchmark-only", "--benchmark-sort=mean"]) 