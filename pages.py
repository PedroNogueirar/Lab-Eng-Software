# webapp/routes/pages.py
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def pagina_login():
    return render_template("login.html")


@pages_bp.get("/chat")
def pagina_chat():
    return render_template("chat.html")
