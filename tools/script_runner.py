import json
import os
import subprocess

WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "script_whitelist.json")
DEFAULT_DIRS = [
    os.path.join(os.path.dirname(__file__), ".."),
]


def _load_whitelist() -> list[str]:
    if not os.path.exists(WHITELIST_PATH):
        return list(DEFAULT_DIRS)
    try:
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return list(DEFAULT_DIRS)


def _save_whitelist(dirs: list[str]) -> None:
    os.makedirs(os.path.dirname(WHITELIST_PATH), exist_ok=True)
    with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
        json.dump(dirs, f, ensure_ascii=False, indent=2)


def get_whitelist() -> list[str]:
    return _load_whitelist()


def add_whitelist_dir(directory: str) -> None:
    dirs = _load_whitelist()
    norm = os.path.abspath(directory)
    if norm not in dirs:
        dirs.append(norm)
        _save_whitelist(dirs)


def remove_whitelist_dir(directory: str) -> None:
    dirs = _load_whitelist()
    norm = os.path.abspath(directory)
    if norm in dirs:
        dirs.remove(norm)
        _save_whitelist(dirs)


def _is_path_allowed(path: str) -> bool:
    abs_path = os.path.abspath(path)
    allowed_dirs = _load_whitelist()
    for d in allowed_dirs:
        try:
            if os.path.commonpath([abs_path, os.path.abspath(d)]) == os.path.abspath(d):
                return True
        except ValueError:
            continue
    return False


def run_script(script_path: str, args: str = "") -> str:
    """
    Exécute un script .bat/.ps1/.py depuis le chat.
    Vérifie que le script est dans un dossier autorisé (whitelist).
    """
    if not os.path.exists(script_path):
        return f"Erreur : fichier introuvable → {script_path}"

    if not _is_path_allowed(script_path):
        allowed = ", ".join(_load_whitelist())
        return (
            f"Erreur sécurité : '{script_path}' n'est pas dans un dossier autorisé.\n"
            f"Dossiers autorisés : {allowed}\n"
            "Ajoute le dossier via la sidebar (Paramètres → Scripts) si besoin."
        )

    timeout = 120
    try:
        if script_path.lower().endswith(".ps1"):
            full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
            if args:
                full_cmd.extend(args.split())
        elif script_path.lower().endswith((".bat", ".cmd")):
            full_cmd = [script_path]
            if args:
                full_cmd.extend(args.split())
        elif script_path.lower().endswith(".py"):
            full_cmd = ["python", script_path]
            if args:
                full_cmd.extend(args.split())
        else:
            return f"Erreur : type de script non supporté (utilise .bat, .ps1 ou .py)"

        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            output = f"✅ Script exécuté (code {result.returncode})"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"Erreur : script interrompu après {timeout}s (timeout)"
    except Exception as e:
        return f"Erreur d'exécution : {e}"


RUN_SCRIPT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_script",
        "description": "Exécute un script .bat, .ps1 (PowerShell) ou .py depuis un dossier autorisé. Retourne la sortie stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Chemin absolu vers le script (.bat, .ps1 ou .py)",
                },
                "args": {
                    "type": "string",
                    "description": "Arguments passés au script (optionnels)",
                },
            },
            "required": ["script_path"],
        },
    },
}
