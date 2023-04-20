import pymysql
from flask import Flask, render_template, request, redirect, url_for, flash,jsonify
from flask_login import LoginManager, login_required, current_user, login_user, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
import secrets
from datetime import datetime
import pytz

app = Flask(__name__, static_url_path='/static')

useame = input('Enter MySQL username: ')
pword = input('Enter MySQL password: ')

app.config['SECRET_KEY'] = secrets.token_hex(16)
db_user = useame
db_password = pword
db_name = 'flask_app'
db_host = 'localhost'
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(15), nullable=False)
    first_name = db.Column(db.String(20), nullable=True)
    last_name = db.Column(db.String(20), nullable=True)

    def get_id(self):
        return str(self.user_id)

class comment( db.Model):
    __tablename__ = 'comment'
    commentid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(20), nullable=False)
    article = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False)

    def get_id(self):
        return str(self.commentid)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def login():
    return render_template('login.html')




@app.route('/register')
def register():
    return render_template('register.html')



# 获取登录参数及处理
@app.route('/login', methods=['POST'])
def getLoginRequest():
    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(email=email, password=password).first()

    if not user:
        return 'Incorrect email or password'

    login_user(user)
    return redirect(url_for('main_menu'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 获取注册请求及处理
@app.route('/registuser', methods=['POST'])
def getRigistRequest():
    email = request.form.get('email')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')

    if not email or not password:
        return 'Email or password cannot be empty'

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return 'Email is already in use, please try another one'

    new_user = User(email=email, password=password, first_name=first_name, last_name=last_name)
    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('login'))



# 电影详情页
@app.route('/movie/<int:movie_id>')
@login_required
def get_movie_by_id(movie_id):
    connection = None
    try:
        # Connect to MySQL database
        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            db=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )

        # Execute the query to get movie details by movie_id
        user_id = current_user.get_id()
        with connection.cursor() as cursor:
            cursor.callproc('get_movie_detail', (movie_id,))
            movie = cursor.fetchone()

            if not movie:
                abort(404, description='Movie not found')

            query = 'select first_name from user where user.user_id = %s'
            cursor.execute(query, (user_id,))
            first_name = cursor.fetchone()
            first_name = first_name['first_name']
            cursor.callproc('moviecomment_num', (movie_id,))
            comment_num = cursor.fetchone()
            comment_num = comment_num['num']
            cursor.callproc('get_comment', (movie_id,))
            comments = cursor.fetchall()

        # Close the database connection
        connection.close()

        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            db=db_name,
            cursorclass=pymysql.cursors.Cursor
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT thumb_num(%s)", (movie_id,))
            result = cursor.fetchone()[0]

        # Close the database connection
        connection.close()

        return render_template('single.html', movie=movie, first_name=first_name, movie_id=movie_id,
                               comment_num=comment_num, comments=comments, user_id=user_id, result=result)

    except Exception as e:
        if connection:
            connection.close()
        return str(e), 500


# main菜单电影按照imdb评分排序
@app.route('/main_menu')
@login_required
def main_menu():
    # 连接到 MySQL 数据库
    user_id = current_user.get_id()
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        db=db_name,
        cursorclass=pymysql.cursors.DictCursor
    )

    # 执行查询语句，获取指定 ID 的电影详细信息
    with connection.cursor() as cursor:
        cursor.callproc('imdbup')
        movies = cursor.fetchall()
        query = 'select first_name from user where user.user_id = %s'
        cursor.execute(query, (user_id,))
        first_name = cursor.fetchone()
        first_name = first_name['first_name']
        # 关闭数据库连接
        connection.close()
        return render_template('main_menu.html', movies=movies, first_name=first_name,user_id=user_id)

# 搜索功能
from flask import abort

# ...

@app.route('/search', methods=['POST'])
@login_required
def search():
    with pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            db=db_name,
            cursorclass=pymysql.cursors.DictCursor
        ) as connection:
        with connection.cursor() as cursor:
            query = 'select movie_id from movie where title_movie like %s'
            cursor.execute(query, ('%' + request.form['search'] + '%',))
            movies = cursor.fetchall()

    if movies:
        first_movie_id = movies[0]['movie_id']
        return redirect(url_for('get_movie_by_id', movie_id=first_movie_id))
    else:
        abort(404, 'No matching films')


@app.route('/post_comment/<int:movie_id>', methods=['POST'])
@login_required
def post_comment(movie_id):
            title = request.form.get('title')
            article = request.form.get('article')
            user_id = current_user.get_id()

            # Get the current time
            current_time = datetime.now(pytz.timezone('America/New_York'))

            # Create a new comment object and add it to the database
            new_comment = comment(title=title, article=article, user_id=user_id, movie_id=movie_id, date=current_time)
            db.session.add(new_comment)
            db.session.commit()

            # Show a success message to the user
            flash('Your comment has been posted successfully!')

            # Redirect the user back to the movie page
            return redirect(url_for('get_movie_by_id', movie_id=movie_id))


