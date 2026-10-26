# webapp/routes/docs_routes.py
import os
import uuid

from flask import Blueprint, request, jsonify, g

from ..db import obter_conexao, agora
from ..auth import requer_autenticacao
from ..chat_service import obter_gerador

docs_bp = Blueprint("docs", __name__)

# Guarda uma cópia do arquivo original enviado (fora da pasta já usada pelo
# RAG em llama/RAG/docs_uploader/documents_txt, que é a base original do
# projeto e não deve ser misturada com uploads feitos pelo front-end).
_PROJETO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(_PROJETO_RAIZ, "llama", "RAG", "docs_uploader", "uploads_originais")

EXTENSOES_SUPORTADAS = {".txt", ".md", ".pdf", ".docx"}


def _extrair_texto(caminho, extensao):
    if extensao in (".txt", ".md"):
        with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if extensao == ".pdf":
        from pypdf import PdfReader

        leitor = PdfReader(caminho)
        return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)

    if extensao == ".docx":
        import docx

        documento = docx.Document(caminho)
        return "\n".join(paragrafo.text for paragrafo in documento.paragraphs)

    return None


@docs_bp.get("/documentos")
@requer_autenticacao
def listar_documentos():
    conn = obter_conexao()
    try:
        linhas = conn.execute(
            "SELECT id, nome, tamanho FROM documentos ORDER BY criado_em ASC"
        ).fetchall()
    finally:
        conn.close()
    return jsonify({"documentos": [dict(linha) for linha in linhas]})


@docs_bp.post("/documentos")
@requer_autenticacao
def enviar_documento():
    arquivo = request.files.get("arquivo")
    if arquivo is None or not arquivo.filename:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    nome_original = arquivo.filename
    extensao = os.path.splitext(nome_original)[1].lower()

    if extensao not in EXTENSOES_SUPORTADAS:
        return jsonify({"erro": "Formato não suportado. Envie .txt, .md, .pdf ou .docx."}), 400

    os.makedirs(DOCS_DIR, exist_ok=True)
    doc_id = uuid.uuid4().hex
    caminho_salvo = os.path.join(DOCS_DIR, f"{doc_id}{extensao}")
    arquivo.save(caminho_salvo)
    tamanho = os.path.getsize(caminho_salvo)

    texto = _extrair_texto(caminho_salvo, extensao)
    if not texto or not texto.strip():
        os.remove(caminho_salvo)
        return jsonify({"erro": "Não foi possível extrair texto deste arquivo."}), 400

    gerador = obter_gerador()
    try:
        gerador.cl.rag_support.add_document_from_text(doc_id, texto, nome_original)
    except Exception as e:
        os.remove(caminho_salvo)
        return jsonify({"erro": f"Erro ao indexar documento: {e}"}), 500

    conn = obter_conexao()
    try:
        conn.execute(
            "INSERT INTO documentos (id, nome, tamanho, usuario_id, criado_em) VALUES (?, ?, ?, ?, ?)",
            (doc_id, nome_original, tamanho, g.usuario_id, agora()),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"id": doc_id, "nome": nome_original, "tamanho": tamanho})


@docs_bp.delete("/documentos/<doc_id>")
@requer_autenticacao
def remover_documento(doc_id):
    conn = obter_conexao()
    try:
        linha = conn.execute("SELECT id FROM documentos WHERE id = ?", (doc_id,)).fetchone()
        if linha is None:
            return jsonify({"erro": "Documento não encontrado."}), 404

        gerador = obter_gerador()
        try:
            gerador.cl.rag_support.remove_document(doc_id)
        except Exception as e:
            return jsonify({"erro": f"Erro ao remover do índice: {e}"}), 500

        conn.execute("DELETE FROM documentos WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})
