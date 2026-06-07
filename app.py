import sys, os, json, io, queue, threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, Response, render_template, request, jsonify, send_file, send_from_directory

from core.agent import Agent
from config.settings import PERSONAS, GROQ_API_KEY
from config.themes import THEMES, css_class_for_status
from config.personas_store import list_personas as list_custom_personas, save_persona as save_custom_persona, delete_persona as delete_custom_persona
from memory.profile import load_profile, save_profile
from memory.long_term import clear_memory, CHROMA_AVAILABLE, get_memory_count, index_document
from memory import sessions as sess
from memory import projects as proj_mod
from tools import TOOLS_ICONS
from tools.tts import speak, VOICES_FR
from tools.discord_webhook import list_webhooks, save_webhook, delete_webhook
from tools.script_runner import get_whitelist, add_whitelist_dir, remove_whitelist_dir
from memory.scheduler import (
    start_scheduler, list_tasks as sched_list, get_task,
    delete_task, toggle_task, add_task, next_run as sched_next, get_log,
    _execute_task,
)
from memory import stats as stats_mod
from tools import whisper_local

ROOT = os.path.dirname(__file__)
UPLOADS_DIR = os.path.join(ROOT, "data", "uploads")
OUTPUTS_DIR = os.path.join(ROOT, "data", "outputs")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── In-memory state ──
_agents: dict[str, Agent] = {}
_current_persona = list(PERSONAS.keys())[0]
_current_theme = "Dark"
_current_voice = VOICES_FR[0]

# ── HITL : pending tool approvals ──
_pending_events: dict[str, threading.Event] = {}
_pending_decisions: dict[str, dict] = {}

# ── Helpers ──
def _get_agent(session_id: str) -> Agent:
    if session_id not in _agents:
        _agents[session_id] = Agent(persona_prompt=PERSONAS[_current_persona])
    agent = _agents[session_id]
    saved = sess.get_summary(session_id)
    if saved and not agent.current_summary:
        agent.current_summary = saved
    return agent

def _auto_title(message: str, response: str) -> str:
    """Génère un titre court (<=6 mots) à partir du premier message."""
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Génère un titre de 6 mots max en français résumant cette conversation. Réponds UNIQUEMENT par le titre, sans guillemets ni ponctuation."},
                {"role": "user", "content": message},
                {"role": "assistant", "content": response[:200]},
            ],
            max_tokens=30,
        )
        return r.choices[0].message.content.strip().strip('"').strip("'")[:50]
    except Exception:
        return ""


def _extract_text(path: str) -> str:
    """Extrait le texte d'un PDF ou DOCX pour indexation ChromaDB."""
    text = ""
    try:
        if path.lower().endswith(".pdf"):
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
        elif path.lower().endswith(".docx"):
            from docx import Document
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        pass
    return text


def transcribe_wav(audio_bytes: bytes) -> str:
    if not audio_bytes:
        return ""
    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            f = ("speech.wav", io.BytesIO(audio_bytes), "audio/wav")
            resp = client.audio.transcriptions.create(
                file=f, model="whisper-large-v3", language="fr", response_format="text"
            )
            return resp if isinstance(resp, str) else resp.text
        except Exception:
            pass
    if whisper_local.is_available():
        try:
            return whisper_local.transcribe_local(audio_bytes)
        except Exception:
            pass
    return ""

# ── Routes ──
@app.route("/")
def index():
    theme = THEMES.get(_current_theme, THEMES["Dark"])
    return render_template("index.html", theme=theme, theme_name=_current_theme,
                           personas=list(PERSONAS.keys()), voices=VOICES_FR)

@app.route("/api/conf")
def api_conf():
    custom_p = list_custom_personas()
    all_personas = list(PERSONAS.keys()) + list(custom_p.keys())
    return jsonify({
        "theme_name": _current_theme,
        "theme": THEMES.get(_current_theme, THEMES["Dark"]),
        "persona": _current_persona,
        "personas": all_personas,
        "custom_personas": custom_p,
        "voice": _current_voice,
        "voices": VOICES_FR,
        "chroma_available": CHROMA_AVAILABLE,
    })

