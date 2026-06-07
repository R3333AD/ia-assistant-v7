/* ── Agent IA v7 — Frontend ─────────────────────────────────── */
let STATE = {
  sessionId: null,
  messages: [],
  imagePath: null,
  streaming: false,
};

/* ── Init ── */
async function init() {
  const conf = await api("/api/conf");
  populateSelect("theme-select", Object.keys(conf.theme), conf.theme_name);
  populateSelect("persona-select", conf.personas, conf.persona);
  populateSelect("voice-select", conf.voices, conf.voice);
  document.getElementById("persona-label").textContent = conf.persona + " · v7";

  const sessions = await api("/api/sessions");
  if (sessions.length) {
    STATE.sessionId = sessions[0].id;
    const msgs = await api(`/api/sessions/${STATE.sessionId}/messages`);
    STATE.messages = msgs;
  } else {
    const ns = await api("/api/sessions", { method: "POST" });
    STATE.sessionId = ns.id;
  }
  renderSessions(sessions);
  renderMessages(STATE.messages);
  loadProfile();
  loadProjects();
  loadTasks();
  loadWebhooks();
  loadWhitelist();
  loadOutputs();
  loadMemoryInfo();
}

/* ── API helper ── */
async function api(url, opts = {}) {
  const resp = await fetch(url, {
    method: opts.method || "GET",
    headers: opts.body ? { "Content-Type": "application/json" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!resp.ok) throw new Error(await resp.text());
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("json")) return resp.json();
  return resp;
}

function populateSelect(id, options, selected) {
  const sel = document.getElementById(id);
  sel.innerHTML = options
    .map((o) => `<option value="${o}"${o === selected ? " selected" : ""}>${o}</option>`)
    .join("");
}

/* ── View switching ── */
function switchView(view) {
  document.querySelectorAll(".view-toggle .btn").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.getElementById("messages").style.display = view === "chat" ? "block" : "none";
  document.getElementById("input-area").style.display = view === "chat" ? "flex" : "none";
  document.getElementById("dashboard").classList.toggle("visible", view === "dashboard");
  if (view === "dashboard") renderDashboard();
}

/* ── Chat ── */
function onInputKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

const SLASH_COMMANDS = {
  "clear":   { desc: "Efface la session actuelle", action: () => clearSessionMem() },
  "new":     { desc: "Nouvelle session", action: () => newSession() },
  "export":  { desc: "Exporte la conversation en Markdown", action: () => exportSession() },
  "task":    { desc: "Ouvre le formulaire de tâche", action: () => showNewTaskModal() },
  "project": { desc: "Ouvre le formulaire de projet", action: () => showNewProjectModal() },
  "help":    { desc: "Affiche cette aide", action: () => showSlashHelp() },
};

function showSlashHelp() {
  const lines = Object.entries(SLASH_COMMANDS).map(([k, v]) => `  /${k} — ${v.desc}`);
  showModal(`<h3>📋 Commandes slash</h3><pre style="font-size:.85rem;line-height:1.6">${lines.join("\n")}</pre>
    <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal()">OK</button></div>`);
}

async function sendMessage() {
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text || STATE.streaming) return;

  if (text.startsWith("/")) {
    const parts = text.slice(1).split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const handler = SLASH_COMMANDS[cmd];
    if (handler) {
      input.value = "";
      input.style.height = "auto";
      handler.action();
      return;
    }
  }

  input.value = "";
  input.style.height = "auto";

  await streamChat(text);
}

