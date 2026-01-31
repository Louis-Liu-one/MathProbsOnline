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
/probs/<probno>                 题目<probno>
/probs/<probno>/submit          提交题目<probno>的答案
/probs/<probno>/solutions       查看题解
/upload-prob                    上传题目
/probs/<probno>/upload-solution 上传题解
/tags/<tag>                     题目标签

计划在Railway部署。
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
from werkzeug.security import generate_password_hash, check_password_hash
from fpevaluator import fpeval


app = Flask(__name__)
app.secret_key = 'MathProbs#Online@Secret-Key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
db = SQLAlchemy(app)

# =========================== 用户数据库与登录系统 ===========================

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    columns = 'uid', 'name', 'password'
    jsoncolumns = 'passedprobs',
    uid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    avatar = db.Column(db.LargeBinary)
    passedprobs = db.Column(db.Text, default='[]')

    def verify_password(self, password):
        return False if self.password is None else \
            check_password_hash(self.password, password)

    def avatar_response(self):
        return Response(self.avatar, mimetype='image/x-icon')

    def get_id(self):
        return self.uid


def find_user(val, key='uid'):
    if not val or key not in User.columns:
        return None
    user = db.session.get(User, val) if key == 'uid' \
        else User.query.filter_by(**{key: val}).first()
    return user if user is not None else None


def add_to_json_column(user, key, value):
    if user and key in User.jsoncolumns:
        updated = json.loads(getattr(user, key))
        if str(value) not in updated:
            updated.append(str(value))
        setattr(user, key, json.dumps(updated))
        db.session.commit()


@login_manager.user_loader
def load_user(uid):
    return find_user(uid)


def register_user(name, password, avatar):
    if name and password:
        user = User(
            name=name, password=generate_password_hash(password))
        if avatar is not None:
            user.avatar = avatar.read()
        db.session.add(user)
        db.session.commit()
        return user


def edit_user_profile(name, password, avatardata):
    if name and name != current_user.name:
        current_user.name = name
    if password and not current_user.verify_password(password):
        current_user.password = password
    if avatardata and avatardata != current_user.avatar:
        current_user.avatar = avatardata
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
    solutions = db.Column(db.Text, default='[]')
    source = db.Column(db.Integer)

    def check_answer(self, userans):
        return fpeval(userans) == fpeval(self.answer) \
            if userans and self.answer else False

    def add_solution(self, uid, solution):
        if find_user(uid) and isinstance(solution, str):
            updated = json.loads(self.solutions)
            updated.append((uid, solution))
            self.solutions = json.dumps(updated)
            db.session.commit()


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


def get_prob(probno):
    if isinstance(probno, str):
        return db.session.get(Prob, probno)


def add_prob(**kwargs):
    prob = Prob(**kwargs)
    db.session.add(prob)
    db.session.commit()


def add_solution(probno, soltitle, solution):
    prob = get_prob(probno)
    updated = json.loads(prob.solutions)
    updated.append((current_user.uid, soltitle, solution))
    prob.solutions = json.dumps(updated)
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


# =========================== 题目各项网页 ===========================


@app.route('/probs/<probno>')
def probs(probno):
    prob = get_prob(probno)
    return render_template('prob.html', prob=prob)


@app.route('/probs/<probno>/<image>')
def imagefile(probno, image):
    return db.session.get(ProbImage, (probno, image)).to_response()


@app.route('/probs/<probno>/submit', methods=['POST'])
def submit(probno):
    userans = request.form.get('submittext')
    result = get_prob(probno).check_answer(userans)
    if result:
        add_to_json_column(current_user, 'passedprobs', probno)
    return str(result)


@app.route('/probs/<probno>/solutions/<int:solno>')
def solutions(probno, solno):
    prob = get_prob(probno)
    solutions = json.loads(prob.solutions)
    uid, soltitle, solution = solutions.pop(solno)
    suggested = random.sample(solutions, min(len(solutions), 3))
    user = find_user(uid)
    return render_template(
        'solutions.html', prob=prob, username=user.name,
        soltitle=soltitle, solution=solution, suggested=suggested)


@app.route('/upload-prob', methods=['GET', 'POST'])
@login_required
def upload_prob():
    if request.method == 'POST':
        probno = request.form.get('probno')
        probtitle = request.form.get('probtitle')
        problabels = request.form.get('problabels')
        statement = request.form.get('statement')
        answer = request.form.get('answer')
        imgfiles = request.files.getlist('imgfiles')
        add_prob(
            probno=probno, probtitle=probtitle,
            problabels=json.dumps(next(csv.reader((problabels,)))),
            statement='\n' + statement, answer=answer,
            source=current_user.uid)
        add_images(probno, imgfiles)
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
    return render_template('upload_solution.html', probno=probno)


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
        avatar = request.files['avatar']
        edit_user_profile(username, password, avatar.read())
        return redirect(url_for('welcome'))
    return render_template('edit_profile.html')


@app.route('/avatars/current')
def avatarfile():
    if current_user.avatar:
        return current_user.avatar_response()
    return send_file('static/images/navbars/avatar.png')


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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.add_template_global(json.loads, 'jsonloads')
    app.add_template_global(find_user, 'find_user')
    app.run(debug=True)
