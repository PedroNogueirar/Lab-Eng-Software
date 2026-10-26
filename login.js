(() => {
  if (API.token()) {
    location.replace("/chat");
    return;
  }

  const formLogin = document.getElementById("form-login");
  const formCadastro = document.getElementById("form-cadastro");
  const erro = document.getElementById("erro");
  const titulo = document.getElementById("titulo");
  const subtitulo = document.getElementById("subtitulo");
  const trocaTexto = document.getElementById("troca-texto");
  const btnTroca = document.getElementById("btn-troca");

  let tela = "entrar";

  function mostrar(qual) {
    tela = qual;
    const entrar = qual === "entrar";
    formLogin.hidden = !entrar;
    formCadastro.hidden = entrar;
    titulo.textContent = entrar ? "Bem-vindo de volta" : "Crie sua conta";
    subtitulo.textContent = entrar
      ? "Converse com uma IA que orienta e revisa o seu TCC."
      : "Leva menos de um minuto. Depois é só começar a conversar.";
    trocaTexto.textContent = entrar ? "Não tem conta?" : "Já tem conta?";
    btnTroca.textContent = entrar ? "Cadastre-se" : "Entrar";
    erro.textContent = "";
    (entrar ? formLogin : formCadastro).querySelector("input").focus();
  }

  btnTroca.addEventListener("click", () => mostrar(tela === "entrar" ? "cadastro" : "entrar"));

  // O login com Google precisa de uma chave OAuth do projeto. Fica para quando o backend real entrar.
  document.getElementById("btn-google").addEventListener("click", () => {
    erro.textContent = "O login com Google ainda não está ligado nesta versão. Use e-mail e senha.";
  });

  async function enviar(form, caminho, corpo, rotuloEspera) {
    const botao = form.querySelector("button[type=submit]");
    const rotulo = botao.textContent;
    botao.disabled = true;
    botao.textContent = rotuloEspera;
    erro.textContent = "";
    try {
      const r = await API.post(caminho, corpo, { semRedirecionar: true });
      API.salvar(r.token, r.nome);
      location.href = "/chat";
    } catch (e) {
      erro.textContent = e.message;
      botao.disabled = false;
      botao.textContent = rotulo;
    }
  }

  formLogin.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = new FormData(formLogin);
    if (!d.get("email") || !d.get("senha")) {
      erro.textContent = "Preencha e-mail e senha para entrar.";
      return;
    }
    enviar(formLogin, "/login", { email: d.get("email"), senha: d.get("senha") }, "Entrando");
  });

  formCadastro.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = new FormData(formCadastro);
    if (!d.get("nome") || !d.get("email") || !d.get("senha")) {
      erro.textContent = "Preencha nome, e-mail e senha para criar a conta.";
      return;
    }
    enviar(
      formCadastro,
      "/cadastro",
      { nome: d.get("nome"), email: d.get("email"), senha: d.get("senha") },
      "Criando conta"
    );
  });
})();
