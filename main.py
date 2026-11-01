"""Лаунчер Minecraft — CustomTkinter UI, профілі, RAM і менеджер модів."""
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import auth
import config
import game
import storage
import updater
from errors import friendly_error

BG = "#080b16"
SIDEBAR = "#0d1020"
PANEL = "#11172a"
PANEL_ALT = "#1a2340"
BORDER = "#283252"
FG = "#f3f5ff"
MUTED = "#929dbb"
ACCENT = "#9b7bff"
ACCENT_HOVER = "#8060ef"
ACCENT_SOFT = "#211b43"
GREEN = ACCENT
GREEN_HOVER = ACCENT_HOVER
RED = "#ff6b8a"


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def F(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.busy = False
        self.settings = storage.load_settings()
        self.profiles = storage.profiles_from_settings(self.settings)
        self.active_profile = self.settings.get("active_profile", "За замовчуванням")
        if self.active_profile not in self.profiles:
            self.active_profile = next(iter(self.profiles))
        profile = self.profiles[self.active_profile]
        self.version_var = ctk.StringVar(value=profile.get("version", self.settings.get("version", config.DEFAULT_VERSION)))
        self.dir_var = ctk.StringVar(value=profile.get("game_dir", self.settings.get("game_dir", config.DEFAULT_GAME_DIR)))
        self.ram_var = ctk.IntVar(value=profile.get("ram_gb", self.settings.get("ram_gb", 4)))
        self.snap_var = ctk.BooleanVar(value=bool(self.settings.get("show_snapshots", False)))
        self.mode_var = ctk.StringVar(value=self.settings.get("auth_mode", "microsoft"))
        self.name_var = ctk.StringVar(value=self.settings.get("offline_name", "Player"))

        root.title(config.APP_NAME)
        root.after(250, self._set_icon)
        root.geometry("1120x760")
        root.minsize(960, 680)
        root.configure(fg_color=BG)
        self._build_ui()
        self._refresh_account_label()
        self._refresh_mods()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(100, self._poll)
        self._load_versions()
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _set_icon(self):
        try: self.root.iconbitmap(resource_path("assets/icon.ico"))
        except Exception: pass

    def _build_ui(self):
        # Clean, editorial layout with a compact navigation rail.
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self.root, width=248, corner_radius=0, fg_color=SIDEBAR,
                                    border_width=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(28, 34))
        self._logo_img = None
        try:
            from PIL import Image
            self._logo_img = ctk.CTkImage(Image.open(resource_path("assets/icon.png")), size=(46, 46))
        except Exception:
            pass
        if self._logo_img:
            ctk.CTkLabel(brand, text="", image=self._logo_img).pack(side="left")
        else:
            ctk.CTkLabel(brand, text="N", width=46, height=46, corner_radius=14,
                         fg_color=ACCENT, text_color="#090b17", font=F(24, "bold")).pack(side="left")
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(names, text="NOVA", font=F(22, "bold"), text_color=FG).pack(anchor="w")
        ctk.CTkLabel(names, text="CRAFT  /  JAVA", font=F(10, "bold"), text_color=ACCENT).pack(anchor="w", pady=(1, 0))

        ctk.CTkLabel(self.sidebar, text="WORKSPACE", text_color="#596486",
                     font=F(10, "bold")).pack(anchor="w", padx=24, pady=(0, 10))
        self.nav = {}
        for icon, label, page in [
            ("⌂", "Головна", "home"),
            ("▦", "Профілі", "profiles"),
            ("◇", "Моди", "mods"),
            ("⚙", "Налаштування", "settings"),
        ]:
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {icon}     {label}", anchor="w", height=48,
                corner_radius=13, font=F(14, "bold"), fg_color="transparent",
                hover_color="#1b2140", text_color=MUTED,
                border_spacing=12, command=lambda p=page: self._show_page(p))
            btn.pack(fill="x", padx=13, pady=4)
            self.nav[page] = btn

        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(expand=True, fill="both")
        chip = ctk.CTkFrame(self.sidebar, fg_color="#141a30", corner_radius=16,
                            border_width=1, border_color=BORDER)
        chip.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(chip, text="ACCOUNT STATUS", text_color="#657198",
                     font=F(9, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        self.side_account = ctk.CTkLabel(chip, text="Офлайн", text_color=FG,
                    font=F(12, "bold"), wraplength=190, justify="left", anchor="w")
        self.side_account.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(self.sidebar, text=f"{config.APP_NAME}  ·  v{config.LAUNCHER_VERSION}",
                     text_color="#59617e", font=F(10)).pack(padx=20, pady=(0, 18), anchor="w")

        self.content = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=34, pady=28)
        self.content.grid_columnconfigure(0, weight=1)
        self._show_page("home")

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.content.grid_rowconfigure(3, weight=0)

    def _show_page(self, page):
        self.page = page
        self._clear_content()
        for key, btn in getattr(self, "nav", {}).items():
            on = key == page
            btn.configure(fg_color=ACCENT_SOFT if on else "transparent", text_color=FG if on else MUTED)
        if page == "home": self._home_page()
        elif page == "profiles": self._profiles_page()
        elif page == "mods": self._mods_page()
        else: self._settings_page()

    def _header(self, title, subtitle):
        ctk.CTkLabel(self.content, text=title, font=F(32, "bold"), text_color=FG).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self.content, text=subtitle, font=F(13), text_color=MUTED).grid(row=1, column=0, sticky="w", pady=(2, 20))

    def _card(self, parent=None, **kw):
        return ctk.CTkFrame(parent or self.content, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER, **kw)

    def _caption(self, parent, text):
        return ctk.CTkLabel(parent, text=text.upper(), text_color=MUTED, font=F(10, "bold"))

    def _btn(self, parent, text, command, secondary=True, **kw):
        base = dict(height=38, corner_radius=10, font=F(13, "bold"), command=command)
        if secondary: base.update(fg_color=PANEL_ALT, hover_color=BORDER, text_color=FG)
        else: base.update(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#04140d")
        base.update(kw)
        return ctk.CTkButton(parent, text=text, **base)

    def _combo(self, parent, **kw):
        return ctk.CTkComboBox(parent, height=38, corner_radius=10, fg_color=PANEL_ALT, border_color=BORDER, border_width=1,
                               button_color=ACCENT, button_hover_color=ACCENT_HOVER, dropdown_fg_color=PANEL_ALT,
                               dropdown_hover_color=BORDER, text_color=FG, font=F(13), dropdown_font=F(13), **kw)

    def _entry(self, parent, **kw):
        return ctk.CTkEntry(parent, height=38, corner_radius=10, fg_color=PANEL_ALT, border_color=BORDER, border_width=1,
                            text_color=FG, font=F(13), **kw)

    def _home_page(self):
        who = self.name_var.get().strip() or "гравцю"
        self._header(f"Привіт, {who}!" if self.mode_var.get() == "offline" else "Твій наступний світ.", "NOVA CRAFT  /  MINECRAFT JAVA EDITION")

        # Main launch panel
        hero = ctk.CTkFrame(self.content, fg_color="#151632", corner_radius=26,
                            border_width=1, border_color="#393266")
        hero.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="✦  YOUR ADVENTURE STARTS HERE",
                     text_color="#b7a5ff", font=F(11, "bold")).grid(
                         row=0, column=0, sticky="w", padx=30, pady=(27, 8))
        ctk.CTkLabel(hero, text="Менше налаштувань.\nБільше пригод.",
                     text_color=FG, font=F(31, "bold"), justify="left").grid(
                         row=1, column=0, sticky="w", padx=30)
        ctk.CTkLabel(hero, text="Обери версію, налаштуй пам’ять і повертайся у свій світ.",
                     text_color="#a7accd", font=F(13), wraplength=590).grid(
                         row=2, column=0, sticky="w", padx=30, pady=(9, 0))
        self.play_btn = ctk.CTkButton(
            hero, text="▶   ЗАПУСТИТИ MINECRAFT", height=54, width=280,
            corner_radius=15, font=F(15, "bold"), fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color="#0b0c1b", command=self._on_play)
        self.play_btn.grid(row=3, column=0, sticky="w", padx=30, pady=(22, 28))
        ctk.CTkLabel(hero, text="JAVA  EDITION   •   LAUNCHER 3.0",
                     text_color="#6d6b9c", font=F(10, "bold")).grid(
                         row=4, column=0, sticky="w", padx=30, pady=(0, 22))

        controls = ctk.CTkFrame(self.content, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew")
        controls.grid_columnconfigure((0, 1), weight=1, uniform="c")
        version_card = self._card(controls)
        version_card.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ctk.CTkLabel(version_card, text="01  /  GAME VERSION", text_color=ACCENT,
                     font=F(10, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
        self.version_box = self._combo(version_card, variable=self.version_var,
                     values=[self.version_var.get()] if self.version_var.get() else [], state="readonly")
        self.version_box.pack(fill="x", padx=20, pady=(0, 20))

        ram_card = self._card(controls)
        ram_card.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        ctk.CTkLabel(ram_card, text="02  /  MEMORY ALLOCATION", text_color=ACCENT,
                     font=F(10, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
        ramrow = ctk.CTkFrame(ram_card, fg_color="transparent")
        ramrow.pack(fill="x", padx=20, pady=(3, 20))
        self.ram_slider = ctk.CTkSlider(ramrow, from_=1, to=16, number_of_steps=15,
                     variable=self.ram_var, command=self._ram_changed,
                     progress_color=ACCENT, button_color=ACCENT,
                     button_hover_color=ACCENT_HOVER, fg_color=PANEL_ALT)
        self.ram_slider.pack(side="left", fill="x", expand=True, padx=(0, 14))
        self.ram_label = ctk.CTkLabel(ramrow, text=f"{self.ram_var.get()} GB",
                     width=58, font=F(15, "bold"), text_color=ACCENT)
        self.ram_label.pack(side="right")

        status = ctk.CTkFrame(self.content, fg_color="#101629", corner_radius=17,
                              border_width=1, border_color=BORDER)
        status.grid(row=4, column=0, sticky="ew", pady=(18, 0))
        top = ctk.CTkFrame(status, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(15, 2))
        ctk.CTkLabel(top, text="●", text_color=ACCENT, font=F(12, "bold")).pack(side="left", padx=(0, 9))
        self.status_label = ctk.CTkLabel(top, text="Готовий до запуску",
                     font=F(13, "bold"), text_color=FG)
        self.status_label.pack(side="left")
        self.detail_label = ctk.CTkLabel(status, text="Лаунчер готовий. Налаштуй параметри та натисни запуск.",
                     text_color=MUTED, font=F(12), wraplength=700, justify="left")
        self.detail_label.pack(anchor="w", padx=20, pady=(2, 10))
        self.progress = ctk.CTkProgressBar(status, progress_color=ACCENT,
                     fg_color=PANEL_ALT, height=7, corner_radius=4)
        self.progress.pack(fill="x", padx=20, pady=(0, 17))
        self.progress.set(0)

        account = ctk.CTkFrame(self.content, fg_color="transparent")
        account.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        self.account_label = ctk.CTkLabel(account, text="", text_color=MUTED, font=F(12))
        self.account_label.pack(side="left")
        self.logout_btn = self._btn(account, "Вийти з акаунта", self._logout, width=130, height=30)
        self.logout_btn.pack(side="right")
        self._refresh_account_label()

    def _profiles_page(self):
        self._header("Профілі", "Окремі налаштування для різних збірок Minecraft.")
        card = self._card(); card.grid(row=2, column=0, sticky="ew")
        self._caption(card, "Активний профіль").pack(anchor="w", padx=20, pady=(18, 6))
        self.profile_var = ctk.StringVar(value=self.active_profile)
        self.profile_box = self._combo(card, values=list(self.profiles), variable=self.profile_var, state="readonly", command=self._select_profile, width=320)
        self.profile_box.pack(anchor="w", padx=20, pady=(0, 14))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=20, pady=(0, 20))
        self._btn(row, "＋  Створити профіль", self._create_profile, secondary=False).pack(side="left", padx=(0, 8))
        self._btn(row, "Видалити профіль", self._delete_profile, fg_color="#5a2a2f", hover_color="#7a3640").pack(side="left")
        ctk.CTkLabel(self.content, text="Профіль зберігає версію, папку гри та виділену RAM. Для ізоляції модів задайте окрему папку гри.", text_color=MUTED, font=F(12), wraplength=680, justify="left").grid(row=3, column=0, sticky="w", pady=16)

    def _mods_page(self):
        self._header("Менеджер модів", "Переглядай, вмикай і вимикай .jar-моди в папці активного профілю.")
        bar = ctk.CTkFrame(self.content, fg_color="transparent"); bar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self._btn(bar, "Відкрити папку mods", self._open_mods_folder, secondary=False).pack(side="left")
        self._btn(bar, "Оновити список", self._refresh_mods).pack(side="left", padx=8)
        self.mods_list = ctk.CTkScrollableFrame(self.content, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER, height=360)
        self.mods_list.grid(row=3, column=0, sticky="nsew")
        self.content.grid_rowconfigure(3, weight=1)
        self._refresh_mods()

    def _settings_page(self):
        self._header("Налаштування", "Параметри лаунчера та спосіб входу.")
        card = self._card(); card.grid(row=2, column=0, sticky="ew")
        self._caption(card, "Папка гри").pack(anchor="w", padx=20, pady=(18, 6))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=20)
        self._entry(row, textvariable=self.dir_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._btn(row, "Обрати…", self._choose_dir, width=100).pack(side="right")
        self._caption(card, "Спосіб входу").pack(anchor="w", padx=20, pady=(18, 6))
        seg = ctk.CTkSegmentedButton(card, values=["Microsoft", "Офлайн"], command=self._set_auth_mode, height=36,
                                     selected_color="#1f9d72", selected_hover_color="#1a8962", unselected_color=PANEL_ALT,
                                     unselected_hover_color=BORDER, text_color=FG, fg_color=PANEL_ALT, font=F(13, "bold"))
        seg.pack(anchor="w", padx=20)
        seg.set("Офлайн" if self.mode_var.get() == "offline" else "Microsoft")
        self._caption(card, "Нік для офлайн-режиму").pack(anchor="w", padx=20, pady=(18, 6))
        self._entry(card, textvariable=self.name_var, width=280).pack(anchor="w", padx=20)
        ctk.CTkCheckBox(card, text="Показувати снапшоти", variable=self.snap_var, command=self._load_versions, font=F(13),
                        fg_color=ACCENT, hover_color=ACCENT_HOVER, checkmark_color="#04140d", border_color=BORDER).pack(anchor="w", padx=20, pady=18)
        self._btn(card, "Зберегти налаштування", self._save_settings, secondary=False).pack(anchor="w", padx=20, pady=(0, 20))

    def _ram_changed(self, value):
        if hasattr(self, "ram_label"): self.ram_label.configure(text=f"{int(float(value))} GB")

    def _set_auth_mode(self, value):
        self.mode_var.set("offline" if value == "Офлайн" else "microsoft")
        self._refresh_account_label()

    def _select_profile(self, name):
        if name not in self.profiles: return
        self._capture_profile()
        self.active_profile = name
        prof = self.profiles[name]
        self.version_var.set(prof["version"]); self.dir_var.set(prof["game_dir"]); self.ram_var.set(prof["ram_gb"])
        if hasattr(self, "ram_label"): self.ram_label.configure(text=f"{self.ram_var.get()} GB")
        self._save_settings(); self._refresh_mods()

    def _capture_profile(self):
        if self.active_profile in self.profiles:
            self.profiles[self.active_profile] = {"version": self.version_var.get(), "game_dir": self.dir_var.get(), "ram_gb": int(self.ram_var.get())}

    def _create_profile(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Новий профіль", "Назва профілю:", parent=self.root)
        if not name: return
        name = name.strip()[:40]
        if not name: return
        if name in self.profiles:
            messagebox.showwarning("Профілі", "Профіль із такою назвою вже існує."); return
        self._capture_profile(); self.profiles[name] = {"version": self.version_var.get(), "game_dir": self.dir_var.get(), "ram_gb": int(self.ram_var.get())}
        self.active_profile = name; self._save_settings(); self._show_page("profiles")

    def _delete_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo("Профілі", "Має залишитися хоча б один профіль."); return
        if not messagebox.askyesno("Видалити профіль", f"Видалити профіль «{self.active_profile}»? Файли гри не видалятимуться."): return
        del self.profiles[self.active_profile]; self.active_profile = next(iter(self.profiles)); prof = self.profiles[self.active_profile]
        self.version_var.set(prof["version"]); self.dir_var.set(prof["game_dir"]); self.ram_var.set(prof["ram_gb"])
        self._save_settings(); self._show_page("profiles")

    def _mods_dir(self): return Path(self.dir_var.get()).expanduser() / "mods"

    def _refresh_mods(self):
        if not hasattr(self, "mods_list") or not self.mods_list.winfo_exists(): return
        for child in self.mods_list.winfo_children(): child.destroy()
        folder = self._mods_dir()
        try: folder.mkdir(parents=True, exist_ok=True); files = sorted([p for p in folder.iterdir() if p.is_file() and (p.suffix.lower() == ".jar" or p.name.lower().endswith(".jar.disabled"))])
        except OSError as exc:
            ctk.CTkLabel(self.mods_list, text=f"Не вдалося прочитати папку модів: {exc}").pack(padx=12, pady=12); return
        if not files:
            ctk.CTkLabel(self.mods_list, text="Модів поки немає. Додай .jar-файли до папки mods.", text_color=MUTED).pack(padx=12, pady=18); return
        for path in files:
            row = ctk.CTkFrame(self.mods_list, fg_color=PANEL_ALT, corner_radius=9); row.pack(fill="x", padx=8, pady=5)
            enabled = path.suffix.lower() == ".jar"
            ctk.CTkLabel(row, text=("●  " if enabled else "○  ") + path.name, anchor="w").pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkButton(row, text="Вимкнути" if enabled else "Увімкнути", width=95, command=lambda p=path: self._toggle_mod(p)).pack(side="right", padx=8, pady=6)

    def _toggle_mod(self, path):
        try:
            if path.name.lower().endswith(".jar.disabled"):
                target = path.with_name(path.name[:-8])
            else: target = path.with_name(path.name + ".disabled")
            if target.exists(): messagebox.showerror("Моди", f"Файл уже існує: {target.name}"); return
            path.rename(target); self._refresh_mods()
        except OSError as exc: messagebox.showerror("Моди", str(exc))

    def _open_mods_folder(self):
        folder = self._mods_dir(); folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt": os.startfile(str(folder))
            else:
                import subprocess; subprocess.Popen(["open" if __import__('sys').platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc: messagebox.showerror("Моди", str(exc))

    def _choose_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or None, title="Оберіть папку гри")
        if chosen: self.dir_var.set(os.path.normpath(chosen)); self._save_settings(); self._refresh_mods(); self._load_versions()

    def _save_settings(self):
        self._capture_profile()
        self.settings.update({"game_dir": self.dir_var.get(), "version": self.version_var.get(), "show_snapshots": bool(self.snap_var.get()), "auth_mode": self.mode_var.get(), "offline_name": self.name_var.get().strip(), "ram_gb": int(self.ram_var.get()), "active_profile": self.active_profile, "profiles": self.profiles})
        storage.save_settings(self.settings)
        if hasattr(self, "status_label") and self.status_label.winfo_exists(): self._on_detail("Налаштування збережено.")

    def _on_close(self): self._save_settings(); self.root.destroy()

    def _logout(self):
        storage.clear_account(); self._refresh_account_label(); self._on_detail("Ви вийшли з акаунта.")

    def _refresh_account_label(self):
        if self.mode_var.get() == "offline": text = f"Офлайн-режим · {self.name_var.get().strip() or 'Player'}"
        else:
            name = storage.load_account().get("name")
            text = f"Microsoft · {name}" if name else "Microsoft · вхід під час запуску"
        if hasattr(self, "account_label") and self.account_label.winfo_exists(): self.account_label.configure(text=text)
        if hasattr(self, "side_account"): self.side_account.configure(text=text)
        if hasattr(self, "logout_btn") and self.logout_btn.winfo_exists():
            if self.mode_var.get() == "offline": self.logout_btn.pack_forget()
            else: self.logout_btn.pack(side="right")

    def _on_play(self):
        if self.busy: return
        offline = self.mode_var.get() == "offline"
        if not offline and not config.client_id_is_set():
            messagebox.showerror("Потрібне налаштування", "У config.py не вказано CLIENT_ID. Інструкція є в README.md."); return
        version, game_dir = self.version_var.get().strip(), self.dir_var.get().strip()
        if not version or not game_dir: messagebox.showerror("Помилка", "Оберіть версію та папку гри."); return
        self._save_settings(); self.busy = True
        self.play_btn.configure(state="disabled", text="ПІДГОТОВКА…")
        threading.Thread(target=self._play_worker, args=(version, game_dir, offline, self.name_var.get().strip(), int(self.ram_var.get())), daemon=True).start()

    def post(self, *msg): self.q.put(msg)

    def _load_versions(self):
        if not hasattr(self, "version_box") or not self.version_box.winfo_exists(): return
        self.version_box.configure(state="disabled")
        self.post("detail", "Завантаження списку версій…")
        show, game_dir = bool(self.snap_var.get()), self.dir_var.get()
        def work():
            ids, online = game.get_versions(game_dir, show); self.post("versions", ids, online)
        threading.Thread(target=work, daemon=True).start()

    def _play_worker(self, version, game_dir, offline, nick, ram_gb):
        try:
            if offline: account = game.offline_account(nick)
            else:
                self.post("status", "Вхід у Microsoft"); self.post("indeterminate")
                account = auth.get_account(lambda t: self.post("detail", t)); self.post("account")
            self.post("status", "Завантаження Minecraft"); self.post("progress", 0)
            game.install_version(version, game_dir, on_detail=lambda t: self.post("detail", t), on_percent=lambda p: self.post("progress", p))
            self.post("status", "Запуск гри"); self.post("indeterminate")
            proc = game.launch(version, game_dir, account, ram_gb=ram_gb)
            self.post("progress_reset"); self.post("status", "Гра запущена"); self.post("detail", f"Minecraft запущено · RAM {ram_gb} GB")
            code = proc.wait()
            if code != 0: self.post("error", f"Minecraft завершився з помилкою (код {code}).\nЛог: {config.LOG_FILE}")
        except Exception as exc:
            traceback.print_exc(); self.post("error", friendly_error(exc))
        finally: self.post("idle")

    def _poll(self):
        try:
            while True:
                kind, *args = self.q.get_nowait()
                try: getattr(self, f"_on_{kind}")(*args)
                except Exception: traceback.print_exc()
        except queue.Empty: pass
        if self.root.winfo_exists(): self.root.after(100, self._poll)

    def _check_update_worker(self):
        info = updater.check_for_update(self.settings.get("update_installed", ""))
        if info: self.post("update", info)

    def _on_update(self, info):
        if self.busy: return
        text = f"Доступна нова версія {info['version']} (у вас {config.LAUNCHER_VERSION})."
        if info.get("notes"): text += f"\n\n{info['notes']}"
        if not updater.can_self_update():
            messagebox.showinfo("Оновлення", text + "\n\nЗавантажте її зі сторінки релізів GitHub.")
            return
        if not messagebox.askyesno("Оновлення", text + "\n\nОновити зараз? Лаунчер перезапуститься."): return
        self.busy = True
        self.play_btn.configure(state="disabled")
        self.status_label.configure(text="Завантаження оновлення...", text_color=FG)
        threading.Thread(target=self._update_worker, args=(info,), daemon=True).start()

    def _update_worker(self, info):
        try:
            path = updater.download_installer(info, lambda p: self.post("progress", p))
            self.post("update_ready", path, info["version"])
        except Exception as e:
            self.post("error", f"Не вдалося оновитися: {e}"); self.post("idle")

    def _on_update_ready(self, path, version):
        self.settings["update_installed"] = version
        self._save_settings()
        updater.run_installer(path)
        os._exit(0)

    def _on_status(self, text): self.status_label.configure(text=text, text_color=FG)
    def _on_detail(self, text):
        if hasattr(self, "detail_label") and self.detail_label.winfo_exists(): self.detail_label.configure(text=text)
    def _on_progress(self, pct): self.progress.set(max(0, min(100, pct)) / 100)
    def _on_progress_reset(self): self.progress.set(0)
    def _on_indeterminate(self):
        # CTkProgressBar підтримує індетермінований режим у сучасних версіях CTk.
        try:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        except Exception:
            self.progress.set(0.35)
    def _on_account(self): self._refresh_account_label()
    def _on_versions(self, ids, online):
        if not hasattr(self, "version_box") or not self.version_box.winfo_exists(): return
        self.version_box.configure(values=ids or [self.version_var.get() or config.DEFAULT_VERSION], state="readonly")
        if ids and self.version_var.get() not in ids: self.version_var.set(ids[0])
        if not online: self._on_detail("Офлайн: показано встановлені версії, якщо вони доступні.")
    def _on_error(self, text):
        if hasattr(self, "status_label") and self.status_label.winfo_exists(): self.status_label.configure(text="Помилка", text_color=RED)
        self._on_detail(text); messagebox.showerror("Помилка", text)
    def _on_idle(self):
        self.busy = False
        if hasattr(self, "progress") and self.progress.winfo_exists():
            try: self.progress.stop(); self.progress.configure(mode="determinate")
            except Exception: pass
            self.progress.set(0)
        if hasattr(self, "play_btn") and self.play_btn.winfo_exists(): self.play_btn.configure(state="normal", text="▶   ГРАТИ")
        if hasattr(self, "status_label") and self.status_label.winfo_exists() and self.status_label.cget("text") != "Помилка": self.status_label.configure(text="Готовий", text_color=FG)
        self._refresh_account_label()


def main():
    try:
        import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass
    root = ctk.CTk()
    App(root)
    root.mainloop()

if __name__ == "__main__": main()
