# Backend web do TCChat (login, sessão, histórico, documentos)

## O que falta para rodar

O backend (Flask) já foi criado inteiro, mas **os 7 arquivos de front-end que
você colou numa mensagem anterior não puderam ser recuperados** depois que a
conversa precisou ser resumida por limite de contexto — o texto colado não
fica salvo em lugar nenhum além da conversa em si. Então preciso que você
reenvie estes arquivos (cole de novo, ou anexe) para eu salvar nos lugares
certos:

| Arquivo             | Onde vai                        |
|---------------------|----------------------------------|
| `login.html`        | `webapp/templates/login.html`   |
| `chat.html`         | `webapp/templates/chat.html`    |
| `style.css`         | `webapp/static/css/style.css`   |
| `icons.svg`         | `webapp/static/icons.svg`       |
| `api.js`            | `webapp/static/js/api.js`       |
| `login.js`          | `webapp/static/js/login.js`     |
| `chat.js`           | `webapp/static/js/chat.js`      |

Assim que eu receber o conteúdo de novo, salvo tudo nesses caminhos e o
backend fica 100% funcional (as rotas já foram escritas combinando
exatamente com o contrato de API que `api.js`/`chat.js` esperam).

## Testando localmente (Windows)

Antes de pensar em EC2, vale rodar tudo na sua própria máquina primeiro.

1. **Apague as sobras de teste** (se ainda existirem): `webapp_data/tcchat.db`
   e `webapp_data/tcchat.db-journal`. Não são necessários, o backend recria
   o banco sozinho na próxima execução.

2. **Instale as dependências** (abra um terminal dentro de
   `Lab_engenharia_Software`):

   ```
   pip install -r requirements.txt
   ```

   É pesado (puxa `torch`/`transformers`), pode demorar alguns minutos na
   primeira vez.

3. **Confirme o `.env`** — já deve ter a sua `OPENAI_API_KEY` preenchida.

4. **Suba o servidor**:

   ```
   python run.py
   ```

   Deixe esse terminal aberto — é nele que aparecem os logs/erros em tempo
   real. Se algo quebrar, o traceback aparece ali.

5. **Abra `http://localhost:5000/`** no navegador — deve aparecer a tela de
   login do TCChat (Lumen).

6. **Crie uma conta de teste** (cadastro, senha com 8+ caracteres) e entre.

7. **Teste os 4 modos do chat**, um de cada vez, pelo menu lateral ou pelos
   cartões de sugestão na tela inicial:
   - **Definir tema** — escreva uma ideia vaga de tema e veja se volta um
     cartão com Tema / Problema / Objetivo geral.
   - **Revisar texto** — troque pra esse modo, escolha uma seção
     (introdução/metodologia/resultados) e cole um parágrafo qualquer; veja
     se as "notas" aparecem destacadas no texto.
   - **Estrutura do trabalho** (menu lateral) — deve listar seções
     sugeridas pro TCC.
   - **Meu progresso** (menu lateral) — deve listar etapas com status.

   ⚠️ A primeira mensagem de todas vai demorar mais: é quando o reranker
   local é carregado na memória e o índice do RAG é construído do zero
   (chamando a API de embeddings da OpenAI — custo bem pequeno, mas real).

8. **Teste a base de conhecimento** — abra "Base de conhecimento" no menu,
   suba um `.txt`/`.pdf`/`.docx`/`.md` pequeno, confira se aparece na lista,
   depois remova e confira se some.

9. **Teste sessão/histórico** — saia (Sair), entre de novo com a mesma
   conta, e veja se a conversa anterior aparece (isso confirma que
   `/api/historico` está funcionando).

10. **Onde olhar se algo não bater**:
    - Terminal do `python run.py` → erros do backend (Python/Flask).
    - DevTools do navegador (F12) → aba *Console* (erros de JS) e aba
      *Network* (ver o que cada chamada a `/api/...` está devolvendo).
    - `llama/logs_llama/llama_logs.jsonl` → log de cada interação enviada
      pro modelo.
    - Pra inspecionar o banco direto: `webapp_data/tcchat.db` abre
      normalmente em ferramentas como o *DB Browser for SQLite*.

Só depois de tudo isso rodando redondo localmente que faz sentido pensar
em migrar pra EC2 (passo a passo em `deploy/DEPLOY_EC2.md`).

