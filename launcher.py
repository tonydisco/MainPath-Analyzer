"""
MainPath Analysis Tool — Windows Launcher
Double-click to start. Opens browser automatically.
Shows a control window to stop the server.
"""
import sys
import os
import subprocess
import threading
import webbrowser
import time
import tkinter as tk
from tkinter import ttk, messagebox

# ── Resolve paths when running as PyInstaller bundle ──
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # extracted bundle dir
    APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BASE_DIR

APP_SCRIPT = os.path.join(BASE_DIR, "app.py")
PORT = 8501
URL = f"http://localhost:{PORT}"


class MainPathLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.process: subprocess.Popen | None = None
        self.running = False

        self._build_ui()
        self._start_server()

    def _build_ui(self):
        self.root.title("MainPath Analysis Tool")
        self.root.geometry("380x220")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set icon if available
        icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # Header
        header = tk.Frame(self.root, bg="#2C3E50", height=55)
        header.pack(fill="x")
        tk.Label(
            header, text="🔬  MainPath Analysis Tool",
            bg="#2C3E50", fg="white",
            font=("Segoe UI", 13, "bold"),
        ).pack(pady=12)

        # Status area
        frame = tk.Frame(self.root, padx=20, pady=12)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Server Status:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Starting…")
        self.status_label = tk.Label(
            frame, textvariable=self.status_var,
            font=("Segoe UI", 9, "bold"), fg="#E67E22",
        )
        self.status_label.grid(row=0, column=1, sticky="w", padx=8)

        tk.Label(frame, text="URL:", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=4)
        url_lbl = tk.Label(
            frame, text=URL, font=("Segoe UI", 9),
            fg="#2980B9", cursor="hand2",
        )
        url_lbl.grid(row=1, column=1, sticky="w", padx=8)
        url_lbl.bind("<Button-1>", lambda e: webbrowser.open(URL))

        # Progress bar
        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=300)
        self.progress.grid(row=2, column=0, columnspan=2, pady=8)
        self.progress.start(12)

        # Buttons
        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=4)

        self.open_btn = tk.Button(
            btn_frame, text="🌐 Open Browser", command=self._open_browser,
            bg="#2980B9", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=16, pady=5, state="disabled",
        )
        self.open_btn.pack(side="left", padx=6)

        self.stop_btn = tk.Button(
            btn_frame, text="⏹ Stop Server", command=self._on_close,
            bg="#C0392B", fg="white", font=("Segoe UI", 9),
            relief="flat", padx=16, pady=5,
        )
        self.stop_btn.pack(side="left", padx=6)

    def _start_server(self):
        """Start Streamlit in a background thread."""
        threading.Thread(target=self._run_streamlit, daemon=True).start()
        threading.Thread(target=self._wait_for_ready, daemon=True).start()

    def _run_streamlit(self):
        python = sys.executable
        cmd = [
            python, "-m", "streamlit", "run", APP_SCRIPT,
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.enableCORS", "false",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = BASE_DIR

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self.running = True
        self.process.wait()
        self.running = False

    def _wait_for_ready(self):
        """Poll until server responds, then update UI."""
        import urllib.request
        for _ in range(60):  # wait up to 60s
            time.sleep(1)
            try:
                urllib.request.urlopen(URL, timeout=2)
                self.root.after(0, self._on_server_ready)
                return
            except Exception:
                continue
        self.root.after(0, lambda: self._set_status("Failed to start", "#E74C3C"))

    def _on_server_ready(self):
        self.progress.stop()
        self.progress.pack_forget()
        self._set_status("Running ✓", "#27AE60")
        self.open_btn.config(state="normal")
        webbrowser.open(URL)

    def _set_status(self, text: str, color: str):
        self.status_var.set(text)
        self.status_label.config(fg=color)

    def _open_browser(self):
        webbrowser.open(URL)

    def _on_close(self):
        if self.process and self.running:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MainPathLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
