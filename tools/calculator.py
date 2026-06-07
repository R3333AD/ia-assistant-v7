import math

def calculator(expression: str) -> str:
    allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    allowed.update({"abs": abs, "round": round})
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Erreur : {e}"

CALCULATOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Calcule une expression mathématique. Supporte +,-,*,/,**,sqrt,sin,cos,log,pi...",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Expression à évaluer"}
            },
            "required": ["expression"],
        },
    },
}
