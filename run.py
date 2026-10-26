# run.py — ponto de entrada do backend TCChat.
#
# Uso:
#   pip install -r requirements.txt
#   # preencha a OPENAI_API_KEY no arquivo .env
#   python run.py
#
# O servidor sobe em http://localhost:5000/  (tela de login)
import os

# Em Windows + Anaconda é comum torch/numpy/scikit-learn carregarem cópias
# duplicadas do runtime OpenMP (libiomp5md.dll), o que derruba o processo
# sem traceback Python nenhum ("OMP: Error #15"). Isso precisa ser definido
# ANTES de qualquer import pesado (webapp -> llama -> torch/transformers).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)          # garante que caminhos relativos (ex: llama/RAG/db) resolvem certo
sys.path.insert(0, BASE_DIR)

from webapp import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    # use_reloader=False: o reloader padrao do Flask fica de olho em TODOS os
    # arquivos .py importados, inclusive dentro de bibliotecas como torch -- que
    # mexe nos proprios arquivos internos ao carregar. Isso faz o reloader
    # reiniciar o servidor NO MEIO de uma requisicao de chat, derrubando a
    # conexao do navegador. Sem isso, a primeira mensagem sempre falha.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
