from flask import Flask, request, render_template, jsonify
from parser.blueprint_parser import parse_ue_blueprint
from parser.graph_parser import parse_blueprint_graph
from parser.formatters import format_blueprint_to_markdown, format_graph_to_pseudocode, MarkdownGraphFormatter

# 初始化Flask应用
app = Flask(__name__)


@app.route('/')
def index():
    """主页路由，显示解析表单"""
    return render_template('index.html')


@app.route('/parse', methods=['POST'])
def parse_blueprint():
    """解析蓝图Widget层级结构"""
    blueprint_text = request.form.get('blueprint_text', '')
    
    if not blueprint_text.strip():
        return render_template('index.html', 
                             error="请输入蓝图文本内容。")
    
    try:
        # 解析蓝图
        blueprint = parse_ue_blueprint(blueprint_text)
        
        if not blueprint:
            return render_template('index.html', 
                                 error="无法解析蓝图文本。请检查输入格式。")
        
        # 格式化为Markdown
        markdown_output = format_blueprint_to_markdown(blueprint)
        
        return render_template('index.html', 
                             result=markdown_output,
                             input_text=blueprint_text)
    
    except Exception as e:
        return render_template('index.html', 
                             error=f"解析过程中发生错误: {str(e)}")


@app.route('/parse_graph', methods=['POST'])
def parse_graph():
    """解析蓝图Graph逻辑并生成伪代码"""
    graph_text = request.form.get('graph_text', '')
    graph_name = request.form.get('graph_name', 'EventGraph')
    
    if not graph_text.strip():
        return render_template('graph.html', 
                             error="请输入Graph文本内容。")
    
    try:
        # 解析Graph
        blueprint_graph = parse_blueprint_graph(graph_text, graph_name)
        
        if not blueprint_graph:
            return render_template('graph.html', 
                                 error="无法解析Graph文本。请检查输入格式。")
        
        # 使用新的Markdown格式化器
        formatter = MarkdownGraphFormatter()
        markdown_output = formatter.format(blueprint_graph)
        
        return render_template('graph.html', 
                             result=markdown_output,
                             input_text=graph_text,
                             graph_name=graph_name)
    
    except Exception as e:
        return render_template('graph.html', 
                             error=f"解析Graph过程中发生错误: {str(e)}")


@app.route('/graph')
def graph_page():
    """Graph解析页面"""
    return render_template('graph.html')


# 启动Web服务器
if __name__ == '__main__':
    # Replit需要 host='0.0.0.0' 才能对外提供服务
    app.run(host='0.0.0.0', port=8080, debug=True)
