#!/usr/bin/env python3
"""Compact GTK4/Libadwaita OmniRename frontend: a thin view over RenameSession."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from omni_session import RenameSession

STYLESHEET = b"""
  .title-1 { color: #19c322; font-size: 38px; font-weight: 800; }
  .old-name { color: #20b8c2; font-size: 25px; }
  .new-name { color: #b6ef19; font-size: 39px; font-weight: 600; }
  .pill { border: 2px solid #16c62a; border-radius: 24px; padding: 10px 22px; font-size: 17px; }
  .pill-entry { border: 2px solid #16c62a; border-radius: 24px; padding: 10px 16px; min-width: 150px; }
  .dim-label { color: #aaa; }
"""


def padded_box(margin: int, spacing: int) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    box.set_margin_top(margin)
    box.set_margin_bottom(margin)
    box.set_margin_start(margin)
    box.set_margin_end(margin)
    return box


class OmniRename(Adw.Application):
    def __init__(self, paths: list[str]):
        super().__init__(application_id="io.github.omnirename.omarchy")
        self.session = RenameSession(paths)
        self.syncing = False
        self.rendered_editor = 0
        self.find_entry: Gtk.Entry | None = None

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self, title="OmniRename")
        self.win.set_default_size(820, 360)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(28)
        root.set_margin_bottom(22)
        root.set_margin_start(32)
        root.set_margin_end(32)
        self.win.set_content(root)

        title = Gtk.Label(label="OmniRename")
        title.add_css_class("title-1")
        root.append(title)

        old = Gtk.Label(label=self.session.original_name)
        old.add_css_class("old-name")
        root.append(old)

        pills = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.date_button = self.pill_button("Date", "date")
        self.prefix_entry = self.pill_entry("Prefix", 8, self.session.set_prefix)
        self.name_entry = self.pill_entry("New Name", 12, self.session.set_name)
        self.suffix_entry = self.pill_entry("Suffix", 8, self.session.set_suffix)
        self.number_button = self.pill_button("Number", "number")
        self.pill_controls = [self.date_button, self.prefix_entry, self.name_entry, self.suffix_entry, self.number_button]
        for control in self.pill_controls:
            pills.append(control)
        root.append(pills)

        self.new_preview = Gtk.Label()
        self.new_preview.add_css_class("new-name")
        root.append(self.new_preview)

        self.detail = Gtk.Label(halign=Gtk.Align.CENTER)
        self.detail.add_css_class("dim-label")
        root.append(self.detail)

        self.editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.editor.set_visible(False)
        root.append(self.editor)

        self.list = Gtk.ListBox()
        self.list.set_visible(False)
        root.append(self.list)

        self.add_css()
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.key_pressed)
        keys.connect("key-released", self.key_released)
        self.win.add_controller(keys)
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda _controller: self.run_and_sync(self.session.focus_lost))
        self.win.add_controller(focus)
        self.sync()
        self.win.present()

    def pill_button(self, label: str, editor: str) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.add_css_class("pill")
        button.connect("clicked", lambda _button: self.run_and_sync(self.session.show_editor, editor))
        button.set_visible(False)
        return button

    def pill_entry(self, placeholder: str, width: int, setter) -> Gtk.Entry:
        entry = Gtk.Entry(placeholder_text=placeholder, width_chars=width)
        entry.add_css_class("pill-entry")
        entry.connect("changed", lambda field: self.field_changed(setter, field.get_text()))
        return entry

    def add_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(STYLESHEET)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # Input

    def field_changed(self, setter, value: str):
        if not self.syncing:
            self.run_and_sync(setter, value)

    def run_and_sync(self, action, *args):
        """Run a session action, then redraw and handle its requests."""
        result = action(*args)
        self.sync()
        return result

    def key_pressed(self, _controller, keyval, code, _state):
        char = Gdk.keyval_to_unicode(keyval)
        handled = self.run_and_sync(self.session.key_down, Gdk.keyval_name(keyval) or "", chr(char) if char else "", code)
        return Gdk.EVENT_STOP if handled else Gdk.EVENT_PROPAGATE

    def key_released(self, _controller, keyval, code, _state):
        self.run_and_sync(self.session.key_up, Gdk.keyval_name(keyval) or "", code)

    # Output

    def sync(self):
        session = self.session
        self.syncing = True
        for entry, text in (
            (self.prefix_entry, session.prefix),
            (self.name_entry, session.name),
            (self.suffix_entry, session.suffix),
        ):
            if entry.get_text() != text:
                entry.set_text(text)
        self.syncing = False

        visible = session.visible_pills
        self.prefix_entry.set_visible("prefix" in visible)
        self.suffix_entry.set_visible("suffix" in visible)
        self.new_preview.set_text(session.new_name)
        self.detail.set_text(session.status)
        if session.editor_opened != self.rendered_editor:
            self.rendered_editor = session.editor_opened
            self.render_editor(session.editor)

        while (child := self.list.get_first_child()) is not None:
            self.list.remove(child)
        for row in session.rows:
            self.list.append(self.preview_row(row))
        self.list.set_visible(not session.safe)

        for request in session.take_requests():
            self.handle(request)

    def preview_row(self, row: dict) -> Gtk.Label:
        label = Gtk.Label(label=f'{row["original"]}  →  {row["renamed"]}', xalign=0)
        if row["problem"]:
            label.set_label(label.get_label() + "  —  " + row["problem"])
            label.add_css_class("error")
        return label

    def render_editor(self, key: str | None):
        self.find_entry = None
        while (child := self.editor.get_first_child()) is not None:
            self.editor.remove(child)
        self.editor.set_visible(key in ("date", "number", "replace"))
        if key == "date":
            box = Gtk.Box(spacing=8)
            for label, fmt in (("YYYYMMDD", "%Y%m%d"), ("YYYYMM", "%Y%m"), ("YYYY", "%Y")):
                check = Gtk.CheckButton(label=label)
                check.connect("toggled", lambda button, f=fmt: self.run_and_sync(self.session.set_date, f, button.get_active()))
                box.append(check)
            self.editor.append(box)
        elif key == "number":
            check = Gtk.CheckButton(label="Enable numbering")
            check.connect("toggled", lambda button: self.run_and_sync(self.session.set_number, button.get_active()))
            self.editor.append(check)
        elif key == "replace":
            box = Gtk.Box(spacing=8)
            self.find_entry = Gtk.Entry(placeholder_text="Find")
            replacement = Gtk.Entry(placeholder_text="Replace with")
            self.find_entry.connect("changed", lambda entry: self.run_and_sync(self.session.set_find, entry.get_text()))
            replacement.connect("changed", lambda entry: self.run_and_sync(self.session.set_replace, entry.get_text()))
            box.append(self.find_entry)
            box.append(replacement)
            self.editor.append(box)

    def handle(self, request: tuple):
        kind = request[0]
        if kind == "focus":
            target = {
                "prefix": self.prefix_entry,
                "name": self.name_entry,
                "suffix": self.suffix_entry,
                "find": self.find_entry,
            }.get(request[1])
            if target is not None:
                target.grab_focus()
        elif kind == "focus_step":
            self.step_focus(request[1])
        elif kind == "insert_text":
            self.insert_text(request[1])
        elif kind == "close":
            self.quit()
        elif kind == "open":
            {
                "save_preset": self.save_preset_dialog,
                "history": self.show_history,
                "shortcuts": self.show_shortcuts,
                "confirm_revert": self.confirm_revert,
            }[request[1]]()

    def step_focus(self, step: int):
        controls = [control for control in self.pill_controls if control.get_visible()]
        focused = self.win.get_focus()
        current = controls.index(focused) if focused in controls else 0
        controls[(current + step) % len(controls)].grab_focus()

    def insert_text(self, text: str):
        field = self.win.get_focus()
        if not isinstance(field, Gtk.Editable):
            return
        field.delete_selection()
        position = field.insert_text(text, field.get_position())
        field.set_position(position)

    # Dialogs

    def dialog(self, title: str, width: int, height: int = -1) -> Gtk.Window:
        return Gtk.Window(title=title, transient_for=self.win, modal=True, default_width=width, default_height=height)

    def save_preset_dialog(self):
        dialog = self.dialog("Save preset", 360)
        box = padded_box(18, 10)
        entry = Gtk.Entry(placeholder_text="Preset name")
        save = Gtk.Button(label="Save preset")
        box.append(entry)
        box.append(save)
        dialog.set_child(box)

        def commit(*_):
            if self.run_and_sync(self.session.save_preset, entry.get_text()):
                dialog.close()

        save.connect("clicked", commit)
        entry.connect("activate", commit)
        dialog.present()
        entry.grab_focus()

    def show_history(self):
        dialog = self.dialog("Rename history", 560, 360)
        box = padded_box(16, 8)
        rows = Gtk.ListBox()
        rows.set_selection_mode(Gtk.SelectionMode.SINGLE)
        entries = self.session.history_entries()
        for current, original in entries:
            rows.append(Gtk.Label(label=Path(current).name + "  →  " + Path(original).name, xalign=0))
        restore = Gtk.Button(label="Restore selected")

        def chosen(*_):
            row = rows.get_selected_row()
            if row is not None:
                self.session.restore_from_history(entries[row.get_index()][0])
                dialog.close()
                self.sync()

        restore.connect("clicked", chosen)
        box.append(rows)
        box.append(restore)
        dialog.set_child(box)
        dialog.present()

    def show_shortcuts(self):
        dialog = self.dialog("OmniRename shortcuts", 560, 540)
        box = padded_box(20, 10)
        box.set_margin_start(24)
        box.set_margin_end(24)
        title = Gtk.Label(label=f"Commands (hold {self.session.command_key})", xalign=0)
        title.add_css_class("title-2")
        box.append(title)
        label = Gtk.Label(label=self.session.cheat_sheet, xalign=0)
        label.set_selectable(True)
        label.add_css_class("monospace")
        box.append(label)
        close = Gtk.Button(label="Close", halign=Gtk.Align.END)
        close.connect("clicked", lambda *_: dialog.close())
        box.append(close)
        dialog.set_child(box)
        dialog.present()

    def confirm_revert(self):
        dialog = Adw.MessageDialog.new(
            self.win,
            "Revert selected names?",
            "This clears the current rules and restores the original filename preview.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("restore", "Restore selected")
        dialog.set_close_response("cancel")
        dialog.set_default_response("restore")
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", lambda _c, keyval, _code, _state: self.revert_key(dialog, keyval))
        dialog.add_controller(keys)
        dialog.connect("response", self.revert_response)
        dialog.present()

    def revert_key(self, dialog, keyval):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            dialog.response("restore")
            return Gdk.EVENT_STOP
        if keyval == Gdk.KEY_Escape:
            dialog.response("cancel")
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def revert_response(self, _dialog, response):
        if response == "restore":
            self.run_and_sync(self.session.revert)


if __name__ == "__main__":
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    raise SystemExit(OmniRename(payload.get("paths", [])).run())