## Deploy na EC2 (quando for a hora)

O projeto já está pronto para subir numa instância EC2 quando vocês quiserem migrar — ver `deploy/DEPLOY_EC2.md` (passo a passo completo), além de `wsgi.py`, `Dockerfile`, `deploy/tcchat.service` e `deploy/nginx_tcchat.conf` já escritos. Nada disso foi executado ainda; é só código/config esperando vocês rodarem na instância.

## Como rodar (depois dos arquivos de front-end estarem no lugar)

```
pip install -r requirements.txt
python run.py
```

Acesse `http://localhost:5000/` (tela de login).

## O que foi implementado

- **Autenticação por token (Bearer), não por cookie/sessão** — bate com o
  que `api.js` já faz (`Authorization: Bearer <token>` + token salvo no
  `localStorage`).
- **Banco SQLite** em `webapp_data/tcchat.db` (criado automaticamente na
  primeira execução), com tabelas `usuarios`, `tokens`, `conversas`,
  `mensagens` e `documentos`. Senhas salvas com hash (`werkzeug.security`),
  nunca em texto puro.
- **Rotas implementadas**, todas sob `/api`:
  - `POST /cadastro`, `POST /login`, `POST /logout`, `GET /me`
  - `POST /chat`, `POST /conversa/nova`, `GET /historico`
  - `GET /documentos`, `POST /documentos` (upload `.txt`/`.pdf`/`.docx`),
    `DELETE /documentos/<id>`
- **Histórico por usuário**: cada usuário só vê a(s) própria(s)
  conversa(s); as respostas do assistente são salvas como JSON completo (o
  mesmo objeto estruturado que o chat devolveu), para o `/historico`
  conseguir re-renderizar exatamente como ficou na tela original.
- **Respostas estruturadas por modo** (`llama/responder.py`, novo arquivo):
  - `modo=tema` → `tipo: "resumo"` (`tema`, `problema`, `objetivo_geral`)
  - `modo=revisao` (+`secao`) → `tipo: "revisao"` (`trecho_original`, `notas[]`)
  - `modo=estrutura` → `tipo: "estrutura"` (`secoes[]`)
  - `modo=progresso` → `tipo: "progresso"` (`etapas[]`, `secoes[]`, `sugestao`)
  - Qualquer outro modo → `tipo: "texto"` (resposta livre, nunca quebra o front)

  Usa `response_format={"type": "json_object"}` da API da OpenAI para
  garantir JSON válido, reaproveitando o RAG/memória/reranker que já
  existiam no `CallLlama`.

- **Upload de documentos para a base de conhecimento**: adicionei
  `add_document_from_text()` e `remove_document()` em
  `llama/RAG/BuildVectorStore.py`, para adicionar/remover um documento do
  índice Chroma **sem precisar reconstruir a base inteira**. Aceita
  `.txt`, `.pdf` (via `pypdf`) e `.docx` (via `python-docx`).

## Pontos que decidi sem te perguntar (me avise se quiser mudar)

1. **Sem papel de Administrador** por enquanto — qualquer usuário logado
   pode enviar/remover documentos da base de conhecimento. Se vocês
   querem distinguir aluno/administrador, dá pra adicionar uma coluna
   `tipo` em `usuarios` e proteger as rotas de `/documentos`.
2. **Uma conversa "ativa" por usuário** (a mais recente) — `/historico`
   sempre devolve a conversa em aberto, e `/conversa/nova` começa outra.
   Não há ainda uma tela de "lista de conversas antigas para escolher";
   se vocês querem múltiplas conversas navegáveis (não só a mais
   recente), é uma rota a mais (`GET /conversas` + trocar a conversa
   ativa).
3. **Os prompts de cada modo** (`llama/responder.py`) são uma primeira
   versão razoável — não testei a renderização real na tela porque não
   tenho o HTML/CSS/JS reais ainda. Depois que eu receber os arquivos de
   front-end, vale rodar uma conversa de teste em cada modo e ajustar o
   texto dos prompts conforme o resultado.
4. O `main.ipynb` e o fluxo antigo (`CallLlama().invoke(...)` puro)
   continuam funcionando sem mudanças — o backend web é uma camada nova
   por cima, não substitui nada.
