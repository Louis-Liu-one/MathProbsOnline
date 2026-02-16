'''MathProbsOnline
Copyright (c) 2026 Louis Liu  All rights reserved.

用户操作：
/login        登录
/logout       登出
/register     注册
/unregister   注销
/edit-profile 编辑个人简介
/users/<uid>  查看他人主页

题目：
/probs                          题集
/upload-prob                    上传题目
/probs/<probno>                 题目<probno>
/probs/<probno>/submit          提交题目<probno>的答案
/probs/<probno>/solutions/<no>  查看题解
/probs/<probno>/upload-solution 上传题解
/labels/<labelname>             题目标签

计划部署至：MathProbsOnline.PythonAnyWhere.com
'''

import io
import csv
import random
import mimetypes
from datetime import datetime

from flask import Flask, Response, request, url_for
from flask import render_template, redirect, send_file
from flask_login import LoginManager, UserMixin, current_user
from flask_login import login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from fpevaluator import fpeval


app = Flask(__name__)
app.secret_key = '2042090d09526f304d37c436f27a5d08'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
db = SQLAlchemy(app)


def csv2list(csvstr):
    return next(csv.reader((csvstr,), skipinitialspace=True))


def list2csv(ls):
    csvstr = io.StringIO()
    writer = csv.writer(csvstr)
    writer.writerow(list(ls))
    return csvstr.getvalue().splitlines()[0]


# =========================== 用户数据库与登录系统 ===========================

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    columns = 'uid', 'name', 'password'
    uid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    avatar = db.Column(db.LargeBinary)
    avmimetype = db.Column(db.String(64))
    submissions = db.relationship(
        'Submission', backref='user', cascade='all, delete')
    uploadedprobs = db.relationship('Prob', backref='source')
    solutions = db.relationship('ProbSolution', backref='user')
    comments = db.relationship('Comment', backref='user')

    def verify_password(self, password):
        return False if self.password is None else \
            check_password_hash(self.password, password)

    def avatar_response(self):
        return Response(self.avatar, mimetype=self.avmimetype)

    def edit_profile(self, name, password, avatarfile):
        avatardata = avatarfile.read()
        if name and name != self.name:
            self.name = name
        if password and not self.verify_password(password):
            self.password = generate_password_hash(password)
        if avatardata:
            self.avatar = avatardata
            self.avmimetype = mimetypes.guess_type(avatarfile.filename)[0]
        db.session.commit()

    def get_probscores(self):
        probscores = {}
        for submission in self.submissions:
            prob = submission.prob
            if prob not in probscores or prob in probscores \
                    and probscores[prob] < submission.score:
                probscores[prob] = submission.score
        return probscores

    def get_passedprobs(self):
        return sorted([
            prob for prob, score in self.get_probscores().items()
            if score == 100])

    def get_id(self):
        return self.uid


def find_user(val, key='uid'):
    if not val or key not in User.columns:
        return None
    user = db.session.get(User, val) if key == 'uid' \
        else User.query.filter_by(**{key: val}).first()
    return user


@login_manager.user_loader
def load_user(uid):
    return find_user(uid)


def register_user(name, password, avatarfile):
    if name and password:
        user = User(
            name=name, password=generate_password_hash(password))
        if avatarfile is not None:
            user.avatar = avatarfile.read()
            user.avmimetype = mimetypes.guess_type(avatarfile.filename)[0]
        db.session.add(user)
        db.session.commit()
        return user


def unregister_user(user):
    if user is not None:
        db.session.delete(user)
        db.session.commit()


# =========================== 题目与图片数据库 ===========================


prob_label = db.Table(
    'probs_labels', db.Column(
        'probno', db.String(16),
        db.ForeignKey('probs.probno'), primary_key=True),
    db.Column(
        'labelname', db.String(16),
        db.ForeignKey('labels.labelname'), primary_key=True))


class Prob(db.Model):
    __tablename__ = 'probs'
    probno = db.Column(db.String(16), primary_key=True)
    probtitle = db.Column(db.String(64))
    problabels = db.relationship(
        'ProbLabel', secondary=prob_label, back_populates='probs',
        collection_class=set)
    statement = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    solutions = db.relationship(
        'ProbSolution', backref='prob', cascade='all, delete')
    sourceuid = db.Column(db.Integer, db.ForeignKey('users.uid'))
    submissions = db.relationship(
        'Submission', backref='prob', cascade='all, delete')

    def check_answer(self, answer):
        return fpeval(answer).do() == fpeval(self.answer).do() \
            if answer and self.answer else False

    def add_submission(self, user, answer):
        ispassed = self.check_answer(answer)
        submission = Submission(
            user=user, answer=answer, ispassed=ispassed,
            score=100 if ispassed else 0)
        db.session.add(submission)
        submission.prob = self
        db.session.commit()
        return submission

    def get_toplevel_comments(self):
        return Comment.query.filter(db.and_(
            Comment.post_type == 'prob', Comment.post_ident == self.probno,
            Comment.replyto_id.is_(None))).order_by(
            Comment.timestamp.desc()).all()

    def edit(self, probtitle, problabels, statement, answer):
        self.probtitle, self.statement, self.answer \
            = probtitle, statement, answer
        self.problabels = {get_label(labelname) for labelname in problabels}
        db.session.commit()

    def as_labelnames(self):
        return {label.labelname for label in self.problabels}

    def url(self):
        return url_for('probs', probno=self.probno)

    def __lt__(self, prob):
        return self.probno < prob.probno


