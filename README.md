# Lab-Eng-Software — TCChat

Laboratório de Engenharia de Software - 2026

TCChat é um sistema especialista de apoio à elaboração de TCC: chat web (Flask) com RAG sobre um guia de TCC (Chroma + reranker) e respostas geradas por LLM via API da OpenAI.

## Rodando localmente

```bash
pip install -r requirements.txt
cp env.example .env   # preencha OPENAI_API_KEY
python run.py
```

A base vetorial (`llama/RAG/db/`) não é versionada. Na primeira solicitação que inicializa o RAG (normalmente a primeira pergunta no chat), ela é criada automaticamente a partir dos arquivos `.txt` em `llama/RAG/docs_uploader/documents_txt/`; também pode ser gerada manualmente com `llama/RAG/BuildVectorStore.py` ou `generate_db.ipynb`.

Para liberar a gestão de documentos, informe no `.env` os e-mails dos administradores, separados por vírgula:

```env
TCCHAT_ADMIN_EMAILS=coordenacao@instituicao.edu.br
```

Contas com esses e-mails recebem o papel de administrador; as demais são alunos. Somente administradores podem listar, enviar ou remover documentos. Como o cadastro ainda não verifica a propriedade do e-mail, configure apenas endereços administrativos sob controle da equipe. A memória usada para contextualizar respostas é filtrada por usuário.

Mais detalhes: [BACKEND_LEIAME.md](BACKEND_LEIAME.md) e [deploy/DEPLOY_EC2.md](deploy/DEPLOY_EC2.md).