@app.route("/api/theme", methods=["POST"])
def api_set_theme():
    global _current_theme
    data = request.get_json()
    if data and data.get("name") in THEMES:
        _current_theme = data["name"]
    return jsonify({"ok": True, "theme": THEMES[_current_theme]})

def _resolve_persona(name: str) -> str:
    """Retourne le prompt d'un persona (built-in ou custom)."""
    if name in PERSONAS:
        return PERSONAS[name]
    custom = list_custom_personas()
    if name in custom:
        return custom[name]
    return list(PERSONAS.values())[0]

@app.route("/api/persona", methods=["POST"])
def api_set_persona():
    global _current_persona
    data = request.get_json()
    if data and data.get("name") in list(PERSONAS.keys()) + list(list_custom_personas().keys()):
        _current_persona = data["name"]
        prompt = _resolve_persona(_current_persona)
        for a in _agents.values():
            a.set_persona(prompt)
    return jsonify({"ok": True})

@app.route("/api/voice", methods=["POST"])
def api_set_voice():
    global _current_voice
    data = request.get_json()
    if data and data.get("voice") in VOICES_FR:
        _current_voice = data["voice"]
    return jsonify({"ok": True})

# ── Sessions ──
@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    return jsonify(sess.list_sessions(limit=30))

@app.route("/api/sessions", methods=["POST"])
def api_new_session():
    sid = sess.new_session()
    _agents.pop(sid, None)
    return jsonify({"id": sid})

@app.route("/api/sessions/<sid>", methods=["DELETE"])
def api_del_session(sid):
    sess.delete_session(sid)
    _agents.pop(sid, None)
    return jsonify({"ok": True})

@app.route("/api/sessions/<sid>/rename", methods=["POST"])
def api_rename_session(sid):
    data = request.get_json()
    if data and data.get("name"):
        sess.rename_session(sid, data["name"])
    return jsonify({"ok": True})

@app.route("/api/sessions/<sid>/messages", methods=["GET"])
def api_get_messages(sid):
    return jsonify(sess.get_messages(sid))

@app.route("/api/sessions/<sid>/export")
def api_export_session(sid):
    msgs = sess.get_messages(sid)
    fmt = request.args.get("format", "md")
    if fmt == "json":
        return jsonify(msgs)
    lines = [f"# Agent IA — Conversation\n"]
    for m in msgs:
        role = "🧑 User" if m["role"] == "user" else "🤖 Assistant"
        lines.append(f"\n## {role}\n\n{m['content']}\n")
        if m.get("thoughts"):
            lines.append(f"\n<details><summary>🧠 Raisonnement</summary>\n\n")
            for t in m["thoughts"]:
                lines.append(f"- **{t['tool']}** : {t['result'][:200]}\n")
            lines.append("</details>\n")
    text = "".join(lines)
    return Response(text, mimetype="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=conversation_{sid}.md"})

