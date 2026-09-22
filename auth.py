from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user
from werkzeug.security import check_password_hash

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Sign in to manage CTI records."

auth_bp = Blueprint("auth", __name__)


class AuthUser(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.email = row["email"]
        self.display_name = row["display_name"]
        self.role = row["role"]
        self.active = bool(row["active"])

    @property
    def is_active(self):
        return self.active


@login_manager.user_loader
def load_user(user_id):
    from phase2.database import fetch_user_by_id

    row = fetch_user_by_id(user_id)
    return AuthUser(row) if row else None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from phase2.database import fetch_user_by_email

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        row = fetch_user_by_email(email)
        if not row or not row["active"] or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html"), 401
        login_user(AuthUser(row), remember=False)
        next_url = request.args.get("next")
        return redirect(next_url if next_url and next_url.startswith("/") else url_for("phase2.dashboard"))
    return render_template("login.html")


@auth_bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.home"))


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def manager_required(view):
    return roles_required("admin", "program_manager")(view)


def assert_can_manage_project(project_id):
    from phase2.database import user_can_manage_project

    if current_user.role == "admin":
        return
    if not user_can_manage_project(current_user.id, project_id):
        abort(403)


def assert_can_manage_program(program):
    from phase2.database import user_can_manage_program

    if current_user.role == "admin":
        return
    if current_user.role != "program_manager" or not user_can_manage_program(current_user.id, program):
        abort(403)
