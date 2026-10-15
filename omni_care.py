
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from datetime import date
from tkinter import ttk

from omni_renamer import RenameError, RenameHistory, RenameTransaction, build_manual_plan
from name_parts import Choices, choice_problems, existing_name, propose_name
from omni_theme import load_palette, mix

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
    problems = choice_problems(choices)
    if problems:
        raise RenameError("Nothing was renamed.\n" + "\n".join(problems))
    plan = build_manual_plan((path, propose_name(Path(path).name, choices)) for path in paths)
    problems = [f"{item.source.name} → {item.destination.name}: {item.problem}"
                for item in plan.items if item.problem]
    if problems:
        raise RenameError("Nothing was renamed.\n" + "\n".join(problems))
    RenameTransaction(history or default_history()).apply(plan)
    return {str(item.source): str(item.destination) for item in plan.changed_items}

def update_current_paths(moves):
    current_paths[:] = [moves.get(path, path) for path in current_paths]

def name_changes(moves):
    return [f"{os.path.basename(old)} → {os.path.basename(new)}" for old, new in moves.items()]

def rename_report(moves):
    """(kind, headline, details) for the status area after a rename."""
    if not moves:
        return "info", "Nothing to change: the names already look like this", []
    changes = name_changes(moves)
    if len(changes) == 1:
        return "success", f"Renamed {changes[0]}", []
    return "success", f"Renamed {len(changes)} items", changes

def undo_report(moves):
    if not moves:
        return "info", "Nothing to undo for these items", []
    restored = [os.path.basename(new) for new in moves.values()]
    if len(restored) == 1:
        return "success", f"Restored {restored[0]}", []
    return "success", f"Restored {len(restored)} items", name_changes(moves)

def problem_report(error):
    headline, *details = str(error).splitlines()
    if headline == "Nothing was renamed." and details:
        if len(details) == 1:
            return "error", f"Nothing was renamed: {details[0]}", []
        return "error", f"Nothing was renamed: {len(details)} Problems", details
    return "error", headline, details

def undo(paths, history=None):
    """Restore the original names of paths renamed earlier; return {old path: new path}."""
    history = history or default_history()
    originals = history.load()
    moves = {str(path): originals[str(path)] for path in paths if str(path) in originals}
    RenameTransaction(history).undo(paths)
    return moves

def rename_selected(choices):
    if not current_paths:
        return "error", "No files or folders selected", []
    try:
        moves = rename(current_paths, choices)
    except RenameError as error:
        return problem_report(error)
    update_current_paths(moves)
    return rename_report(moves)

def undo_selected():
    try:
        moves = undo(current_paths)
    except RenameError as error:
        return problem_report(error)
    update_current_paths(moves)
    return undo_report(moves)

FONT = "JetBrainsMono Nerd Font"
STYLES = ["kebab-case", "PascalCase", "snake_case", "camelCase", "UPPERCASE", "lowercase", "Title Case", "Sentence case"]

