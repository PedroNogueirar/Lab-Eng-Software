# Dockerfile do TCChat — alternativa ao deploy direto via systemd (deploy/tcchat.service).
# Útil se no futuro vocês quiserem trocar de instância/provedor sem reconfigurar tudo de novo.
#
# Build:
#   docker build -t tcchat .
#
# Run (ajuste os volumes se quiser nomes diferentes; eles existem para que
# contas de usuário, histórico, índice do RAG e memória de conversa
# sobrevivam a um "docker rm"/restart do container):
#   docker run -d --name tcchat -p 5000:5000 \
#       --env-file .env \
#       -v tcchat_dados:/app/webapp_data \
#       -v tcchat_rag_db:/app/llama/RAG/db \
#       -v tcchat_memoria:/app/llama/memory_support_db \
#       tcchat
#
# Se for usar atrás do Nginx (deploy/nginx_tcchat.conf), mantenha o -p 5000:5000
# e aponte o proxy_pass para 127.0.0.1:5000 como já está no arquivo.

FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema que torch/transformers costumam precisar.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY deploy/requirements-prod.txt deploy/requirements-prod.txt
RUN pip install --no-cache-dir -r requirements.txt -r deploy/requirements-prod.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "120", "--bind", "0.0.0.0:5000", "wsgi:app"]
