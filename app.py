from flask import Flask, request, render_template, jsonify
from parser.graph_parser import parse_blueprint_graph_v2
from parser.widget_parser import parse_v2 as parse_widget_v2
from parser.formatters import MarkdownEventGraphFormatter, WidgetTreeFormatter, VerboseStrategy
from parser.analyzer import GraphAnalyzer
import re
from typing import Optional, Tuple

# 初始化Flask应用
app = Flask(__name__)


def extract_blueprint_info(graph_result: Optional['BlueprintParseResult'], 
                         widget_result: Optional['BlueprintParseResult']) -> Tuple[str, str]:
    """
    从解析结果中提取统一的蓝图信息
    优先使用成功解析的结果中的信息
    """
    # 优先从Graph结果提取
    if graph_result and graph_result.success:
        return graph_result.blueprint_name, graph_result.blueprint_path
    
    # 其次从Widget结果提取
    if widget_result and widget_result.success:
        return widget_result.blueprint_name, widget_result.blueprint_path
    
    # 如果都失败了，返回默认值
    return "Unknown Blueprint", ""


def format_graph_content(graph) -> str:
    """格式化Graph内容为Markdown"""
    if not graph:
        return "无法生成AST"
    
    # 分析生成AST
    analyzer = GraphAnalyzer()
    ast_nodes = analyzer.analyze(graph)
    if not ast_nodes:
        return "未找到可处理的入口节点"
    
    # 格式化输出
    strategy = VerboseStrategy()  # 硬编码使用详细模式
    formatter = MarkdownEventGraphFormatter(strategy)
    
    results = []
    for ast_node in ast_nodes:
        result = formatter.format(ast_node)
        if result:
            results.append(result)
    
    return '\n\n'.join(results) if results else "无法生成格式化输出"


def format_widget_content(widget_nodes) -> str:
    """格式化Widget内容为树状结构"""
    if not widget_nodes:
        return "无法生成Widget树"
    
    formatter = WidgetTreeFormatter(show_properties=True)  # 硬编码显示属性
    result = formatter.format(widget_nodes)
    
    return result if result else "无法生成Widget树状结构"


@app.route('/', methods=['GET', 'POST'])
def unified_parser():
    """统一蓝图解析器 - 支持同时解析Widget和Graph"""
    if request.method == 'GET':
        return render_template('unified.html')
    
    # 获取用户输入
    widget_text = request.form.get('widget_text', '').strip()
    graph_text = request.form.get('graph_text', '').strip()
    
    # 解析结果容器
    widget_result = None
    graph_result = None
    widget_formatted = None
    graph_formatted = None
    widget_error = None
    graph_error = None
    
    # 条件解析Widget
    if widget_text:
        widget_result = parse_widget_v2(widget_text)
        if widget_result.success:
            widget_formatted = format_widget_content(widget_result.content)
        else:
            widget_error = widget_result.error_message
    
    # 条件解析Graph
    if graph_text:
        graph_result = parse_blueprint_graph_v2(graph_text)
        if graph_result.success:
            graph_formatted = format_graph_content(graph_result.content)
        else:
            graph_error = graph_result.error_message
    
    # 提取统一的蓝图信息
    blueprint_name, blueprint_path = extract_blueprint_info(graph_result, widget_result)
    
    # 名称一致性检查
    consistency_error = None
    if (widget_result and widget_result.success and 
        graph_result and graph_result.success):
        if widget_result.blueprint_name != graph_result.blueprint_name:
            consistency_error = (f"警告：检测到不同的蓝图名称 - "
                               f"Widget: {widget_result.blueprint_name}, "
                               f"Graph: {graph_result.blueprint_name}。"
                               f"请确认输入的是同一蓝图的不同部分。")
    
    return render_template('unified.html',
                         blueprint_name=blueprint_name,
                         blueprint_path=blueprint_path,
                         widget_result=widget_formatted,
                         widget_error=widget_error,
                         graph_result=graph_formatted,
                         graph_error=graph_error,
                         consistency_error=consistency_error,
                         widget_text=widget_text,
                         graph_text=graph_text)


# 启动Web服务器
if __name__ == '__main__':
    # Replit需要 host='0.0.0.0' 才能对外提供服务
    app.run(host='0.0.0.0', port=8080, debug=True)
