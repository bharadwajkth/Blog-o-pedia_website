# Upgraded Blog Website Project [Capstone Project] day_57_59_60_67_69

from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, send_from_directory
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, ContactForm, ForgotPasswordForm, ResetPasswordForm
import os
from dotenv import load_dotenv
import re
import bleach
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask_mail import Mail, Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

load_dotenv()

app = Flask(__name__)
mail = Mail(app)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
MY_EMAIL = os.environ.get("MY_SECRET_EMAIL")
MY_PASSWORD = os.environ.get("MY_SECRET_PASSWORD")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = MY_EMAIL  # Replace with your email
app.config['MAIL_PASSWORD'] = MY_PASSWORD
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


db_uri = os.environ.get("DB_URI")
print(db_uri)
if not db_uri:
    raise ValueError("DB_URI environment variable is not set!")

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
db = SQLAlchemy(model_class=Base)
db.init_app(app)

current_year = date.today().year


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("Users.id"))
    author = relationship("User", back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post", cascade='all, delete-orphan')


# TODO: Create a User table for all your registered users.

class User(UserMixin, db.Model):
    __tablename__ = "Users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")
    is_verified: Mapped[bool] = mapped_column(default=False)

    def get_verification_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        token = s.dumps({'user_id': self.id})
        return token

    @staticmethod
    def verify_token(token, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except (SignatureExpired, BadSignature):
            return None
        return User.query.get(user_id)

    def get_reset_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        token = s.dumps({'user_id': self.id})
        return token

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except (SignatureExpired, BadSignature):
            return None
        return User.query.get(user_id)


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("Users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()


def send_verification_email(user):
    token = user.get_verification_token()
    verification_link = url_for('verify_email', token=token, _external=True)

    subject = "Email Verification"
    body = f"Hi {user.name},\n\nTo verify your account, please click the following link:\n{verification_link}\n\nIf you did not register, please ignore this email."

    msg = MIMEMultipart()
    msg['From'] = MY_EMAIL
    msg['To'] = user.email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MY_EMAIL, MY_PASSWORD)
            server.sendmail(MY_EMAIL, user.email, msg.as_string())
        print("Verification email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")


# Decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


# TODO: Use Werkzeug to hash the user's password when creating a new user.


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()

        send_verification_email(new_user)
        flash('Your account has been created! Check your email to verify your account.', 'info')
        return redirect(url_for("login"))
    return render_template("register.html", form=form, current_user=current_user, current_year=current_year)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()

        if not user:
            flash("Email does not exist, please register!")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        elif not user.is_verified:
            flash('Please verify your email before logging in. Check your inbox for the verification link.', 'warning')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=form, current_user=current_user, current_year=current_year)


@app.route('/verify_email/<token>')
def verify_email(token):
    user = User.verify_token(token)
    if user is None:
        flash('The verification link is invalid or has expired.', 'danger')
        return redirect(url_for('register'))

    user.is_verified = True
    db.session.commit()
    flash('Your account has been verified! You can now log in.', 'success')
    return redirect(url_for('login'))


@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            # Generate reset token
            token = user.get_reset_token()

            # Send reset email
            send_reset_email(user, token)

            flash('A mail has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('login'))
        else:
            flash('Email not found, please check and try again.', 'danger')
            return redirect(url_for('login'))

    return render_template('forgot_password.html', form=form)


def send_reset_email(user, token):

    reset_link = url_for('reset_password', token=token, _external=True)
    subject = 'Password Reset request'
    body = f'''To reset your password, visit the following link:
    {reset_link}

    If you did not request this, simply ignore this email and no changes will be made.
    '''

    msg = MIMEMultipart()
    msg['From'] = MY_EMAIL
    msg['To'] = user.email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MY_EMAIL, MY_PASSWORD)
            server.sendmail(MY_EMAIL, user.email, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")


@app.route('/reset_password/<token>', methods=["GET", "POST"])
def reset_password(token):
    user = User.verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token', 'danger')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Hash the new password and update it
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        user.password = hashed_password
        db.session.commit()

        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user=current_user, current_year=current_year)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if comment_form.validate_on_submit():
        comment_text = bleach.clean(comment_form.comment.data, tags=[], strip=True)
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_text,
            comment_author=current_user,
            parent_post=requested_post,
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id) + '#comments-section')
    return render_template("post.html", post=requested_post, current_user=current_user,
                           current_year=current_year, form=comment_form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user, current_year=current_year)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user, current_year=current_year)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    # Allow only the comment author or an admin to delete
    if comment.comment_author != current_user and current_user.id != 1:  # Assuming admin has id = 1
        flash('You do not have permission to delete this comment.', 'danger')
        return redirect(url_for('show_post', post_id=comment.post_id) + "#comments-section")
    
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('show_post', post_id=comment.post_id) + "#comments-section")


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user, current_year=current_year)


def send_mail(name, email, phone, message):
    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage:{message}"
    with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(MY_EMAIL, MY_PASSWORD)
        msg_encoded = email_message.encode('utf-8')
        connection.sendmail(from_addr=MY_EMAIL,
                            to_addrs=MY_EMAIL,
                            msg=msg_encoded)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    msg_sent = False
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        number = form.phone_number.data
        message = form.message.data
        send_mail(name, email, number, message)
        msg_sent = True
        flash("Your message has been sent successfully.")
        return redirect(url_for("contact"))
    return render_template("contact.html", form=form, current_user=current_user, current_year=current_year, msg_sent=msg_sent)


if __name__ == "__main__":
    app.run(debug=False)
