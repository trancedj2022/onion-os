#!/usr/bin/env python3
import configparser
import datetime
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango, PangoCairo

HOME = Path.home()
STATE_DIR = HOME / ".config" / "ming-os"
LAYOUT_PATH = STATE_DIR / "desktop-layout.json"
READY_MARKER = HOME / ".cache" / "ming-os" / "ming-phone-desktop.ready"
DESKTOP_DIR = HOME / "Desktop"
APP_DIRS = [DESKTOP_DIR, Path("/usr/share/applications"), HOME / ".local/share/applications"]
CORE_NAMES = {
    "ming-settings.desktop",
    "ming-files.desktop",
    "ming-app-library.desktop",
    "ming-update.desktop",
    "ming-terminal.desktop",
    "firefox-esr.desktop",
    "spark-store.desktop",
    "ming-disk-hub.desktop",
    "ming-wechat.desktop",
    "wps-office.desktop",
    "garlic-claw.desktop",
}
DESKTOP_ORDER = {name: idx for idx, name in enumerate([
    "ming-settings.desktop",
    "ming-app-library.desktop",
    "ming-files.desktop",
    "firefox-esr.desktop",
    "ming-wechat.desktop",
    "wps-office.desktop",
    "spark-store.desktop",
    "ming-update.desktop",
    "ming-disk-hub.desktop",
    "garlic-claw.desktop",
    "ming-terminal.desktop",
])}
CORE_FALLBACKS = {
    "firefox-esr.desktop": ["firefox.desktop"],
    "wps-office.desktop": ["ming-install-wps.desktop"],
    "spark-store.desktop": ["ming-install-spark-store.desktop"],
}
CORE_GENERATED = {
    "ming-settings.desktop": ("Ming 设置", "ming-control-center", "ming-control-center", "Settings;System;"),
    "ming-app-library.desktop": ("Ming 应用库", "ming-app-library", "ming-app-library", "Utility;System;"),
    "ming-files.desktop": ("文件", "ming-files", "files-icon", "System;FileManager;"),
    "ming-update.desktop": ("系统更新", "ming-update-gui", "ming-update-icon", "System;Settings;"),
    "ming-terminal.desktop": ("Ming 终端", "ming-terminal", "ming-terminal", "System;TerminalEmulator;"),
    "ming-disk-hub.desktop": ("所有磁盘", "ming-disk-hub --open", "drive-harddisk", "System;FileManager;"),
    "garlic-claw.desktop": ("Garlic Claw", "xfce4-terminal --hide-menubar --title=\"Garlic Claw\" -e garlic-claw", "utilities-terminal", "Utility;"),
}
LOG_PATH = HOME / ".cache" / "ming-os" / "ming-phone-desktop.log"
LAYOUT_VERSION = 5
GRID_W = 86
GRID_H = 98
PAD_X = 34
PAD_Y = 92
DROP_DISTANCE = 50
ICON_SIZE = 34
TILE_W = 76
TILE_H = 88
CLOCK_MARGIN_X = 26
CLOCK_MARGIN_Y = 20
WALLPAPER_PATHS = [
    Path("/usr/share/backgrounds/ming-os/default.png"),
    Path("/usr/share/backgrounds/ming-os/default-1366x768.png"),
    Path("/usr/share/backgrounds/ming-os/default.svg"),
]

