import os
import unittest

from webapp.routes.docs_routes import DOCS_DIR, _PROJETO_RAIZ


class TestDocumentUploadPaths(unittest.TestCase):
    def test_uploaded_documents_are_stored_outside_webapp(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.assertEqual(_PROJETO_RAIZ, project_root)
        self.assertEqual(
            DOCS_DIR,
            os.path.join(
                project_root,
                "llama",
                "RAG",
                "docs_uploader",
                "uploads_originais",
            ),
        )


if __name__ == "__main__":
    unittest.main()
