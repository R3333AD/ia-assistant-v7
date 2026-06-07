"""
Agent IA — Mode Desktop (PyQt6).
Lance Flask en arrière-plan et l'encapsule dans une fenêtre standalone
avec icône dans la barre des tâches, tray icon, et cleanup propre.

Usage :
    python run_desktop.py

Prérequis :
    pip install PyQt6 PyQt6-WebEngine
"""
import sys
import os
import subprocess
import time
import urllib.request
import urllib.error
import atexit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8502
URL = f"http://localhost:{PORT}"
FLASK_CMD = [sys.executable, os.path.join(BASE_DIR, "app.py")]

_flask_proc = None


def _start_flask():
    global _flask_proc
    _flask_proc = subprocess.Popen(
        FLASK_CMD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    atexit.register(_stop_flask)

    for i in range(40):
        try:
            with urllib.request.urlopen(f"{URL}/api/conf", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionRefusedError):
            pass
        time.sleep(0.5)
    return False


def _stop_flask():
    if _flask_proc and _flask_proc.poll() is None:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(_flask_proc.pid)],
                           capture_output=True)
        else:
            _flask_proc.terminate()
            try:
                _flask_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _flask_proc.kill()


def main():
    if not _start_flask():
        print("❌ Impossible de démarrer Flask.")
        sys.exit(1)

    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl, Qt
        from PyQt6.QtGui import QAction
    except ImportError:
        print("PyQt6 non installé. Lance l'app normalement :")
        print(f"  python app.py")
        print("Ou installe PyQt6 :")
        print(f"  pip install PyQt6 PyQt6-WebEngine")
        _stop_flask()
        sys.exit(1)

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Agent IA")
    qt_app.setOrganizationName("WhiteBullet")

    window = QMainWindow()
    window.setWindowTitle("Agent IA v7")
    window.resize(1280, 800)
    window.setMinimumSize(800, 500)

    web = QWebEngineView()
    web.setUrl(QUrl(URL))
    web.page().setBackgroundColor(Qt.GlobalColor.transparent)
    window.setCentralWidget(web)

    # System tray
    tray = QSystemTrayIcon(qt_app.style().standardIcon(qt_app.style().StandardPixmap.SP_ComputerIcon))
    tray.setToolTip("Agent IA v7")
    tray_menu = QMenu()
    show_action = QAction("Afficher/Masquer")
    show_action.triggered.connect(lambda: window.show() if window.isHidden() else window.hide())
    tray_menu.addAction(show_action)
    quit_action = QAction("Quitter")
    quit_action.triggered.connect(qt_app.quit)
    tray_menu.addAction(quit_action)
    tray.setContextMenu(tray_menu)
    tray.show()

    # Tray double-click
    tray.activated.connect(lambda reason: window.show() if reason == tray.ActivationReason.DoubleClick else None)

    window.show()

    # Clean shutdown
    def cleanup():
        _stop_flask()
        tray.hide()

    qt_app.aboutToQuit.connect(cleanup)

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