def apply_theme(root, palette):
    """Colour every ttk widget with the Omarchy palette."""
    background, surface, foreground = palette["background"], palette["surface"], palette["foreground"]
    muted, accent = palette["muted"], palette["accent"]
    root.configure(bg=background)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=background, foreground=foreground, font=(FONT, 10),
                    bordercolor=muted, lightcolor=background, darkcolor=background,
                    troughcolor=surface, focuscolor=accent, insertcolor=foreground)
    style.configure("Heading.TLabel", foreground=muted, font=(FONT, 9, "bold"))
    style.configure("TCheckbutton", indicatorbackground=surface, indicatorforeground=background,
                    indicatormargin=(0, 0, 8, 0), padding=(0, 3))
    style.map("TCheckbutton", background=[("active", background)],
              indicatorbackground=[("selected", accent), ("active", mix(surface, accent, 0.25))])
    for widget in ("TEntry", "TCombobox"):
        style.configure(widget, fieldbackground=surface, foreground=foreground, padding=(6, 4),
                        bordercolor=surface, lightcolor=surface, darkcolor=surface,
                        selectbackground=accent, selectforeground=background, arrowcolor=foreground)
        style.map(widget, bordercolor=[("focus", accent)], lightcolor=[("focus", accent)],
                  fieldbackground=[("readonly", surface)], foreground=[("readonly", foreground)],
                  selectbackground=[("readonly", surface)], selectforeground=[("readonly", foreground)])
    style.configure("Placeholder.TEntry", foreground=muted)
    style.map("TCombobox", background=[("active", surface), ("readonly", surface)])
    root.option_add("*TCombobox*Listbox.background", surface)
    root.option_add("*TCombobox*Listbox.foreground", foreground)
    root.option_add("*TCombobox*Listbox.selectBackground", accent)
    root.option_add("*TCombobox*Listbox.selectForeground", background)
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    style.configure("Rename.TButton", background=accent, foreground=background, bordercolor=accent,
                    font=(FONT, 10, "bold"), padding=(0, 7))
    style.map("Rename.TButton", background=[("active", mix(accent, foreground, 0.2))])
    style.configure("Undo.TButton", background=background, foreground=foreground, bordercolor=muted,
                    padding=(0, 6))
    style.map("Undo.TButton", background=[("active", surface)], bordercolor=[("active", accent)])