# ── Chat SSE ──
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    message = data.get("message", "")
    session_id = data.get("session_id", "")
    image_path = data.get("image_path")

    if not session_id:
        session_id = sess.new_session()
    if not message:
        return jsonify({"error": "message required"}), 400

    full_prompt = message
    if image_path and any(w in message.lower() for w in ["image","photo","screenshot","capture","vois","analyse","regarde"]):
        full_prompt = f"{message}\n[Image disponible : {image_path}]"

    def generate():
        q = queue.Queue()
        agent = _get_agent(session_id)
        agent_ref = agent
        sid = session_id

        # Statut initial immédiat
        q.put(("status", {"type": "status_update", "provider": agent.provider, "model": agent.model, "status": "thinking"}))

        def on_token(tok):
            q.put(("token", tok))

        def on_tool(name, args, result):
            stats_mod.track_tool_call(name, sid)
            q.put(("tool", name, args, str(result)[:600]))

        def on_approval(name, args, tool_id):
            ev = threading.Event()
            _pending_events[sid] = ev
            _pending_decisions[sid] = None
            q.put(("approval", name, args, tool_id))
            q.put(("status", {"type": "status_update", "status": "waiting_approval"}))
            timed_out = not ev.wait(timeout=300)
            if timed_out or _pending_decisions.get(sid) is None:
                decision = {"approved": False, "reason": "timeout"}
            else:
                decision = _pending_decisions.pop(sid, {"approved": False, "reason": "refused"})
            _pending_events.pop(sid, None)
            q.put(("status", {"type": "status_update", "status": "thinking"}))
            return decision

        def runner():
            try:
                resp, thoughts = agent_ref.run(full_prompt, on_token=on_token, on_tool=on_tool, on_approval=on_approval)
                q.put(("done", resp, thoughts))
            except Exception as e:
                q.put(("error", str(e)))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Yield events
        try:
            while True:
                try:
                    item = q.get(timeout=300)
                except queue.Empty:
                    yield "data: {\"type\":\"timeout\"}\n\n"
                    break

                if item[0] == "token":
                    yield f"data: {json.dumps({'type':'token','content':item[1]})}\n\n"
                elif item[0] == "tool":
                    yield f"data: {json.dumps({'type':'tool','name':item[1],'args':item[2],'result':item[3]})}\n\n"
                elif item[0] == "approval":
                    yield f"data: {json.dumps({'type':'requires_approval','tool_name':item[1],'tool_args':item[2],'tool_id':item[3]})}\n\n"
                elif item[0] == "status":
                    yield f"data: {json.dumps(item[1])}\n\n"
                elif item[0] == "done":
                    resp, thoughts = item[1], item[2]
                    img_used = image_path if image_path and "image" in message.lower() else None
                    sess.add_message(session_id, "user", message, image_path=img_used)
                    stats_mod.track_message(session_id, "user")
                    sess.add_message(session_id, "assistant", resp, thoughts=thoughts)
                    stats_mod.track_message(session_id, "assistant")
                    # Persister le résumé récursif
                    sess.save_summary(session_id, agent.current_summary)
                    # Auto-titrage : renommer après le 1er échange
                    msgs = sess.get_messages(session_id)
                    if len(msgs) <= 2:
                        title = _auto_title(message, resp)
                        if title:
                            sess.rename_session(session_id, title)
                    yield f"data: {json.dumps({'type':'status_update','status':'ready'})}\n\n"
                    yield f"data: {json.dumps({'type':'done','content':resp,'thoughts':thoughts,'session_id':session_id})}\n\n"
                    break
                elif item[0] == "error":
                    yield f"data: {json.dumps({'type':'error','content':item[1]})}\n\n"
                    break
        except GeneratorExit:
            # Client déconnecté → libérer le thread agent en attente
            if session_id in _pending_events:
                _pending_decisions[session_id] = {"approved": False, "reason": "disconnected"}
                _pending_events[session_id].set()
            raise

    return Response(generate(), mimetype="text/event-stream")

# ── HITL : approbation d'outil ──
@app.route("/api/approve_tool", methods=["POST"])
def api_approve_tool():
    data = request.get_json()
    sid = data.get("session_id", "")
    approved = data.get("approved", False)
    modified_args = data.get("modified_args")

    if sid not in _pending_events:
        return jsonify({"error": "no pending tool"}), 400

    decision = {"approved": approved}
    if modified_args is not None:
        decision["modified_args"] = modified_args
    _pending_decisions[sid] = decision
    _pending_events[sid].set()
    return jsonify({"ok": True})

# ── TTS ──
@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json()
    text, voice = data.get("text", ""), data.get("voice", _current_voice)
    audio = speak(text, voice)
    if isinstance(audio, bytes) and not audio.startswith(b"[TTS"):
        return Response(audio, mimetype="audio/mpeg")
    return jsonify({"error": audio.decode() if isinstance(audio, bytes) else str(audio)}), 500

