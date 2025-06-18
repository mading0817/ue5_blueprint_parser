from flask import Flask, request, render_template
from parser.blueprint_parser import parse_ue_blueprint
from parser.formatters import format_blueprint_to_markdown

# 初始化Flask应用
app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    处理Web请求，协调解析器和格式化器，并渲染最终页面。
    """
    result_text = ""
    input_text = ""
    if request.method == 'POST':
        input_text = request.form.get('blueprint_text', '')

        # 1. 调用解析器获取结构化数据
        blueprint_data = parse_ue_blueprint(input_text)

        # 2. 调用格式化器将数据转换为Markdown字符串
        if blueprint_data and blueprint_data.root_nodes:
            result_text = format_blueprint_to_markdown(blueprint_data)
        else:
            # 如果没有解析到任何节点，提供一个友好的提示
            if input_text.strip():  # 只有在用户确实输入了内容时才显示错误
                result_text = "解析失败：无法找到根节点或蓝图格式有误。\\n(Parsing failed: Could not find root node or the format is incorrect.)"
            else:
                result_text = "请输入蓝图内容。(Please enter blueprint content.)"

    # 渲染HTML页面，并传入结果
    # 使用 render_template 来渲染外部HTML文件
    return render_template('index.html', result=result_text, blueprint_input=input_text)


# 启动Web服务器
if __name__ == '__main__':
    # Replit需要 host='0.0.0.0' 才能对外提供服务
    app.run(host='0.0.0.0', port=8080, debug=True)
