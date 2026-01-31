
# MathProbsOnline

为MathProbs项目建立的网站。尚未上线。

## 构建方法

1. 项目使用Marked渲染Markdown，使用KaTeX渲染数学公式。需要在`static/`中添加文件`marked.min.js`、`auto-render.min.js`、`katex.min.js`、`katex.min.css`；
2. KaTeX渲染所需的字体存于`static/fonts`中；
3. 所需的Python第三方库有：SymPy、PyParsing、Werkzeug、Flask、Flask-Login、Flask-SQLAlchemy，具体参见`requirements.txt`，可以直接使用`pip`安装，建议使用虚拟环境；
4. 直接运行`webapp.py`。