class Submission(db.Model):
    __tablename__ = 'submissions'
    submitid = db.Column(db.Integer, primary_key=True)
    probno = db.Column(
        db.String(16), db.ForeignKey('probs.probno'), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('users.uid'), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    ispassed = db.Column(db.Boolean)
    score = db.Column(db.Integer)

    def __lt__(self, sub):
        return self.probno < sub.probno


class ProbSolution(db.Model):
    __tablename__ = 'solutions'
    probno = db.Column(
        db.String(16), db.ForeignKey('probs.probno'), primary_key=True)
    solno = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer, db.ForeignKey('users.uid'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)

    def url(self):
        return url_for('solutions', probno=self.probno, solno=self.solno)

    def get_post_ident(self):
        return list2csv([self.probno, self.solno])

    def get_toplevel_comments(self):
        post_ident = self.get_post_ident()
        return Comment.query.filter(db.and_(
            Comment.post_type == 'solution', Comment.post_ident == post_ident,
            Comment.replyto_id.is_(None))).order_by(
            Comment.timestamp.desc()).all()

    def edit(self, title, content):
        self.title, self.content = title, content
        db.session.commit()


class ProbImage(db.Model):
    __tablename__ = 'images'
    probno = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.String(64), primary_key=True)
    uid = db.Column(db.Integer)
    size = db.Column(db.Integer)
    mimetype = db.Column(db.String(64))
    data = db.Column(db.LargeBinary)

    def to_response(self):
        return Response(self.data, mimetype=self.mimetype)


class ProbLabel(db.Model):
    __tablename__ = 'labels'
    labelname = db.Column(db.String(16), primary_key=True)
    probs = db.relationship(
        'Prob', secondary=prob_label, back_populates='problabels',
        collection_class=set)

    def add_prob(self, prob):
        self.probs.add(prob)
        db.session.commit()


def get_prob(probno):
    if isinstance(probno, str):
        return db.session.get(Prob, probno)


def search_probs(form, extra_req=None):
    requirements = []
    if form.get('probno'):
        requirements.append(Prob.probno == form['probno'])
    if form.get('probtitle'):
        requirements.append(Prob.probtitle.like(f'%{form['probtitle']}%'))
    if form.get('statement'):
        requirements.append(Prob.statement.like(f'%{form['statement']}%'))
    if form.get('problabels'):
        requirements.append(db.or_(Prob.problabels.any(
            ProbLabel.labelname == problabel) for problabel
            in csv2list(form['problabels'])))
    if form.get('source'):
        source = []
        for name in csv2list(form['source']):
            user = find_user(name, 'name')
            if user:
                source.append(user)
        if source:
            requirements.append(db.or_(Prob.source == user for user in source))
    flag = bool(requirements)
    if extra_req is not None:
        requirements.append(extra_req)
    if not requirements:
        return Prob.query.order_by(Prob.probno.asc()), flag
    return Prob.query.filter(db.and_(*requirements)).order_by(
        Prob.probno.asc()), flag


def add_prob(**kwargs):
    prob = Prob(**kwargs)
    db.session.add(prob)
    db.session.commit()
    return prob


def get_solution(probno, solno):
    if isinstance(probno, str) and isinstance(solno, int):
        return db.session.get(ProbSolution, (probno, solno))


def add_solution(probno, title, content):
    prob = get_prob(probno)
    solution = ProbSolution(
        prob=prob, solno=len(prob.solutions),
        user=current_user, title=title, content=content)
    db.session.add(solution)
    db.session.commit()
    return solution


def add_images(probno, imgfiles):
    for imgfile in imgfiles:
        imgdata = imgfile.read()
        if len(imgdata):
            img = ProbImage(
                probno=probno, name=imgfile.filename, uid=current_user.uid,
                size=len(imgdata), data=imgdata,
                mimetype=mimetypes.guess_type(imgfile.filename)[0])
            db.session.add(img)
    db.session.commit()


