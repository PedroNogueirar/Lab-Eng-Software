# webapp/routes/auth_routes.py
from flask import Blueprint, request, jsonify, g

from ..db import obter_conexao, agora
from ..auth import gerar_hash_senha, senha_valida, gerar_token, requer_autenticacao

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/cadastro")
def cadastro():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome or not email or not senha:
        return jsonify({"erro": "Preencha nome, e-mail e senha."}), 400
    if len(senha) < 8:
        return jsonify({"erro": "A senha precisa ter pelo menos 8 caracteres."}), 400

    conn = obter_conexao()
    try:
        existente = conn.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        if existente:
            return jsonify({"erro": "Já existe uma conta com este e-mail."}), 409

        cursor = conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?)",
            (nome, email, gerar_hash_senha(senha), agora()),
        )
        usuario_id = cursor.lastrowid

        token = gerar_token()
        conn.execute(
            "INSERT INTO tokens (token, usuario_id, criado_em) VALUES (?, ?, ?)",
            (token, usuario_id, agora()),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"token": token, "nome": nome})


@auth_bp.post("/login")
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    conn = obter_conexao()
    try:
        usuario = conn.execute(
            "SELECT id, nome, senha_hash FROM usuarios WHERE email = ?", (email,)
        ).fetchone()

        if usuario is None or not senha_valida(senha, usuario["senha_hash"]):
            return jsonify({"erro": "E-mail ou senha inválidos."}), 401

        token = gerar_token()
        conn.execute(
            "INSERT INTO tokens (token, usuario_id, criado_em) VALUES (?, ?, ?)",
            (token, usuario["id"], agora()),
        )
        conn.commit()
        nome = usuario["nome"]
    finally:
        conn.close()

    return jsonify({"token": token, "nome": nome})


@auth_bp.post("/logout")
@requer_autenticacao
def logout():
    conn = obter_conexao()
    try:
        conn.execute("DELETE FROM tokens WHERE token = ?", (g.token,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@auth_bp.get("/me")
@requer_autenticacao
def me():
    return jsonify({"nome": g.usuario_nome, "email": g.usuario_email})
