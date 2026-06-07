import sys
import io
import traceback
import contextlib

def run_python_code(code: str) -> str:
    """
    Exécute du code Python dans un environnement sécurisé et retourne le résultat.
    """
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Modules autorisés
    safe_globals = {
        "__builtins__": {
            "print": print, "len": len, "range": range, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "sorted": sorted,
            "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
            "int": int, "float": float, "str": str, "list": list, "dict": dict,
            "tuple": tuple, "set": set, "bool": bool, "type": type,
            "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
        }
    }

    # Ajoute numpy, pandas, matplotlib si disponibles
    for lib in ["math", "statistics", "random", "datetime", "json", "re"]:
        try:
            safe_globals[lib] = __import__(lib)
        except ImportError:
            pass
    try:
        import numpy as np
        safe_globals["np"] = np
        safe_globals["numpy"] = np
    except ImportError:
        pass
    try:
        import pandas as pd
        safe_globals["pd"] = pd
        safe_globals["pandas"] = pd
    except ImportError:
        pass

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(code, safe_globals)  # noqa: S102
        output = stdout_capture.getvalue()
        error = stderr_capture.getvalue()
        if error:
            return f"Résultat :\n{output}\nAvertissements :\n{error}"
        return output or "Code exécuté sans sortie."
    except Exception:
        return f"Erreur d'exécution :\n{traceback.format_exc()}"

CODE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_python_code",
        "description": "Écrit et exécute du code Python pour résoudre des problèmes complexes : calculs, stats, manipulation de données. Retourne le résultat.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Code Python à exécuter"}
            },
            "required": ["code"],
        },
    },
}
