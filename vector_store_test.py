import unittest
# Importe a sua classe (supondo que o código acima esteja num arquivo chamado rag_store.py)
from rag_store import PDFVectorStore 

class MockPDFVectorStore:
    """Classe temporária ou simulada caso queira testar a lógica pura 
       sem carregar o modelo pesado do HuggingFace no Jenkins."""
    def _normalize(self, text):
        import unicodedata
        import re
        text = unicodedata.normalize("NFKD", text)
        text = text.replace("\x0c", " ")
        text = re.sub(r"-\s*\n\s*", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()


class TestPDFVectorStore(unittest.TestCase):

    def setUp(self):
        # Instancia para testar os métodos utilitários
        self.store = MockPDFVectorStore()

    def test_normalize_text(self):
        # Testa se a normalização remove espaços múltiplos e coloca em minúsculo
        texto_sujo = "  Este é   um    TEXTO de  Exemplo!  \n"
        texto_esperado = "este é um texto de exemplo!"
        
        resultado = self.store._normalize(texto_sujo)
        self.assertEqual(resultado, texto_esperado)

    def test_normalize_hyphenation(self):
        # Testa se remove hifenizações quebradas típicas de PDF
        texto_com_hifen = "pro-\ncedimento"
        texto_esperado = "procedimento"
        
        resultado = self.store._normalize(texto_com_hifen)
        self.assertEqual(resultado, texto_esperado)


if __name__ == "__main__":
    unittest.main()