def main():
    current_paths[:] = [os.path.abspath(p) for p in sys.argv[1:]]
    palette = load_palette()

    # The window class lets the Hyprland rule float and centre the window
    root = tk.Tk(className="omnirename")
    root.title("OmniRename")
    root.resizable(False, False)
    root.minsize(320, 1)
    apply_theme(root, palette)
    root.bind("<Escape>", lambda event: root.destroy())

    form = ttk.Frame(root, padding=(18, 14, 18, 16))
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)
    row = 0

    def heading(text, top=12):
        nonlocal row
        ttk.Label(form, text=text.upper(), style="Heading.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(top, 4))
        row += 1

    def ticked_value(label, value=""):
        nonlocal row
        var = tk.BooleanVar()
        entry = ttk.Entry(form, width=12, font=(FONT, 10))
        entry.insert(0, value)
        ttk.Checkbutton(form, text=label, variable=var).grid(row=row, column=0, sticky="w")
        entry.grid(row=row, column=1, sticky="e", padx=(16, 0), pady=2)
        row += 1
        return var, entry

    heading("Name", top=0)
    name_entry = ttk.Entry(form, font=(FONT, 10))
    name_entry.grid(row=row, column=0, columnspan=2, sticky="ew")
    row += 1
    # The current Name shows as a grey placeholder; leaving the box empty keeps it
    def current_name():
        if len(current_paths) == 1:
            return existing_name(os.path.basename(current_paths[0]))
        return "Keep each item's name"

    placeholder = current_name()
    showing_placeholder = True

    def show_placeholder(event=None):
        nonlocal showing_placeholder
        if not name_entry.get():
            showing_placeholder = True
            name_entry.configure(style="Placeholder.TEntry")
            name_entry.insert(0, placeholder)

    def hide_placeholder(event=None):
        nonlocal showing_placeholder
        if showing_placeholder:
            showing_placeholder = False
            name_entry.delete(0, "end")
            name_entry.configure(style="TEntry")

    def refresh_placeholder():
        nonlocal placeholder
        placeholder = current_name()
        if showing_placeholder:
            name_entry.delete(0, "end")
            name_entry.insert(0, placeholder)

    name_entry.bind("<FocusIn>", hide_placeholder)
    name_entry.bind("<FocusOut>", show_placeholder)
    show_placeholder()

    heading("Style")
    style_var = tk.StringVar(value="kebab-case")
    ttk.Combobox(form, textvariable=style_var, values=STYLES, state="readonly", font=(FONT, 10)).grid(
        row=row, column=0, columnspan=2, sticky="ew")
    row += 1

    heading("Date")
    date_boxes = {label: ticked_value(label, date.today().strftime(DATE_ENTRY_FORMATS[label]))
                  for label in DATE_ENTRY_FORMATS}

    heading("Version and Initials")
    version_box = ticked_value("Version")
    initials_box = ticked_value("Initials")

    # At most one Date: ticking one date box unticks the others
    def keep_one_date(chosen):
        if date_boxes[chosen][0].get():
            for label, (var, entry) in date_boxes.items():
                if label != chosen:
                    var.set(False)

    for label, (var, entry) in date_boxes.items():
        var.trace_add("write", lambda *args, label=label: keep_one_date(label))

    def typed_if_ticked(box):
        var, entry = box
        return entry.get().strip() if var.get() else None

    def get_choices():
        dates = [typed_if_ticked(box) for box in date_boxes.values() if box[0].get()]
        return Choices(
            style_var.get(),
            name=None if showing_placeholder else name_entry.get().strip() or None,
            date=dates[0] if dates else None,
            version=typed_if_ticked(version_box),
            initials=typed_if_ticked(initials_box) or None,
        )

    # Status area: one line about the last action, with the full list behind Show all
    status = tk.Frame(form, bg=palette["background"])
    status_text = tk.Label(status, justify="left", anchor="w", wraplength=300, font=(FONT, 9),
                           padx=10, pady=8)
    status_text.pack(fill="x")
    show_all = tk.Button(status, relief="flat", borderwidth=0, highlightthickness=0, cursor="hand2", padx=0, pady=0,
                         font=(FONT, 9, "underline"), fg=palette["accent"],
                         activeforeground=palette["foreground"])
    details = tk.Text(status, height=1, width=36, relief="flat", wrap="word", font=(FONT, 9),
                      bg=palette["surface"], fg=palette["foreground"], padx=10, pady=6,
                      highlightthickness=0)

    def show(report):
        refresh_placeholder()
        kind, headline, lines = report
        colour = {"success": palette["success"], "error": palette["error"]}.get(kind, palette["muted"])
        tint = mix(palette["background"], colour, 0.15)
        status.configure(bg=tint, highlightbackground=colour, highlightthickness=1)
        status_text.configure(text=headline, bg=tint, fg=colour if kind != "info" else palette["foreground"])
        details.pack_forget()
        show_all.pack_forget()
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.insert("1.0", "\n".join(lines))
        # Wrapped lines take more than one row; show up to 10 rows and scroll the rest
        rows = sum(-(-len(line) // 36) or 1 for line in lines)
        details.configure(state="disabled", height=min(rows, 10))
        status.grid(row=status_row, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        if lines:
            def toggle():
                if details.winfo_ismapped():
                    details.pack_forget()
                    show_all.configure(text=f"Show all {len(lines)}")
                else:
                    details.pack(fill="both", padx=1, pady=(0, 1))
                    show_all.configure(text="Hide list")
            show_all.configure(text=f"Show all {len(lines)}", command=toggle, bg=tint, activebackground=tint)
            show_all.pack(anchor="w", padx=10, pady=(0, 8))

    buttons = ttk.Frame(form)
    buttons.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(16, 0))
    buttons.columnconfigure(0, weight=1)
    row += 1
    status_row = row
    ttk.Button(buttons, text="Rename", style="Rename.TButton",
               command=lambda: show(rename_selected(get_choices()))).grid(row=0, column=0, sticky="ew")
    ttk.Button(buttons, text="Undo Rename", style="Undo.TButton",
               command=lambda: show(undo_selected())).grid(row=1, column=0, sticky="ew", pady=(6, 0))
    root.bind("<Return>", lambda event: show(rename_selected(get_choices())))

    root.mainloop()

if __name__ == "__main__":
    main()