# ── Whisper ──
@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "no audio"}), 400
    text = transcribe_wav(audio.read())
    return jsonify({"text": text})

# ── Profile ──
# ── Custom Personas ──
@app.route("/api/custom-personas", methods=["GET"])
def api_list_custom_personas():
    return jsonify(list_custom_personas())

@app.route("/api/custom-personas", methods=["POST"])
def api_save_custom_persona():
    data = request.get_json()
    if data and data.get("name") and data.get("prompt"):
        save_custom_persona(data["name"], data["prompt"])
    return jsonify({"ok": True})

@app.route("/api/custom-personas/<name>", methods=["DELETE"])
def api_delete_custom_persona(name):
    delete_custom_persona(name)
    return jsonify({"ok": True})

# ── Profile ──
@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    return jsonify(load_profile())

@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    data = request.get_json()
    if data:
        save_profile(data)
        for a in _agents.values():
            a.reset()
    return jsonify({"ok": True})

# ── Projects ──
@app.route("/api/projects", methods=["GET"])
def api_list_projects():
    return jsonify(proj_mod.list_projects())

@app.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name required"}), 400
    p = proj_mod.create_project(data["name"], data.get("description", ""),
                                data.get("status", "planifié"))
    for a in _agents.values():
        a.reset()
    return jsonify(p)

@app.route("/api/projects/<pid>", methods=["PUT"])
def api_update_project(pid):
    data = request.get_json()
    if data:
        proj_mod.update_project(pid, **data)
        for a in _agents.values():
            a.reset()
    return jsonify({"ok": True})

@app.route("/api/projects/<pid>", methods=["DELETE"])
def api_delete_project(pid):
    proj_mod.delete_project(pid)
    for a in _agents.values():
        a.reset()
    return jsonify({"ok": True})

@app.route("/api/projects/<pid>/todos", methods=["POST"])
def api_add_todo(pid):
    data = request.get_json()
    if data and data.get("text"):
        proj_mod.add_todo(pid, data["text"])
    return jsonify({"ok": True})

@app.route("/api/projects/<pid>/todos/<tid>", methods=["PUT"])
def api_toggle_todo(pid, tid):
    proj_mod.toggle_todo(pid, tid)
    return jsonify({"ok": True})

# ── Stats ──
@app.route("/api/stats")
def api_stats():
    return jsonify(stats_mod.get_summary())

@app.route("/api/stats/tools")
def api_stats_tools():
    return jsonify(stats_mod.get_tool_stats())

@app.route("/api/stats/timeline")
def api_stats_timeline():
    return jsonify(stats_mod.get_message_timeline())

@app.route("/api/stats/tool-timeline")
def api_stats_tool_timeline():
    return jsonify(stats_mod.get_tool_timeline())

# ── Webhooks ──
@app.route("/api/webhooks", methods=["GET"])
def api_list_webhooks():
    return jsonify(list_webhooks())

@app.route("/api/webhooks", methods=["POST"])
def api_add_webhook():
    data = request.get_json()
    if data and data.get("name") and data.get("url"):
        save_webhook(data["name"], data["url"])
    return jsonify({"ok": True})

@app.route("/api/webhooks/<name>", methods=["DELETE"])
def api_del_webhook(name):
    delete_webhook(name)
    return jsonify({"ok": True})

# ── Script whitelist ──
@app.route("/api/whitelist", methods=["GET"])
def api_get_whitelist():
    return jsonify(get_whitelist())

@app.route("/api/whitelist", methods=["POST"])
def api_add_whitelist():
    data = request.get_json()
    if data and data.get("dir"):
        add_whitelist_dir(data["dir"])
    return jsonify({"ok": True})

@app.route("/api/whitelist/<path:dirpath>", methods=["DELETE"])
def api_remove_whitelist(dirpath):
    remove_whitelist_dir(dirpath)
    return jsonify({"ok": True})

