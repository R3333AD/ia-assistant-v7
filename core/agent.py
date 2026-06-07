import json
from groq import Groq, BadRequestError
from anthropic import Anthropic
from config.settings import (
    GROQ_API_KEY, ANTHROPIC_API_KEY, MODEL, ANTHROPIC_MODEL,
    MAX_TOKENS, MAX_ITERATIONS,
)
from tools import TOOLS_SCHEMAS, TOOLS_FUNCTIONS
from memory.profile import load_profile, profile_to_context
from memory.long_term import search_memory, save_memory
from memory.projects import projects_to_context

MAX_TOOL_ERRORS = 3
MAX_CODE_RETRIES = 2
MAX_HISTORY = 8
SUMMARY_WINDOW = 3
MAX_TOOL_RESULT_CHARS = 500
SUMMARY_MAX_TOKENS = 200

SENSITIVE_TOOLS = {"run_python_code", "run_script", "analyze_file", "manage_project", "send_discord"}


class Agent:
    def __init__(self, persona_prompt: str = ""):
        self.provider = "anthropic" if ANTHROPIC_API_KEY else "groq"
        self.persona_prompt = persona_prompt
        self.history = []
        self.thought_log = []
        self.current_summary = ""

        if self.provider == "anthropic":
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
            self.model = ANTHROPIC_MODEL
        else:
            self.client = Groq(api_key=GROQ_API_KEY)
            self.model = MODEL

        self._summarizer = Groq(api_key=GROQ_API_KEY)
        self._init_history()

    def _init_history(self):
        lines = [self.persona_prompt or "Assistant IA en français."]
        profile_ctx = profile_to_context(load_profile())
        if profile_ctx:
            lines.append(profile_ctx)
        pctx = projects_to_context()
        if pctx:
            lines.append(f"{pctx}\nOutil: manage_project")
        system = " ".join(lines)
        if self.provider == "anthropic":
            self.system_prompt = system
            self.history = []
        else:
            self.history = [{"role": "system", "content": system}]
        self.current_summary = ""

    # ── Adapter : OpenAI → Anthropic ──────────────────────

    @staticmethod
    def _to_anthropic_tools(tools_schemas):
        if not tools_schemas:
            return []
        result = []
        for tool in tools_schemas:
            func = tool.get("function", tool)
            result.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {
                    "type": "object", "properties": {}
                }),
            })
        return result

    def _to_anthropic_messages(self):
        system = None
        raw = []

        for m in self.history:
            role = m["role"]
            if role == "system":
                system = m["content"]
                continue

            if role == "user":
                txt = m.get("content", "")
                if txt:
                    raw.append({"role": "user", "content": txt})

            elif role == "assistant":
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    try:
                        inp = json.loads(tc["function"]["arguments"])
                    except Exception:
                        inp = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", f"toolu_{abs(hash(tc['function']['name'])):016x}"),
                        "name": tc["function"]["name"],
                        "input": inp,
                    })
                if blocks:
                    raw.append({"role": "assistant", "content": blocks})

            elif role == "tool":
                raw.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": str(m.get("content", "")),
                    }],
                })

        merged = []
        for m in raw:
            if merged and merged[-1]["role"] == m["role"] == "user":
                a, b = merged[-1]["content"], m["content"]
                if isinstance(a, list) and isinstance(b, list):
                    a.extend(b)
                elif isinstance(a, list) and isinstance(b, str):
                    a.append({"type": "text", "text": b})
                elif isinstance(a, str) and isinstance(b, list):
                    merged[-1]["content"] = [{"type": "text", "text": a}] + b
                elif isinstance(a, str) and isinstance(b, str):
                    merged[-1]["content"] = [{"type": "text", "text": a},
                                             {"type": "text", "text": b}]
            elif merged and merged[-1]["role"] == m["role"] == "assistant":
                merged[-1]["content"].extend(m["content"])
            else:
                merged.append(m)

        while merged and merged[0]["role"] == "assistant":
            merged.pop(0)

        if system is None:
            system = self.system_prompt if hasattr(self, "system_prompt") else ""
        return system, merged

    # ── Truncation / Compression ──────────────────────────

    def _truncate_tool_results(self):
        for m in self.history:
            c = m.get("content", "")
            if m.get("role") == "tool" and len(c) > MAX_TOOL_RESULT_CHARS:
                m["content"] = c[:250] + "\n…[tronqué]…\n" + c[-MAX_TOOL_RESULT_CHARS + 255:]

    def _trim_history(self):
        self._truncate_tool_results()
        self._summarize_and_compress()

    def _summarize_and_compress(self):
        if len(self.history) <= MAX_HISTORY + 1:
            return
        compressible = self.history[1:-SUMMARY_WINDOW]
        if len(compressible) < 2:
            self.history = [self.history[0]] + self.history[-(MAX_HISTORY):]
            return
        texts = "\n".join(
            f"{'U' if m['role']=='user' else 'A'}:{(m.get('content') or '')[:200]}"
            for m in compressible
        )
        prompt = (
            f"Tu es un module de mémoire. Mets à jour le résumé d'une conversation.\n\n"
            f"--- ANCIEN RÉSUMÉ ---\n{self.current_summary or 'Aucun.'}\n\n"
            f"--- NOUVEAUX ÉCHANGES À INTÉGRER ---\n{texts}\n\n"
            f"Rédige un nouveau résumé unique, fluide et condensé (max {SUMMARY_MAX_TOKENS} tokens). "
            f"Conserve les faits, entités (noms, projets) et décisions. Va droit au but."
        )
        try:
            r = self._summarizer.chat.completions.create(
                model=MODEL, max_tokens=SUMMARY_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            self.current_summary = r.choices[0].message.content.strip()[:500]
        except Exception:
            self.current_summary = self.current_summary or "(résumé)"
        self.history = (
            [self.history[0]]
            + [{"role": "user", "content": f"[Résumé] {self.current_summary}"}]
            + [{"role": "assistant", "content": "OK"}]
            + self.history[-SUMMARY_WINDOW:]
        )

    # ── Groq streaming ───────────────────────────────────

    def _groq_stream_once(self, on_token=None):
        stream = self.client.chat.completions.create(
            model=MODEL, max_tokens=MAX_TOKENS, messages=self.history,
            tools=TOOLS_SCHEMAS, tool_choice="auto", stream=True,
        )
        content = ""
        tool_calls = {}

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                content += delta.content
                if on_token:
                    on_token(delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments

        msg = {"role": "assistant", "content": content or None}
        if tool_calls:
            calls = []
            for idx in sorted(tool_calls.keys()):
                tc = tool_calls[idx]
                calls.append({
                    "id": tc["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })
            msg["tool_calls"] = calls
        return msg, bool(tool_calls)

    def _groq_fallback_stream(self, on_token=None):
        kwargs = dict(model=MODEL, max_tokens=MAX_TOKENS, messages=self.history, stream=True)
        full = ""
        for chunk in self.client.chat.completions.create(**kwargs):
            token = chunk.choices[0].delta.content or ""
            full += token
            if on_token:
                on_token(token)
        return full

    # ── Anthropic streaming ──────────────────────────────

    def _anthropic_stream_once(self, on_token=None):
        system, messages = self._to_anthropic_messages()
        tools = self._to_anthropic_tools(TOOLS_SCHEMAS)

        with self.client.messages.stream(
            model=self.model, max_tokens=MAX_TOKENS,
            system=system, messages=messages, tools=tools or [],
        ) as stream:
            content = ""
            tool_calls = {}

            for event in stream:
                if event.type == "content_block_start":
                    cb = event.content_block
                    if cb.type == "tool_use":
                        tool_calls[event.index] = {
                            "id": cb.id,
                            "type": "function",
                            "function": {"name": cb.name, "arguments": ""},
                        }

                elif event.type == "content_block_delta":
                    d = event.delta
                    if d.type == "text_delta":
                        content += d.text
                        if on_token:
                            on_token(d.text)
                    elif d.type == "input_json_delta":
                        idx = event.index
                        if idx in tool_calls:
                            tool_calls[idx]["function"]["arguments"] += d.partial_json

            msg = {"role": "assistant", "content": content or None}
            if tool_calls:
                msg["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
            return msg, bool(tool_calls)

    def _anthropic_fallback_stream(self, on_token=None):
        system, messages = self._to_anthropic_messages()
        with self.client.messages.stream(
            model=self.model, max_tokens=MAX_TOKENS,
            system=system, messages=messages,
        ) as stream:
            full = ""
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    full += event.delta.text
                    if on_token:
                        on_token(event.delta.text)
            return full

    # ── Dispatch ──────────────────────────────────────────

    def _stream_once(self, on_token=None):
        if self.provider == "anthropic":
            return self._anthropic_stream_once(on_token)
        return self._groq_stream_once(on_token)

    def _fallback_stream(self, on_token=None):
        if self.provider == "anthropic":
            return self._anthropic_fallback_stream(on_token)
        return self._groq_fallback_stream(on_token)

    # ── Main loop ─────────────────────────────────────────

    def run(self, user_message: str, on_token=None, on_tool=None, on_approval=None) -> tuple:
        self.thought_log = []
        tool_error_counts = {}

        memory_ctx = search_memory(user_message)
        if memory_ctx:
            memory_ctx = memory_ctx[:800]
        enriched = f"{user_message}\n\n[Mémoire : {memory_ctx}]" if memory_ctx else user_message
        self.history.append({"role": "user", "content": enriched})

        for iteration in range(MAX_ITERATIONS):
            try:
                msg, has_tools = self._stream_once(on_token=on_token)
            except Exception:
                try:
                    final = self._fallback_stream(on_token=on_token)
                    save_memory(user_message, final)
                    self._trim_history()
                    return final, self.thought_log
                except Exception as e:
                    return f"Erreur : {e}", self.thought_log

            self.history.append(msg)

            if not has_tools:
                final = msg.get("content") or ""
                save_memory(user_message, final)
                self._trim_history()
                return final, self.thought_log

            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except Exception:
                    args = {}

                err_count = tool_error_counts.get(name, 0)
                if err_count >= MAX_TOOL_ERRORS:
                    result = f"[ARRÊT] Outil '{name}' a échoué {MAX_TOOL_ERRORS} fois."
                    self.thought_log.append({"tool": name, "args": args, "result": result, "error": True})
                    self.history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                    continue

                # HITL : outil sensible → demande approbation utilisateur
                if name in SENSITIVE_TOOLS and on_approval:
                    decision = on_approval(name, args, tc["id"])
                    if not decision.get("approved"):
                        reason = decision.get("reason", "refused")
                        if reason == "timeout":
                            result = f"[TIMEOUT] L'utilisateur n'a pas répondu à temps. Exécution de '{name}' annulée."
                        else:
                            result = f"[REFUSÉ] L'utilisateur a refusé l'exécution de '{name}'."
                        self.thought_log.append({
                            "tool": name, "args": args, "result": result, "error": True,
                        })
                        self.history.append({
                            "role": "tool", "tool_call_id": tc["id"], "content": result,
                        })
                        continue
                    if "modified_args" in decision:
                        args = decision["modified_args"]

                func = TOOLS_FUNCTIONS.get(name)
                result = func(**args) if func else f"Outil inconnu : {name}"

                if name == "run_python_code" and "Erreur d'exécution" in str(result):
                    for retry in range(MAX_CODE_RETRIES):
                        fix = f"Le code a produit cette erreur :\n{result}\nCorrige le code et réessaie."
                        self.history.append({"role": "tool", "tool_call_id": tc["id"], "content": fix})
                        try:
                            fix_msg, fix_has = self._stream_once()
                            self.history.append(fix_msg)
                            if fix_has:
                                for ftc in fix_msg["tool_calls"]:
                                    if ftc["function"]["name"] == "run_python_code":
                                        fargs = json.loads(ftc["function"]["arguments"])
                                        result = TOOLS_FUNCTIONS["run_python_code"](**fargs)
                                        if "Erreur d'exécution" not in str(result):
                                            self.thought_log.append({
                                                "tool": f"{name} (corrigé, tentative {retry+1})",
                                                "args": fargs, "result": result, "error": False,
                                            })
                                            self.history.append({
                                                "role": "tool", "tool_call_id": ftc["id"],
                                                "content": str(result),
                                            })
                                            break
                        except Exception:
                            pass
                        if "Erreur d'exécution" not in str(result):
                            break
                    else:
                        tool_error_counts[name] = err_count + 1

                is_error = any(w in str(result) for w in ["Erreur", "Error", "ARRÊT", "introuvable"])
                if is_error:
                    tool_error_counts[name] = err_count + 1

                self.thought_log.append({"tool": name, "args": args, "result": result, "error": is_error})
                if on_tool:
                    on_tool(name, args, result)
                self.history.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

        self._trim_history()
        return "Limite d'itérations atteinte.", self.thought_log

    def reset(self):
        self.thought_log = []
        self._init_history()

    def set_persona(self, persona_prompt: str):
        self.persona_prompt = persona_prompt
        self._init_history()
