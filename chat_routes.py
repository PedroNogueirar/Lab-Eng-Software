# webapp/routes/chat_routes.py
import json
import traceback

from flask import Blueprint, request, jsonify, g

from ..db import obter_conexao, agora
from ..auth import requer_autenticacao
from ..chat_service import obter_gerador

chat_bp = Blueprint("chat", __name__)

TAMANHO_TITULO = 60


def _conversa_atual(conn, usuario_id):
    """Pega a conversa mais recente do usuário, ou cria uma nova se não houver."""
    linha = conn.execute(
        "SELECT id FROM conversas WHERE usuario_id = ? ORDER BY id DESC LIMIT 1",
        (usuario_id,),
    ).fetchone()
    if linha:
        return linha["id"]

    agora_str = agora()
    cursor = conn.execute(
        "INSERT INTO conversas (usuario_id, titulo, criado_em, atualizado_em) VALUES (?, ?, ?, ?)",
        (usuario_id, None, agora_str, agora_str),
    )
    return cursor.lastrowid


def _conversa_do_usuario(conn, usuario_id, conversa_id):
    """Confere que a conversa existe e pertence ao usuário. Retorna o id ou None."""
    linha = conn.execute(
        "SELECT id FROM conversas WHERE id = ? AND usuario_id = ?",
        (conversa_id, usuario_id),
    ).fetchone()
    return linha["id"] if linha else None


def _tocar_conversa(conn, conversa_id):
    """Atualiza o timestamp de atividade da conversa (pra ordenar a lista de recentes)."""
    conn.execute(
        "UPDATE conversas SET atualizado_em = ? WHERE id = ?",
        (agora(), conversa_id),
    )


def _definir_titulo_se_vazio(conn, conversa_id, mensagem):
    """Na primeira mensagem de uma conversa, usa o início dela como título."""
    linha = conn.execute("SELECT titulo FROM conversas WHERE id = ?", (conversa_id,)).fetchone()
    if linha and not linha["titulo"]:
        titulo = mensagem.strip().replace("\n", " ")
        if len(titulo) > TAMANHO_TITULO:
            titulo = titulo[:TAMANHO_TITULO].rstrip() + "…"
        conn.execute("UPDATE conversas SET titulo = ? WHERE id = ?", (titulo, conversa_id))


@chat_bp.post("/conversa/nova")
@requer_autenticacao
def nova_conversa():
    conn = obter_conexao()
    try:
        agora_str = agora()
        cursor = conn.execute(
            "INSERT INTO conversas (usuario_id, titulo, criado_em, atualizado_em) VALUES (?, ?, ?, ?)",
            (g.usuario_id, None, agora_str, agora_str),
        )
        conn.commit()
        conversa_id = cursor.lastrowid
    finally:
        conn.close()
    return jsonify({"conversa_id": conversa_id})


@chat_bp.get("/conversas")
@requer_autenticacao
def listar_conversas():
    conn = obter_conexao()
    try:
        linhas = conn.execute(
            """
            SELECT id, titulo, criado_em, atualizado_em
            FROM conversas
            WHERE usuario_id = ?
            ORDER BY COALESCE(atualizado_em, criado_em) DESC, id DESC
            LIMIT 100
            """,
            (g.usuario_id,),
        ).fetchall()
    finally:
        conn.close()

    conversas = [
        {
            "id": linha["id"],
            "titulo": linha["titulo"],
            "criado_em": linha["criado_em"],
            "atualizado_em": linha["atualizado_em"] or linha["criado_em"],
        }
        for linha in linhas
    ]
    return jsonify({"conversas": conversas})


@chat_bp.delete("/conversa/<int:conversa_id>")
@requer_autenticacao
def excluir_conversa(conversa_id):
    conn = obter_conexao()
    try:
        if not _conversa_do_usuario(conn, g.usuario_id, conversa_id):
            return jsonify({"erro": "Conversa não encontrada."}), 404
        conn.execute("DELETE FROM mensagens WHERE conversa_id = ?", (conversa_id,))
        conn.execute("DELETE FROM conversas WHERE id = ?", (conversa_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@chat_bp.post("/chat")
@requer_autenticacao
def chat():
    dados = request.get_json(silent=True) or {}
    mensagem = (dados.get("mensagem") or "").strip()
    modo = dados.get("modo") or "tema"
    secao = dados.get("secao")
    conversa_id_pedida = dados.get("conversa_id")

    if not mensagem:
        return jsonify({"erro": "Mensagem vazia."}), 400

    conn = obter_conexao()
    try:
        if conversa_id_pedida:
            conversa_id = _conversa_do_usuario(conn, g.usuario_id, conversa_id_pedida)
            if conversa_id is None:
                return jsonify({"erro": "Conversa não encontrada."}), 404
        else:
            conversa_id = _conversa_atual(conn, g.usuario_id)

        _definir_titulo_se_vazio(conn, conversa_id, mensagem)
        conn.execute(
            "INSERT INTO mensagens (conversa_id, papel, conteudo, criado_em) VALUES (?, 'usuario', ?, ?)",
            (conversa_id, mensagem, agora()),
        )
        _tocar_conversa(conn, conversa_id)
        conn.commit()

        gerador = obter_gerador()
        try:
            resposta = gerador.responder(mensagem, modo=modo, secao=secao)
        except Exception as e:
            # Imprime o traceback completo no terminal (facilita achar a causa raiz);
            # o front-end só recebe a mensagem curta, não a pilha inteira.
            traceback.print_exc()
            return jsonify({"erro": f"Erro ao gerar resposta: {e}"}), 500

        conn.execute(
            "INSERT INTO mensagens (conversa_id, papel, conteudo, criado_em) VALUES (?, 'assistente', ?, ?)",
            (conversa_id, json.dumps(resposta, ensure_ascii=False), agora()),
        )
        _tocar_conversa(conn, conversa_id)
        conn.commit()
    finally:
        conn.close()

    resposta["conversa_id"] = conversa_id
    return jsonify(resposta)


@chat_bp.get("/historico")
@requer_autenticacao
def historico():
    conversa_id_pedida = request.args.get("conversa_id", type=int)

    conn = obter_conexao()
    try:
        if conversa_id_pedida:
            conversa_id = _conversa_do_usuario(conn, g.usuario_id, conversa_id_pedida)
            if conversa_id is None:
                return jsonify({"erro": "Conversa não encontrada."}), 404
        else:
            conversa_id = _conversa_atual(conn, g.usuario_id)
            conn.commit()  # _conversa_atual pode ter criado uma conversa nova

        linhas = conn.execute(
            "SELECT papel, conteudo FROM mensagens WHERE conversa_id = ? ORDER BY id ASC",
            (conversa_id,),
        ).fetchall()
    finally:
        conn.close()

    mensagens = []
    for linha in linhas:
        if linha["papel"] == "usuario":
            mensagens.append({"papel": "usuario", "conteudo": linha["conteudo"]})
        else:
            try:
                conteudo = json.loads(linha["conteudo"])
            except (TypeError, ValueError):
                conteudo = {"tipo": "texto", "texto": linha["conteudo"]}
            mensagens.append({"papel": "assistente", "conteudo": conteudo})

    return jsonify({"conversa_id": conversa_id, "mensagens": mensagens})
