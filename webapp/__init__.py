# webapp/__init__.py
import os

from flask import Flask

from .db import inicializar_banco


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )
    app.config["SECRET_KEY"] = os.urandom(32)
    app.config["JSON_AS_ASCII"] = False  # preserva acentuação nas respostas JSON
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB, bate com o aviso da tela de upload

    inicializar_banco()

    from .routes.pages import pages_bp
    from .routes.auth_routes import auth_bp
    from .routes.chat_routes import chat_bp
    from .routes.docs_routes import docs_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(docs_bp, url_prefix="/api")

    from flask import jsonify

    @app.errorhandler(413)
    def arquivo_grande_demais(_e):
        return jsonify({"erro": "Arquivo muito grande (limite de 20 MB)."}), 413

    return app
