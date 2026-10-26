# wsgi.py — ponto de entrada para servidores WSGI de produção (gunicorn, uwsgi).
#
# Em desenvolvimento local (Windows), continue usando: python run.py
# Em produção (instância EC2 / Docker), use algo como:
#   gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:5000 wsgi:app
#
# --workers 1: o CallLlama carrega um modelo de reranking local (transformers)
# na memória na primeira requisição, UMA VEZ por processo. Cada worker do
# gunicorn é um processo separado, então mais de 1 worker = o modelo
# carregado várias vezes (mais RAM usada). Para um projeto de TCC, 1 worker
# com várias threads já atende bem; só aumente --workers se a instância
# tiver RAM de sobra e o uso justificar.
import os

# Em Windows + Anaconda é comum torch/numpy/scikit-learn carregarem cópias
# duplicadas do runtime OpenMP (libiomp5md.dll), o que derruba o processo
# sem traceback Python nenhum ("OMP: Error #15"). Isso precisa ser definido
# ANTES de qualquer import pesado (webapp -> llama -> torch/transformers).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from webapp import create_app

app = create_app()
