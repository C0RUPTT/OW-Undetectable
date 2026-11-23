"""Small status window for a second monitor. Optional: audio cues work without it."""
from __future__ import annotations

import tkinter as tk

BG, FG, DIM, HOT, ULT = "#14161a", "#e8e8e8", "#7a7f87", "#ffb347", "#7fb3ff"
STATE_COLOR = {"used": HOT, "charging": DIM, "possible": "#ffd166", "likely": "#ff6b6b",
               "unknown": ULT}


class StatusWindow:
    def __init__(self, controller, topmost: bool = True):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Cooldown Tracker")
        self.root.configure(bg=BG)
        self.root.geometry("320x360")
        self.root.attributes("-topmost", topmost)
        self.last = tk.Label(self.root, text="listening…", bg=BG, fg=DIM,
                             font=("Segoe UI", 10), anchor="w")
        self.last.pack(fill="x", padx=12, pady=(10, 4))
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=12)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        self._tick()
        self.root.mainloop()

    def close(self) -> None:
        self.controller.shutdown()
        self.root.destroy()

    def _row(self, text: str, value: str, color: str) -> None:
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=text, bg=BG, fg=FG, font=("Segoe UI", 12)).pack(side="left")
        tk.Label(row, text=value, bg=BG, fg=color,
                 font=("Consolas", 14, "bold")).pack(side="right")

    def _tick(self) -> None:
        status, last_heard = self.controller.tick()
        for w in self.body.winfo_children():
            w.destroy()
        if status.cooldowns:
            tk.Label(self.body, text="DOWN", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w")
            for ability, remaining in status.cooldowns:
                color = HOT if remaining <= 3 else FG
                self._row(ability.label, f"{remaining:4.1f}s", color)
        if status.ults:
            tk.Label(self.body, text="ENEMY ULTS", bg=BG, fg=DIM,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
            for u in status.ults:
                if u.state == "charging":
                    value = f"~{int(u.possible_in)}s"
                elif u.state in ("possible", "likely"):
                    value = f"{u.state}"
                else:
                    value = f"{int(u.elapsed)}s ago"
                self._row(u.ability.label, value, STATE_COLOR[u.state])
        if last_heard:
            self.last.config(text=f"heard: {last_heard}")
        self.root.after(100, self._tick)
