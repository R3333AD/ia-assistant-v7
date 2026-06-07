import os
from datetime import datetime

_OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "outputs")
_BROWSER = None


def _get_browser():
    global _BROWSER
    if _BROWSER is not None:
        return _BROWSER
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        p = sync_playwright().start()
        _BROWSER = p.chromium.launch(headless=True, args=["--no-sandbox"])
    except Exception:
        return None
    return _BROWSER


def browse_web(
    action: str = "navigate",
    url: str = "",
    selector: str = "",
    value: str = "",
    timeout: int = 30000,
) -> str:
    browser = _get_browser()
    if browser is None:
        return (
            "Playwright non disponible. Installe-le d'abord :\n"
            "  pip install playwright\n  playwright install chromium"
        )

    page = browser.new_page()
    try:
        if action == "navigate":
            if not url:
                return "Erreur : URL requise pour navigate."
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            content = page.content()[:3000]
            return f"Titre : {page.title()}\nContenu (début) : {content[:1000]}"

        if action == "click":
            if not selector:
                return "Erreur : selector requis pour click."
            page.click(selector, timeout=timeout)
            return f"✅ Clic sur '{selector}'"

        if action == "fill":
            if not selector or value is None:
                return "Erreur : selector et value requis pour fill."
            page.fill(selector, value, timeout=timeout)
            return f"✅ Rempli '{selector}' avec '{value[:100]}'"

        if action == "extract":
            if not selector:
                return "Erreur : selector requis pour extract."
            els = page.query_selector_all(selector)
            texts = [el.inner_text().strip() for el in els if el.inner_text().strip()]
            if not texts:
                return f"Aucun élément trouvé pour '{selector}'."
            out = "\n".join(texts[:60])
            return f"{len(texts)} résultat(s) :\n{out}"

        if action == "screenshot":
            os.makedirs(_OUTPUTS_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(_OUTPUTS_DIR, f"screenshot_{ts}.png")
            page.screenshot(path=path, full_page=True)
            return f"📸 Screenshot sauvegardé : {path}"

        if action == "wait":
            if not selector:
                return "Erreur : selector requis pour wait."
            page.wait_for_selector(selector, timeout=timeout)
            return f"✅ Sélecteur '{selector}' apparu"

        return f"Action '{action}' non supportée. Supportées : navigate, click, fill, extract, screenshot, wait"

    except Exception as e:
        return f"Erreur Playwright : {e}"
    finally:
        page.close()


BROWSE_WEB_SCHEMA = {
    "type": "function",
    "function": {
        "name": "browse_web",
        "description": (
            "Ouvre un navigateur Chromium et interagit avec une page web. "
            "Actions : navigate (aller sur une URL), click, fill (remplir formulaire), "
            "extract (extraire du texte), screenshot, wait (attendre un élément)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action : navigate, click, fill, extract, screenshot, wait",
                },
                "url": {
                    "type": "string",
                    "description": "URL (pour navigate)",
                },
                "selector": {
                    "type": "string",
                    "description": "Sélecteur CSS (pour click, fill, extract, wait). Ex: '#login', '.btn-primary', 'form input[name=email]'",
                },
                "value": {
                    "type": "string",
                    "description": "Valeur à saisir (pour fill)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout en ms (défaut 30000)",
                },
            },
            "required": ["action"],
        },
    },
}
