import io
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from webapp import create_app
from webapp import db


class FakeRAG:
    def __init__(self):
        self.added = []
        self.removed = []

    def add_document_from_text(self, doc_id, text, source_name):
        self.added.append((doc_id, text, source_name))

    def remove_document(self, doc_id):
        self.removed.append(doc_id)


class TestAdminDocumentAccess(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path_patch = patch.object(
            db, "DB_PATH", os.path.join(self.temp_dir.name, "tcchat.db")
        )
        self.db_path_patch.start()
        self.env_patch = patch.dict(
            os.environ,
            {"TCCHAT_ADMIN_EMAILS": "coord@example.com"},
        )
        self.env_patch.start()
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.rag = FakeRAG()
        self.generator = SimpleNamespace(cl=SimpleNamespace(rag_support=self.rag))
        self.generator_patch = patch(
            "webapp.routes.docs_routes.obter_gerador",
            return_value=self.generator,
        )
        self.generator_patch.start()
        self.docs_dir_patch = patch(
            "webapp.routes.docs_routes.DOCS_DIR",
            os.path.join(self.temp_dir.name, "uploads"),
        )
        self.docs_dir_patch.start()
        self.admin_token = self._register("coord@example.com")
        self.student_token = self._register("student@example.com", role="admin")

    def tearDown(self):
        self.docs_dir_patch.stop()
        self.generator_patch.stop()
        self.env_patch.stop()
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def _register(self, email, role=None):
        response = self.client.post(
            "/api/cadastro",
            json={
                "nome": "Teste",
                "email": email,
                "senha": "senha-segura-123",
                "papel": role,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["token"]

    @staticmethod
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}

    def test_configured_email_is_admin_and_client_cannot_assign_role(self):
        admin = self.client.get("/api/me", headers=self._headers(self.admin_token))
        student = self.client.get(
            "/api/me", headers=self._headers(self.student_token)
        )

        self.assertEqual(admin.get_json()["papel"], "admin")
        self.assertEqual(student.get_json()["papel"], "aluno")

    def test_student_cannot_list_upload_or_delete_documents(self):
        headers = self._headers(self.student_token)

        self.assertEqual(
            self.client.get("/api/documentos", headers=headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/documentos",
                headers=headers,
                data={"arquivo": (io.BytesIO(b"documento"), "guia.txt")},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(
                "/api/documentos/documento-id", headers=headers
            ).status_code,
            403,
        )
        self.assertEqual(self.rag.added, [])
        self.assertEqual(self.rag.removed, [])

    def test_chat_passes_authenticated_user_id_to_response_generator(self):
        response_data = {"tipo": "texto", "texto": "Resposta", "fontes": []}
        responder = Mock(return_value=response_data)
        with patch(
            "webapp.routes.chat_routes.obter_gerador",
            return_value=SimpleNamespace(responder=responder),
        ):
            response = self.client.post(
                "/api/chat",
                headers=self._headers(self.student_token),
                json={"mensagem": "Pergunta de teste"},
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["fontes"], [])
        self.assertEqual(responder.call_args.kwargs["user_id"], 2)
        self.assertEqual(responder.call_args.kwargs["historico"], [])
        self.assertNotIn("modo", responder.call_args.kwargs)

    def test_chat_passes_recent_messages_from_the_same_conversation(self):
        response_data = {"tipo": "texto", "texto": "Resposta", "fontes": []}
        responder = Mock(return_value=response_data)
        with patch(
            "webapp.routes.chat_routes.obter_gerador",
            return_value=SimpleNamespace(responder=responder),
        ):
            first = self.client.post(
                "/api/chat",
                headers=self._headers(self.student_token),
                json={"mensagem": "Meu tema é sustentabilidade."},
            )
            conversation_id = first.get_json()["conversa_id"]
            second = self.client.post(
                "/api/chat",
                headers=self._headers(self.student_token),
                json={
                    "mensagem": "E como fica a metodologia?",
                    "conversa_id": conversation_id,
                },
            )

        self.assertEqual(second.status_code, 200, second.get_json())
        historico = responder.call_args.kwargs["historico"]
        self.assertEqual(
            [item["papel"] for item in historico],
            ["usuario", "assistente"],
        )
        self.assertEqual(historico[0]["conteudo"], "Meu tema é sustentabilidade.")
        self.assertEqual(
            historico[1]["conteudo"],
            '{"tipo": "texto", "texto": "Resposta", "fontes": []}',
        )

    def test_admin_can_list_upload_and_remove_documents(self):
        headers = self._headers(self.admin_token)

        self.assertEqual(
            self.client.get("/api/documentos", headers=headers).status_code,
            200,
        )
        uploaded = self.client.post(
            "/api/documentos",
            headers=headers,
            data={"arquivo": (io.BytesIO(b"conteudo do guia"), "guia.txt")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.get_json())
        document_id = uploaded.get_json()["id"]
        self.assertEqual(self.rag.added[0][1:], ("conteudo do guia", "guia.txt"))

        removed = self.client.delete(
            f"/api/documentos/{document_id}", headers=headers
        )

        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertEqual(self.rag.removed, [document_id])


class TestLegacyRoleMigration(unittest.TestCase):
    def test_existing_users_receive_role_and_configured_admin_is_promoted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "legacy.db")
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY,
                    nome TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    criado_em TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO usuarios VALUES (1, 'Coordenação', 'coord@example.com', 'hash', 'now')"
            )
            connection.execute(
                "INSERT INTO usuarios VALUES (2, 'Aluno', 'student@example.com', 'hash', 'now')"
            )
            connection.commit()
            connection.close()

            with patch.object(db, "DB_PATH", database_path), patch.dict(
                os.environ, {"TCCHAT_ADMIN_EMAILS": "COORD@example.com"}
            ):
                db.inicializar_banco()
                connection = db.obter_conexao()
                roles = {
                    row["email"]: row["papel"]
                    for row in connection.execute(
                        "SELECT email, papel FROM usuarios"
                    )
                }
                connection.close()

        self.assertEqual(roles["coord@example.com"], "admin")
        self.assertEqual(roles["student@example.com"], "aluno")


if __name__ == "__main__":
    unittest.main()
