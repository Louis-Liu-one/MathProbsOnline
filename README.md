
# MathProbsOnline

为MathProbs项目建立的网站。尚未上线。

## 构建方法

1. 项目使用Marked渲染Markdown，使用MathJax渲染数学公式。需要在`static/`中添加文件`marked.min.js`与命名为`MathJax`的、在GitHub下载的4.1.0或以上版本的MathJax文件夹；
2. 所需的Python第三方库有：SymPy、PyParsing、Werkzeug、Flask、Flask-Login、Flask-SQLAlchemy，具体参见`requirements.txt`，可以直接使用`pip`安装，建议使用虚拟环境；
3. 直接运行`webapp.py`。

## 部署域名

计划在PythonAnyWhere上部署，域名为`MathProbsOnline.PythonAnyWhere.com`。
