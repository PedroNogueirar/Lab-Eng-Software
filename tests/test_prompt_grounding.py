import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from llama.call_llama import CallLlama
from llama.prompts import INSTRUCOES_BASE
from llama.responder import GeradorRespostas


class TestPromptGrounding(unittest.TestCase):
    def test_json_modes_receive_shared_tcc_instructions(self):
        completion = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"tipo": "texto", "texto": "Orientação."}'
                    )
                )
            ]
        )
        create_completion = Mock(return_value=completion)
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_completion)
            )
        )
        call_llama = SimpleNamespace(
            client=client,
            model_id="test-model",
            _log_interaction=Mock(),
        )
        generator = GeradorRespostas(call_llama)

        generator._chat_json("Instruções específicas do modo.", "Pergunta")

        system_prompt = create_completion.call_args.kwargs["messages"][0]["content"]
        self.assertTrue(system_prompt.startswith(INSTRUCOES_BASE))
        self.assertIn("Instruções específicas do modo.", system_prompt)

    def test_legacy_call_llama_uses_the_same_shared_instructions(self):
        call_llama = CallLlama.__new__(CallLlama)
        call_llama.memory_support = SimpleNamespace(
            mount_prompt_memory=Mock(return_value="")
        )
        call_llama._extract_info_chunks = Mock(return_value=[])

        messages = call_llama.build_prompt("Pergunta")

        system_prompt = messages[0]["content"]
        self.assertTrue(system_prompt.startswith(INSTRUCOES_BASE))
        self.assertNotIn("REPRODUZA E RESPEITE FIELMENTE", system_prompt)