async function streamChat(text) {
  STATE.streaming = true;
  const msgContainer = document.getElementById("messages");
  const welcome = msgContainer.querySelector(".welcome-msg");
  if (welcome) welcome.remove();

  // Show user message
  appendMessage("user", text, STATE.imagePath);

  // Show assistant placeholder
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg assistant";
  msgDiv.innerHTML = `<div class="avatar">🤖</div><div class="body"><div class="status-indicator"><span class="spinner"></span>Réflexion…</div></div>`;
  msgContainer.appendChild(msgDiv);
  msgContainer.scrollTop = msgContainer.scrollHeight;

  const body = msgDiv.querySelector(".body");
  let responseText = "";
  const thoughts = [];

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: STATE.sessionId,
        image_path: STATE.imagePath,
      }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          handleStreamEvent(evt, body, msgDiv, msgContainer, thoughts);
        } catch (e) {
          /* skip parse errors */
        }
      }
    }
    // Flush remaining buffer
    if (buffer.startsWith("data: ")) {
      try {
        const evt = JSON.parse(buffer.slice(6));
        handleStreamEvent(evt, body, msgDiv, msgContainer, thoughts);
      } catch (e) {
        /* skip */
      }
    }
  } catch (e) {
    body.innerHTML = `<span style="color:var(--error-text)">Erreur: ${e.message}</span>`;
  }

  STATE.streaming = false;
  STATE.imagePath = null;
  document.getElementById("upload-info").textContent = "";
  refreshSessions();
}

function handleStreamEvent(evt, body, msgDiv, msgContainer, thoughts) {
  if (evt.type === "status_update") {
    const providerEl = document.getElementById("badge-provider");
    const modelEl = document.getElementById("badge-model");
    const textEl = document.getElementById("status-text");
    if (evt.provider) {
      providerEl.textContent = evt.provider;
      providerEl.className = "badge provider-" + evt.provider;
    }
    if (evt.model) {
      modelEl.textContent = evt.model;
    }
    if (evt.status === "thinking") {
      textEl.textContent = "⚡ Réflexion…"; textEl.className = "status-thinking";
    } else if (evt.status === "waiting_approval") {
      textEl.textContent = "⏳ Attente d'autorisation…"; textEl.className = "status-waiting";
    } else if (evt.status === "executing_tool") {
      textEl.textContent = "⚙️ Exécution…"; textEl.className = "status-executing";
    } else if (evt.status === "ready") {
      textEl.textContent = "🟢 Prêt"; textEl.className = "status-ready";
    }
    return;
  }
  if (evt.type === "token") {
    const cursor = body.querySelector(".stream-cursor");
    if (!body.querySelector(".status-indicator")) {
      body.innerHTML = "";
    }
    if (evt.content) {
      const span = document.createElement("span");
      span.textContent = evt.content;
      body.appendChild(span);
    }
    // Remove old cursor, add new
    const cur = body.querySelector(".stream-cursor");
    if (cur) cur.remove();
    const nc = document.createElement("span");
    nc.className = "stream-cursor";
    nc.textContent = "▌";
    body.appendChild(nc);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  } else if (evt.type === "tool") {
    const ti = document.createElement("div");
    ti.className = "tool-inline";
    const icon = { calculator: "🧮", web_search: "🔍", get_weather: "🌤️", get_news: "📰", analyze_file: "📄", run_python_code: "⚙️", analyze_image: "👁️", generate_pdf: "📕", generate_word: "📝", generate_excel: "📊", generate_pptx: "📽️", manage_project: "📋", send_discord: "💬", run_script: "▶️", schedule_task: "⏰", browse_web: "🌐" }[evt.name] || "⚡";
    ti.textContent = `${icon} ${evt.name} exécuté`;
    const oldStatus = body.querySelector(".status-indicator");
    if (oldStatus) oldStatus.remove();
    body.appendChild(ti);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  } else if (evt.type === "done") {
    const cursor = body.querySelector(".stream-cursor");
    if (cursor) cursor.remove();
    body.querySelectorAll(".tool-inline").forEach((t) => t.remove());
    if (evt.content) {
      body.innerHTML = escapeHtml(evt.content);
    }
    if (evt.thoughts && evt.thoughts.length) {
      thoughts.push(...evt.thoughts);
      renderThoughts(body, evt.thoughts, msgDiv);
    }
    // TTS button
    const ttsBtn = document.createElement("button");
    ttsBtn.className = "tts-btn";
    ttsBtn.textContent = "🔊";
    ttsBtn.title = "Lire à voix haute";
    ttsBtn.onclick = () => playTTS(evt.content);
    msgDiv.querySelector(".avatar").after(ttsBtn);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  } else if (evt.type === "requires_approval") {
    body.innerHTML = `<span style="color:var(--accent);font-size:.75rem">⏳ Demande d'autorisation…</span>`;
    showApprovalModal(evt.tool_name, evt.tool_args, evt.tool_id);
  } else if (evt.type === "error") {
    body.innerHTML = `<span style="color:var(--error-text)">Erreur: ${escapeHtml(evt.content)}</span>`;
  }
}

