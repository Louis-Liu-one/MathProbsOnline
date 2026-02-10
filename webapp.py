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

import csv
import json
import random
import mimetypes

from flask import Flask, Response, request, url_for
from flask import render_template, redirect, send_file
from flask_login import LoginManager, UserMixin, current_user
from flask_login import login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import and_, or_
from werkzeug.security import generate_password_hash, check_password_hash

from fpevaluator import fpeval


app = Flask(__name__)
app.secret_key = '2042090d09526f304d37c436f27a5d08'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
db = SQLAlchemy(app)

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
    allsubs = db.relationship(
        'Submission', backref='user', lazy=True, cascade='all, delete',
        overlaps='user,passedsubs,triedsubs')
    passedsubs = db.relationship(
        'Submission', lazy=True,
        overlaps=','.join(['user', 'allsubs', 'triedsubs']),
        primaryjoin='and_(Submission.userid == User.uid, '
        'Submission.ispassed == True)')
    triedsubs = db.relationship(
        'Submission', lazy=True,
        overlaps=','.join(['user', 'allsubs', 'passedsubs']),
        primaryjoin='and_(Submission.userid == User.uid, '
        'Submission.ispassed == False)')
    uploadedprobs = db.relationship('Prob', backref='source', lazy=True)
    solutions = db.relationship('ProbSolution', backref='user', lazy=True)

    def verify_password(self, password):
        return False if self.password is None else \
            check_password_hash(self.password, password)

    def avatar_response(self):
        return Response(self.avatar, mimetype=self.avmimetype)

    def get_id(self):
        return self.uid


def find_user(val, key='uid'):
    if not val or key not in User.columns:
        return None
    user = db.session.get(User, val) if key == 'uid' \
        else User.query.filter_by(**{key: val}).first()
    return user if user is not None else None


def csv2list(csvstr):
    return next(csv.reader((csvstr,), skipinitialspace=True))


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


def edit_user_profile(name, password, avatarfile):
    avatardata = avatarfile.read()
    if name and name != current_user.name:
        current_user.name = name
    if password and not current_user.verify_password(password):
        current_user.password = password
    if avatardata and avatardata != current_user.avatar:
        current_user.avatar = avatardata
        current_user.avmimetype = mimetypes.guess_type(avatarfile.filename)[0]
    db.session.commit()


def unregister_user(user):
    if user is not None:
        db.session.delete(user)
        db.session.commit()


# =========================== 题目与图片数据库 ===========================


class Prob(db.Model):
    __tablename__ = 'probs'
    probno = db.Column(db.String(5), primary_key=True)
    probtitle = db.Column(db.String(64))
    problabels = db.Column(db.Text, default='[]')
    statement = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    solutions = db.relationship(
        'ProbSolution', backref='prob', lazy=True, cascade='all, delete')
    sourceuid = db.Column(db.Integer, db.ForeignKey('users.uid'))
    submissions = db.relationship(
        'Submission', backref='prob', lazy=True, cascade='all, delete')

    def check_answer(self, answer):
        return fpeval(answer) == fpeval(self.answer) \
            if answer and self.answer else False

    def create_submission(self, user, answer):
        ispassed = self.check_answer(answer)
        return Submission(
            prob=self, user=user, answer=answer, ispassed=ispassed,
            score=100 if ispassed else 0)

    def __lt__(self, prob):
        return self.probno < prob.probno


