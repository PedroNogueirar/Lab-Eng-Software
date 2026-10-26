# call_llama.py
import os
import json
from tqdm import tqdm
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings

# Carrega o .env da raiz do projeto (um nível acima de llama/), independente
# de onde o notebook/script é executado.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from llama.memory_support.memory_support import Memory_support
from llama.RAG.BuildVectorStore import PDFVectorStore
from llama.RAG.rank_context import RankContext
from llama.perplexity import CalculatePerplexity

class CallLlama:
    def __init__(self,
                 model_id: str = "gpt-4o-mini",
                 log_file: str = "logs_llama/llama_logs.jsonl"):

        print("🚀 Inicializando call_llama...")

        # Configurações de caminhos base
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_id = model_id
        self.log_file = os.path.join(self.base_dir, log_file)
        self.memory_path = os.path.join(self.base_dir, "memory_support_db")
        print(self.memory_path)
        os.makedirs(self.memory_path, exist_ok=True)

        # Definição das etapas de carregamento
        steps = [
            {"desc": "🔍 Carregando sistema de Re Rank", "func": self._init_rerank},
            {"desc": "🧠 Iniciando sistema de memória", "func": self._init_memory},
            {"desc": "📚 Iniciando sistema de RAG", "func": self._init_rag},
            {"desc": "⚙️ Configurando cliente OpenAI", "func": self._init_llm_client},
            {"desc": "📊 Inicializando Answer Evaluation", "func": self._init_perplexity}
        ]

        # Barra de progresso principal
        with tqdm(total=len(steps), desc="Progresso Geral", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:
            for step in steps:
                pbar.set_description(step["desc"])
                step["func"]()  # Executa a função de inicialização
                pbar.update(1)

        print("\n✅ call_llama inicializado com sucesso!")

    # --- Métodos Auxiliares para organizar o código ---

    def _init_rerank(self):
        self.rank_context = RankContext(model="BAAI/bge-reranker-v2-m3")

    def _init_memory(self):
        self.memory_support = Memory_support(
            db_path=self.memory_path,
            embedding_model=OpenAIEmbeddings(model="text-embedding-3-small"),
            threshold_distance=0.70,
            max_memories=300
        )

    def _init_rag(self):
        self.rag_support = PDFVectorStore(persist_dir='llama/RAG/db')
        self.db_rag = self.rag_support._load_db()

    def _init_perplexity(self):
        # Não depende mais de modelo/tokenizer locais: a API da OpenAI já
        # retorna os logprobs dos tokens gerados (ver invoke()).
        self.calculate_perplexity = CalculatePerplexity()

    # -------------------------------------------------------------------------
    #   CONFIGURA CLIENTE OPENAI
    # -------------------------------------------------------------------------
    def _init_llm_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Variável de ambiente OPENAI_API_KEY não encontrada. Defina-a "
                "no seu sistema antes de instanciar o CallLlama "
                "(Windows: setx OPENAI_API_KEY \"sua-chave\" e reabra o terminal; "
                "Linux/Mac: export OPENAI_API_KEY=\"sua-chave\")."
            )
        self.client = OpenAI(api_key=api_key)

    # -------------------------------------------------------------------------
    #   LOG INTERAÇÕES
    # -------------------------------------------------------------------------
    def _log_interaction(self, user, response):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "response": response
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def _extract_info_chunks(self, user, k):

        relevant_chunks = self.db_rag.max_marginal_relevance_search(
            user, 
            k=k,        # Quantidade para o Re-ranker analisar
            fetch_k=50,  # Quantidade que o Chroma analisa internamente
            lambda_mult=0.50
        )

        reranked_docs = self.rank_context.call_rank(query=user, documents = relevant_chunks)

        return reranked_docs

    # -------------------------------------------------------------------------
    #   MONTA PROMPT (mensagens no formato da Chat Completions API)
    # -------------------------------------------------------------------------
    def build_prompt(self, user: str):

        memory_block = self.memory_support.mount_prompt_memory(user, k=3)
        rag_docs = self._extract_info_chunks(user, k=20)
    
        if rag_docs:
            rag_block = "\n\n".join(
                f"[FONTE {d.id}] {d.page_content}"
                for d in rag_docs
            )
        else:
            rag_block = ""

        print(f"RAG_BLOCK: {rag_block}")

        system_prompt = f"""Você é um especialista em GRC.

Construa uma resposta completa e explicativa usando todas as informações relevantes disponíveis.

Responda utilizando as informações do <CONTEXT_RAG> como base factual.
Use também o <CONTEXT_MEMORY> se complementar a resposta.

Não invente fatos que não estejam no contexto.

Se múltiplos documentos se complementarem, combine-os.

Se não houver informação suficiente:
Informação não encontrada no contexto.

<CONTEXT_MEMORY>
{memory_block if memory_block.strip() else "[Nenhuma memória relevante encontrada]"}
</CONTEXT_MEMORY>

<CONTEXT_RAG>
{rag_block if rag_block.strip() else "[Nenhum documento relevante foi encontrado.]"}
</CONTEXT_RAG>
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ]

        return messages


    # -------------------------------------------------------------------------
    #   INVOCAÇÃO PRINCIPAL (chamada à API da OpenAI)
    # -------------------------------------------------------------------------
    def invoke(self, user: str, temp=0.3, max_tokens=512, top_p=0.7, top_k=40):
        # Nota: `top_k` não existe na Chat Completions API da OpenAI; o
        # parâmetro foi mantido apenas para não quebrar chamadas existentes
        # que ainda o informam, mas é ignorado.

        messages = self.build_prompt(user)

        # =============================
        # GERAR RESPOSTA (API da OpenAI)
        # =============================
        completion = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            temperature=temp,
            max_tokens=max_tokens,
            top_p=top_p,
            logprobs=True,
        )

        answer = completion.choices[0].message.content

        # =============================
        # PERPLEXITY (a partir dos logprobs retornados pela API)
        # =============================
        pairs, mean_lp, ppl = self.calculate_perplexity.get_logprobs(completion)

        # ---- MEMÓRIA ----
        try:
            self.memory_support.append_on_memory_database(user, answer)
        except Exception as e:
            print(f"⚠️ Erro ao salvar memória: {e}")

        # ---- LOG ----
        self._log_interaction(user, answer)

        print("\nPairs logprob x tokens\n", pairs)
        print(f"\nMean logprob: {mean_lp:.4f}")
        print(f"Perplexity: {ppl:.4f}")

        return answer
