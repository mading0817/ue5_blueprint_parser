from flask import Flask, request, render_template, jsonify
from parser.graph_parser import parse_blueprint_graph
from parser.formatters import MarkdownFormatter, ConciseStrategy, VerboseStrategy

# 初始化Flask应用
app = Flask(__name__)


@app.route('/')
def index():
    """主页路由，指向Widget解析器"""
    return render_template('index.html')


@app.route('/widget')
def widget_page():
    """Widget解析页面"""
    return render_template('index.html')


@app.route('/parse_widget', methods=['POST'])
def parse_widget():
    """解析蓝图Widget UI结构并生成层级树"""
    widget_text = request.form.get('widget_text', '')
    show_properties = request.form.get('show_properties', '').lower() == 'true'
    
    if not widget_text.strip():
        return render_template('index.html', 
                             error="请输入Widget蓝图文本内容。")
    
    try:
        # 使用Widget解析管道
        markdown_output = run_widget_pipeline(widget_text, show_properties)
        
        if not markdown_output or "失败" in markdown_output:
            return render_template('index.html', 
                                 error=f"解析失败: {markdown_output}")
        
        return render_template('index.html', 
                             result=markdown_output,
                             input_text=widget_text)
    
    except Exception as e:
        return render_template('index.html', 
                             error=f"解析Widget过程中发生错误: {str(e)}")


@app.route('/parse_graph', methods=['POST'])
def parse_graph():
    """解析蓝图Graph逻辑并生成伪代码"""
    graph_text = request.form.get('graph_text', '')
    graph_name = request.form.get('graph_name', 'EventGraph')
    use_verbose = request.form.get('verbose', '').lower() == 'true'
    
    if not graph_text.strip():
        return render_template('graph.html', 
                             error="请输入Graph文本内容。")
    
    try:
        # 使用新的三阶段管道
        markdown_output = run_new_pipeline(graph_text, graph_name, use_verbose)
        
        if not markdown_output or "失败" in markdown_output:
            return render_template('graph.html', 
                                 error=f"解析失败: {markdown_output}")
        
        return render_template('graph.html', 
                             result=markdown_output,
                             input_text=graph_text,
                             graph_name=graph_name)
    
    except Exception as e:
        return render_template('graph.html', 
                             error=f"解析Graph过程中发生错误: {str(e)}")


def run_new_pipeline(graph_text: str, graph_name: str = "EventGraph", verbose: bool = False) -> str:
    """
    运行新的三阶段管道：graph_parser -> GraphAnalyzer -> MarkdownFormatter
    
    :param graph_text: 图文本
    :param graph_name: 图名称
    :param verbose: 是否使用详细格式
    :return: 格式化的Markdown输出
    """
    from parser.analyzer import GraphAnalyzer
    
    # 阶段1: 解析图结构
    graph = parse_blueprint_graph(graph_text, graph_name)
    if not graph:
        return "解析图结构失败：无法识别Graph文本格式"
    
    # 阶段2: 分析生成AST
    analyzer = GraphAnalyzer()
    ast_nodes = analyzer.analyze(graph)
    if not ast_nodes:
        return "生成AST失败：未找到可处理的入口节点"
    
    # 阶段3: 格式化输出
    strategy = VerboseStrategy() if verbose else ConciseStrategy()
    formatter = MarkdownFormatter(strategy)
    
    # 格式化所有AST节点
    results = []
    for ast_node in ast_nodes:
        result = formatter.format_ast(ast_node)
        if result:
            results.append(result)
    
    if not results:
        return "格式化输出失败：无法生成Markdown输出"
    
    return '\n\n---\n\n'.join(results)


def run_widget_pipeline(widget_text: str, show_properties: bool = False) -> str:
    """
    运行Widget解析管道：blueprint_parser -> WidgetTreeFormatter
    用于解析UE5 UserWidget的UI层级结构
    
    :param widget_text: Widget蓝图文本
    :param show_properties: 是否显示Widget属性
    :return: 格式化的Markdown树状结构输出
    """
    from parser.blueprint_parser import parse_ue_blueprint
    from parser.formatters import WidgetTreeFormatter
    
    # 阶段1: 解析Widget蓝图结构
    blueprint = parse_ue_blueprint(widget_text)
    if not blueprint:
        return "解析Widget蓝图失败：无法识别蓝图文本格式或文本为空"
    
    # 阶段2: 格式化为树状结构
    formatter = WidgetTreeFormatter(show_properties=show_properties)
    result = formatter.format_blueprint(blueprint)
    
    if not result or result.strip() == "":
        return "格式化输出失败：无法生成Widget树状结构"
    
    return result


@app.route('/graph')
def graph_page():
    """Graph解析页面"""
    return render_template('graph.html')


# 启动Web服务器
if __name__ == '__main__':
    # Replit需要 host='0.0.0.0' 才能对外提供服务
    app.run(host='0.0.0.0', port=8080, debug=True)