def get_label(labelname):
    if isinstance(labelname, str):
        return db.session.get(ProbLabel, labelname)


def add_to_label(labelname, prob):
    label = get_label(labelname)
    if label is None:
        label = ProbLabel(labelname=labelname)
        db.session.add(label)
    label.add_prob(prob)


# =========================== 讨论区数据库支持 ===========================


class Comment(db.Model):
    __tablename__ = 'comments'
    cmtid = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('users.uid'))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    replyto_id = db.Column(db.Integer, db.ForeignKey('comments.cmtid'))
    # 帖子类型为'prob'，标识符为题目编号
    # 帖子类型为'solution'，标识符为CSV格式的题目编号与题解编号的组合
    post_type = db.Column(db.String(16), nullable=False)  # 帖子类型
    post_ident = db.Column(db.Text, nullable=False)       # 帖子标识符
    replyto = db.relationship(
        'Comment', back_populates='replies', remote_side=[cmtid])
    replies = db.relationship(
        'Comment', back_populates='replyto', cascade='all, delete')

    def get_all_replies(self):
        return sorted(sum(
            [comment.get_all_replies() for comment in self.replies],
            start=self.replies.copy()))

    def __lt__(self, comment):
        return self.timestamp < comment.timestamp


def get_comment(cmtid):
    if isinstance(cmtid, int):
        return db.session.get(Comment, cmtid)


def find_post(post_type, post_ident):
    if post_type == 'prob':
        return get_prob(post_ident)
    elif post_type == 'solution':
        probno, solno = csv2list(post_ident)
        return get_solution(probno, int(solno))


# =========================== 讨论区路由 ===========================


@app.route('/post-comment/<post_type>/<post_ident>', methods=['POST'])
def post_comment(post_type, post_ident):
    content = request.form.get('commenttext')
    db.session.add(Comment(
        user=current_user, content=content,
        post_type=post_type, post_ident=post_ident))
    db.session.commit()
    return redirect(find_post(post_type, post_ident).url())


@app.route(
    '/post-comment/<post_type>/<post_ident>/<int:cmtid>', methods=['POST'])
def post_subcomment(post_type, post_ident, cmtid):
    content = request.form.get('commenttext')
    db.session.add(Comment(
        user=current_user, content=content, replyto_id=cmtid,
        post_type=post_type, post_ident=post_ident))
    db.session.commit()
    return redirect(find_post(post_type, post_ident).url())


@app.route('/delete-comment', methods=['POST'])
def delete_comment():
    cmtid = int(request.form.get('cmtid'))
    comment = get_comment(cmtid)
    post = find_post(comment.post_type, comment.post_ident)
    if comment and current_user == comment.user:
        db.session.delete(comment)
        db.session.commit()
    return redirect(post.url())


# =========================== 题目各项网页 ===========================


@app.route('/probs', methods=['GET', 'POST'])
def problist():
    form = {}
    if request.method == 'POST':
        for key in (
                'probno', 'probtitle', 'statement', 'problabels', 'source'):
            form[key] = request.form.get(key)
    probs, query = search_probs(form)
    return render_template(
        'problist.html', probs=probs, query=query, form=form)


@app.route('/labels/<labelname>', methods=['GET', 'POST'])
def problistoflabel(labelname):
    form = {}
    if request.method == 'POST':
        for key in (
                'probno', 'probtitle', 'statement', 'problabels', 'source'):
            form[key] = request.form.get(key)
    probs, query = search_probs(form, Prob.problabels.any(
        ProbLabel.labelname == labelname))
    return render_template(
        'problist.html', labelname=labelname, oflabel=True, form=form,
        probs=probs, query=query)


@app.route('/probs/<probno>')
def probs(probno):
    prob = get_prob(probno)
    if prob:
        return render_template('prob.html', prob=prob)
    return render_template('notfound.html', error='未能找到题目。')


@app.route('/images/<probno>/<image>')
def imagefile(probno, image):
    image = db.session.get(ProbImage, (probno, image))
    return '' if image is None else image.to_response()


@app.route('/probs/<probno>/submit', methods=['POST'])
def submit(probno):
    userans = request.form.get('answertext')
    prob = get_prob(probno)
    submission = prob.add_submission(current_user, userans)
    return str(submission.score)


@app.route('/probs/<probno>/solutions/<int:solno>')
def solutions(probno, solno):
    solution = get_solution(probno, solno)
    if not solution:
        return render_template('notfound.html', error='未能找到题解。')
    prob = solution.prob
    solutions = prob.solutions.copy()
    solutions.remove(solution)
    suggested = random.sample(solutions, min(len(solutions), 3))
    return render_template(
        'solutions.html', prob=prob, solution=solution, suggested=suggested)


