import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from llama.RAG.BuildVectorStore import PDFVectorStore


class TestPDFVectorStoreInitialization(unittest.TestCase):
    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_default_paths_are_relative_to_module(self, _embeddings):
        store = PDFVectorStore()
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rag_dir = os.path.join(project_dir, "llama", "RAG")

        self.assertEqual(
            store.docs_path,
            os.path.join(rag_dir, "docs_uploader", "documents_txt"),
        )
        self.assertEqual(store.persist_dir, os.path.join(rag_dir, "db"))

    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_default_documents_directory_loads_guide(self, _embeddings):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(
                os.path.join(temp_dir, "guia.txt"), "w", encoding="utf-8"
            ) as guide:
                guide.write("Conteúdo de teste do guia.")
            store = PDFVectorStore(docs_path=temp_dir)

            documents = store._load_files()

        self.assertTrue(documents)
        self.assertEqual(
            documents[0].metadata["source"],
            "guia.txt",
        )

    @patch("llama.RAG.BuildVectorStore.Chroma.from_documents")
    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_build_uses_guide_and_persists_chunks(
        self, _embeddings, from_documents
    ):
        store = PDFVectorStore()
        database = object()
        from_documents.return_value = database
        document = Document(
            page_content="Conteúdo de teste do guia.",
            metadata={"source": "guia.txt", "doc_id": "guia.txt_0"},
        )

        with patch.object(
            store, "_load_files", return_value=[document]
        ), patch.object(
            store, "_semantic_dedup", side_effect=lambda documents: documents
        ):
            result = store._build_db()

        self.assertIs(result, database)
        chunks = from_documents.call_args.args[0]
        self.assertTrue(chunks)
        self.assertTrue(
            all(
                chunk.metadata["source"] == "guia.txt"
                for chunk in chunks
            )
        )
        self.assertEqual(
            from_documents.call_args.kwargs["persist_directory"],
            store.persist_dir,
        )

    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_build_creates_empty_database_when_no_seed_documents(self, _embeddings):
        store = PDFVectorStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            store.docs_path = os.path.join(temp_dir, "empty-documents")
            os.makedirs(store.docs_path)
            store.persist_dir = os.path.join(temp_dir, "db")
            database = object()
            with patch.object(store, "_load_db", return_value=database) as load:
                result = store._build_db()

        load.assert_called_once_with()
        self.assertIs(result, database)
        self.assertIs(store.db, database)

    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_uploaded_document_can_be_indexed_without_seed_documents(
        self, _embeddings
    ):
        store = PDFVectorStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            store.docs_path = os.path.join(temp_dir, "empty-documents")
            os.makedirs(store.docs_path)
            store.persist_dir = os.path.join(temp_dir, "db")
            database = Mock()
            with patch.object(store, "_load_db", return_value=database):
                chunk_count = store.add_document_from_text(
                    "uploaded-1",
                    "Documento enviado pelo administrador para a base do RAG.",
                    "manual.txt",
                )

        self.assertGreater(chunk_count, 0)
        database.add_documents.assert_called_once()
        chunks = database.add_documents.call_args.args[0]
        self.assertTrue(chunks)
        self.assertTrue(
            all(chunk.metadata["doc_id"] == "uploaded-1" for chunk in chunks)
        )

    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_initialize_builds_when_database_is_missing(self, _embeddings):
        store = PDFVectorStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            store.persist_dir = os.path.join(temp_dir, "db")
            database = object()
            with patch.object(store, "_build_db", return_value=database) as build:
                result = store.initialize()

        build.assert_called_once_with()
        self.assertIs(result, database)
        self.assertIs(store.db, database)

    @patch("llama.RAG.BuildVectorStore.OpenAIEmbeddings")
    def test_initialize_loads_when_database_exists(self, _embeddings):
        store = PDFVectorStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            store.persist_dir = os.path.join(temp_dir, "db")
            os.makedirs(store.persist_dir)
            with open(os.path.join(store.persist_dir, "marker"), "w") as marker:
                marker.write("existing database")

            database = object()
            with patch.object(store, "_load_db", return_value=database) as load:
                result = store.initialize()

        load.assert_called_once_with()
        self.assertIs(result, database)
        self.assertIs(store.db, database)


class TestCallLlamaRAGInitialization(unittest.TestCase):
    def test_uses_project_paths_and_initializes_database(self):
        rank_context_name = "llama.RAG.rank_context"
        rank_context = types.ModuleType(rank_context_name)
        rank_context.RankContext = object
        missing = object()
        previous_rank_context = sys.modules.get(rank_context_name, missing)
        sys.modules[rank_context_name] = rank_context
        try:
            call_llama_module = importlib.import_module("llama.call_llama")
        finally:
            if previous_rank_context is missing:
                sys.modules.pop(rank_context_name, None)
            else:
                sys.modules[rank_context_name] = previous_rank_context

        instance = call_llama_module.CallLlama.__new__(call_llama_module.CallLlama)
        instance.base_dir = os.path.join("project", "llama")
        database = object()

        with patch.object(call_llama_module, "PDFVectorStore") as vector_store:
            vector_store.return_value.initialize.return_value = database
            instance._init_rag()

        rag_dir = os.path.join(instance.base_dir, "RAG")
        vector_store.assert_called_once_with(
            docs_path=os.path.join(rag_dir, "docs_uploader", "documents_txt"),
            persist_dir=os.path.join(rag_dir, "db"),
        )
        vector_store.return_value.initialize.assert_called_once_with()
        self.assertIs(instance.db_rag, database)


if __name__ == "__main__":
    unittest.main()
