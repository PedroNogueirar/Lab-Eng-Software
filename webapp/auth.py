# webapp/auth.py
import secrets
from functools import wraps

from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from .db import obter_conexao


def gerar_hash_senha(senha):
    return generate_password_hash(senha)


def senha_valida(senha, hash_senha):
    return check_password_hash(hash_senha, senha)


def gerar_token():
    return secrets.token_hex(32)


def requer_autenticacao(f):
    """Decorator que exige um header 'Authorization: Bearer <token>' válido.
    Em caso de sucesso, popula g.usuario_id / g.usuario_nome / g.usuario_email / g.token.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"erro": "Não autenticado."}), 401

        token = auth_header[len("Bearer "):].strip()
        if not token:
            return jsonify({"erro": "Não autenticado."}), 401

        conn = obter_conexao()
        linha = conn.execute(
            """
            SELECT u.id AS id, u.nome AS nome, u.email AS email
            FROM tokens t
            JOIN usuarios u ON u.id = t.usuario_id
            WHERE t.token = ?
            """,
            (token,),
        ).fetchone()
        conn.close()

        if linha is None:
            return jsonify({"erro": "Sessão inválida ou expirada."}), 401

        g.usuario_id = linha["id"]
        g.usuario_nome = linha["nome"]
        g.usuario_email = linha["email"]
        g.token = token

        return f(*args, **kwargs)

    return wrapper