CSS = b"""
window.ming-desktop {
  background-color: #EFF7F2;
}
.tile {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.34);
  border: 1px solid rgba(255, 255, 255, 0.54);
  box-shadow: 0 8px 22px rgba(21, 68, 56, 0.08), inset 0 1px 0 rgba(255,255,255,0.58);
  padding: 7px 6px 6px;
  color: #1D2421;
}
.tile:hover, .tile.dragging {
  background: rgba(255, 255, 255, 0.60);
  border-color: rgba(47, 138, 125, 0.24);
  box-shadow: 0 12px 28px rgba(21, 68, 56, 0.13), inset 0 1px 0 rgba(255,255,255,0.70);
}
.folder {
  background: rgba(232, 248, 242, 0.64);
  border-color: rgba(47, 138, 125, 0.24);
}
.label {
  color: #1D2421;
  font-size: 10.5px;
  font-weight: 700;
  text-shadow: 0 1px 0 rgba(255,255,255,0.82);
}
.folder-title {
  color: #1D2421;
  font-size: 18px;
  font-weight: 700;
}
.folder-panel {
  background: rgba(251, 253, 251, 0.98);
  border: 1px solid rgba(31, 98, 84, 0.10);
  border-radius: 12px;
  padding: 18px;
}
.folder-action {
  border-radius: 9px;
  padding: 7px 10px;
}
.clock-widget {
  border-radius: 14px;
  padding: 9px 13px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.70);
  box-shadow: 0 12px 34px rgba(21, 68, 56, 0.12), inset 0 1px 0 rgba(255,255,255,0.75);
}
.clock-time {
  font-size: 26px;
  font-weight: 800;
  color: #17231F;
}
.clock-date {
  font-size: 11.5px;
  font-weight: 700;
  color: #2D695C;
}
.clock-subdate {
  font-size: 10px;
  font-weight: 700;
  color: #6A7670;
}
"""


def log(msg):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(datetime.datetime.now().strftime("[%F %T] ") + msg + "\n")
    except Exception:
        pass


def app_id(path):
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]


def read_app(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except Exception:
        return None
    if not parser.has_section("Desktop Entry"):
        return None
    entry = parser["Desktop Entry"]
    if entry.get("Type", "Application") != "Application":
        return None
    if entry.get("NoDisplay", "").lower() == "true" or entry.get("Hidden", "").lower() == "true":
        return None
    exec_line = entry.get("Exec", "")
    if not exec_line:
        return None
    return {
        "id": app_id(path),
        "type": "app",
        "path": str(path),
        "basename": Path(path).name,
        "name": entry.get("Name[zh_CN]") or entry.get("Name") or Path(path).stem,
        "icon": entry.get("Icon") or "application-x-executable",
        "categories": entry.get("Categories", ""),
    }


def launch_item(item):
    path = item.get("path")
    if not path:
        return False
    try:
        info = Gio.DesktopAppInfo.new_from_filename(path)
        if info and info.launch([], None):
            return True
    except Exception:
        pass
    try:
        subprocess.Popen(["gtk-launch", Path(path).stem])
        return True
    except Exception:
        pass
    try:
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read(path, encoding="utf-8")
        exec_line = parser["Desktop Entry"].get("Exec", "")
        argv = [part for part in shlex.split(exec_line) if not part.startswith("%")]
        if argv:
            subprocess.Popen(argv)
            return True
    except Exception as exc:
        log(f"exec fallback failed for {path}: {exc}")
    return False


def write_generated_core_launcher(basename):
    data = CORE_GENERATED.get(basename)
    if not data:
        return None
    name, exec_cmd, icon, categories = data
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    path = DESKTOP_DIR / basename
    if not path.exists():
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Name[zh_CN]={name}\n"
            f"Exec={exec_cmd}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            f"Categories={categories}\n"
            "StartupNotify=true\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
    return path


def add_app_from_path(apps_by_basename, path, default_only=False):
    item = read_app(path)
    if not item:
        return False
    basename = item["basename"]
    if default_only and basename not in CORE_NAMES:
        return False
    if basename in apps_by_basename:
        return False
    apps_by_basename[basename] = item
    return True


def add_core_app(apps_by_basename, basename):
    candidates = [DESKTOP_DIR / basename, Path("/usr/share/applications") / basename]
    candidates.extend(Path("/usr/share/applications") / alt for alt in CORE_FALLBACKS.get(basename, []))
    for candidate in candidates:
        if add_app_from_path(apps_by_basename, candidate):
            return True
    generated = write_generated_core_launcher(basename)
    if generated:
        return add_app_from_path(apps_by_basename, generated)
    return False


def load_apps(default_only=False):
    apps_by_basename = {}
    if default_only:
        for basename in sorted(CORE_NAMES, key=lambda name: DESKTOP_ORDER.get(name, 999)):
            add_core_app(apps_by_basename, basename)
    for directory in APP_DIRS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.desktop")):
            add_app_from_path(apps_by_basename, path, default_only=default_only)
    apps = list(apps_by_basename.values())
    apps.sort(key=lambda item: (DESKTOP_ORDER.get(item["basename"], 999), item["name"].lower()))
    return apps


def empty_layout():
    return {"version": LAYOUT_VERSION, "items": []}


def load_layout():
    try:
        data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except Exception:
        pass
    return empty_layout()


def save_layout(layout):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LAYOUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LAYOUT_PATH)


