"""
Authentication module for Flask web dashboard.
Provides secure login/logout functionality with session management.
"""

from functools import wraps

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)

# Default admin credentials (change in production!)
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD_HASH = generate_password_hash("admin123")


def login_required(f):
    """Decorator to require login for routes."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Simple authentication (in production, use database)
        if username == DEFAULT_USERNAME and check_password_hash(
            DEFAULT_PASSWORD_HASH, password
        ):
            session["logged_in"] = True
            session["username"] = username
            flash("Successfully logged in.", "success")
            return redirect(url_for("web.dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Handle user logout."""
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for("auth.login"))
