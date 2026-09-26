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

    def test_normalize_form_feed(self):
        # Testa se remove form feed (\x0c), comum em PDFs extraídos
        texto_com_form_feed = "Página 1\x0cPágina 2"
        texto_esperado = "página 1 página 2"

        resultado = PDFVectorStore._normalize(texto_com_form_feed)
        self.assertEqual(resultado, texto_esperado)

    def test_normalize_multiplas_quebras_de_linha(self):
        # Testa se múltiplas quebras de linha e tabs viram um único espaço
        texto_bagunçado = "Linha 1\n\n\n\tLinha 2\t\t\nLinha 3"
        texto_esperado = "linha 1 linha 2 linha 3"

        resultado = PDFVectorStore._normalize(texto_bagunçado)
        self.assertEqual(resultado, texto_esperado)

    def test_normalize_string_vazia(self):
        # Testa o caso extremo de string vazia (não deve lançar erro)
        resultado = PDFVectorStore._normalize("")
        self.assertEqual(resultado, "")


if __name__ == "__main__":
    unittest.main()
