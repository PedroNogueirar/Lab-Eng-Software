# webapp/db.py
import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto (Lab_engenharia_Software)
load_dotenv(os.path.join(BASE_DIR, ".env"))
# Pode ser sobrescrito pela variável de ambiente TCCHAT_DB_PATH (ex.: para
# apontar o banco pra outro disco em produção). Por padrão fica dentro do
# próprio projeto, em webapp_data/.
DB_PATH = os.environ.get("TCCHAT_DB_PATH") or os.path.join(BASE_DIR, "webapp_data", "tcchat.db")


def emails_administradores():
    return {
        email.strip().lower()
        for email in os.environ.get("TCCHAT_ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def papel_do_email(email):
    return "admin" if email.strip().lower() in emails_administradores() else "aluno"


def obter_conexao():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_banco():
    conn = obter_conexao()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            papel TEXT NOT NULL DEFAULT 'aluno',
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id INTEGER NOT NULL,
            papel TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (conversa_id) REFERENCES conversas(id)
        );

        CREATE TABLE IF NOT EXISTS documentos (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            tamanho INTEGER NOT NULL,
            usuario_id INTEGER,
            criado_em TEXT NOT NULL
        );
        """
    )
    conn.commit()

    colunas_usuario = {
        linha["name"] for linha in conn.execute("PRAGMA table_info(usuarios)")
    }
    if "papel" not in colunas_usuario:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN papel TEXT NOT NULL DEFAULT 'aluno'"
        )
        conn.commit()

    # A lista de e-mails configurada no ambiente é a fonte de verdade para
    # administradores: remover um e-mail da lista revoga o papel no próximo start.
    conn.execute("UPDATE usuarios SET papel = 'aluno'")
    administradores = emails_administradores()
    if administradores:
        placeholders = ",".join("?" for _ in administradores)
        conn.execute(
            f"UPDATE usuarios SET papel = 'admin' WHERE lower(email) IN ({placeholders})",
            tuple(administradores),
        )
    conn.commit()

    # Migração leve: bancos criados antes da coluna "atualizado_em" existir.
    # ALTER TABLE falha se a coluna já existe, por isso o try/except.
    try:
        conn.execute("ALTER TABLE conversas ADD COLUMN atualizado_em TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.execute(
        "UPDATE conversas SET atualizado_em = criado_em WHERE atualizado_em IS NULL"
    )
    conn.commit()
    conn.close()


def agora():
    return datetime.utcnow().isoformat()