@app.route('/personal')
@login_required
def personal():
    try:
        user_id = current_user.get_id()
        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            db=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        with connection.cursor() as cursor:
            cursor.callproc('display_comment', (user_id,))
            comments = cursor.fetchall()
            cursor.callproc('thumb_movie', (user_id,))
            thumb_movies = cursor.fetchall()
            query = 'select first_name from user where user.user_id = %s'
            cursor.execute(query, (user_id,))
            first_name = cursor.fetchone()
            first_name = first_name['first_name']
            cursor.close()
        return render_template('personal_center.html', comments=comments, thumb_movies=thumb_movies,user_id=user_id,first_name=first_name)
    except Exception as e:
        return str(e), 500
    finally:
        connection.close()



@app.route('/delete_comment', methods=['POST'])
@login_required
def delete_comment():
    data = request.get_json()
    comment_id = data.get('comment_id')
    comment_instance = comment.query.get(comment_id)
    if comment_instance:
        db.session.delete(comment_instance)
        db.session.commit()
        return jsonify(success=True)
    else:
        return jsonify(success=False, message='Comment not found.')

@app.route('/edit_comment', methods=['POST'])
@login_required
def edit_comment():
    comment_id = request.form.get('comment_id')
    new_title = request.form.get('title')
    new_article = request.form.get('article')

    comment_instance = comment.query.get(comment_id)
    if comment_instance:
        comment_instance.title = new_title
        comment_instance.article = new_article
        db.session.commit()
        return jsonify(success=True)
    else:
        return jsonify(success=False, message='Comment not found.')



@app.route('/toggle_like', methods=['POST'])
@login_required
def toggle_like():
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        db=db_name,
        cursorclass=pymysql.cursors.DictCursor
    )

    movie_id = request.form.get('movie_id')
    user_id = request.form.get('user_id')

    if not movie_id or not user_id:
        return jsonify({"error": "Movie ID or User ID not provided"}), 400

    try:
        with connection.cursor() as cursor:
            # 检查电影是否存在
            sql = "SELECT * FROM movie WHERE movie_id = %s"
            cursor.execute(sql, (movie_id,))
            movie = cursor.fetchone()

            if not movie:
                return jsonify({"error": "Movie not found"}), 404

            # 检查点赞记录是否存在
            sql = "SELECT * FROM thumb WHERE movie_id = %s AND user_id = %s"
            cursor.execute(sql, (movie_id, user_id))
            thumb = cursor.fetchone()

            if thumb:
                # 删除点赞记录
                sql = "DELETE FROM thumb WHERE movie_id = %s AND user_id = %s"
                cursor.execute(sql, (movie_id, user_id))
                connection.commit()
                return jsonify({"liked": False})
            else:
                # 添加点赞记录
                current_time = datetime.now(pytz.timezone('America/New_York'))
                sql = "INSERT INTO thumb (movie_id, user_id, thumb_time) VALUES (%s, %s, %s)"
                thumb_time = datetime.utcnow()
                cursor.execute(sql, (movie_id, user_id, current_time))
                connection.commit()
                return jsonify({"liked": True})
    finally:
        connection.close()



@app.route('/check_like_status', methods=['GET'])
@login_required
def check_like_status():
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        db=db_name,
        cursorclass=pymysql.cursors.DictCursor
    )

    movie_id = request.args.get('movie_id')
    user_id = request.args.get('user_id')
    if not movie_id or not user_id:
        return jsonify({"error": "Movie ID or User ID not provided"}), 400

    try:
        with connection.cursor() as cursor:
            # 检查点赞记录是否存在
            sql = "SELECT * FROM thumb WHERE movie_id = %s AND user_id = %s"
            cursor.execute(sql, (movie_id, user_id))
            thumb = cursor.fetchone()

            return jsonify({"liked": bool(thumb)})
    finally:
        connection.close()

@app.route('/complex_data_visualization')
@login_required
def complex_data_visualization():
    connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_password,
                                 db=db_name,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    cursor = connection.cursor()
    user_id = current_user.get_id()

    cursor.execute('CALL GetComplexStatistics();')

    genre_avg_ratings = cursor.fetchall()
    cursor.nextset()

    director_movie_counts = cursor.fetchall()
    cursor.nextset()

    actor_movie_counts = cursor.fetchall()
    cursor.execute('CALL GetUserLikesStatistics(%s);',user_id)
    GetUserLikesStatistics = cursor.fetchall()
    query = 'select first_name from user where user.user_id = %s'
    cursor.execute(query, (user_id,))
    first_name = cursor.fetchone()
    first_name = first_name['first_name']



    cursor.close()
    connection.close()

    return render_template('Data_Visulization.html',
                           genre_avg_ratings=genre_avg_ratings,
                           director_movie_counts=director_movie_counts,
                           actor_movie_counts=actor_movie_counts,
                           GetUserLikesStatistics=GetUserLikesStatistics,
                           user_id=user_id,
                           first_name=first_name)



if __name__ == '__main__':
    app.run(debug=True)








