"""
Outil agent pour gérer les projets de l'utilisateur.
Une seule fonction, plusieurs actions, pour simplifier le choix du LLM.
"""
import json
from memory import projects as proj

VALID_ACTIONS = ("list", "get", "create", "update", "delete",
                 "add_todo", "toggle_todo", "remove_todo")


def manage_project(
    action: str,
    name: str = "",
    project_id: str = "",
    status: str = "",
    description: str = "",
    tags: str = "",
    todo_text: str = "",
    todo_id: str = "",
) -> str:
    """
    Gère la base de projets. Actions :
    - list : liste tous les projets
    - get : détails d'un projet (par project_id)
    - create : crée un projet (name requis)
    - update : modifie status/description/tags d'un projet
    - delete : supprime un projet (par project_id)
    - add_todo : ajoute un todo à un projet (project_id + todo_text)
    - toggle_todo : coche/décoche un todo
    - remove_todo : supprime un todo
    Status valides : planifié, en cours, en pause, terminé, abandonné
    """
    action = action.strip().lower()
    if action not in VALID_ACTIONS:
        return f"Erreur : action '{action}' invalide. Valides : {VALID_ACTIONS}"

    if action == "list":
        items = proj.list_projects()
        if not items:
            return "Aucun projet enregistré."
        return json.dumps(
            [{"id": p["id"], "name": p["name"], "status": p["status"],
              "todos_open": sum(1 for t in p["todos"] if not t.get("done")),
              "todos_total": len(p["todos"])} for p in items],
            ensure_ascii=False,
        )

    if action == "get":
        if not project_id:
            return "Erreur : project_id requis."
        p = proj.get_project(project_id)
        if not p:
            return f"Projet '{project_id}' introuvable."
        return json.dumps(p, ensure_ascii=False)

    if action == "create":
        if not name:
            return "Erreur : name requis pour create."
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        p = proj.create_project(name=name, description=description, status=status or "planifié", tags=tag_list)
        return f"✅ Projet créé : '{p['name']}' (id={p['id']})"

    if action == "update":
        if not project_id:
            return "Erreur : project_id requis pour update."
        fields = {}
        if status:
            fields["status"] = status
        if description:
            fields["description"] = description
        if tags:
            fields["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        if name:
            fields["name"] = name
        if not fields:
            return "Erreur : rien à mettre à jour."
        p = proj.update_project(project_id, **fields)
        return f"✅ Projet '{p['name']}' mis à jour." if p else f"Projet '{project_id}' introuvable."

    if action == "delete":
        if not project_id:
            return "Erreur : project_id requis."
        if proj.delete_project(project_id):
            return f"🗑️ Projet '{project_id}' supprimé."
        return f"Projet '{project_id}' introuvable."

    if action == "add_todo":
        if not (project_id and todo_text):
            return "Erreur : project_id et todo_text requis."
        p = proj.add_todo(project_id, todo_text)
        return f"✅ TODO ajouté à '{p['name']}'." if p else f"Projet '{project_id}' introuvable."

    if action == "toggle_todo":
        if not (project_id and todo_id):
            return "Erreur : project_id et todo_id requis."
        p = proj.toggle_todo(project_id, todo_id)
        return f"✅ TODO basculé dans '{p['name']}'." if p else "Introuvable."

    if action == "remove_todo":
        if not (project_id and todo_id):
            return "Erreur : project_id et todo_id requis."
        p = proj.remove_todo(project_id, todo_id)
        return f"🗑️ TODO supprimé de '{p['name']}'." if p else "Introuvable."

    return "Action non gérée."


MANAGE_PROJECT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "manage_project",
        "description": (
            "Gère la base de projets de l'utilisateur. Actions : list, get, create, update, delete, "
            "add_todo, toggle_todo, remove_todo. Status valides : planifié, en cours, en pause, terminé, abandonné."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action : list, get, create, update, delete, add_todo, toggle_todo, remove_todo"},
                "name": {"type": "string", "description": "Nom du projet (create/update)"},
                "project_id": {"type": "string", "description": "ID du projet"},
                "status": {"type": "string", "description": "Nouveau statut (update/create)"},
                "description": {"type": "string", "description": "Description (create/update)"},
                "tags": {"type": "string", "description": "Tags séparés par virgules"},
                "todo_text": {"type": "string", "description": "Texte du TODO (add_todo)"},
                "todo_id": {"type": "string", "description": "ID du TODO (toggle/remove)"},
            },
            "required": ["action"],
        },
    },
}
