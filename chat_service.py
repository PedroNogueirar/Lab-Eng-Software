# webapp/chat_service.py
"""Singleton do CallLlama/GeradorRespostas.

O CallLlama carrega o reranker local (transformers) e inicializa RAG/memória
no __init__, então ele deve ser instanciado UMA VEZ só (não por request).
A inicialização acontece de forma preguiçosa (lazy), na primeira chamada que
precisar dele, para o servidor Flask subir rápido.
"""
import threading

_lock = threading.Lock()
_call_llama = None
_gerador = None


def obter_gerador():
    global _call_llama, _gerador
    if _gerador is None:
        with _lock:
            if _gerador is None:
                # imports aqui dentro (e não no topo do módulo) para não pagar o
                # custo de carregar torch/transformers só por importar este arquivo.
                from llama.call_llama import CallLlama
                from llama.responder import GeradorRespostas

                _call_llama = CallLlama()
                _gerador = GeradorRespostas(_call_llama)
    return _gerador
