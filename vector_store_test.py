import unittest

# Importa a classe real. Como _normalize agora é @staticmethod, dá pra
# chamar PDFVectorStore._normalize(...) diretamente, sem instanciar a
# classe e sem disparar o __init__ pesado (HuggingFaceEmbeddings/tokenizer).
from rag_store import PDFVectorStore


class TestPDFVectorStore(unittest.TestCase):

    def test_normalize_text(self):
        # Testa se a normalização remove espaços múltiplos e coloca em minúsculo
        texto_sujo = "  Este é   um    TEXTO de  Exemplo!  \n"
        texto_esperado = "este é um texto de exemplo!"

        resultado = PDFVectorStore._normalize(texto_sujo)
        self.assertEqual(resultado, texto_esperado)

    def test_normalize_hyphenation(self):
        # Testa se remove hifenizações quebradas típicas de PDF
        texto_com_hifen = "pro-\ncedimento"
        texto_esperado = "procedimento"

        resultado = PDFVectorStore._normalize(texto_com_hifen)
        self.assertEqual(resultado, texto_esperado)


if __name__ == "__main__":
    unittest.main()
