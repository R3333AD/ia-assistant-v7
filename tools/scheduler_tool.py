from memory import scheduler as sched

VALID_ACTIONS = ("list", "get", "create", "update", "delete", "toggle")
SUPPORTED_ACTIONS = ("message", "script", "webhook")


def schedule_task(
    action: str,
    name: str = "",
    task_id: str = "",
    cron: str = "",
    task_action: str = "message",
    prompt: str = "",
    webhook_name: str = "",
    script_path: str = "",
    message: str = "",
    enabled: int = 1,
) -> str:
    action = action.strip().lower()
    if action not in VALID_ACTIONS:
        valid_str = ", ".join(VALID_ACTIONS)
        return f"Erreur : action '{action}' invalide. Valides : {valid_str}"

    if action == "list":
        tasks = sched.list_tasks()
        if not tasks:
            return "Aucune tâche planifiée."
        lines = ["Tâches planifiées :"]
        for t in tasks:
            icon = "✅" if t.get("enabled") else "⏸️"
            nxt = sched.next_run(t["id"])
            nxt_str = f" → prochaine exécution : {nxt}" if nxt else ""
            lines.append(f"  {icon} {t['name']} ({t['action']}) {t['cron']}{nxt_str}")
        return "\n".join(lines)

    if action == "get":
        if not task_id:
            return "Erreur : task_id requis."
        t = sched.get_task(task_id)
        if not t:
            return f"Tâche '{task_id}' introuvable."
        import json as _json
        return _json.dumps(t, ensure_ascii=False)

    if action == "create":
        if not name or not cron:
            return "Erreur : name et cron requis.\nExemples cron : '0 9 * * *' (09h), '*/30 * * * *' (30min), '0 */2 * * *' (2h)"
        if task_action not in SUPPORTED_ACTIONS:
            return f"Erreur : task_action invalide. Supportées : {', '.join(SUPPORTED_ACTIONS)}"
        t = sched.add_task(
            name=name, action=task_action, cron=cron,
            prompt=prompt, webhook_name=webhook_name,
            script_path=script_path, message=message,
        )
        return f"✅ Tâche '{t['name']}' créée (id={t['id']}, cron={t['cron']})"

    if action == "update":
        if not task_id:
            return "Erreur : task_id requis."
        fields = {}
        if name:
            fields["name"] = name
        if cron:
            fields["cron"] = cron
        if task_action:
            if task_action not in SUPPORTED_ACTIONS:
                return f"Erreur : task_action invalide."
            fields["action"] = task_action
        if prompt is not None:
            fields["prompt"] = prompt
        if webhook_name is not None:
            fields["webhook_name"] = webhook_name
        if script_path is not None:
            fields["script_path"] = script_path
        if message is not None:
            fields["message"] = message
        if enabled is not None:
            fields["enabled"] = enabled
        t = sched.update_task(task_id, **fields)
        return f"✅ Tâche mise à jour." if t else f"Tâche '{task_id}' introuvable."

    if action == "delete":
        if not task_id:
            return "Erreur : task_id requis."
        sched.delete_task(task_id)
        return f"🗑️ Tâche '{task_id}' supprimée."

    if action == "toggle":
        if not task_id:
            return "Erreur : task_id requis."
        t = sched.toggle_task(task_id)
        status = "activée" if t.get("enabled") else "désactivée"
        return f"✅ Tâche '{t['name']}' {status} (id={t['id']})."

    return "Action non gérée."


SCHEDULE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "schedule_task",
        "description": (
            "Planifie une tâche récurrente (cron). Actions : list, get, create, update, delete, toggle. "
            "task_action supportées : message (rappel simple), script (exécute .bat/.ps1), webhook (envoi Discord). "
            "Cron exemples : '0 9 * * *' (tous les jours à 9h), '*/30 * * * *' (toutes les 30min), '0 8,18 * * 1-5' (lun-ven 8h et 18h)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action : list, get, create, update, delete, toggle",
                },
                "name": {
                    "type": "string",
                    "description": "Nom de la tâche",
                },
                "task_id": {
                    "type": "string",
                    "description": "ID de la tâche (get/update/delete/toggle)",
                },
                "cron": {
                    "type": "string",
                    "description": "Expression cron 5 champs : minute heure jour mois jour_semaine",
                },
                "task_action": {
                    "type": "string",
                    "description": "Type d'action : message (rappel), script (.bat/.ps1), webhook (Discord)",
                },
                "prompt": {
                    "type": "string",
                    "description": "Prompt pour l'action agent (optionnel)",
                },
                "webhook_name": {
                    "type": "string",
                    "description": "Nom de la webhook Discord enregistrée (pour action=webhook)",
                },
                "script_path": {
                    "type": "string",
                    "description": "Chemin absolu du script (pour action=script)",
                },
                "message": {
                    "type": "string",
                    "description": "Message du rappel (pour action=message)",
                },
                "enabled": {
                    "type": "integer",
                    "description": "1 = activé, 0 = désactivé",
                },
            },
            "required": ["action"],
        },
    },
}