function renderThoughts(body, thoughts, msgDiv) {
  const exp = document.createElement("div");
  exp.className = "thought-expander";
  exp.textContent = "🧠 Afficher le raisonnement";
  exp.onclick = () => content.classList.toggle("open");
  const content = document.createElement("div");
  content.className = "thought-content";
  for (const t of thoughts) {
    const isErr = t.error;
    const icon = { calculator: "🧮", web_search: "🔍", get_weather: "🌤️", get_news: "📰", analyze_file: "📄", run_python_code: "⚙️", analyze_image: "👁️", generate_pdf: "📕", generate_word: "📝", generate_excel: "📊", generate_pptx: "📽️", manage_project: "📋", send_discord: "💬", run_script: "▶️", schedule_task: "⏰", browse_web: "🌐" }[t.tool] || "⚡";
    const tn = document.createElement("div");
    tn.innerHTML =
      `<span class="tool-name">${icon} ${escapeHtml(t.tool)}</span> <span style="color:#555;font-size:.7rem">${escapeHtml(JSON.stringify(t.args))}</span><br>` +
      `<span class="${isErr ? "tool-error" : "tool-result"}">${escapeHtml(String(t.result).slice(0, 600))}</span>`;
    content.appendChild(tn);
  }
  body.appendChild(exp);
  body.appendChild(content);
}

