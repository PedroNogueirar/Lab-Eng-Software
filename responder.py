# llama/responder.py
"""Camada que converte o CallLlama (que hoje só devolve texto puro) em
respostas ESTRUTURADAS, no formato que o front-end (chat.js) espera:

    {
      "texto": "...",            # opcional
      "tipo": "texto" | "resumo" | "estrutura" | "revisao" | "progresso",
      ... campos específicos de cada tipo ...
      "acao": {...}               # opcional
    }

NOTA DE IMPLEMENTAÇÃO: os prompts de cada modo abaixo são uma primeira versão
razoável, escrita a partir da descrição do contrato esperado pelo front-end.
Ajuste os prompts livremente — a parte estrutural (chamar com
response_format=json_object, usar o RAG/memória existentes, gravar no log e
na memória) já fica pronta e não deve precisar mudar.
"""
import json

MODOS_VALIDOS = {"tema", "revisao", "estrutura", "progresso"}
SECOES_VALIDAS = {"introducao", "metodologia", "resultados"}


class GeradorRespostas:
    def __init__(self, call_llama):
        self.cl = call_llama  # instância já inicializada de CallLlama

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def responder(self, mensagem, modo="tema", secao=None):
        modo = (modo or "tema").strip().lower()

        if modo == "revisao":
            return self._responder_revisao(mensagem, secao)
        if modo == "estrutura":
            return self._responder_estrutura(mensagem)
        if modo == "progresso":
            return self._responder_progresso(mensagem)
        if modo == "tema":
            return self._responder_tema(mensagem)

        # modo desconhecido -> cai para texto livre, nunca quebra o front
        return {"tipo": "texto", "texto": self.cl.invoke(mensagem)}

    # ------------------------------------------------------------------
    # Helpers compartilhados
    # ------------------------------------------------------------------
    def _contexto(self, mensagem, k_rag=20):
        memory_block = self.cl.memory_support.mount_prompt_memory(mensagem, k=3)
        rag_docs = self.cl._extract_info_chunks(mensagem, k=k_rag)
        if rag_docs:
            rag_block = "\n\n".join(f"[FONTE {d.id}] {d.page_content}" for d in rag_docs)
        else:
            rag_block = ""
        return memory_block, rag_block

    def _chat_json(self, system_prompt, user_content, max_tokens=900):
        completion = self.cl.client.chat.completions.create(
            model=self.cl.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        conteudo = completion.choices[0].message.content

        try:
            self.cl._log_interaction(user_content, conteudo)
        except Exception as e:
            print(f"⚠️ Erro ao logar interação: {e}")

        try:
            return json.loads(conteudo)
        except (TypeError, ValueError):
            # o modelo não devolveu JSON válido -> fallback seguro
            return {"tipo": "texto", "texto": conteudo}

    def _salvar_memoria(self, mensagem, dados):
        try:
            self.cl.memory_support.append_on_memory_database(
                mensagem, json.dumps(dados, ensure_ascii=False)
            )
        except Exception as e:
            print(f"⚠️ Erro ao salvar memória: {e}")

    # ------------------------------------------------------------------
    # Modo: tema  -> tipo "resumo"
    # ------------------------------------------------------------------
    def _responder_tema(self, mensagem):
        memory_block, rag_block = self._contexto(mensagem)

        system_prompt = f"""Você é um especialista em orientação de TCC.

Primeiro avalie a mensagem do usuário e classifique em UM destes três casos:

CASO 1 — Ideia própria com conteúdo concreto: o usuário descreve (mesmo
vagamente) pelo menos UM elemento concreto e específico de tema, problema ou
objetivo para o TCC dele (ex.: uma área + recorte, tipo "autenticação
multifator em apps web"), ou está confirmando/ajustando um resumo anterior
(ex.: "confirmo o resumo", "quero ajustar"). Aqui sim você estrutura um
cartão de Tema/Problema/Objetivo.

CASO 2 — Pergunta genérica sobre o processo: o usuário pergunta "como
funciona" algo (ex.: "como escolho um tema?", "o que é um problema de
pesquisa?") sem trazer nenhum conteúdo próprio. Responda com texto
explicativo, baseado no contexto.

CASO 3 — Intenção sem conteúdo: o usuário diz que quer trabalhar nisso mas
NÃO deu nenhuma informação concreta ainda (ex.: "quero definir o tema do meu
TCC", "me ajuda a escolher um tema", "vamos começar"). Aqui NÃO existe nada
para extrair — não gere um cartão de resumo vazio. Em vez disso, responda
com texto fazendo 2 a 3 perguntas objetivas para ajudar o usuário a trazer
informação concreta (ex.: qual é a área/curso dele, que assuntos despertam
interesse, se já tem alguma ideia mesmo que vaga de problema a resolver).
Baseie as perguntas nos critérios de um bom tema (relevância, viabilidade,
interesse pessoal) quando estiverem no contexto.

REGRA IMPORTANTE: só use o formato "resumo" no CASO 1, ou seja, quando a
mensagem do usuário contiver pelo menos uma informação concreta e específica
que você possa usar para preencher um dos campos. Se a mensagem é só
intenção/pedido de ajuda sem nenhum dado concreto (CASO 3), é SEMPRE
"texto", mesmo que o usuário mencione "tema", "TCC" ou "definir".

Responda SOMENTE em JSON.

Para o CASO 1, use este formato:
{{
  "texto": "<um parágrafo curto de introdução/comentário>",
  "tipo": "resumo",
  "resumo": {{
    "tema": "<tema do trabalho, uma frase>",
    "problema": "<problema de pesquisa>",
    "objetivo_geral": "<objetivo geral, uma frase>"
  }}
}}

Para os CASOS 2 e 3, use este formato (sem o campo "resumo"):
{{
  "texto": "<resposta explicativa, ou perguntas objetivas para o CASO 3>",
  "tipo": "texto"
}}

Não invente fatos fora do contexto. No CASO 1, se mesmo assim faltar alguma
informação específica do usuário para UM dos três campos (mas não todos),
use o texto "Informação não encontrada no contexto." apenas nesse campo, em
vez de inventar.

<CONTEXT_MEMORY>
{memory_block if memory_block.strip() else "[Nenhuma memória relevante encontrada]"}
</CONTEXT_MEMORY>

<CONTEXT_RAG>
{rag_block if rag_block.strip() else "[Nenhum documento relevante foi encontrado.]"}
</CONTEXT_RAG>
"""
        dados = self._chat_json(system_prompt, mensagem)
        if dados.get("tipo") not in ("resumo", "texto"):
            dados["tipo"] = "texto"  # resposta do modelo veio fora do formato esperado; cai pro mais seguro
        self._salvar_memoria(mensagem, dados)
        return dados

    # ------------------------------------------------------------------
    # Modo: revisao (+ secao) -> tipo "revisao"
    # ------------------------------------------------------------------
    def _responder_revisao(self, mensagem, secao):
        secao = (secao or "introducao").strip().lower()
        if secao not in SECOES_VALIDAS:
            secao = "introducao"

        memory_block, rag_block = self._contexto(mensagem)

        system_prompt = f"""Você é um revisor especialista em TCC, avaliando a
seção "{secao}" do trabalho. O usuário vai colar um trecho do texto dele.
Revise esse trecho e aponte observações pontuais.

Responda SOMENTE em JSON, no formato exato:
{{
  "texto": "<comentário geral curto sobre o trecho>",
  "tipo": "revisao",
  "trecho_original": "<o texto original do usuário, sem alterações>",
  "notas": [
    {{
      "id": 1,
      "trecho": "<substring EXATA de trecho_original a destacar>",
      "categoria": "<ex: clareza, metodologia, formatação, argumentação>",
      "comentario": "<explicação da observação>",
      "tom": "<alerta | sugestao | elogio>"
    }}
  ]
}}

IMPORTANTE: cada "trecho" dentro de "notas" precisa ser uma substring
LITERAL de "trecho_original" (caractere por caractere), para poder ser
destacada na tela. Baseie-se no contexto de RAG/memória como referência de
boas práticas, sem inventar regras que não estejam lá.

<CONTEXT_MEMORY>
{memory_block if memory_block.strip() else "[Nenhuma memória relevante encontrada]"}
</CONTEXT_MEMORY>

<CONTEXT_RAG>
{rag_block if rag_block.strip() else "[Nenhum documento relevante foi encontrado.]"}
</CONTEXT_RAG>
"""
        dados = self._chat_json(system_prompt, mensagem)
        dados.setdefault("tipo", "revisao")
        dados.setdefault("trecho_original", mensagem)
        dados.setdefault("notas", [])
        self._salvar_memoria(mensagem, dados)
        return dados

    # ------------------------------------------------------------------
    # Modo: estrutura -> tipo "estrutura"
    # ------------------------------------------------------------------
    def _responder_estrutura(self, mensagem):
        memory_block, rag_block = self._contexto(mensagem)

        system_prompt = f"""Você é um especialista em estrutura de TCC/monografia.
A partir da mensagem do usuário (tema/contexto do trabalho), proponha uma
estrutura de seções para o trabalho.

Responda SOMENTE em JSON, no formato exato:
{{
  "texto": "<comentário curto introdutório>",
  "tipo": "estrutura",
  "secoes": [
    {{"nome": "<nome da seção>", "descricao": "<o que deve conter>"}}
  ],
  "fonte": "<opcional: referência/norma usada como base, ou omita o campo>"
}}

Baseie a estrutura proposta no contexto de RAG quando houver normas/modelos
disponíveis; caso contrário, use uma estrutura acadêmica padrão (introdução,
referencial teórico, metodologia, resultados, conclusão).

<CONTEXT_MEMORY>
{memory_block if memory_block.strip() else "[Nenhuma memória relevante encontrada]"}
</CONTEXT_MEMORY>

<CONTEXT_RAG>
{rag_block if rag_block.strip() else "[Nenhum documento relevante foi encontrado.]"}
</CONTEXT_RAG>
"""
        dados = self._chat_json(system_prompt, mensagem)
        dados.setdefault("tipo", "estrutura")
        dados.setdefault("secoes", [])
        self._salvar_memoria(mensagem, dados)
        return dados

    # ------------------------------------------------------------------
    # Modo: progresso -> tipo "progresso"
    # ------------------------------------------------------------------
    def _responder_progresso(self, mensagem):
        memory_block, rag_block = self._contexto(mensagem)

        system_prompt = f"""Você acompanha o progresso de um TCC a partir do
histórico de conversa do usuário (fornecido como contexto de memória) e da
mensagem atual dele.

Responda SOMENTE em JSON, no formato exato:
{{
  "texto": "<comentário curto sobre o progresso geral>",
  "tipo": "progresso",
  "etapas": [
    {{"nome": "<nome da etapa>", "status": "concluido|em_andamento|nao_iniciado", "detalhe": "<opcional>"}}
  ],
  "secoes": [
    {{"nome": "<nome da seção do TCC>", "status": "concluido|em_andamento|nao_iniciado", "detalhe": "<opcional>"}}
  ],
  "sugestao": "<próximo passo recomendado>"
}}

Se não houver histórico suficiente no contexto de memória, marque as etapas
como "nao_iniciado" e sugira começar pela definição do tema.

<CONTEXT_MEMORY>
{memory_block if memory_block.strip() else "[Nenhuma memória relevante encontrada]"}
</CONTEXT_MEMORY>

<CONTEXT_RAG>
{rag_block if rag_block.strip() else "[Nenhum documento relevante foi encontrado.]"}
</CONTEXT_RAG>
"""
        dados = self._chat_json(system_prompt, mensagem)
        dados.setdefault("tipo", "progresso")
        dados.setdefault("etapas", [])
        dados.setdefault("secoes", [])
        return dados
