"""Общие виджеты GUI."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


class LogView(ttk.Frame):
    """Панель с логом (Text + scrollbar + очистка)."""

    def __init__(self, parent, height: int = 10):
        super().__init__(parent)
        self.text = tk.Text(self, height=height, wrap="word", font=("Consolas", 9))
        self.text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)
        self.text.configure(state="disabled")

    def append(self, msg: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", msg + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class StatusCard(ttk.LabelFrame):
    """Карточка статуса."""

    def __init__(self, parent, title: str):
        super().__init__(parent, text=title, padding=8)
        self.value_label = ttk.Label(self, text="—", font=("Segoe UI", 11, "bold"))
        self.value_label.pack()
        self.detail_label = ttk.Label(self, text="", font=("Segoe UI", 8))
        self.detail_label.pack()

    def set(self, value: str, detail: str = "") -> None:
        self.value_label.configure(text=value)
        self.detail_label.configure(text=detail)


def ask_text(parent, title: str, prompt: str, initial: str = "") -> str | None:
    return simpledialog.askstring(title, prompt, parent=parent, initialvalue=initial)


def confirm(parent, title: str, message: str) -> bool:
    return messagebox.askyesno(title, message, parent=parent)


def show_error(parent, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=parent)


def show_info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=parent)


def open_url(url: str) -> None:
    import webbrowser
    webbrowser.open(url)
