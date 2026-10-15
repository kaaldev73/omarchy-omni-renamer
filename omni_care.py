
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

def name_chain(path, originals):
    """Every name path has had, newest first, following the history {new: old}."""
    chain = [str(path)]
    while chain[-1] in originals and originals[chain[-1]] not in chain:
        chain.append(originals[chain[-1]])
    return chain

def restore(path, earlier, history=None):
    """Step path back through its history to an earlier name; return {old path: new path}."""
    history = history or default_history()
    chain = name_chain(path, history.load())
    earlier = str(earlier)
    if earlier not in chain[1:]:
        raise RenameError(f"{os.path.basename(earlier)} is not an earlier name of {os.path.basename(str(path))}")
    if os.path.lexists(earlier):
        raise RenameError(f"Cannot restore {os.path.basename(earlier)}: an item with that name exists")
    for current in chain[:chain.index(earlier)]:
        RenameTransaction(history).undo([current])
    return {str(path): earlier}

def undo_selected():
    try:
        moves = undo(current_paths)
    except RenameError as error:
        return problem_report(error)
    update_current_paths(moves)
    return undo_report(moves)

def restore_selected(path, earlier):
    try:
        moves = restore(path, earlier)
    except RenameError as error:
        return problem_report(error)
    update_current_paths(moves)
    return undo_report(moves)

FONT = "JetBrainsMono Nerd Font"
STYLES = ["kebab-case", "PascalCase", "snake_case", "camelCase", "UPPERCASE", "lowercase", "Title Case", "Sentence case"]

def guide_examples(day):
    """(Style, example name) for every Style, made by the same code that renames."""
    choices = dict(date=day.strftime("%Y%m%d"), version="2", initials="KR")
    return [(style, propose_name("Project Report.pdf", Choices(style, **choices))) for style in STYLES]

GUIDE_PARTS = [
    ("Date", "yyyymmdd, yyyymm or yyyy, always first"),
    ("Name", "what the item is; shaped by the Style, and typed only for one item at a time"),
    ("Version", "v and a number; an empty box bumps it"),
    ("Initials", "who made it, kept exactly as typed"),
]

GUIDE_FOLDERS = [
    ("Top-level folders", "Sentence case", "Client projects"),
    ("Everything inside", "kebab-case", "project-report"),
]

