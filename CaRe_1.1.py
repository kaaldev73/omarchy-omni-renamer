
import os
import re
import json
import tkinter as tk
from tkinter import ttk, messagebox
import pythoncom
import win32com.client

BACKUP_FILE = os.path.join(os.path.dirname(__file__), "rename_backlog.json")

def to_kebab_case(name):
    name, ext = os.path.splitext(name)
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[_\s]+', '-', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', name)
    name = re.sub(r'([0-9])([a-zA-Z])', r'\1-\2', name)
    name = re.sub(r'([a-zA-Z])([0-9])', r'\1-\2', name)
    return name.lower()

def get_selected_items():
    pythoncom.CoInitialize()
    shell = win32com.client.Dispatch("Shell.Application")
    all_paths = []
    for window in shell.Windows():
        try:
            if window and window.Document:
                items = window.Document.SelectedItems()
                for i in range(items.Count):
                    all_paths.append(items.Item(i).Path)
        except Exception:
            continue
    return all_paths

def load_backup():
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_backup(backup):
    with open(BACKUP_FILE, 'w') as f:
        json.dump(backup, f, indent=2)

def rename_selected(case_style, prefixes, suffixes):
    from datetime import datetime
    paths = get_selected_items()
    if not paths:
        messagebox.showwarning("Selection Not Found", "No files or folders selected.")
        return

    backup = load_backup()
    renamed = []

    for path in paths:
        folder, original_name = os.path.split(path)
        name, ext = os.path.splitext(original_name)

        # Convert case
        if case_style == "kebab-case":
            name = to_kebab_case(name)
        elif case_style == "PascalCase":
            name = ''.join(word.capitalize() for word in re.split(r'[_\s-]', name))
        elif case_style == "snake_case":
            name = to_kebab_case(name).replace("-", "_")
        elif case_style == "camelCase":
            parts = to_kebab_case(name).split("-")
            name = parts[0] + ''.join(word.capitalize() for word in parts[1:])
        elif case_style == "UPPERCASE":
            name = name.upper()
        elif case_style == "lowercase":
            name = name.lower()
        elif case_style == "Title Case":
            name = name.title()
        elif case_style == "Sentence case":
            name = name.capitalize()

        prefix_str = '-'.join([p for p in prefixes if p])
        suffix_str = '-'.join([s for s in suffixes if s])

        new_name = f"{prefix_str + '-' if prefix_str else ''}{name}{'-' + suffix_str if suffix_str else ''}{ext}"
        new_path = os.path.join(folder, new_name)

        if new_path != path:
            try:
                os.rename(path, new_path)
                renamed.append(f"{original_name} → {new_name}")
                backup[new_path] = path
            except Exception as e:
                messagebox.showerror("Rename Failed", f"{original_name} → {e}")

    save_backup(backup)
    if renamed:
        messagebox.showinfo("Renamed", "\n".join(renamed))

def undo_selected():
    paths = get_selected_items()
    backup = load_backup()
    undone = []

    for path in paths:
        if path in backup:
            original_path = backup[path]
            try:
                os.rename(path, original_path)
                undone.append(os.path.basename(path))
                del backup[path]
            except Exception as e:
                messagebox.showerror("Undo Failed", f"{path} → {e}")
        else:
            # Try reverse lookup
            for renamed, original in list(backup.items()):
                if os.path.basename(path) == os.path.basename(renamed):
                    try:
                        os.rename(path, original)
                        undone.append(os.path.basename(path))
                        del backup[renamed]
                        break
                    except Exception as e:
                        messagebox.showerror("Restore Failed", f"{path} → {e}")
                        break

    save_backup(backup)
    if undone:
        messagebox.showinfo("Restored", "Restored original name for:\n" + "\n".join(undone))
    else:
        messagebox.showinfo("Nothing Restored", "No match found in backup.")

# GUI
root = tk.Tk()
root.title("CaRe - Renamer")
root.geometry("370x470+1200+700")
root.configure(bg="#F0F0F0")
root.attributes("-topmost", True)

def start_move(event): root.x, root.y = event.x, event.y
def stop_move(event): root.x, root.y = None, None
def do_move(event): root.geometry(f"+{root.winfo_x() + (event.x - root.x)}+{root.winfo_y() + (event.y - root.y)}")

# Header
title_bar = tk.Frame(root, bg="#262626", relief="raised", bd=0)
title_bar.pack(fill=tk.X)
tk.Label(title_bar, text="🔁 CaRe - Renamer", bg="#262626", fg="white", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=6)
tk.Button(title_bar, text="–", command=root.iconify, bg="#262626", fg="white", bd=0).pack(side=tk.RIGHT, padx=5)
tk.Button(title_bar, text="×", command=root.destroy, bg="#262626", fg="white", bd=0).pack(side=tk.RIGHT)
title_bar.bind("<Button-1>", start_move)
title_bar.bind("<B1-Motion>", do_move)
title_bar.bind("<ButtonRelease-1>", stop_move)

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

def get_prefix_values():
    return [entry.get() for var, entry in prefixes.values() if var.get()]

def get_suffix_values():
    return [entry.get() for var, entry in suffixes.values() if var.get()]

# Buttons
tk.Button(root, text="Rename", command=lambda: rename_selected(
    style_var.get(), get_prefix_values(), get_suffix_values()
), bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold")).pack(pady=(8, 2), padx=20, fill="x")

tk.Button(root, text="Undo Rename", command=undo_selected,
          bg="#607D8B", fg="white", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10), padx=20, fill="x")

root.mainloop()
