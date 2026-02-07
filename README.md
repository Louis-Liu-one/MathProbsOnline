
# MathProbsOnline

为MathProbs项目建立的网站。尚未上线。

## 构建方法

- 项目使用Markdown-It渲染Markdown，使用Markdown-It-TeXMath插件和KaTeX引擎渲染数学公式。需要添加的文件有：
1. `static/markdown-it.min.js`
2. `static/texmath.min.js`
3. `static/texmath.min.css`
4. `static/katex.min.js`
5. `static/katex.min.css`
这些文件皆可在网上下载。

- 网页所需的Python第三方库有：SymPy、PyParsing、Werkzeug、Flask、Flask-Login、Flask-SQLAlchemy，具体参见`requirements.txt`，可以直接使用`pip`安装，建议使用虚拟环境。命令如下：
```bash
cd MathProbsOnline
python -m venv webenv
source webenv/bin/activate
pip install -r requirements.txt
```

- 所有构建都完成时，直接运行`webapp.py`，或从他处导入：
```python
from webapp import app
app.run()
```
此时，网页可在`localhost:5000`访问。

## 部署域名

计划在PythonAnyWhere上部署，域名为`MathProbsOnline.PythonAnyWhere.com`。