class Submission(db.Model):
    __tablename__ = 'submissions'
    submitid = db.Column(db.Integer, primary_key=True)
    probno = db.Column(
        db.String(5), db.ForeignKey('probs.probno'), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('users.uid'), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    ispassed = db.Column(db.Boolean)
    score = db.Column(db.Integer)

    def __lt__(self, sub):
        return self.probno < sub.probno


class ProbSolution(db.Model):
    __tablename__ = 'solutions'
    solutionid = db.Column(db.Integer, primary_key=True)
    probno = db.Column(
        db.String(5), db.ForeignKey('probs.probno'), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('users.uid'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)


class ProbImage(db.Model):
    __tablename__ = 'images'
    probno = db.Column(db.String(5), primary_key=True)
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
    probs = db.Column(db.Text, default='[]')

    def add_prob(self, probno):
        updated = set() if self.probs is None else set(json.loads(self.probs))
        updated.add(probno)
        self.probs = json.dumps(list(updated), ensure_ascii=False)
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
        requirements.append(or_(Prob.problabels.like(
            f'%{problabels}%') for problabels
                in csv2list(form['problabels'])))
    if form.get('source'):
        source = []
        for name in csv2list(form['source']):
            user = find_user(name, 'name')
            if user:
                source.append(user)
        if source:
            requirements.append(or_(Prob.source == user for user in source))
    flag = bool(requirements)
    if extra_req is not None:
        requirements.append(extra_req)
    if not requirements:
        return Prob.query.order_by(Prob.probno.asc()), flag
    return Prob.query.filter(and_(*requirements)).order_by(
        Prob.probno.asc()), flag


def add_prob(**kwargs):
    prob = Prob(**kwargs)
    db.session.add(prob)
    db.session.commit()


def add_solution(probno, title, content):
    prob = get_prob(probno)
    solution = ProbSolution(
        prob=prob, user=current_user, title=title, content=content)
    db.session.add(solution)
    db.session.commit()


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


def add_to_label(labelname, probno):
    label = get_label(labelname)
    if label is None:
        label = ProbLabel(labelname=labelname)
        db.session.add(label)
    label.add_prob(probno)


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
    probs, query = search_probs(form, Prob.problabels.like(f'%{labelname}%'))
    return render_template(
        'problist.html', labelname=labelname, oflabel=True, form=form,
        probs=probs, query=query)


@app.route('/probs/<probno>')
def probs(probno):
    return render_template('prob.html', prob=get_prob(probno))


@app.route('/probs/<probno>/<image>')
def imagefile(probno, image):
    return db.session.get(ProbImage, (probno, image)).to_response()


@app.route('/probs/<probno>/submit', methods=['POST'])
def submit(probno):
    userans = request.form.get('submittext')
    prob = get_prob(probno)
    db.session.add(prob.create_submission(current_user, userans))
    db.session.commit()
    result = prob.check_answer(userans)
    return str(result)


@app.route('/probs/<probno>/solutions/<int:solno>')
def solutions(probno, solno):
    prob = get_prob(probno)
    solutions = prob.solutions.copy()
    sol = solutions.pop(solno)
    user, soltitle, solution = sol.user, sol.title, sol.content
    suggested = random.sample(solutions, min(len(solutions), 3))
    return render_template(
        'solutions.html', prob=prob, username=user.name,
        soltitle=soltitle, solution=solution, suggested=suggested)


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
        add_prob(
            probno=probno, probtitle=probtitle,
            problabels=json.dumps(problabels, ensure_ascii=False),
            statement='\n' + statement, answer=answer, source=current_user)
        add_images(probno, imgfiles)
        for labelname in problabels:
            add_to_label(labelname, probno)
        return redirect(url_for('probs', probno=probno))
    return render_template('upload_prob.html')


@app.route('/probs/<probno>/upload-solution', methods=['GET', 'POST'])
@login_required
def upload_solution(probno):
    if request.method == 'POST':
        soltitle = request.form.get('soltitle')
        solution = request.form.get('solution')
        imgfiles = request.files.getlist('imgfiles')
        add_solution(probno, soltitle, '\n' + solution)
        add_images(probno, imgfiles)
        return redirect(url_for('home'))
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
    return render_template('welcome.html')


@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        avatar = request.files.get('avatar')
        edit_user_profile(username, password, avatar)
        return redirect(url_for('welcome'))
    return render_template('edit_profile.html')


@app.route('/avatars/current')
def avatarfile():
    if current_user.avatar:
        return current_user.avatar_response()
    return send_file('static/images/avatar.svg')


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


app.add_template_global(json.loads, 'jsonloads')
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