class Panel:
    """A page of headings and two-column lines, shown in place of the form."""

    def __init__(self, parent, palette):
        self.palette = palette
        self.frame = ttk.Frame(parent, padding=(18, 14, 18, 16))
        self.frame.columnconfigure(1, weight=1)
        self.row = 0

    def heading(self, text, top=14):
        ttk.Label(self.frame, text=text.upper(), style="Heading.TLabel").grid(
            row=self.row, column=0, columnspan=2, sticky="w", pady=(top if self.row else 0, 4))
        self.row += 1

    def text(self, text, colour=None, size=9, bold=False):
        ttk.Label(self.frame, text=text, foreground=colour or self.palette["muted"],
                  font=(FONT, size, "bold") if bold else (FONT, size), wraplength=380).grid(
            row=self.row, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.row += 1

    def line(self, left, right, right_colour=None):
        ttk.Label(self.frame, text=left, foreground=self.palette["muted"], font=(FONT, 9)).grid(
            row=self.row, column=0, sticky="nw", padx=(0, 14), pady=1)
        ttk.Label(self.frame, text=right, foreground=right_colour or self.palette["foreground"],
                  font=(FONT, 9), wraplength=300, justify="left").grid(
            row=self.row, column=1, sticky="w", pady=1)
        self.row += 1

    def link(self, left, text, command):
        ttk.Label(self.frame, text=left, foreground=self.palette["muted"], font=(FONT, 9)).grid(
            row=self.row, column=0, sticky="nw", padx=(0, 14), pady=1)
        tk.Button(self.frame, text=text, command=command, relief="flat", borderwidth=0,
                  highlightthickness=0, cursor="hand2", padx=0, pady=0, font=(FONT, 9, "underline"),
                  bg=self.palette["background"], fg=self.palette["accent"],
                  activebackground=self.palette["background"],
                  activeforeground=self.palette["foreground"]).grid(row=self.row, column=1, sticky="w", pady=1)
        self.row += 1

def build_history(parent, palette, paths, on_restore, on_undo_last):
    """Every earlier name of the selected items; one item can jump to any of them."""
    originals = default_history().load()
    chains = [name_chain(path, originals) for path in paths]
    panel = Panel(parent, palette)
    panel.heading("History")
    if not any(len(chain) > 1 for chain in chains):
        panel.text("No renames recorded for these items.")
    elif len(chains) == 1:
        chain = chains[0]
        panel.text("Click an earlier name to restore it.")
        for index, name in enumerate(chain):
            label = "now" if index == 0 else "original" if index == len(chain) - 1 else ""
            if index == 0:
                panel.line(label, os.path.basename(name))
            else:
                panel.link(label, os.path.basename(name), lambda name=name: on_restore(chain[0], name))
    else:
        panel.text("Newest first. Select one item to jump further back.")
        for chain in chains:
            panel.line("", " ← ".join(os.path.basename(name) for name in chain))
    if any(len(chain) > 1 for chain in chains):
        ttk.Button(panel.frame, text="Undo last rename", style="Undo.TButton", command=on_undo_last).grid(
            row=panel.row, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        panel.row += 1
    panel.text("Escape goes back.")
    return panel.frame

def build_guide(parent, palette):
    """The naming structure, an example in every Style, and the folder rule."""
    panel = Panel(parent, palette)
    panel.heading("Naming structure")
    panel.text("DATE-NAME-VERSION-INITIALS.ext", palette["accent"], size=11, bold=True)
    panel.text("Only the Name is always there; the Style sets the separator.")
    panel.heading("Parts")
    for part, rule in GUIDE_PARTS:
        panel.line(part, rule)
    panel.heading("Every Style")
    for style, example in guide_examples(date.today()):
        panel.line(style, example, palette["accent"])
    panel.heading("Folders")
    for where, style, example in GUIDE_FOLDERS:
        panel.line(where, f"{style}  ({example})")
    return panel.frame

HELP_RENAME = [
    "Select one or more files or folders in Nautilus",
    "Press Alt+S to open this window",
    "Type a new Name if you want one (the Name box shows only when one item is selected), choose a Style, and tick a Date, Version or Initials",
    "Press Rename (or Enter); the window closes after 3 seconds",
]

HELP_UNDO = [
    "Select the renamed files or folders in Nautilus",
    "Press Alt+S",
    "Press Undo Rename to see their History",
    "One item: click any earlier name to restore it. Several: Undo last rename steps each back once",
]

HELP_KEYS = [("Enter", "Rename"), ("Escape", "close this page, or the window"), ("?", "this page")]

def build_help(parent, palette):
    """How to rename, and how to undo a rename."""
    panel = Panel(parent, palette)
    panel.heading("How to rename")
    for number, step in enumerate(HELP_RENAME, 1):
        panel.line(str(number), step)
    panel.heading("How to undo")
    for number, step in enumerate(HELP_UNDO, 1):
        panel.line(str(number), step)
    panel.heading("Keys")
    for key, action in HELP_KEYS:
        panel.line(key, action, palette["accent"])
    return panel.frame

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
    root.bind("<Escape>", lambda event: toggle_page(open_page) if open_page else root.destroy())
    root.bind("<question>", lambda event: None if isinstance(event.widget, ttk.Entry) else toggle_page("help"))

    form = ttk.Frame(root, padding=(18, 14, 18, 16))
    form.pack(fill="both", expand=True)
    # The two icons in the top right corner swap the form for a help page and back
    pages = {"guide": build_guide(root, palette), "help": build_help(root, palette)}
    icons = {}
    open_page = None

    def toggle_page(name):
        nonlocal open_page
        if name == "history" and open_page != "history":
            try:
                page = build_history(root, palette, current_paths, restore_and_show, undo_and_show)
            except RenameError as error:
                show(problem_report(error))
                return
            if "history" in pages:
                pages["history"].destroy()
            pages["history"] = page
        (pages[open_page] if open_page else form).pack_forget()
        open_page = None if open_page == name else name
        (pages[open_page] if open_page else form).pack(fill="both", expand=True)
        for page, (icon, glyph) in icons.items():
            icon.configure(text="\uf00d" if page == open_page else glyph)
            icon.lift()

    for x, page, glyph in ((-12, "guide", "\uf05a"), (-40, "help", "\uf059")):
        icon = tk.Button(root, text=glyph, command=lambda page=page: toggle_page(page), relief="flat",
                         borderwidth=0, highlightthickness=0, cursor="hand2", font=(FONT, 13),
                         padx=4, pady=0, bg=palette["background"], fg=palette["muted"],
                         activebackground=palette["background"], activeforeground=palette["accent"])
        icon.place(relx=1.0, x=x, y=6, anchor="ne")
        icons[page] = (icon, glyph)
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

    # The Name box is for one item only; several items always keep their own Names.
    # The current Name shows as a grey placeholder; leaving the box empty keeps it.
    one_item = len(current_paths) == 1
    name_entry = ttk.Entry(form, font=(FONT, 10))
    if one_item:
        heading("Name", top=0)
        name_entry.grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1

    def current_name():
        return existing_name(os.path.basename(current_paths[0])) if one_item else ""

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

    heading("Style", top=12 if one_item else 0)
    style_var = tk.StringVar(value="kebab-case")
    style_box = ttk.Combobox(form, textvariable=style_var, values=STYLES, state="readonly", font=(FONT, 10))
    style_box.grid(row=row, column=0, columnspan=2, sticky="ew")
    row += 1

    # A dropdown list opens as a window of its own, which Hyprland stretches over most of the
    # screen, so the Styles open as a list inside this window instead
    style_list = tk.Listbox(form, height=len(STYLES), activestyle="none", exportselection=False,
                            relief="flat", borderwidth=0, highlightthickness=1, font=(FONT, 10),
                            bg=palette["surface"], fg=palette["foreground"],
                            selectbackground=palette["accent"], selectforeground=palette["background"],
                            highlightbackground=palette["muted"], highlightcolor=palette["accent"])
    style_list.insert("end", *STYLES)
    style_list.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 0))
    style_list.grid_remove()
    row += 1

    def open_styles(event=None):
        if style_list.winfo_ismapped():
            return close_styles()
        current = STYLES.index(style_var.get())
        style_list.selection_clear(0, "end")
        style_list.selection_set(current)
        style_list.activate(current)
        style_list.grid()
        style_list.focus_set()
        return "break"

    def close_styles(event=None):
        style_list.grid_remove()
        style_box.focus_set()
        return "break"

    def choose_style(event=None):
        chosen = style_list.curselection()
        if chosen:
            style_var.set(STYLES[chosen[0]])
        return close_styles()

    for sequence in ("<Button-1>", "<Down>", "<space>"):
        style_box.bind(sequence, open_styles)
    style_list.bind("<ButtonRelease-1>", choose_style)
    style_list.bind("<Return>", choose_style)
    style_list.bind("<Escape>", close_styles)

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

    closing = None

    def stay_open():
        nonlocal closing
        if closing:
            root.after_cancel(closing)
            closing = None

    def show(report):
        stay_open()
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
                stay_open()
                if details.winfo_ismapped():
                    details.pack_forget()
                    show_all.configure(text=f"Show all {len(lines)}")
                else:
                    details.pack(fill="both", padx=1, pady=(0, 1))
                    show_all.configure(text="Hide list")
            show_all.configure(text=f"Show all {len(lines)}", command=toggle, bg=tint, activebackground=tint)
            show_all.pack(anchor="w", padx=10, pady=(0, 8))

    # A successful rename closes the window after 3 seconds unless Show all or Undo is used
    def rename_and_close():
        nonlocal closing
        report = rename_selected(get_choices())
        show(report)
        if report[0] == "success":
            status_text.configure(text=report[1] + "\nClosing in 3 seconds")
            closing = root.after(3000, root.destroy)

    buttons = ttk.Frame(form)
    buttons.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(16, 0))
    buttons.columnconfigure(0, weight=1)
    row += 1
    status_row = row
    ttk.Button(buttons, text="Rename", style="Rename.TButton",
               command=rename_and_close).grid(row=0, column=0, sticky="ew")
    # Undo Rename opens the History page; restoring returns to the form with the result
    def restore_and_show(path, earlier):
        toggle_page("history")
        show(restore_selected(path, earlier))

    def undo_and_show():
        toggle_page("history")
        show(undo_selected())

    ttk.Button(buttons, text="Undo Rename", style="Undo.TButton",
               command=lambda: (stay_open(), toggle_page("history"))).grid(row=1, column=0, sticky="ew", pady=(6, 0))
    root.bind("<Return>", lambda event: rename_and_close())

    root.mainloop()

if __name__ == "__main__":
    main()
