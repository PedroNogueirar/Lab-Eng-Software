(() => {
  if (!API.token()) {
    location.replace("/");
    return;
  }

  const $ = (id) => document.getElementById(id);

  // Cria elementos sem usar innerHTML: o texto do estudante entra sempre como texto.
  function el(tag, attrs, ...filhos) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === "class") n.className = v;
      else n.setAttribute(k, v === true ? "" : v);
    }
    n.append(...filhos.flat().filter((f) => f != null && f !== false));
    return n;
  }

  function icone(nome) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("class", "ico");
    svg.setAttribute("aria-hidden", "true");
    const uso = document.createElementNS(ns, "use");
    uso.setAttribute("href", "/static/icons.svg#" + nome);
    svg.append(uso);
    return svg;
  }

  const ROTULO_STATUS = {
    concluido: "concluído",
    em_andamento: "em andamento",
    nao_iniciado: "não iniciado",
  };

  const PLACEHOLDER = {
    tema: "Conte sua ideia de tema, mesmo vaga",
    revisao: "Cole aqui o trecho que você escreveu",
  };

  const SUGESTOES = [
    { texto: "Quero definir o tema do meu TCC", modo: "tema", enviar: true },
    { texto: "Mostre a estrutura esperada do trabalho", modo: "estrutura", enviar: true },
    { texto: "Quero revisar um trecho que escrevi", modo: "revisao", enviar: false },
    { texto: "Como está meu progresso?", modo: "progresso", enviar: true },
  ];

  let modo = "tema";
  let secao = "introducao";
  let ocupado = false;
  let temMensagens = false;
  let primeiraPergunta = "";
  let conversaIdAtual = null;
  let conversas = [];

  /* ---------- Telas: inicial x conversa ---------- */

  function mostrarConversa(sim) {
    temMensagens = sim;
    $("vazio").hidden = sim;
    $("mensagens").hidden = !sim;
  }

  function tituloConversa(c) {
    const titulo = (c.titulo || "Nova conversa").trim();
    return titulo.length > 32 ? titulo.slice(0, 32).trimEnd() + "…" : titulo;
  }

  function renderRecentes() {
    if (!conversas.length) {
      $("recentes").replaceChildren(el("li", { class: "recentes-vazio" }, "Nenhuma conversa ainda"));
      return;
    }
    $("recentes").replaceChildren(
      ...conversas.map((c) => {
        const ativa = c.id === conversaIdAtual;
        const abrir = el(
          "button",
          { type: "button", class: ativa ? "item-ativo" : null, "aria-current": ativa ? "true" : false },
          icone("conversa"),
          el("span", {}, tituloConversa(c))
        );
        abrir.addEventListener("click", () => abrirConversa(c.id));
        const remover = el(
          "button",
          { type: "button", class: "btn-icone", "aria-label": "Excluir conversa" },
          icone("lixeira")
        );
        remover.addEventListener("click", (ev) => {
          ev.stopPropagation();
          excluirConversa(c.id);
        });
        return el("li", {}, abrir, remover);
      })
    );
  }

  async function carregarConversas() {
    try {
      const r = await API.get("/conversas");
      conversas = r.conversas;
    } catch {
      conversas = [];
    }
    renderRecentes();
  }

  async function abrirConversa(id) {
    if (ocupado || id === conversaIdAtual) {
      abrirLateral(false);
      return;
    }
    abrirLateral(false);
    conversaIdAtual = id;
    $("mensagens").replaceChildren();
    primeiraPergunta = "";
    mostrarConversa(false);
    definirModo("tema");
    renderRecentes();
    try {
      const { mensagens } = await API.get("/historico?conversa_id=" + id);
      for (const m of mensagens) {
        if (m.papel === "usuario") {
          if (!primeiraPergunta) primeiraPergunta = m.conteudo;
          msgUsuario(m.conteudo);
        } else {
          msgBot(m.conteudo, true);
        }
      }
      if (mensagens.length) $("rolagem").scrollTop = $("rolagem").scrollHeight;
    } catch (e) {
      msgErro(e.message);
    }
  }

  async function excluirConversa(id) {
    try {
      await API.remover("/conversa/" + id);
    } catch (e) {
      msgErro(e.message);
      return;
    }
    const eraAtual = id === conversaIdAtual;
    await carregarConversas();
    if (!eraAtual) return;
    conversaIdAtual = null;
    if (conversas.length) {
      await abrirConversa(conversas[0].id);
    } else {
      $("mensagens").replaceChildren();
      primeiraPergunta = "";
      mostrarConversa(false);
      renderRecentes();
    }
  }

  function rolarParaFim() {
    const r = $("rolagem");
    r.scrollTop = r.scrollHeight;
  }

  /* ---------- Etapas (cartão de progresso) ---------- */

  function renderEtapa(item) {
    return el(
      "li",
      { class: "etapa", "data-status": item.status },
      el("span", { class: "indicador", "aria-hidden": "true" }),
      el(
        "span",
        {},
        el("span", { class: "nome" }, item.nome),
        el("span", { class: "detalhe" }, item.detalhe || ROTULO_STATUS[item.status])
      )
    );
  }

  /* ---------- Mensagens ---------- */

  function msgUsuario(texto) {
    mostrarConversa(true);
    $("mensagens").append(el("div", { class: "msg-usuario" }, el("p", { class: "balao" }, texto)));
    rolarParaFim();
  }

  function msgErro(texto) {
    mostrarConversa(true);
    $("mensagens").append(
      el("div", { class: "msg-bot erro-msg", role: "alert" }, el("p", { class: "fala" }, texto))
    );
    rolarParaFim();
  }

  function botaoClaro(rotulo, aoClicar) {
    const b = el("button", { class: "btn-claro", type: "button" }, rotulo);
    b.addEventListener("click", aoClicar);
    return b;
  }

  function botaoCheio(rotulo, aoClicar) {
    const b = el("button", { class: "btn-cheio", type: "button" }, rotulo);
    b.addEventListener("click", aoClicar);
    return b;
  }

  // Cada tipo de resposta do backend tem um desenho próprio.
  const RENDER = {
    texto: () => [],

    resumo(r, leitura) {
      const d = r.resumo;
      const cartao = el(
        "dl",
        { class: "resumo" },
        el("dt", {}, "Tema"), el("dd", {}, d.tema),
        el("dt", {}, "Problema"), el("dd", {}, d.problema),
        el("dt", {}, "Objetivo geral"), el("dd", {}, d.objetivo_geral)
      );
      const saida = [cartao];
      if (!leitura) {
        const confirmar = botaoCheio("Confirmar", () => {
          if (ocupado) return;
          confirmar.disabled = ajustar.disabled = true;
          enviar("Confirmo o resumo", { modo: "tema" });
        });
        const ajustar = botaoClaro("Ajustar", () => {
          if (ocupado) return;
          confirmar.disabled = ajustar.disabled = true;
          enviar("Quero ajustar algo no resumo", { modo: "tema" });
        });
        saida.push(el("div", { class: "acoes" }, confirmar, ajustar));
      }
      return saida;
    },

    estrutura(r, leitura) {
      const lista = el(
        "ul",
        { class: "secoes-abnt" },
        r.secoes.map((s) =>
          el(
            "li",
            {},
            el(
              "label",
              {},
              el("input", { type: "checkbox" }),
              el("span", {}, el("strong", {}, s.nome), el("span", { class: "desc" }, s.descricao))
            )
          )
        )
      );
      const saida = [lista];
      if (r.fonte) saida.push(el("p", { class: "fonte" }, "Fonte: " + r.fonte));
      if (!leitura) {
        const entendi = botaoClaro("Entendi a estrutura", () => {
          if (ocupado) return;
          entendi.disabled = true;
          enviar("Entendi a estrutura", { modo: "estrutura" });
        });
        saida.push(el("div", { class: "acoes" }, entendi));
      }
      return saida;
    },

    revisao(r) {
      const pagina = el(
        "div",
        { class: "pagina-revisada", role: "group", "aria-label": "Seu trecho com marcações" },
        marcarTrecho(r.trecho_original, r.notas)
      );
      const notas = el(
        "ol",
        { class: "notas" },
        r.notas.map((n) =>
          el(
            "li",
            { class: "nota", "data-tom": n.tom },
            el("span", { class: "nota-num", "aria-hidden": "true" }, String(n.id)),
            el(
              "div",
              {},
              el("span", { class: "nota-categoria" }, n.categoria),
              el("span", { class: "nota-texto" }, n.comentario)
            )
          )
        )
      );
      return [pagina, notas];
    },

    progresso(r) {
      const cartao = el(
        "div",
        { class: "cartao-progresso" },
        el("ul", { class: "etapas" }, r.etapas.map(renderEtapa)),
        el("p", { class: "subtitulo-lista" }, "Revisão por seção"),
        el("ul", { class: "etapas" }, r.secoes.map(renderEtapa))
      );
      const saida = [cartao];
      if (r.sugestao) saida.push(el("p", { class: "sugestao" }, "Sugestão: " + r.sugestao));
      return saida;
    },
  };

  // Destaca no texto do estudante os trechos que viraram notas.
  function marcarTrecho(texto, notas) {
    const marcas = [];
    for (const n of notas) {
      if (!n.trecho) continue;
      const i = texto.indexOf(n.trecho);
      if (i >= 0) marcas.push({ ini: i, fim: i + n.trecho.length, id: n.id });
    }
    marcas.sort((a, b) => a.ini - b.ini);

    const frag = document.createDocumentFragment();
    let pos = 0;
    for (const m of marcas) {
      if (m.ini < pos) continue; // trechos sobrepostos: mantém o primeiro
      frag.append(
        texto.slice(pos, m.ini),
        el("mark", { class: "trecho" }, texto.slice(m.ini, m.fim)),
        el("sup", { class: "marca-num" }, String(m.id))
      );
      pos = m.fim;
    }
    frag.append(texto.slice(pos));
    return frag;
  }

  function msgBot(r, leitura = false) {
    mostrarConversa(true);
    const caixa = el("div", { class: "msg-bot" });
    if (r.texto) caixa.append(el("p", { class: "fala" }, r.texto));
    const desenho = RENDER[r.tipo];
    if (desenho) caixa.append(...desenho(r, leitura));
    if (r.acao && !leitura) {
      caixa.append(el("div", { class: "acoes" }, botaoClaro(r.acao.rotulo, () => executarAcao(r.acao))));
    }
    $("mensagens").append(caixa);
    rolarParaFim();
  }

  /* ---------- Modos e ações ---------- */

  function definirModo(novo, novaSecao) {
    modo = novo;
    if (novaSecao) {
      secao = novaSecao;
      $("seletor-secao").value = novaSecao;
    }
    $("seletor-modo").value = modo;
    $("seletor-secao").hidden = modo !== "revisao";
    $("campo").placeholder = PLACEHOLDER[modo] || "";
    ajustarAltura();
    $("campo").focus();
  }

  function executarAcao(acao) {
    if (ocupado) return;
    abrirLateral(false);
    if (acao.modo === "estrutura") {
      enviar("Quero ver a estrutura do trabalho", { modo: "estrutura" });
    } else if (acao.modo === "progresso") {
      enviar("Como está meu progresso?", { modo: "progresso" });
    } else if (acao.enviar) {
      definirModo(acao.modo, acao.secao);
      enviar(acao.texto, { modo: acao.modo });
    } else {
      definirModo(acao.modo, acao.secao);
    }
  }

  $("seletor-modo").addEventListener("change", (ev) => definirModo(ev.target.value));
  $("seletor-secao").addEventListener("change", (ev) => { secao = ev.target.value; });

  $("sugestoes").replaceChildren(
    ...SUGESTOES.map((s) => {
      const b = el("button", { type: "button", class: "sugestao-card" }, s.texto);
      b.addEventListener("click", () => executarAcao(s));
      return b;
    })
  );

  /* ---------- Envio ---------- */

  async function enviar(texto, opcoes = {}) {
    if (ocupado) return;
    const m = opcoes.modo || modo;
    const s = opcoes.secao || secao;
    ocupado = true;
    $("btn-enviar").disabled = true;

    if (!temMensagens) primeiraPergunta = texto;
    msgUsuario(texto);
    const espera = el("div", { class: "msg-bot carregando" }, el("p", { class: "fala" }, "Pensando…"));
    $("mensagens").append(espera);
    rolarParaFim();

    try {
      const r = await API.post("/chat", { mensagem: texto, modo: m, secao: s, conversa_id: conversaIdAtual });
      espera.remove();
      msgBot(r);
      if (r.conversa_id) conversaIdAtual = r.conversa_id;
      await carregarConversas();
    } catch (e) {
      espera.remove();
      msgErro(e.message);
    } finally {
      ocupado = false;
      atualizarBotaoEnviar();
    }
  }

  function atualizarBotaoEnviar() {
    $("btn-enviar").disabled = ocupado || !$("campo").value.trim();
  }

  function ajustarAltura() {
    const c = $("campo");
    c.style.height = "auto";
    c.style.height = Math.min(c.scrollHeight, 224) + "px";
  }

  $("campo").addEventListener("input", () => {
    ajustarAltura();
    atualizarBotaoEnviar();
  });

  $("campo").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault();
      $("form-msg").requestSubmit();
    }
  });

  $("form-msg").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const texto = $("campo").value.trim();
    if (!texto || ocupado) return;
    $("campo").value = "";
    ajustarAltura();
    atualizarBotaoEnviar();
    enviar(texto);
  });

  /* ---------- Nova conversa ---------- */

  async function novaConversa() {
    if (ocupado) return;
    abrirLateral(false);
    let novoId;
    try {
      const r = await API.post("/conversa/nova");
      novoId = r.conversa_id;
    } catch (e) {
      msgErro(e.message);
      return;
    }
    conversaIdAtual = novoId;
    $("mensagens").replaceChildren();
    primeiraPergunta = "";
    mostrarConversa(false);
    definirModo("tema");
    $("rolagem").scrollTop = 0;
    await carregarConversas();
  }

  $("menu-nova").addEventListener("click", novaConversa);
  $("btn-nova-topo").addEventListener("click", novaConversa);
  $("menu-estrutura").addEventListener("click", () => executarAcao({ modo: "estrutura" }));
  $("menu-progresso").addEventListener("click", () => executarAcao({ modo: "progresso" }));

  /* ---------- Barra lateral no celular ---------- */

  function abrirLateral(abrir) {
    $("lateral").classList.toggle("aberta", abrir);
    $("veu").classList.toggle("aberto", abrir);
    $("btn-menu").setAttribute("aria-expanded", String(abrir));
  }

  $("btn-menu").addEventListener("click", () => abrirLateral(true));
  $("veu").addEventListener("click", () => abrirLateral(false));

  /* ---------- Base de conhecimento ---------- */

  let docs = [];
  let focoAntes = null;

  function tamanhoLegivel(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
    return (bytes / 1024 / 1024).toFixed(1).replace(".", ",") + " MB";
  }

  function renderDocs() {
    const n = docs.length;
    $("contagem-docs").textContent = `${n} ${n === 1 ? "documento" : "documentos"} na base`;
    $("docs-vazio").hidden = n > 0;
    $("lista-docs").replaceChildren(
      ...docs.map((d) => {
        const remover = el("button", { type: "button", class: "btn-icone", "aria-label": "Remover " + d.nome }, icone("lixeira"));
        remover.addEventListener("click", async () => {
          try {
            await API.remover("/documentos/" + encodeURIComponent(d.id));
            docs = docs.filter((x) => x.id !== d.id);
            renderDocs();
          } catch (e) {
            $("erro-base").textContent = e.message;
          }
        });
        return el(
          "li",
          {},
          icone("arquivo"),
          el("span", { class: "doc-nome" }, d.nome),
          el("span", { class: "doc-tam" }, tamanhoLegivel(d.tamanho)),
          remover
        );
      })
    );
  }

  async function carregarDocs() {
    try {
      docs = (await API.get("/documentos")).documentos;
    } catch { docs = []; }
    renderDocs();
  }

  async function enviarArquivos(arquivos) {
    $("erro-base").textContent = "";
    for (const arq of arquivos) {
      try {
        docs.push(await API.enviarArquivo("/documentos", arq));
        renderDocs();
      } catch (e) {
        $("erro-base").textContent = `${arq.name}: ${e.message}`;
      }
    }
  }

  function abrirBase() {
    abrirLateral(false);
    focoAntes = document.activeElement;
    $("erro-base").textContent = "";
    $("modal-base").hidden = false;
    $("modal-fechar").focus();
  }

  function fecharBase() {
    $("modal-base").hidden = true;
    if (focoAntes && focoAntes.focus) focoAntes.focus();
  }

  $("menu-base").addEventListener("click", abrirBase);
  $("btn-base").addEventListener("click", abrirBase);
  $("modal-fechar").addEventListener("click", fecharBase);
  $("modal-fundo").addEventListener("click", fecharBase);

  $("arquivo").addEventListener("change", (ev) => {
    enviarArquivos([...ev.target.files]);
    ev.target.value = "";
  });

  const zona = $("zona-envio");
  ["dragenter", "dragover"].forEach((nome) =>
    zona.addEventListener(nome, (ev) => { ev.preventDefault(); zona.classList.add("sobre"); })
  );
  ["dragleave", "drop"].forEach((nome) =>
    zona.addEventListener(nome, (ev) => { ev.preventDefault(); zona.classList.remove("sobre"); })
  );
  zona.addEventListener("drop", (ev) => enviarArquivos([...ev.dataTransfer.files]));

  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    if (!$("modal-base").hidden) fecharBase();
    else abrirLateral(false);
  });

  /* ---------- Sair ---------- */

  $("btn-sair").addEventListener("click", async () => {
    try { await API.post("/logout", {}, { semRedirecionar: true }); } catch { /* sai mesmo assim */ }
    API.limpar();
    location.href = "/";
  });

  /* ---------- Início ---------- */

  async function iniciar() {
    const nome = API.nome() || "";
    const primeiroNome = nome.split(" ")[0];
    $("saudacao").textContent = primeiroNome ? `Olá, ${primeiroNome}.` : "Olá.";
    $("nome-usuario").textContent = nome;
    $("avatar").textContent = (nome[0] || "?").toUpperCase();
    API.get("/me").then((u) => { $("email-usuario").textContent = u.email; }).catch(() => {});

    definirModo("tema");
    atualizarBotaoEnviar();
    carregarDocs();

    await carregarConversas();
    if (conversas.length) {
      conversaIdAtual = conversas[0].id;
      renderRecentes();
      try {
        const { mensagens } = await API.get("/historico?conversa_id=" + conversaIdAtual);
        for (const m of mensagens) {
          if (m.papel === "usuario") {
            if (!primeiraPergunta) primeiraPergunta = m.conteudo;
            msgUsuario(m.conteudo);
          } else {
            msgBot(m.conteudo, true);
          }
        }
        if (mensagens.length) $("rolagem").scrollTop = $("rolagem").scrollHeight;
      } catch (e) {
        msgErro(e.message);
      }
    } else {
      mostrarConversa(false);
    }
    $("campo").blur();
  }

  iniciar();
})();