function appendMessage(role, content, imagePath) {
  const container = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<div class="avatar">${role === "user" ? "🧑" : "🤖"}</div><div class="body">${escapeHtml(content)}</div>`;
  if (imagePath) {
    div.innerHTML += `<div class="body"><img src="${imagePath}" style="max-width:150px;border-radius:4px;margin:4px 0"></div>`;
  }
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function renderMessages(msgs) {
  const container = document.getElementById("messages");
  container.innerHTML = "";
  if (!msgs.length) {
    container.innerHTML = '<div class="welcome-msg">💬 Pose une question pour commencer</div>';
    return;
  }
  for (const m of msgs) {
    appendMessage(m.role, m.content, m.image_used);
    const lastMsg = container.lastElementChild;
    const body = lastMsg.querySelector(".body");
    if (m.role === "assistant" && m.thoughts && m.thoughts.length) {
      renderThoughts(body, m.thoughts, lastMsg);
    }
    if (m.role === "assistant" && m.content) {
      const ttsBtn = document.createElement("button");
      ttsBtn.className = "tts-btn";
      ttsBtn.textContent = "🔊";
      ttsBtn.title = "Lire à voix haute";
      ttsBtn.onclick = () => playTTS(m.content);
      lastMsg.querySelector(".avatar").after(ttsBtn);
    }
  }
  container.scrollTop = container.scrollHeight;
}

/* ── TTS ── */
async function playTTS(text) {
  const voice = document.getElementById("voice-select").value;
  try {
    const resp = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice }),
    });
    if (!resp.ok) return;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
  } catch (e) {
    console.error("TTS error:", e);
  }
}

/* ── Mic ── */
let micRecorder = null;
let micChunks = [];
async function toggleMic() {
  const btn = document.getElementById("mic-btn");
  if (micRecorder) {
    micRecorder.stop();
    micRecorder = null;
    btn.style.color = "";
    return;
  }
  if (!navigator.mediaDevices) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
    micRecorder = new MediaRecorder(stream);
    micChunks = [];
    micRecorder.ondataavailable = (e) => { if (e.data.size) micChunks.push(e.data); };
    micRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(micChunks, { type: "audio/webm" });
      const form = new FormData();
      form.append("audio", blob, "speech.webm");
      try {
        const resp = await fetch("/api/transcribe", { method: "POST", body: form });
        const data = await resp.json();
        if (data.text) {
          document.getElementById("chat-input").value = data.text;
          sendMessage();
        }
      } catch (e) {
        console.error("Transcribe error:", e);
      }
    };
    micRecorder.start();
    btn.style.color = "var(--error-text)";
  } catch (e) {
    console.error("Mic error:", e);
  }
}

/* ── Sessions ── */
async function newSession() {
  const ns = await api("/api/sessions", { method: "POST" });
  STATE.sessionId = ns.id;
  STATE.messages = [];
  renderMessages([]);
  refreshSessions();
}

async function deleteCurrentSession() {
  if (!STATE.sessionId) return;
  await api(`/api/sessions/${STATE.sessionId}`, { method: "DELETE" });
  await newSession();
}

async function refreshSessions() {
  const sessions = await api("/api/sessions");
  renderSessions(sessions);
}

function renderSessions(sessions) {
  const list = document.getElementById("session-list");
  list.innerHTML = sessions
    .map(
      (s) =>
        `<button class="btn btn-sm ${s.id === STATE.sessionId ? "btn-primary" : ""}" onclick="switchSession('${s.id}')">${s.id === STATE.sessionId ? "🟢" : "💬"} ${escapeHtml(s.name)} · ${s.msg_count}msg</button>`
    )
    .join("");
}

async function exportSession() {
  if (!STATE.sessionId) return;
  window.open(`/api/sessions/${STATE.sessionId}/export`, "_blank");
}

async function switchSession(sid) {
  if (sid === STATE.sessionId) return;
  STATE.sessionId = sid;
  STATE.messages = await api(`/api/sessions/${sid}/messages`);
  renderMessages(STATE.messages);
  refreshSessions();
  loadMemoryInfo();
}

/* ── Theme ── */
async function setTheme(name) {
  const data = await api("/api/theme", { method: "POST", body: { name } });
  applyTheme(data.theme);
}

function applyTheme(t) {
  const r = document.querySelector(":root");
  Object.entries(t).forEach(([k, v]) => {
    const cssVar = "--" + k.replace(/_/g, "-");
    r.style.setProperty(cssVar, v);
  });
  document.body.style.background = t.bg;
}

/* ── Persona ── */
async function setPersona(name) {
  await api("/api/persona", { method: "POST", body: { name } });
  document.getElementById("persona-label").textContent = name + " · v7";
}

async function showCustomPersonasModal() {
  const custom = await api("/api/custom-personas");
  const rows = Object.entries(custom).length
    ? Object.entries(custom).map(([k, v]) =>
        `<div style="border-bottom:1px solid var(--box-border);padding:6px 0">
          <strong>${escapeHtml(k)}</strong>
          <div style="font-size:.72rem;color:var(--subtitle);margin:2px 0">${escapeHtml(v.slice(0, 100))}</div>
          <button class="btn btn-sm btn-danger" onclick="deleteCustomPersona('${escapeHtml(k)}')">🗑️ Supprimer</button>
        </div>`
      ).join("")
    : '<div class="file-info">Aucun persona personnalisé</div>';

  showModal(`
    <h3>✏️ Personas personnalisés</h3>
    <div style="max-height:200px;overflow-y:auto;margin-bottom:8px">${rows}</div>
    <hr style="border-color:var(--box-border);margin:8px 0">
    <h4 style="margin:0 0 6px">➕ Nouveau persona</h4>
    <input type="text" id="cp-name" placeholder="Nom du persona">
    <textarea id="cp-prompt" placeholder="Prompt système…" rows="3" style="resize:vertical;min-height:60px;width:100%"></textarea>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Fermer</button>
      <button class="btn btn-primary" onclick="saveCustomPersona()">💾 Enregistrer</button>
    </div>`);
}

async function saveCustomPersona() {
  const name = document.getElementById("cp-name").value;
  const prompt = document.getElementById("cp-prompt").value;
  if (!name || !prompt) return;
  await api("/api/custom-personas", { method: "POST", body: { name, prompt } });
  closeModal();
  // Refresh persona dropdown
  const conf = await api("/api/conf");
  populateSelect("persona-select", conf.personas, conf.persona);
}

async function deleteCustomPersona(name) {
  await api(`/api/custom-personas/${encodeURIComponent(name)}`, { method: "DELETE" });
  showCustomPersonasModal();
  // Refresh persona dropdown
  const conf = await api("/api/conf");
  populateSelect("persona-select", conf.personas, conf.persona);
}

/* ── Voice ── */
async function setVoice(voice) {
  await api("/api/voice", { method: "POST", body: { voice } });
}

/* ── Profile ── */
async function loadProfile() {
  try {
    const p = await api("/api/profile");
    document.getElementById("p-name").value = p.name || "";
    document.getElementById("p-job").value = p.job || "";
    document.getElementById("p-interests").value = p.interests || "";
    document.getElementById("p-notes").value = p.notes || "";
  } catch (e) {
    /* ignore */
  }
}

async function saveProfile() {
  await api("/api/profile", {
    method: "POST",
    body: {
      name: document.getElementById("p-name").value,
      job: document.getElementById("p-job").value,
      interests: document.getElementById("p-interests").value,
      notes: document.getElementById("p-notes").value,
      language: "français",
    },
  });
}

/* ── Projects ── */
async function loadProjects() {
  const list = document.getElementById("project-list");
  try {
    const projects = await api("/api/projects");
    list.innerHTML = projects
      .slice(0, 8)
      .map((p) => {
        const openTodos = (p.todos || []).filter((t) => !t.done).length;
        const sc = "st-" + (p.status || "planifie").replace(/ /g, "-");
        return `<details class="sidebar-expander"><summary>📁 ${escapeHtml(p.name)} (${openTodos} open)</summary>
          <div class="expander-body">
            <span class="proj-status ${sc}">${escapeHtml(p.status)}</span>
            ${p.description ? `<div class="file-info">${escapeHtml(p.description)}</div>` : ""}
            <select onchange="updateProjectStatus('${p.id}',this.value)" style="width:100%;font-size:.75rem">
              ${["en cours","en pause","terminé","abandonné","planifié"].map((s) => `<option value="${s}"${s===p.status?" selected":""}>${s}</option>`).join("")}
            </select>
            <div class="file-info">TODOs:</div>
            ${(p.todos||[]).map((t) => `<label style="display:flex;align-items:center;gap:4px;font-size:.72rem;cursor:pointer"><input type="checkbox"${t.done?" checked":""} onchange="toggleTodo('${p.id}','${t.id}')">${escapeHtml(t.text)}</label>`).join("")}
            <div style="display:flex;gap:4px;margin-top:4px">
              <input type="text" id="todo-input-${p.id}" placeholder="Nouveau TODO…" style="flex:1;font-size:.72rem;padding:2px 6px">
              <button class="btn btn-sm" onclick="addTodo('${p.id}')">➕</button>
            </div>
            <button class="btn btn-sm btn-danger" onclick="deleteProject('${p.id}')">🗑️ Supprimer projet</button>
          </div></details>`;
      })
      .join("");
  } catch (e) {
    list.innerHTML = "";
  }
}

function showNewProjectModal() {
  showModal(`
    <h3>➕ Nouveau projet</h3>
    <input type="text" id="np-name" placeholder="Nom">
    <input type="text" id="np-desc" placeholder="Description (optionnel)">
    <select id="np-status"><option>planifié</option><option>en cours</option><option>en pause</option></select>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Annuler</button>
      <button class="btn btn-primary" onclick="createProject()">Créer</button>
    </div>`);
}

async function createProject() {
  const name = document.getElementById("np-name").value;
  if (!name) return;
  await api("/api/projects", {
    method: "POST",
    body: { name, description: document.getElementById("np-desc").value, status: document.getElementById("np-status").value },
  });
  closeModal();
  loadProjects();
}

async function updateProjectStatus(pid, status) {
  await api(`/api/projects/${pid}`, { method: "PUT", body: { status } });
  loadProjects();
}

async function toggleTodo(pid, tid) {
  await api(`/api/projects/${pid}/todos/${tid}`, { method: "PUT" });
  loadProjects();
}

async function addTodo(pid) {
  const input = document.getElementById(`todo-input-${pid}`);
  if (!input || !input.value.trim()) return;
  await api(`/api/projects/${pid}/todos`, { method: "POST", body: { text: input.value } });
  input.value = "";
  loadProjects();
}

async function deleteProject(pid) {
  await api(`/api/projects/${pid}`, { method: "DELETE" });
  loadProjects();
}

/* ── Tasks ── */
async function loadTasks() {
  const list = document.getElementById("task-list");
  try {
    const tasks = await api("/api/tasks");
    list.innerHTML = tasks
      .slice(0, 6)
      .map((t) => {
        const icon = t.enabled ? "✅" : "⏸️";
        const next = t.next_run ? `→ ${t.next_run}` : "";
        return `<details class="sidebar-expander"><summary>${icon} ${escapeHtml(t.name)} (${t.cron}) ${next}</summary>
          <div class="expander-body">
            <div class="file-info">Action: ${t.action}</div>
            ${t.message ? `<div class="file-info">Message: ${escapeHtml(t.message)}</div>` : ""}
            <div style="display:flex;gap:4px">
              <button class="btn btn-sm" onclick="runTask('${t.id}')">▶️ Exécuter</button>
              <button class="btn btn-sm" onclick="toggleTask('${t.id}')">${t.enabled ? "⏸️ Désactiver" : "▶️ Activer"}</button>
              <button class="btn btn-sm btn-danger" onclick="deleteTask('${t.id}')">🗑️</button>
            </div>
            <div id="task-logs-${t.id}" class="file-info"></div>
          </div></details>`;
      })
      .join("");
    // Load logs for each task
    for (const t of tasks.slice(0, 6)) {
      loadTaskLogs(t.id);
    }
  } catch (e) {
    list.innerHTML = "";
  }
}

async function loadTaskLogs(tid) {
  try {
    const logs = await api(`/api/tasks/${tid}/logs`);
    const el = document.getElementById(`task-logs-${tid}`);
    if (el) {
      el.innerHTML = logs
        .slice(0, 3)
        .map((l) => `${l.success ? "✅" : "❌"} ${l.ran_at.slice(0, 16)}: ${escapeHtml((l.result || "").slice(0, 80))}`)
        .join("<br>");
    }
  } catch (e) {
    /* ignore */
  }
}

function showNewTaskModal() {
  showModal(`
    <h3>➕ Nouvelle tâche</h3>
    <input type="text" id="nt-name" placeholder="Nom">
    <input type="text" id="nt-cron" placeholder="Cron" value="0 9 * * *">
    <select id="nt-action"><option value="message">message</option><option value="webhook">webhook</option><option value="script">script</option></select>
    <input type="text" id="nt-msg" placeholder="Message (message/webhook)">
    <input type="text" id="nt-script" placeholder="Chemin script (script)">
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Annuler</button>
      <button class="btn btn-primary" onclick="createTask()">Créer</button>
    </div>`);
}

async function createTask() {
  const name = document.getElementById("nt-name").value;
  const cron = document.getElementById("nt-cron").value;
  if (!name || !cron) return;
  await api("/api/tasks", {
    method: "POST",
    body: { name, cron, action: document.getElementById("nt-action").value, message: document.getElementById("nt-msg").value, script_path: document.getElementById("nt-script").value },
  });
  closeModal();
  loadTasks();
}

async function runTask(tid) {
  await api(`/api/tasks/${tid}/run`, { method: "POST" });
  loadTasks();
}

async function toggleTask(tid) {
  await api(`/api/tasks/${tid}/toggle`, { method: "POST" });
  loadTasks();
}

async function deleteTask(tid) {
  await api(`/api/tasks/${tid}`, { method: "DELETE" });
  loadTasks();
}

/* ── Webhooks ── */
async function loadWebhooks() {
  const list = document.getElementById("webhook-list");
  try {
    const wh = await api("/api/webhooks");
    list.innerHTML = wh.length
      ? wh.map((w) => `<div class="file-info">🔗 ${escapeHtml(w.name)}</div>`).join("")
      : "";
  } catch (e) {
    list.innerHTML = "";
  }
}

function showWebhookModal() {
  showModal(`
    <h3>➕ Ajouter webhook Discord</h3>
    <input type="text" id="wh-name" placeholder="Nom">
    <input type="text" id="wh-url" placeholder="URL du webhook">
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Annuler</button>
      <button class="btn btn-primary" onclick="createWebhook()">Enregistrer</button>
    </div>`);
}

async function createWebhook() {
  const name = document.getElementById("wh-name").value;
  const url = document.getElementById("wh-url").value;
  if (!name || !url) return;
  await api("/api/webhooks", { method: "POST", body: { name, url } });
  closeModal();
  loadWebhooks();
}

/* ── Whitelist ── */
async function loadWhitelist() {
  const list = document.getElementById("whitelist-list");
  try {
    const wl = await api("/api/whitelist");
    list.innerHTML = wl.length ? wl.map((d) => `<div class="file-info">📁 ${escapeHtml(d)}</div>`).join("") : "";
  } catch (e) {
    list.innerHTML = "";
  }
}

function showWhitelistModal() {
  showModal(`
    <h3>➕ Ajouter dossier whitelist</h3>
    <input type="text" id="wl-dir" placeholder="Chemin absolu du dossier">
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Annuler</button>
      <button class="btn btn-primary" onclick="addWhitelistDir()">Ajouter</button>
    </div>`);
}

async function addWhitelistDir() {
  const dir = document.getElementById("wl-dir").value;
  if (!dir) return;
  await api("/api/whitelist", { method: "POST", body: { dir } });
  closeModal();
  loadWhitelist();
}

/* ── Upload ── */
async function uploadFile(file) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const info = document.getElementById("upload-info");
  info.textContent = "Uploading…";
  try {
    const resp = await fetch("/api/upload", { method: "POST", body: form });
    const data = await resp.json();
    if (file.type.startsWith("image/")) {
      STATE.imagePath = data.path;
      info.innerHTML = `✅ ${escapeHtml(file.name)} (image chargée)`;
    } else {
      info.innerHTML = `✅ ${escapeHtml(file.name)}${data.indexed ? ` (${data.indexed} chunks indexés)` : ""}`;
    }
  } catch (e) {
    info.textContent = "Erreur upload";
  }
}

/* ── Documents générés ── */
async function loadOutputs() {
  const list = document.getElementById("outputs-list");
  try {
    const files = await api("/api/outputs");
    list.innerHTML = files.length
      ? files
          .map((f) => `<button class="btn btn-sm" onclick="downloadOutput('${f.name}')">⬇️ ${escapeHtml(f.name)}</button>`)
          .join("")
      : '<div class="file-info">Aucun document généré</div>';
  } catch (e) {
    list.innerHTML = "";
  }
}

function downloadOutput(name) {
  window.open(`/api/outputs/${name}`, "_blank");
}

/* ── Dashboard ── */
async function renderDashboard() {
  try {
    const summary = await api("/api/stats");
    const metrics = document.getElementById("dash-metrics");
    metrics.innerHTML = `
      <div class="metric-card"><div class="value">${summary.total_messages}</div><div class="label">💬 Messages${summary.messages_today ? ` (+${summary.messages_today}a)`:""}</div></div>
      <div class="metric-card"><div class="value">${summary.total_tools}</div><div class="label">🛠️ Appels outils</div></div>
      <div class="metric-card"><div class="value">${summary.total_sessions}</div><div class="label">📂 Sessions</div></div>
      <div class="metric-card"><div class="value">${summary.top_tool.tool_name}</div><div class="label">⭐ Top outil (${summary.top_tool.n})</div></div>`;

    const charts = document.getElementById("dash-charts");
    charts.innerHTML = "";

    // Tool stats
    const toolStats = await api("/api/stats/tools");
    if (toolStats.length) {
      const max = Math.max(...toolStats.map((t) => t.count));
      let section = '<div class="chart-section"><h3>🛠️ Outils (7 jours)</h3><div class="chart-bar">';
      section += toolStats
        .map(
          (t) =>
            `<div class="chart-bar-item" style="height:${Math.max((t.count / max) * 100, 4)}%"><div class="clabel">${escapeHtml(t.tool_name)}</div></div>`
        )
        .join("");
      section += "</div></div>";
      charts.innerHTML += section;
    }

    // Message timeline
    const msgTL = await api("/api/stats/timeline");
    if (msgTL.length) {
      const byDay = {};
      for (const m of msgTL) {
        if (!byDay[m.day]) byDay[m.day] = { day: m.day, user: 0, assistant: 0 };
        byDay[m.day][m.role] = m.count;
      }
      const days = Object.values(byDay);
      const maxV = Math.max(...days.map((d) => d.user + d.assistant), 1);
      let section = '<div class="chart-section"><h3>📊 Messages par jour</h3><div class="chart-bar">';
      section += days
        .map(
          (d) =>
            `<div class="chart-bar-item" style="height:${Math.max(((d.user + d.assistant) / maxV) * 100, 4)}%;background:var(--accent)"><div class="clabel">${d.day.slice(5)}</div></div>`
        )
        .join("");
      section += "</div></div>";
      charts.innerHTML += section;
    }
  } catch (e) {
    /* ignore */
  }
}

/* ── Memory ── */
async function loadMemoryInfo() {
  try {
    const mem = await api("/api/memory");
    document.getElementById("memory-info").textContent = `${mem.chroma ? "✅" : "⚠️"} ${mem.count} fragments stockés`;
  } catch (e) {
    /* ignore */
  }
}

async function clearSessionMem() {
  const data = await api("/api/memory/clear-session", { method: "POST", body: { session_id: STATE.sessionId } });
  STATE.sessionId = data.session_id;
  STATE.messages = [];
  renderMessages([]);
  refreshSessions();
}

async function clearAllMem() {
  await api("/api/memory/clear", { method: "POST" });
  loadMemoryInfo();
}

/* ── Modals ── */
function showModal(html) {
  document.getElementById("modal-container").innerHTML = `<div class="modal-overlay"><div class="modal">${html}</div></div>`;
}

function closeModal() {
  document.getElementById("modal-container").innerHTML = "";
}

/* ── HITL Approval ── */
let _pendingApprovalSession = "";

function showApprovalModal(toolName, toolArgs, toolId) {
  _pendingApprovalSession = STATE.sessionId;
  const argsStr = toolArgs ? JSON.stringify(toolArgs, null, 2) : "";
  const argsHtml = toolArgs
    ? `<textarea class="approval-args" id="approval-args-text" rows="6">${escapeHtml(argsStr)}</textarea>`
    : "<p style='color:var(--subtitle);font-size:.8rem'>Aucun argument</p>";
  showModal(`
    <h3>🛡️ Autorisation requise</h3>
    <p style="font-size:.85rem;margin-bottom:12px">L'agent souhaite exécuter un outil sensible :</p>
    <div class="approval-tool-name">${toolName}</div>
    ${argsHtml}
    <div class="modal-actions">
      <button class="btn btn-ghost" onclick="sendApproval(false)">Refuser</button>
      <button class="btn btn-primary" onclick="sendApproval(true)">Autoriser</button>
    </div>
  `);
}

async function sendApproval(approved) {
  const sid = _pendingApprovalSession;
  _pendingApprovalSession = "";
  const body = { session_id: sid, approved };
  if (approved) {
    const ta = document.getElementById("approval-args-text");
    if (ta) {
      try { body.modified_args = JSON.parse(ta.value); } catch (e) { /* keep original */ }
    }
  }
  closeModal();
  await fetch("/api/approve_tool", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/* ── Keyboard shortcuts ── */
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "k") {
    e.preventDefault();
    document.getElementById("chat-input").focus();
  }
  if (e.ctrlKey && e.key === "n") {
    e.preventDefault();
    newSession();
  }
  if (e.ctrlKey && e.key === "r") {
    e.preventDefault();
    clearSessionMem();
  }
});

/* ── Helpers ── */
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/* ── Start ── */
document.addEventListener("DOMContentLoaded", init);
