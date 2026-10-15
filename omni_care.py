
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from datetime import date
from tkinter import ttk, messagebox

from care_core import RenameError, RenameHistory, RenameTransaction, build_manual_plan
from name_parts import Choices, propose_name

STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "omnirename")
BACKUP_FILE = os.path.join(STATE_DIR, "rename_backlog.json")

class CareHistory(RenameHistory):
    """Rename history that also reads the flat {new path: old path} file the CaRe app wrote."""

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return super().load()
        if isinstance(data, dict) and "renames" not in data and all(
            isinstance(key, str) and isinstance(value, str) for key, value in data.items()
        ):
            return data
        return super().load()

def default_history():
    return CareHistory(Path(BACKUP_FILE))

DATE_ENTRY_FORMATS = {"yyyymmdd": "%Y%m%d", "yyyymm": "%Y%m", "yyyy": "%Y"}

# Paths handed over by the dispatcher; kept current after every rename and undo
current_paths = []

def rename(paths, choices, history=None):
    """Rename every path or none; return {old path: new path} for the renamed ones."""
    plan = build_manual_plan((path, propose_name(Path(path).name, choices)) for path in paths)
    problems = [f"{item.source.name} → {item.destination.name}: {item.problem}"
                for item in plan.items if item.problem]
    if problems:
        raise RenameError("Nothing was renamed.\n" + "\n".join(problems))
    RenameTransaction(history or default_history()).apply(plan)
    return {str(item.source): str(item.destination) for item in plan.changed_items}

def update_current_paths(moves):
    current_paths[:] = [moves.get(path, path) for path in current_paths]

def rename_selected(choices):
    if not current_paths:
        messagebox.showwarning("Selection Not Found", "No files or folders selected.")
        return
    try:
        moves = rename(current_paths, choices)
    except RenameError as error:
        messagebox.showerror("Rename Failed", str(error))
        return
    update_current_paths(moves)
    if moves:
        messagebox.showinfo("Renamed", "\n".join(
            f"{os.path.basename(old)} → {os.path.basename(new)}" for old, new in moves.items()))

def undo(paths, history=None):
    """Restore the original names of paths renamed earlier; return {old path: new path}."""
    history = history or default_history()
    originals = history.load()
    moves = {str(path): originals[str(path)] for path in paths if str(path) in originals}
    RenameTransaction(history).undo(paths)
    return moves

def undo_selected():
    try:
        moves = undo(current_paths)
    except RenameError as error:
        messagebox.showerror("Undo Failed", str(error))
        return
    update_current_paths(moves)
    if moves:
        messagebox.showinfo("Restored", "Restored original name for:\n" + "\n".join(
            os.path.basename(old) for old in moves))
    else:
        messagebox.showinfo("Nothing Restored", "No match found in backup.")

def main():
    current_paths[:] = [os.path.abspath(p) for p in sys.argv[1:]]

    # The window class lets the Hyprland rule float and centre the window
    root = tk.Tk(className="omnirename")
    root.title("OmniRename")
    root.geometry("370x420")
    root.configure(bg="#F0F0F0")
    root.bind("<Escape>", lambda event: root.destroy())
    root.bind("<Return>", lambda event: rename_selected(get_choices()))

    # Case style dropdown
    style_var = tk.StringVar(value="kebab-case")
    ttk.Label(root, text="Choose case style:", background="#F0F0F0").pack(pady=(10, 0))
    ttk.Combobox(root, textvariable=style_var, values=[
        "kebab-case", "PascalCase", "snake_case", "camelCase", "UPPERCASE", "lowercase", "Title Case", "Sentence case"
    ], state="readonly").pack(pady=4)

    # Prefix UI
    tk.Label(root, text="Prefix Options:", bg="#F0F0F0", font=("Segoe UI", 9, "bold")).pack()
    prefixes = {}
    for label in ["yyyymmdd", "yyyymm", "yyyy"]:
        f = tk.Frame(root, bg="#F0F0F0")
        var = tk.BooleanVar()
        entry = tk.Entry(f, width=10)
        tk.Checkbutton(f, text=label, variable=var, bg="#F0F0F0").pack(side="left")
        entry.pack(side="right")
        f.pack(pady=1)
        entry.insert(0, date.today().strftime(DATE_ENTRY_FORMATS[label]))
        prefixes[label] = (var, entry)

    # Suffix UI
    tk.Label(root, text="Suffix Options:", bg="#F0F0F0", font=("Segoe UI", 9, "bold")).pack()
    suffixes = {}
    for label in ["v", "initials"]:
        f = tk.Frame(root, bg="#F0F0F0")
        var = tk.BooleanVar()
        entry = tk.Entry(f, width=10)
        tk.Checkbutton(f, text=label, variable=var, bg="#F0F0F0").pack(side="left")
        entry.pack(side="right")
        f.pack(pady=1)
        suffixes[label] = (var, entry)

    # At most one Date: ticking one date box unticks the others
    def keep_one_date(chosen):
        if prefixes[chosen][0].get():
            for label, (var, entry) in prefixes.items():
                if label != chosen:
                    var.set(False)

    for label, (var, entry) in prefixes.items():
        var.trace_add("write", lambda *args, label=label: keep_one_date(label))

    def ticked(boxes, label):
        var, entry = boxes[label]
        return entry.get().strip() if var.get() else None

    def get_choices():
        dates = [ticked(prefixes, label) for label in prefixes if prefixes[label][0].get()]
        return Choices(
            style_var.get(),
            date=dates[0] if dates else None,
            version=ticked(suffixes, "v"),
            initials=ticked(suffixes, "initials") or None,
        )

    # Buttons
    tk.Button(root, text="Rename", command=lambda: rename_selected(get_choices()), bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold")).pack(pady=(8, 2), padx=20, fill="x")

    tk.Button(root, text="Undo Rename", command=undo_selected,
              bg="#607D8B", fg="white", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10), padx=20, fill="x")

    root.mainloop()

if __name__ == "__main__":
    main()