def next_position(index, width=1366):
    cols = min(6, max(3, int((width - PAD_X * 2) / GRID_W)))
    row = index // cols
    col = index % cols
    return PAD_X + col * GRID_W, PAD_Y + row * GRID_H


def sync_layout(width=1366):
    apps = load_apps(default_only=True)
    layout = load_layout()
    if layout.get("version") != LAYOUT_VERSION:
        layout = empty_layout()
    items = []
    known = set()
    for item in layout.get("items", []):
        if item.get("type") == "folder":
            if item.get("pinned"):
                items.append(item)
                known.update(item.get("children", []))
        elif item.get("path"):
            basename = Path(item["path"]).name
            if basename in CORE_NAMES or item.get("pinned"):
                items.append(item)
                known.add(item["path"])
    index = len(items)
    for app in apps:
        if app["path"] in known:
            continue
        app["x"], app["y"] = next_position(index, width)
        app["pinned"] = False
        items.append(app)
        index += 1
    layout["version"] = LAYOUT_VERSION
    layout["items"] = items
    if items:
        save_layout(layout)
        sync_files(layout)
    return layout


def safe_name(name):
    cleaned = "".join("-" if ch in '/\\:*?"<>|' else ch for ch in name).strip()
    return cleaned or "应用"


def copy_desktop(path, target_dir, name=None, preserve_basename=False):
    src = Path(path)
    if not src.is_file():
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = src.name if preserve_basename else f"{safe_name(name or src.stem)}.desktop"
    target = target_dir / target_name
    try:
        if src.resolve() == target.resolve():
            target.chmod(0o755)
            return target
        shutil.copy2(src, target)
        target.chmod(0o755)
        return target
    except Exception:
        return None


def sync_files(layout):
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    folders_seen = set()
    launchers_seen = set()
    allowed_dirs = {"Apps", "System", "Internet", "Office", "Media", "Games", "Tools", "Common"}
    for item in layout.get("items", []):
        if item.get("type") == "folder":
            folder_dir = DESKTOP_DIR / safe_name(item.get("name", "folder"))
            folders_seen.add(folder_dir)
            folder_dir.mkdir(parents=True, exist_ok=True)
            for child_path in item.get("children", []):
                child = read_app(child_path)
                if child:
                    copy_desktop(child_path, folder_dir, child["name"])
        elif item.get("path") and (Path(item["path"]).name in CORE_NAMES or item.get("pinned")):
            is_core = Path(item["path"]).name in CORE_NAMES
            copied = copy_desktop(item["path"], DESKTOP_DIR, item.get("name"), preserve_basename=is_core)
            if copied:
                launchers_seen.add(copied)
    for old in DESKTOP_DIR.glob("*.desktop"):
        if old not in launchers_seen:
            try:
                old.unlink()
            except Exception:
                pass
    for old in DESKTOP_DIR.iterdir() if DESKTOP_DIR.exists() else []:
        if old.is_dir() and old.name not in allowed_dirs and old not in folders_seen:
            try:
                if not any(old.iterdir()):
                    old.rmdir()
            except Exception:
                pass


def command_add(path, folder=False):
    item = read_app(path)
    if not item:
        return 1
    layout = sync_layout()
    items = layout["items"]
    if any(x.get("path") == item["path"] for x in items):
        return 0
    if folder:
        folder_item = next((x for x in items if x.get("type") == "folder"), None)
        if not folder_item:
            folder_item = {"id": "folder-" + app_id(item["path"]), "type": "folder", "name": "文件夹", "children": [], "x": PAD_X, "y": PAD_Y, "pinned": True}
            items.insert(0, folder_item)
        folder_item["pinned"] = True
        if item["path"] not in folder_item["children"]:
            folder_item["children"].append(item["path"])
    else:
        item["x"], item["y"] = next_position(len(items))
        item["pinned"] = True
        items.append(item)
    save_layout(layout)
    sync_files(layout)
    return 0