# ── Scheduler ──
@app.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    tasks = sched_list()
    out = []
    for t in tasks:
        t["next_run"] = sched_next(t["id"])
        out.append(t)
    return jsonify(out)

@app.route("/api/tasks", methods=["POST"])
def api_add_task():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("cron"):
        return jsonify({"error": "name and cron required"}), 400
    task = add_task(name=data["name"], action=data.get("action", "message"),
                    cron=data["cron"], prompt=data.get("prompt", ""),
                    webhook_name=data.get("webhook_name", ""),
                    script_path=data.get("script_path", ""),
                    message=data.get("message", ""))
    return jsonify(task)

@app.route("/api/tasks/<tid>/toggle", methods=["POST"])
def api_toggle_task(tid):
    toggle_task(tid)
    return jsonify({"ok": True})

@app.route("/api/tasks/<tid>", methods=["DELETE"])
def api_del_task(tid):
    delete_task(tid)
    return jsonify({"ok": True})

@app.route("/api/tasks/<tid>/run", methods=["POST"])
def api_run_task(tid):
    _execute_task(tid)
    return jsonify({"ok": True})

@app.route("/api/tasks/<tid>/logs", methods=["GET"])
def api_task_logs(tid):
    return jsonify(get_log(tid, limit=10))

# ── Output files ──
@app.route("/api/outputs")
def api_list_outputs():
    files = []
    for fname in sorted(os.listdir(OUTPUTS_DIR), reverse=True):
        if fname.endswith((".pdf", ".docx", ".xlsx", ".pptx")):
            fpath = os.path.join(OUTPUTS_DIR, fname)
            files.append({"name": fname, "size": os.path.getsize(fpath),
                          "mtime": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()})
    return jsonify(files[:10])

@app.route("/api/outputs/<fname>")
def api_download_output(fname):
    return send_file(os.path.join(OUTPUTS_DIR, fname), as_attachment=True)

# ── Upload ──
@app.route("/api/upload", methods=["POST"])
def api_upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400
    dest = os.path.join(UPLOADS_DIR, f.filename)
    f.save(dest)
    result = {"path": dest, "name": f.filename}
    if CHROMA_AVAILABLE:
        text = ""
        try:
            if f.filename.endswith((".txt", ".md")):
                with open(dest, "r", encoding="utf-8") as fh:
                    text = fh.read()
            elif f.filename.endswith(".pdf"):
                text = _extract_text(dest)
            elif f.filename.endswith(".docx"):
                text = _extract_text(dest)
        except Exception:
            pass
        if text.strip():
            try:
                n = index_document(text, source=f.filename)
                result["indexed"] = n
            except Exception:
                pass
    return jsonify(result)

# ── Memory ──
@app.route("/api/memory")
def api_memory():
    return jsonify({"count": get_memory_count(), "chroma": CHROMA_AVAILABLE})

@app.route("/api/memory/clear", methods=["POST"])
def api_clear_memory():
    clear_memory()
    return jsonify({"ok": True})

@app.route("/api/memory/clear-session", methods=["POST"])
def api_clear_session():
    sid = request.get_json().get("session_id", "")
    if sid:
        sess.delete_session(sid)
        _agents.pop(sid, None)
        nsid = sess.new_session()
        return jsonify({"session_id": nsid})
    return jsonify({"ok": True})

# ── Documents ──
@app.route("/api/documents")
def api_list_documents():
    files = []
    for fname in os.listdir(UPLOADS_DIR):
        fpath = os.path.join(UPLOADS_DIR, fname)
        if os.path.isfile(fpath):
            files.append({"name": fname, "size": os.path.getsize(fpath)})
    return jsonify(files)

# ── Static files alias ──
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(ROOT, "favicon.ico") if os.path.exists(os.path.join(ROOT, "favicon.ico")) else ("", 404)

# ── Main ──
if __name__ == "__main__":
    start_scheduler()
    print("Agent IA v7 - http://localhost:8501", flush=True)
    app.run(host="127.0.0.1", port=8501, debug=False, threaded=True)
