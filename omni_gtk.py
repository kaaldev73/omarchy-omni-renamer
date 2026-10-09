#!/usr/bin/env python3
"""Compact GTK4/Libadwaita OmniRename frontend."""
from __future__ import annotations
import json, sys, time
from datetime import date
from pathlib import Path
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk
from care_cli import execute
from care_core import RenameHistory
from care_presets import PresetStore

class OmniRename(Adw.Application):
    def __init__(self, paths):
        super().__init__(application_id="io.github.omnirename.omarchy")
        self.paths = paths
        self.leader = False
        self.sequence = ""
        self.sequence_timer = 0
        self.last_escape = 0.0
        self.preset_index = -1
        self.options = {"case_style":"kebab-case", "name":"", "prefixes":[], "suffixes":[], "counter_start":None, "counter_step":1, "counter_padding":2, "counter_position":"suffix"}
        self.prefix_before_date = False
        self.prefix_text = ""
        self.date_token = ""
        self.suffix_text = ""
        self.manual_names = None

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self, title="OmniRename")
        self.win.set_default_size(820, 360)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(28); root.set_margin_bottom(22); root.set_margin_start(32); root.set_margin_end(32)
        self.win.set_content(root)
        title = Gtk.Label(label="OmniRename"); title.add_css_class("title-1"); root.append(title)
        old = Gtk.Label(label=self.paths[0].rsplit("/",1)[-1] if self.paths else "OldName.type"); old.add_css_class("old-name"); root.append(old)
        pills = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.pill_controls = []
        self.date_button=Gtk.Button(label="Date"); self.date_button.add_css_class("pill"); self.date_button.connect("clicked",self.show_editor,"date"); self.date_button.set_visible(False); pills.append(self.date_button); self.pill_controls.append(self.date_button)
        self.prefix_entry=Gtk.Entry(placeholder_text="Prefix",width_chars=8); self.prefix_entry.add_css_class("pill-entry"); self.prefix_entry.connect("changed",lambda e:self.set_part("prefixes",e.get_text())); self.prefix_entry.set_visible(False); pills.append(self.prefix_entry); self.pill_controls.append(self.prefix_entry)
        self.name_entry=Gtk.Entry(placeholder_text="New Name",width_chars=12); self.name_entry.add_css_class("pill-entry"); self.name_entry.connect("changed",self.name_changed); pills.append(self.name_entry)
        self.pill_controls.append(self.name_entry)
        self.suffix_entry=Gtk.Entry(placeholder_text="Suffix",width_chars=8); self.suffix_entry.add_css_class("pill-entry"); self.suffix_entry.connect("changed",lambda e:self.set_part("suffixes",e.get_text())); self.suffix_entry.set_visible(False); pills.append(self.suffix_entry); self.pill_controls.append(self.suffix_entry)
        self.number_button=Gtk.Button(label="Number"); self.number_button.add_css_class("pill"); self.number_button.connect("clicked",self.show_editor,"number"); self.number_button.set_visible(False); pills.append(self.number_button); self.pill_controls.append(self.number_button)
        root.append(pills)
        self.new_preview=Gtk.Label(label="NewName.type"); self.new_preview.add_css_class("new-name"); root.append(self.new_preview)
        self.editor=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8); self.editor.set_visible(False); root.append(self.editor)
        self.detail=Gtk.Label(label="Press a pill to edit that part of the filename",halign=Gtk.Align.CENTER); self.detail.add_css_class("dim-label"); self.editor.append(self.detail)
        self.list=Gtk.ListBox(); self.list.set_visible(False); root.append(self.list)
        self.add_css()
        key=Gtk.EventControllerKey(); key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE); key.connect("key-pressed",self.key_pressed); self.win.add_controller(key)
        self.preview(); self.win.present()

    def add_css(self):
        p=Gtk.CssProvider(); p.load_from_data(b"""
          .title-1 { color: #19c322; font-size: 38px; font-weight: 800; }
          .old-name { color: #20b8c2; font-size: 25px; }
          .new-name { color: #b6ef19; font-size: 39px; font-weight: 600; }
          .pill { border: 2px solid #16c62a; border-radius: 24px; padding: 10px 22px; font-size: 17px; }
          .pill-entry { border: 2px solid #16c62a; border-radius: 24px; padding: 10px 16px; min-width: 150px; }
          .dim-label { color: #aaa; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),p,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def clear_editor(self):
        while (c:=self.editor.get_first_child()) is not None:self.editor.remove(c)
        self.editor.append(self.detail)
    def show_editor(self,_button,key):
        self.clear_editor(); self.detail.set_text({"date":"Choose YYYYMMDD, YYYYMM, or YYYY","prefix":"Prefix text appears before the name","suffix":"Suffix text appears after the name","number":"Choose sequence start, step, and digits","replace":"Find text and replace it in the filename","style":"Choose how words are separated and capitalized"}[key])
        if key=="prefix":self.prefix_entry.set_visible(True);self.prefix_entry.grab_focus()
        elif key=="suffix":self.suffix_entry.set_visible(True);self.suffix_entry.grab_focus()
        elif key=="date":
            box=Gtk.Box(spacing=8)
            for label,fmt in (("YYYYMMDD","%Y%m%d"),("YYYYMM","%Y%m"),("YYYY","%Y")):
                c=Gtk.CheckButton(label=label); c.connect("toggled",lambda x,f=fmt:self.set_date(f,x.get_active())); box.append(c)
            self.editor.prepend(box)
        elif key=="number":
            c=Gtk.CheckButton(label="Enable numbering"); c.connect("toggled",lambda x:self.set_number(x.get_active())); self.editor.prepend(c)
        elif key=="replace":
            box=Gtk.Box(spacing=8); find=Gtk.Entry(placeholder_text="Find"); replacement=Gtk.Entry(placeholder_text="Replace with")
            find.connect("changed",lambda e:self.set_replace("find",e.get_text())); replacement.connect("changed",lambda e:self.set_replace("replace",e.get_text()))
            box.append(find);box.append(replacement);self.editor.prepend(box);find.grab_focus()
        elif key=="name":self.name_entry.grab_focus()
    def set_part(self,part,value):
        if part=="prefixes":self.prefix_text=value
        else:self.suffix_text=value
        self.preview()
    def set_date(self,fmt,enabled):
        self.date_token=date.today().strftime(fmt) if enabled else ""
        self.preview()
    def set_number(self,enabled):self.options["counter_start"]=1 if enabled else None;self.preview()
    def set_replace(self,key,value):self.options[key]=value;self.preview()
    def set_style(self,value):self.options["case_style"]=value;self.manual_names=None;self.preview()
    def cycle_style(self):
        styles=["kebab-case","snake_case","PascalCase","camelCase","UPPERCASE","lowercase","Sentence case"]
        current=styles.index(self.options["case_style"]);next_style=styles[(current+1)%len(styles)]
        self.set_style(next_style);self.detail.set_text("Style: "+next_style)
    def name_changed(self,*_):self.manual_names=None;self.preview()
    def key_pressed(self,_c,keyval,_code,_state):
        char=Gdk.keyval_to_unicode(keyval); key=chr(char) if char else ""
        key_name = Gdk.keyval_name(keyval) or ""
        if not self.leader and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.rename();return Gdk.EVENT_STOP
        if not self.leader and (key == "`" or key_name in ("grave", "dead_grave")):
            self.leader=True;self.sequence="";self.detail.set_text("⌁ Command mode — press the next key");return Gdk.EVENT_STOP
        if not self.leader:
            if keyval==Gdk.KEY_Escape and time.monotonic()-self.last_escape<1.2:self.show_history();self.last_escape=0.0;return Gdk.EVENT_STOP
            return Gdk.EVENT_PROPAGATE
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            controls = [control for control in self.pill_controls if control.get_visible()]
            focused = self.win.get_focus(); current = controls.index(focused) if focused in controls else 0
            step = 1 if keyval == Gdk.KEY_Right else -1
            controls[(current + step) % len(controls)].grab_focus(); return Gdk.EVENT_STOP
        if keyval==Gdk.KEY_Escape:self.leader=False;self.sequence="";self.confirm_revert();return Gdk.EVENT_STOP
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):self.leader=False;self.rename();return Gdk.EVENT_STOP
        if key:
            self.sequence+=key.lower()
            if self.sequence_timer: GLib.source_remove(self.sequence_timer)
            self.detail.set_text("⌁ Command: ` + "+self.sequence)
            self.sequence_timer=GLib.timeout_add(1500,self.run_sequence)
            return Gdk.EVENT_STOP
        return Gdk.EVENT_STOP
    def run_sequence(self):
        cmd=self.sequence;self.sequence="";self.leader=False;self.sequence_timer=0;self.detail.set_text("Command: ` + " + cmd)
        if cmd=="1":self.show_editor(None,"prefix")
        elif cmd=="1x":self.prefix_entry.set_text("");self.prefix_entry.set_visible(False);self.options["prefixes"]=[];self.preview()
        elif cmd=="31":self.prefix_before_date=True;self.preview()
        elif cmd=="13":self.prefix_before_date=False;self.preview()
        elif cmd=="41":self.prefix_before_date=False;self.preview()
        elif cmd=="14":self.prefix_before_date=True;self.preview()
        elif cmd=="2":self.name_entry.grab_focus()
        elif cmd=="s":self.cycle_style()
        elif cmd=="3":self.show_editor(None,"suffix")
        elif cmd=="3x":self.suffix_entry.set_text("");self.suffix_entry.set_visible(False);self.options["suffixes"]=[];self.preview()
        elif cmd=="53":self.options["counter_position"]="suffix";self.preview()
        elif cmd=="35":self.options["counter_position"]="before_suffix";self.preview()
        elif cmd=="4":self.apply_date("%Y%m%d","YYYYMMDD")
        elif cmd=="4c2":self.apply_date("%Y%m","YYYYMM")
        elif cmd=="4c3":self.apply_date("%Y","YYYY")
        elif cmd=="4x":self.remove_date()
        elif cmd=="22":self.suggest_names()
        elif cmd=="22x":self.manual_names=None;self.detail.set_text("AI suggestion removed");self.preview()
        elif cmd=="2c":self.show_editor(None,"replace")
        elif cmd=="5":self.configure_number(1,1,2)
        elif cmd.startswith("5c") and len(cmd)==5 and cmd[2:].isdigit():self.configure_number(int(cmd[2]),int(cmd[3]),int(cmd[4]))
        elif cmd=="5x":self.set_number(False);self.detail.set_text("Numbering removed")
        elif cmd=="u":self.undo()
        elif cmd=="w":self.save_preset_dialog()
        elif cmd=="e":self.cycle_preset()
        elif cmd=="?":self.show_shortcuts()
        elif cmd=="return":self.rename()
        return GLib.SOURCE_REMOVE
    def apply_date(self,fmt,label):
        self.date_token=date.today().strftime(fmt);self.detail.set_text("Date enabled: "+label);self.preview()
    def remove_date(self):
        self.date_token="";self.detail.set_text("Date removed");self.preview()
    def configure_number(self,start,step,digits):
        self.options["counter_start"]=start;self.options["counter_step"]=step;self.options["counter_padding"]=max(1,digits)
        self.detail.set_text(f"Numbering: start {start}, step {step}, digits {digits}");self.preview()
    def save_preset_dialog(self):
        dialog=Gtk.Window(title="Save preset",transient_for=self.win,modal=True,default_width=360)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);box.set_margin_top(18);box.set_margin_bottom(18);box.set_margin_start(18);box.set_margin_end(18)
        entry=Gtk.Entry(placeholder_text="Preset name");save=Gtk.Button(label="Save preset");box.append(entry);box.append(save);dialog.set_child(box)
        def commit(*_):
            if entry.get_text().strip():PresetStore().save(entry.get_text(),dict(self.options));self.detail.set_text("Preset saved: "+entry.get_text().strip());dialog.close()
        save.connect("clicked",commit);entry.connect("activate",commit);dialog.present();entry.grab_focus()
    def cycle_preset(self):
        store=PresetStore();names=store.names()
        if not names:self.detail.set_text("No saved presets");return
        self.preset_index=(self.preset_index+1)%len(names);loaded=store.load(names[self.preset_index]);self.options.update(loaded)
        prefixes=list(loaded.get("prefixes",[]));self.date_token=next((x for x in prefixes if str(x).isdigit() and len(str(x)) in (4,6,8)),"");self.prefix_text=next((x for x in prefixes if x!=self.date_token),"")
        suffixes=list(loaded.get("suffixes",[]));self.suffix_text=suffixes[0] if suffixes else ""
        self.prefix_entry.set_text(self.prefix_text);self.prefix_entry.set_visible(bool(self.prefix_text));self.suffix_entry.set_text(self.suffix_text);self.suffix_entry.set_visible(bool(self.suffix_text))
        self.name_entry.set_text(str(self.options.get("name","")));self.detail.set_text("Preset: "+names[self.preset_index]);self.preview()
    def show_history(self):
        history=RenameHistory().load();dialog=Gtk.Window(title="Rename history",transient_for=self.win,modal=True,default_width=560,default_height=360)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);box.set_margin_top(16);box.set_margin_bottom(16);box.set_margin_start(16);box.set_margin_end(16);rows=Gtk.ListBox();rows.set_selection_mode(Gtk.SelectionMode.SINGLE)
        entries=list(history.items())
        for current,original in entries:rows.append(Gtk.Label(label=Path(current).name+"  →  "+Path(original).name,xalign=0))
        restore=Gtk.Button(label="Restore selected")
        def chosen(*_):
            row=rows.get_selected_row()
            if row is not None:execute("undo",{"paths":[entries[row.get_index()][0]]});dialog.close();self.preview()
        restore.connect("clicked",chosen);box.append(rows);box.append(restore);dialog.set_child(box);dialog.present()
    def show_shortcuts(self):
        dialog=Gtk.Window(title="OmniRename shortcuts",transient_for=self.win,modal=True,default_width=560,default_height=540)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);box.set_margin_top(20);box.set_margin_bottom(20);box.set_margin_start(24);box.set_margin_end(24)
        title=Gtk.Label(label="Backtick command shortcuts",xalign=0);title.add_css_class("title-2");box.append(title)
        commands=(
            "` + S     Cycle filename style\n"
            "` + 1     Add/edit Prefix       ` + 1x   Remove Prefix\n"
            "` + 2     Edit New Name          ` + 22   Suggest contextual name\n"
            "` + 22x   Remove suggestion      ` + 2c   Find and Replace\n"
            "` + 3     Add/edit Suffix       ` + 3x   Remove Suffix\n"
            "` + 4     Date YYYYMMDD          ` + 4c2  Date YYYYMM\n"
            "` + 4c3   Date YYYY             ` + 4x   Remove Date\n"
            "` + 5     Number defaults 112   ` + 5cXYZ Configure numbering\n"
            "` + 5x    Remove Number\n"
            "` + 41    Date then Prefix      ` + 14   Prefix then Date\n"
            "` + 53    Suffix then Number    ` + 35   Number then Suffix\n"
            "` + W     Save preset           ` + E    Cycle/load presets\n"
            "` + Esc   Revert; Esc again opens history\n"
            "` + ←/→   Move through visible fields\n"
            "Enter     Apply rename"
        )
        label=Gtk.Label(label=commands,xalign=0);label.set_selectable(True);label.add_css_class("monospace");box.append(label)
        close=Gtk.Button(label="Close",halign=Gtk.Align.END);close.connect("clicked",lambda *_:dialog.close());box.append(close);dialog.set_child(box);dialog.present()
    def suggest_names(self):
        result=execute("recommend",{"paths":self.paths,"allow_agent":False,"include_content":False})
        recommendations=result.get("recommendations",[])
        self.manual_names=[item["suggested_name"] for item in recommendations] if recommendations else None
        self.detail.set_text("Contextual names suggested" if self.manual_names else "No suggestion available");self.preview()
    def preview(self):
        self.options["name"]=self.name_entry.get_text()
        before=[self.prefix_text,self.date_token] if self.prefix_before_date else [self.date_token,self.prefix_text]
        self.options["prefixes"]=[value for value in before if value]
        self.options["suffixes"]=[self.suffix_text] if self.suffix_text else []
        command="preview-manual" if self.manual_names else "preview"
        payload={"paths":self.paths,"options":self.options,"names":self.manual_names or []}
        result=execute(command,payload);items=result.get("items",[]);self.new_preview.set_text(items[0]["renamed"] if items else "NewName.type")
        while (c:=self.list.get_first_child()) is not None:self.list.remove(c)
        for item in items:self.list.append(Gtk.Label(label=f'{item["original"]}  →  {item["renamed"]}',xalign=0))
    def rename(self,*_):
        if execute("apply",{"paths":self.paths,"options":self.options}).get("ok"):self.quit()
    def undo(self,*_):execute("undo",{"paths":self.paths});self.preview()
    def restore_original(self):
        self.name_entry.set_text("")
        self.prefix_entry.set_text(""); self.suffix_entry.set_text("")
        self.prefix_entry.set_visible(False); self.suffix_entry.set_visible(False); self.date_button.set_visible(False); self.number_button.set_visible(False)
        self.options.update({"name":"","prefixes":[],"suffixes":[],"counter_start":None,"find":"","replace":""})
        self.prefix_text="";self.date_token="";self.suffix_text=""
        self.manual_names=None
        self.preview()
    def confirm_revert(self):
        dialog=Adw.MessageDialog.new(self.win,"Revert selected names?","This clears the current rules and restores the original filename preview.")
        dialog.add_response("cancel","Cancel");dialog.add_response("restore","Restore selected")
        dialog.set_close_response("cancel");dialog.set_default_response("restore")
        dialog.set_response_appearance("restore",Adw.ResponseAppearance.DESTRUCTIVE)
        keys=Gtk.EventControllerKey();keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed",lambda _c,keyval,_code,_state:self.revert_key(dialog,keyval));dialog.add_controller(keys)
        dialog.connect("response",self.revert_response);dialog.present()
    def revert_key(self,dialog,keyval):
        if keyval in (Gdk.KEY_Return,Gdk.KEY_KP_Enter):dialog.response("restore");return Gdk.EVENT_STOP
        if keyval==Gdk.KEY_Escape:dialog.response("cancel");return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE
    def revert_response(self,_dialog,response):
        if response=="restore":
            self.restore_original();self.detail.set_text("Original name restored")

if __name__=="__main__":
    payload=json.loads(sys.argv[1]) if len(sys.argv)>1 else {};raise SystemExit(OmniRename(payload.get("paths",[])).run())
