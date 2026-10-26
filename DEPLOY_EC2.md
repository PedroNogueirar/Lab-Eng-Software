# Guia de deploy na EC2 (quando for a hora de migrar)

Este guia assume que você já tem uma instância EC2 criada. O código já está
pronto pro deploy; aqui vai o passo a passo de quando você for rodar de
verdade.

## 1. Escolha de instância

O reranker local (`BAAI/bge-reranker-v2-m3`, via `transformers`) é o que
mais pesa em RAM/CPU — ele roda inteiro na memória da instância. Recomendo:

- **Mínimo**: `t3.medium` (2 vCPU, 4 GB RAM) — deve rodar, mas sem folga.
- **Confortável**: `t3.large` (2 vCPU, 8 GB RAM) ou `t3.xlarge`.
- Não precisa de GPU — tudo que roda local (reranker) é pequeno o bastante
  para CPU; o resto (chat, embeddings) já vai via API da OpenAI.

Sistema operacional: Amazon Linux 2023 ou Ubuntu 22.04/24.04 — os comandos
abaixo citam os dois onde o pacote muda de nome.

## 2. Security Group (portas)

- `22` (SSH) — liberado só para o seu IP, não para `0.0.0.0/0`.
- Se for usar **Nginx na frente** (recomendado): libere `80` (e `443` se for
  configurar HTTPS com domínio) para `0.0.0.0/0`.
- Se for acessar **direto pela porta do Flask/gunicorn** (mais simples, sem
  Nginx): libere a `5000` para `0.0.0.0/0` em vez de 80/443.

## 3. Copiar o projeto para a instância

A pasta inteira `Lab_engenharia_Software/` é o que precisa ir para a
instância (ela já está isolada de tudo que não é necessário para rodar).
Algumas formas de levar:

```bash
# Do seu computador, via scp (ajuste o caminho da sua chave .pem e o IP/DNS da instância):
scp -i sua-chave.pem -r Lab_engenharia_Software ec2-user@SEU-IP-OU-DNS:~/

# ...ou via rsync, se preferir (reenvia só o que mudou nas próximas vezes):
rsync -avz -e "ssh -i sua-chave.pem" Lab_engenharia_Software/ ec2-user@SEU-IP-OU-DNS:~/Lab_engenharia_Software/
```

(troque `ec2-user` por `ubuntu` se a instância for Ubuntu)

**Não leve o `.env` com a chave da OpenAI por esse caminho se puder evitar**
— é mais seguro criar o `.env` direto na instância (passo 5), aparecendo só
lá, nunca passeando por e-mail/chat/repositório.

## 4. Instalar dependências na instância

```bash
ssh -i sua-chave.pem ec2-user@SEU-IP-OU-DNS   # entra na instância

# Amazon Linux 2023:
sudo dnf install -y python3.11 python3.11-pip git
# Ubuntu:
sudo apt update && sudo apt install -y python3-pip python3-venv git

cd ~/Lab_engenharia_Software
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt -r deploy/requirements-prod.txt
```

Isso vai baixar torch/transformers (pesado, pode levar alguns minutos) e o
`gunicorn` (que só existe nesse segundo arquivo porque não roda no Windows).

## 5. Configurar a chave da OpenAI

```bash
cd ~/Lab_engenharia_Software
nano .env
```

Confirme que tem uma linha assim (sem isso o backend não sobe):

```
OPENAI_API_KEY="sua-chave-aqui"
```

## 6. Primeira execução manual (antes de virar serviço)

Rode manualmente primeiro, só para ver se sobe sem erro e para deixar a
base RAG já construída antes de colocar o `systemd` de verdade:

```bash
source venv/bin/activate
python run.py
```

Acesse `http://SEU-IP-OU-DNS:5000/` no navegador. Se abrir a tela de login,
funcionou. Pare com `Ctrl+C` depois de confirmar.

(A primeira pergunta no chat vai reconstruir o índice do RAG do zero,
chamando a API de embeddings da OpenAI — é esperado, documentado no
`BACKEND_LEIAME.md`.)

## 7. Subir como serviço (fica de pé sozinho)

```bash
nano deploy/tcchat.service
# ajuste User= e os caminhos de WorkingDirectory/ExecStart se o usuário ou
# a pasta não forem exatamente "ec2-user" / "/home/ec2-user/Lab_engenharia_Software"

sudo cp deploy/tcchat.service /etc/systemd/system/tcchat.service
sudo systemctl daemon-reload
sudo systemctl enable --now tcchat
sudo systemctl status tcchat     # deve aparecer "active (running)"
journalctl -u tcchat -f          # Ctrl+C para sair do acompanhamento de logs
```

A partir daqui, a aplicação reinicia sozinha se cair e volta a subir
automaticamente se a instância reiniciar.

## 8. (Opcional) Nginx na frente + HTTPS

Só faça isso se quiser acessar pela porta 80/443 em vez da 5000, e/ou
quiser HTTPS com domínio.

```bash
# Amazon Linux:
sudo dnf install -y nginx
# Ubuntu:
sudo apt install -y nginx

sudo cp deploy/nginx_tcchat.conf /etc/nginx/conf.d/tcchat.conf   # Amazon Linux
# ou, no Ubuntu:
# sudo cp deploy/nginx_tcchat.conf /etc/nginx/sites-available/tcchat.conf
# sudo ln -s /etc/nginx/sites-available/tcchat.conf /etc/nginx/sites-enabled/

sudo nginx -t && sudo systemctl enable --now nginx
```

Para HTTPS, só funciona com um domínio de verdade apontando (registro A) para
o IP da instância:

```bash
sudo dnf install -y certbot python3-certbot-nginx   # Amazon Linux
# sudo apt install -y certbot python3-certbot-nginx  # Ubuntu

sudo certbot --nginx -d seu-dominio.com.br
```

## 9. Alternativa: Docker

Se preferir não instalar Python/torch direto na instância (ex.: para trocar
de instância/provedor sem reconfigurar tudo), o `Dockerfile` na raiz do
projeto já está pronto:

```bash
docker build -t tcchat .
docker run -d --name tcchat -p 5000:5000 \
    --env-file .env \
    -v tcchat_dados:/app/webapp_data \
    -v tcchat_rag_db:/app/llama/RAG/db \
    -v tcchat_memoria:/app/llama/memory_support_db \
    tcchat
```

Os três volumes (`-v`) são o que precisa sobreviver a um `docker rm`/restart:
contas de usuário + histórico, índice do RAG, e memória de conversa.

## 10. Checklist rápido antes de considerar "no ar"

- [ ] `.env` com `OPENAI_API_KEY` real criado **direto na instância** (nunca commitado)
- [ ] Security Group liberando só a porta certa (5000, ou 80/443 se usar Nginx)
- [ ] Serviço rodando via `systemctl status tcchat` (ou container via `docker ps`)
- [ ] Testou criar conta, logar e mandar uma mensagem em cada um dos 4 modos
      (tema, revisão, estrutura, progresso)
- [ ] `webapp_data/`, `llama/RAG/db/` e `llama/memory_support_db/` estão em
      disco persistente da instância (volume EBS padrão já resolve — não é
      preciso fazer nada extra aqui, só não usar instance store efêmero)
