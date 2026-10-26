import unittest

# Importa a classe real. Como _normalize é @staticmethod, dá pra chamar
# PDFVectorStore._normalize(...) diretamente, sem instanciar a classe e
# sem disparar o __init__ pesado (HuggingFaceEmbeddings/tokenizer).
from rag_store import PDFVectorStore


class TestPDFVectorStore(unittest.TestCase):

    def test_normalize_espacos_e_maiusculas(self):
        # Cada tupla é um caso de teste: (entrada, saída esperada)
        casos = [
            ("  Este é   um    TEXTO de  Exemplo!  \n", "este é um texto de exemplo!"),
            ("OUTRO   Texto\tCom   Espaços", "outro texto com espaços"),
        ]

        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                resultado = PDFVectorStore._normalize(entrada)
                self.assertEqual(resultado, esperado)

    def test_normalize_hifenizacao(self):
        # Testa se remove hifenizações quebradas típicas de PDF
        casos = [
            ("pro-\ncedimento", "procedimento"),
            ("desenvolvi-\nmento de soft-\nware", "desenvolvimento de software"),
        ]

        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                resultado = PDFVectorStore._normalize(entrada)
                self.assertEqual(resultado, esperado)

    def test_normalize_form_feed(self):
        # Testa se remove form feed (\x0c), comum em PDFs extraídos
        casos = [
            ("Página 1\x0cPágina 2", "página 1 página 2"),
            ("Capítulo A\x0c\x0cCapítulo B", "capítulo a capítulo b"),
        ]

        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                resultado = PDFVectorStore._normalize(entrada)
                self.assertEqual(resultado, esperado)

    def test_normalize_multiplas_quebras_de_linha(self):
        # Testa se várias quebras de linha e tabs seguidos colapsam em um espaço
        casos = [
            ("Linha 1\n\n\n\tLinha 2\t\t\nLinha 3", "linha 1 linha 2 linha 3"),
            ("A\n\nB\n\n\nC", "a b c"),
        ]

        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                resultado = PDFVectorStore._normalize(entrada)
                self.assertEqual(resultado, esperado)

    def test_normalize_casos_extremos(self):
        # Casos extremos: string vazia e string só com espaços/quebras
        casos = [
            ("", ""),
            ("   \n\t  ", ""),
        ]

        for entrada, esperado in casos:
            with self.subTest(entrada=repr(entrada)):
                resultado = PDFVectorStore._normalize(entrada)
                self.assertEqual(resultado, esperado)


if __name__ == "__main__":
    unittest.main()
