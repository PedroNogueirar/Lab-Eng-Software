import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from llama.responder import GeradorRespostas


class TestResponseSources(unittest.TestCase):
    def setUp(self):
        self.memory = Mock()
        self.memory.mount_prompt_memory.return_value = "memória do aluno"
        self.memory.append_on_memory_database = Mock()
        self.document = SimpleNamespace(
            id="chunk-1",
            page_content="Trecho literal recuperado do guia institucional.",
            metadata={"source": "guia-tcc.txt"},
        )
        self.call_llama = SimpleNamespace(
            memory_support=self.memory,
            _extract_info_chunks=Mock(return_value=[self.document]),
        )
        self.generator = GeradorRespostas(self.call_llama)

    def test_response_contains_retrieved_citation_and_user_memory_scope(self):
        generated = {
            "tipo": "texto",
            "texto": "Resposta fundamentada.",
        }
        with patch.object(self.generator, "_chat_json", return_value=generated):
            result = self.generator.responder(
                "Qual é a orientação?",
                user_id=17,
            )

        self.assertEqual(
            result["fontes"],
            [{
                "nome": "guia-tcc.txt",
                "trechos": ["Trecho literal recuperado do guia institucional."],
            }],
        )
        self.memory.mount_prompt_memory.assert_called_once_with(
            "Qual é a orientação?", k=3, user_id=17
        )
        self.memory.append_on_memory_database.assert_called_once()
        self.assertEqual(
            self.memory.append_on_memory_database.call_args.kwargs["user_id"],
            17,
        )

    def test_rag_context_identifies_attached_document_as_source(self):
        _, rag_block, _ = self.generator._contexto(
            "Qual é a orientação?",
            user_id=17,
        )

        self.assertIn("FONTE: guia-tcc.txt", rag_block)
        self.assertIn("Trecho literal recuperado do guia institucional.", rag_block)

    def test_response_has_empty_sources_when_retrieval_returns_none(self):
        self.call_llama._extract_info_chunks.return_value = []
        with patch.object(
            self.generator,
            "_chat_json",
            return_value={"tipo": "texto", "texto": "Sem fontes."},
        ):
            result = self.generator.responder("Pergunta", user_id=17)

        self.assertEqual(result["fontes"], [])

    def test_chat_classifies_intent_and_includes_conversation_context(self):
        resposta = {
            "tipo": "revisao",
            "texto": "Há pontos a esclarecer.",
            "trecho_original": "texto alterado",
            "notas": [],
        }
        historico = [
            {"papel": "usuario", "conteudo": "Meu tema é sustentabilidade."},
            {
                "papel": "assistente",
                "conteudo": '{"tipo":"texto","texto":"Qual recorte você escolheu?"}',
            },
        ]
        with patch.object(self.generator, "_chat_json", return_value=resposta) as chat:
            result = self.generator.responder(
                "Analise este trecho sobre metodologia.",
                historico=historico,
                user_id=17,
            )

        prompt = chat.call_args.args[0]
        mensagem = chat.call_args.args[1]
        self.assertIn("identifique por conta própria a intenção", prompt)
        self.assertIn("nunca reescreva, corrija ou substitua", prompt)
        self.assertIn("Pedido de revisão sem um trecho de texto enviado", prompt)
        self.assertIn("Meu tema é sustentabilidade.", mensagem)
        self.assertIn("Qual recorte você escolheu?", mensagem)
        self.assertIn("Analise este trecho sobre metodologia.", mensagem)
        self.assertEqual(
            result["trecho_original"],
            "Analise este trecho sobre metodologia.",
        )
        self.assertEqual(result["tipo"], "revisao")
        self.assertIn(
            "Meu tema é sustentabilidade.\n"
            "Analise este trecho sobre metodologia.",
            self.call_llama._extract_info_chunks.call_args.args[0],
        )