@app.route('/probs/<probno>/edit', methods=['GET', 'POST'])
@login_required
def edit_prob(probno):
    prob = get_prob(probno)
    if not prob:
        return render_template('notfound.html', error='未能找到题目。')
    if current_user != prob.source:
        return redirect(url_for('probs', probno=probno))
    if request.method == 'POST':
        probtitle = request.form.get('probtitle')
        problabels = [
            labelname.replace(' ', '')
            for labelname in csv2list(request.form.get('problabels'))]
        statement = request.form.get('statement')
        answer = request.form.get('answer')
        imgfiles = request.files.getlist('imgfiles')
        prob.edit(probtitle, problabels, statement, answer)
        add_images(probno, imgfiles)
        return redirect(url_for('probs', probno=probno))
    return render_template('edit_prob.html', prob=prob)


@app.route(
    '/probs/<probno>/solutions/<int:solno>/edit', methods=['GET', 'POST'])
@login_required
def edit_solution(probno, solno):
    solution = get_solution(probno, solno)
    if not solution:
        return render_template('notfound.html', error='未能找到题解。')
    if current_user != solution.user:
        return redirect(url_for('solutions', probno=probno, solno=solno))
    if request.method == 'POST':
        soltitle = request.form.get('soltitle')
        content = request.form.get('solution')
        imgfiles = request.files.getlist('imgfiles')
        solution.edit(soltitle, content)
        add_images(probno, imgfiles)
        return redirect(url_for('solutions', probno=probno, solno=solno))
    return render_template(
        'edit_solution.html', prob=solution.prob, solution=solution)


@app.route('/upload-prob', methods=['GET', 'POST'])
@login_required
def upload_prob():
    if request.method == 'POST':
        probno = request.form.get('probno')
        probtitle = request.form.get('probtitle')
        problabels = [
            labelname.replace(' ', '')
            for labelname in csv2list(request.form.get('problabels'))]
        statement = request.form.get('statement')
        answer = request.form.get('answer')
        imgfiles = request.files.getlist('imgfiles')
        prob = add_prob(
            probno=probno, probtitle=probtitle,
            statement=statement, answer=answer, source=current_user)
        add_images(probno, imgfiles)
        for labelname in problabels:
            add_to_label(labelname, prob)
        return redirect(url_for('probs', probno=probno))
    return render_template('upload_prob.html')


@app.route('/probs/<probno>/upload-solution', methods=['GET', 'POST'])
@login_required
def upload_solution(probno):
    prob = get_prob(probno)
    if not prob:
        return render_template('notfound.html', error='未能找到题目。')
    if request.method == 'POST':
        soltitle = request.form.get('soltitle')
        content = request.form.get('solution')
        imgfiles = request.files.getlist('imgfiles')
        solution = add_solution(probno, soltitle, content)
        add_images(probno, imgfiles)
        return redirect(url_for(
            'solutions', probno=probno, solno=solution.solno))
    return render_template('upload_solution.html', prob=get_prob(probno))


# =========================== 登录系统网页 ===========================


@app.route('/')
def home():
    return redirect(url_for('welcome'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = find_user(username, 'name')
        if user is not None and user.verify_password(password):
            login_user(user, remember=True)
            return redirect(url_for('welcome'))
        else:
            error = '用户名或密码错误'
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        avatar = request.files.get('avatar')
        user = register_user(username, password, avatar)
        if user is not None:
            login_user(user, remember=True)
            return redirect(url_for('welcome'))
        else:
            error = '账户创建失败'
    return render_template('register.html', error=error)


@app.route('/welcome')
@login_required
def welcome():
    return render_template('welcome.html', user=current_user)


@app.route('/users/<int:uid>')
def users(uid):
    user = find_user(uid)
    if user:
        return render_template('welcome.html', user=find_user(uid))
    return render_template('notfound.html', error='未能找到用户。')


@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        avatar = request.files.get('avatar')
        current_user.edit_profile(username, password, avatar)
        return redirect(url_for('welcome'))
    return render_template('edit_profile.html')


@app.route('/avatars/<int:uid>')
def avatarfile(uid):
    user = find_user(uid)
    if user and user.avatar:
        return user.avatar_response()
    return send_file('static/images/avatar.svg')


@app.route('/avatars/<int:uid>/black')
def avatarfile_black(uid):
    user = find_user(uid)
    if user and user.avatar:
        return user.avatar_response()
    return send_file('static/images/avatar-black.svg')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/unregister')
@login_required
def unregister():
    unregister_user(current_user)
    logout_user()
    return redirect(url_for('home'))


app.jinja_env.add_extension('jinja2.ext.do')
app.add_template_global(list2csv, 'list2csv')
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
