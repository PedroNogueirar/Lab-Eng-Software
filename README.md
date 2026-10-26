# Lab-Eng-Software — TCChat

Laboratório de Engenharia de Software - 2026

TCChat é um sistema especialista de apoio à elaboração de TCC: chat web (Flask) com RAG sobre um guia de TCC (Chroma + reranker) e respostas geradas por LLM via API da OpenAI.

## Rodando localmente

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha OPENAI_API_KEY
python run.py
```

A base vetorial (`llama/RAG/db/`) não é versionada; ela é gerada a partir de `llama/RAG/docs_uploader/documents_txt/` com `llama/RAG/BuildVectorStore.py` (ou `generate_db.ipynb`).

Mais detalhes: [BACKEND_LEIAME.md](BACKEND_LEIAME.md) e [deploy/DEPLOY_EC2.md](deploy/DEPLOY_EC2.md).
