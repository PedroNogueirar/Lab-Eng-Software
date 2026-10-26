// Cliente da API. Se o backend rodar em outro endereço, troque API_BASE
// (e habilite CORS no Flask, por exemplo com flask-cors).
const API_BASE = "/api";

const API = {
  token() {
    try { return localStorage.getItem("tcc_token"); } catch { return null; }
  },

  nome() {
    try { return localStorage.getItem("tcc_nome"); } catch { return null; }
  },

  salvar(token, nome) {
    try {
      localStorage.setItem("tcc_token", token);
      localStorage.setItem("tcc_nome", nome);
    } catch { /* sem armazenamento: a sessão dura só nesta aba */ }
  },

  limpar() {
    try {
      localStorage.removeItem("tcc_token");
      localStorage.removeItem("tcc_nome");
    } catch { /* ignorado */ }
  },

  async req(caminho, { metodo = "GET", corpo, formulario, semRedirecionar = false } = {}) {
    // Com FormData o navegador define o Content-Type (com o boundary) sozinho.
    const cabecalhos = formulario ? {} : { "Content-Type": "application/json" };
    const token = this.token();
    if (token) cabecalhos.Authorization = "Bearer " + token;

    let resposta;
    try {
      resposta = await fetch(API_BASE + caminho, {
        method: metodo,
        headers: cabecalhos,
        body: formulario || (corpo === undefined ? undefined : JSON.stringify(corpo)),
      });
    } catch {
      throw new Error("Não foi possível falar com o servidor. Confira se o Flask está rodando.");
    }

    let dados = {};
    try { dados = await resposta.json(); } catch { /* resposta sem corpo */ }

    if (resposta.status === 401 && !semRedirecionar) {
      this.limpar();
      location.href = "/";
      throw new Error(dados.erro || "Sua sessão expirou. Entre de novo.");
    }
    if (!resposta.ok) throw new Error(dados.erro || "Algo deu errado. Tente de novo.");
    return dados;
  },

  get(caminho) {
    return this.req(caminho);
  },

  enviarArquivo(caminho, arquivo) {
    const formulario = new FormData();
    formulario.append("arquivo", arquivo);
    return this.req(caminho, { metodo: "POST", formulario });
  },

  remover(caminho) {
    return this.req(caminho, { metodo: "DELETE" });
  },

  post(caminho, corpo, opcoes = {}) {
    return this.req(caminho, { ...opcoes, metodo: "POST", corpo: corpo || {} });
  },
};