class DesktopTile(Gtk.EventBox):
    def __init__(self, desktop, item):
        super().__init__()
        self.desktop = desktop
        self.item = item
        self.dragging = False
        self.offset = (0, 0)
        self.set_size_request(TILE_W, TILE_H)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("button-press-event", self.on_press)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("button-release-event", self.on_release)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_size_request(70, 82)
        box.get_style_context().add_class("tile")
        if item.get("type") == "folder":
            box.get_style_context().add_class("folder")
            image = Gtk.Image.new_from_icon_name("folder", Gtk.IconSize.DIALOG)
        else:
            image = Gtk.Image.new_from_icon_name(item.get("icon") or "application-x-executable", Gtk.IconSize.DIALOG)
        image.set_pixel_size(ICON_SIZE)
        label = Gtk.Label(label=item.get("name", "应用"))
        label.get_style_context().add_class("label")
        label.set_justify(Gtk.Justification.CENTER)
        label.set_line_wrap(True)
        label.set_lines(2)
        label.set_max_width_chars(6)
        box.pack_start(image, True, True, 0)
        box.pack_start(label, False, False, 0)
        self.box = box
        self.add(box)
        self.show_all()

    def on_press(self, _widget, event):
        if event.button == 3:
            self.desktop.show_context_menu(self.item, event)
            return True
        if event.button != 1:
            return False
        self.dragging = False
        self.offset = (event.x, event.y)
        return True

    def on_motion(self, _widget, event):
        if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
            return False
        self.dragging = True
        self.box.get_style_context().add_class("dragging")
        root_x, root_y = event.x_root, event.y_root
        win_x, win_y = self.desktop.window_origin
        x = int(root_x - win_x - self.offset[0])
        y = int(root_y - win_y - self.offset[1])
        self.desktop.fixed.move(self, max(8, x), max(8, y))
        return True

    def on_release(self, _widget, event):
        self.box.get_style_context().remove_class("dragging")
        if self.dragging and getattr(event, "button", 0) == 1:
            root_x, root_y = event.x_root, event.y_root
            win_x, win_y = self.desktop.window_origin
            x = int(root_x - win_x - self.offset[0])
            y = int(root_y - win_y - self.offset[1])
            self.desktop.finish_drag(self.item, max(8, x), max(8, y))
        elif getattr(event, "button", 0) == 1:
            self.desktop.open_item(self.item)
        self.dragging = False
        return True


class ClockWidget(Gtk.EventBox):
    def __init__(self):
        super().__init__()
        self.set_visible_window(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.get_style_context().add_class("clock-widget")
        box.set_halign(Gtk.Align.END)

        self.time_label = Gtk.Label()
        self.time_label.get_style_context().add_class("clock-time")
        self.time_label.set_halign(Gtk.Align.END)

        self.date_label = Gtk.Label()
        self.date_label.get_style_context().add_class("clock-date")
        self.date_label.set_halign(Gtk.Align.END)

        self.subdate_label = Gtk.Label()
        self.subdate_label.get_style_context().add_class("clock-subdate")
        self.subdate_label.set_halign(Gtk.Align.END)

        box.pack_start(self.time_label, False, False, 0)
        box.pack_start(self.date_label, False, False, 0)
        box.pack_start(self.subdate_label, False, False, 0)
        self.add(box)
        self.refresh()
        GLib.timeout_add_seconds(30, self.refresh)

    def refresh(self):
        now = datetime.datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        self.time_label.set_text(now.strftime("%H:%M"))
        self.date_label.set_text(weekdays[now.weekday()])
        self.subdate_label.set_text(now.strftime("%m/%d"))
        return True


class WallpaperCanvas(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.pixbuf = self.load_wallpaper()
        self.connect("draw", self.on_draw)

    def load_wallpaper(self):
        for path in WALLPAPER_PATHS:
            if path.exists():
                try:
                    return GdkPixbuf.Pixbuf.new_from_file(str(path))
                except Exception:
                    pass
        return None

    def on_draw(self, widget, cr):
        width = max(1, widget.get_allocated_width())
        height = max(1, widget.get_allocated_height())
        if not self.pixbuf:
            cr.set_source_rgb(0.937, 0.969, 0.949)
            cr.rectangle(0, 0, width, height)
            cr.fill()
            return False
        src_w = self.pixbuf.get_width()
        src_h = self.pixbuf.get_height()
        scale = max(width / src_w, height / src_h)
        draw_w = int(src_w * scale)
        draw_h = int(src_h * scale)
        scaled = self.pixbuf.scale_simple(draw_w, draw_h, GdkPixbuf.InterpType.BILINEAR)
        x = int((width - draw_w) / 2)
        y = int((height - draw_h) / 2)
        Gdk.cairo_set_source_pixbuf(cr, scaled, x, y)
        cr.paint()
        cr.set_source_rgba(1, 1, 1, 0.10)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        return False


class PhoneDesktop(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ming Desktop")
        try:
            READY_MARKER.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        self.set_name("ming-desktop-window")
        self.get_style_context().add_class("ming-desktop")
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        try:
            self.set_keep_below(True)
            self.stick()
        except Exception:
            pass
        screen = self.get_screen()
        screen_w = max(320, screen.get_width())
        screen_h = max(240, screen.get_height())
        self.set_default_size(screen_w, screen_h)
        self.resize(screen_w, screen_h)
        self.move(0, 0)
        self.fullscreen()
        self.connect("destroy", Gtk.main_quit)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, 700)

        self.wallpaper = WallpaperCanvas()
        self.fixed = Gtk.Fixed()
        self.fixed.set_hexpand(True)
        self.fixed.set_vexpand(True)
        self.fixed.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.fixed.connect("draw", self.draw_background)
        self.fixed.connect("button-release-event", self.on_fixed_button_release)
        self.add(self.fixed)
        self.tiles = {}
        self.clock = ClockWidget()
        self.connect("map-event", lambda *_args: self.enforce_desktop_layer())
        self.connect("size-allocate", lambda *_args: self.place_clock())
        self.layout = sync_layout(screen_w)
        self.render()
        GLib.timeout_add_seconds(2, self.mark_ready)
        GLib.timeout_add_seconds(4, self.enforce_desktop_layer)
        GLib.timeout_add_seconds(8, self.refresh_from_apps)

    @property
    def window_origin(self):
        window = self.get_window()
        if window:
            try:
                ok, x, y = window.get_origin()
                if ok:
                    return x, y
            except Exception:
                pass
        return 0, 0

    def mark_ready(self):
        try:
            READY_MARKER.parent.mkdir(parents=True, exist_ok=True)
            READY_MARKER.write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
        except Exception:
            pass
        return False

    def enforce_desktop_layer(self):
        try:
            self.set_keep_below(True)
            self.stick()
        except Exception:
            pass
        try:
            subprocess.run(
                ["wmctrl", "-r", "Ming Desktop", "-b", "add,below,sticky,skip_taskbar,skip_pager"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
        except Exception:
            pass
        return True

    def draw_background(self, widget, cr):
        self.wallpaper.on_draw(widget, cr)
        self.draw_icon_fallback(cr)
        return False

    def rounded_rect(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        cr.arc(x + r, y + r, r, 3.1416, 4.7124)
        cr.close_path()

    def draw_icon_fallback(self, cr):
        icon_theme = Gtk.IconTheme.get_default()
        for item in self.layout.get("items", []):
            if item.get("type") != "app":
                continue
            x = int(item.get("x", PAD_X))
            y = int(item.get("y", PAD_Y))
            self.rounded_rect(cr, x, y, 70, 82, 12)
            cr.set_source_rgba(1, 1, 1, 0.48)
            cr.fill_preserve()
            cr.set_source_rgba(0.18, 0.54, 0.49, 0.18)
            cr.set_line_width(1)
            cr.stroke()
            icon_name = item.get("icon") or "application-x-executable"
            try:
                pixbuf = icon_theme.load_icon(icon_name, ICON_SIZE, Gtk.IconLookupFlags.FORCE_SIZE)
            except Exception:
                pixbuf = None
            if pixbuf:
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, x + 18, y + 7)
                cr.paint()
            layout = PangoCairo.create_layout(cr)
            layout.set_text(item.get("name", "应用"), -1)
            layout.set_width(70 * Pango.SCALE)
            layout.set_height(30 * Pango.SCALE)
            layout.set_alignment(Pango.Alignment.CENTER)
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_font_description(Pango.FontDescription("Sans Bold 10"))
            cr.set_source_rgba(0.11, 0.15, 0.13, 0.96)
            cr.move_to(x, y + 48)
            PangoCairo.show_layout(cr, layout)

    def item_at(self, x, y):
        for item in reversed(self.layout.get("items", [])):
            ix = int(item.get("x", PAD_X))
            iy = int(item.get("y", PAD_Y))
            if ix <= x <= ix + TILE_W and iy <= y <= iy + TILE_H:
                return item
        return None

    def on_fixed_button_release(self, _widget, event):
        item = self.item_at(event.x, event.y)
        if not item:
            return False
        if getattr(event, "button", 0) == 3:
            self.show_context_menu(item, event)
            return True
        if getattr(event, "button", 0) == 1:
            self.open_item(item)
            return True
        return False

    def render(self):
        screen_w = max(320, self.get_screen().get_width())
        screen_h = max(240, self.get_screen().get_height())
        self.fixed.set_size_request(screen_w, screen_h)
        for child in self.fixed.get_children():
            self.fixed.remove(child)
        self.tiles = {}
        log(f"render desktop items={len(self.layout.get('items', []))} screen={screen_w}x{screen_h}")
        for item in self.layout.get("items", []):
            tile = DesktopTile(self, item)
            self.tiles[item["id"]] = tile
            self.fixed.put(tile, int(item.get("x", PAD_X)), int(item.get("y", PAD_Y)))
            tile.show_all()
        self.place_clock()
        self.show_all()
        self.enforce_desktop_layer()

    def place_clock(self):
        screen_w = max(320, self.get_screen().get_width())
        widget_w = 158 if screen_w >= 900 else 132
        self.clock.set_size_request(widget_w, 72)
        x = max(CLOCK_MARGIN_X, screen_w - widget_w - CLOCK_MARGIN_X)
        y = CLOCK_MARGIN_Y
        if self.clock.get_parent() is None:
            self.fixed.put(self.clock, x, y)
        else:
            self.fixed.move(self.clock, x, y)

    def refresh_from_apps(self):
        self.layout = sync_layout(self.get_screen().get_width())
        self.render()
        return True

    def find_drop_target(self, source, x, y):
        best = None
        best_distance = DROP_DISTANCE
        for item in self.layout.get("items", []):
            if item.get("id") == source.get("id"):
                continue
            dx = int(item.get("x", 0)) - x
            dy = int(item.get("y", 0)) - y
            distance = (dx * dx + dy * dy) ** 0.5
            if distance < best_distance:
                best = item
                best_distance = distance
        return best

    def finish_drag(self, item, x, y):
        target = self.find_drop_target(item, x, y)
        if target and item.get("type") == "app":
            self.create_or_merge_folder(item, target)
        else:
            item["x"] = x
            item["y"] = y
        save_layout(self.layout)
        sync_files(self.layout)
        self.render()

    def create_or_merge_folder(self, source, target):
        items = self.layout.get("items", [])
        if target.get("type") == "folder":
            if source.get("path") not in target.setdefault("children", []):
                target["children"].append(source.get("path"))
            items[:] = [x for x in items if x.get("id") != source.get("id")]
            return
        if target.get("type") != "app":
            return
        folder = {
            "id": "folder-" + app_id(source.get("path", "") + target.get("path", "")),
            "type": "folder",
            "name": "文件夹",
            "children": [target.get("path"), source.get("path")],
            "x": target.get("x", PAD_X),
            "y": target.get("y", PAD_Y),
        }
        items[:] = [x for x in items if x.get("id") not in {source.get("id"), target.get("id")}]
        items.append(folder)

    def open_item(self, item):
        if item.get("type") == "folder":
            self.show_folder(item)
            return
        if not launch_item(item):
            log(f"no launch method worked for {item.get('path')}")

    def show_folder(self, folder):
        dialog = Gtk.Dialog(title=folder.get("name", "文件夹"), transient_for=self, flags=0)
        dialog.set_default_size(520, 420)
        area = dialog.get_content_area()
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        panel.get_style_context().add_class("folder-panel")
        panel.set_border_width(16)
        area.add(panel)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Entry()
        title.set_text(folder.get("name", "文件夹"))
        title.get_style_context().add_class("folder-title")
        rename = Gtk.Button(label="改名")
        rename.get_style_context().add_class("folder-action")
        rename.connect("clicked", lambda _b: self.rename_folder(folder, title.get_text(), dialog))
        header.pack_start(title, True, True, 0)
        header.pack_start(rename, False, False, 0)
        panel.pack_start(header, False, False, 0)
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(4)
        flow.set_row_spacing(10)
        flow.set_column_spacing(10)
        panel.pack_start(flow, True, True, 0)
        for child_path in list(folder.get("children", [])):
            child = read_app(child_path)
            if not child:
                continue
            button = Gtk.Button()
            button.set_size_request(104, 94)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            child_image = Gtk.Image.new_from_icon_name(child.get("icon"), Gtk.IconSize.DIALOG)
            child_image.set_pixel_size(ICON_SIZE)
            box.pack_start(child_image, True, True, 0)
            label = Gtk.Label(label=child.get("name"))
            label.set_line_wrap(True)
            label.set_max_width_chars(8)
            box.pack_start(label, False, False, 0)
            button.add(box)
            button.connect("clicked", lambda _b, app=child: self.open_item(app))
            button.connect("button-press-event", lambda w, e, app=child, f=folder, d=dialog: self.child_menu(w, e, app, f, d))
            flow.add(button)
        close = Gtk.Button(label="关闭")
        close.connect("clicked", lambda _b: dialog.destroy())
        panel.pack_start(close, False, False, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def child_menu(self, widget, event, app, folder, dialog):
        if getattr(event, "button", 0) != 3:
            return False
        menu = Gtk.Menu()
        move = Gtk.MenuItem(label="移到桌面")
        move.connect("activate", lambda _i: self.move_child_to_desktop(app, folder, dialog))
        menu.append(move)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def rename_folder(self, folder, name, dialog):
        folder["name"] = safe_name(name)
        save_layout(self.layout)
        sync_files(self.layout)
        dialog.destroy()
        self.render()

    def move_child_to_desktop(self, app, folder, dialog):
        folder["children"] = [x for x in folder.get("children", []) if x != app.get("path")]
        app["x"], app["y"] = next_position(len(self.layout.get("items", [])), self.get_screen().get_width())
        self.layout["items"].append(app)
        if not folder["children"]:
            self.layout["items"] = [x for x in self.layout["items"] if x.get("id") != folder.get("id")]
        save_layout(self.layout)
        sync_files(self.layout)
        dialog.destroy()
        self.render()

    def show_context_menu(self, item, event):
        menu = Gtk.Menu()
        open_item = Gtk.MenuItem(label="打开")
        open_item.connect("activate", lambda _i: self.open_item(item))
        menu.append(open_item)
        if item.get("type") == "folder":
            rename = Gtk.MenuItem(label="重命名文件夹")
            rename.connect("activate", lambda _i: self.show_folder(item))
            menu.append(rename)
            if not item.get("children"):
                delete = Gtk.MenuItem(label="删除空文件夹")
                delete.connect("activate", lambda _i: self.delete_item(item))
                menu.append(delete)
        else:
            remove = Gtk.MenuItem(label="从桌面移除")
            remove.connect("activate", lambda _i: self.delete_item(item))
            menu.append(remove)
        menu.show_all()
        menu.popup_at_pointer(event)

    def delete_item(self, item):
        self.layout["items"] = [x for x in self.layout.get("items", []) if x.get("id") != item.get("id")]
        save_layout(self.layout)
        sync_files(self.layout)
        self.render()


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--add":
        raise SystemExit(command_add(sys.argv[2], folder=False))
    if len(sys.argv) >= 3 and sys.argv[1] == "--add-to-folder":
        raise SystemExit(command_add(sys.argv[2], folder=True))
    if len(sys.argv) >= 2 and sys.argv[1] == "--sync":
        sync_layout()
        return
    PhoneDesktop()
    Gtk.main()


if __name__ == "__main__":
    main()
