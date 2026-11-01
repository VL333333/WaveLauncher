"""Лаунчер Minecraft — CustomTkinter UI, профілі, RAM і менеджер модів."""
import math
import os
import queue
import sys
import threading
import tkinter as tk
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

BG = "#070b1a"
SIDEBAR = "#0a1024"
PANEL = "#0f1733"
PANEL_ALT = "#172150"
BORDER = "#243060"
FG = "#eef3ff"
MUTED = "#8b9bc4"
DIM = "#5f6f9e"
ACCENT = "#38bdf8"
ACCENT_HOVER = "#7dd3fc"
ACCENT2 = "#818cf8"
ACCENT_SOFT = "#12264f"
ON_ACCENT = "#04121f"
HERO = "#0c1536"
GREEN = ACCENT
GREEN_HOVER = ACCENT_HOVER
RED = "#fb7185"


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def F(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


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
        self.client_var = ctk.StringVar(value=profile.get("client", "java"))
        self.rust_exe_var = ctk.StringVar(value=profile.get("rust_exe", ""))
        self.rust_args_var = ctk.StringVar(value=profile.get("rust_args", ""))
        self.snap_var = ctk.BooleanVar(value=bool(self.settings.get("show_snapshots", False)))
        self.mode_var = ctk.StringVar(value=self.settings.get("auth_mode", "microsoft"))
        self.name_var = ctk.StringVar(value=self.settings.get("offline_name", "Player"))

        for _v in (self.version_var, self.client_var):
            _v.trace_add("write", lambda *a: self._update_chips())
        root.title(config.APP_NAME)
        root.after(250, self._set_icon)
        root.geometry("1120x760")
        root.minsize(960, 680)
        root.configure(fg_color=BG)
        self._build_ui()
        try:
            root.attributes("-alpha", 0.0); self._fade(0.0)
        except Exception:
            pass
        self._refresh_account_label()
        self._refresh_mods()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(100, self._poll)
        self._load_versions()
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _fade(self, a):
        try:
            a = min(1.0, a + 0.1); self.root.attributes("-alpha", a)
            if a < 1.0: self.root.after(18, lambda: self._fade(a))
        except Exception:
            pass

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
            ctk.CTkLabel(brand, text="W", width=46, height=46, corner_radius=14,
                         fg_color=ACCENT, text_color=ON_ACCENT, font=F(24, "bold")).pack(side="left")
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(names, text="WAVE", font=F(24, "bold"), text_color=FG).pack(anchor="w")
        ctk.CTkLabel(names, text="LAUNCHER  /  JAVA", font=F(10, "bold"), text_color=ACCENT).pack(anchor="w", pady=(1, 0))

        ctk.CTkLabel(self.sidebar, text="МЕНЮ", text_color=DIM,
                     font=F(10, "bold")).pack(anchor="w", padx=24, pady=(0, 10))
        self.nav = {}
        self.nav_ind = {}
        for icon, label, page in [
            ("⌂", "Головна", "home"),
            ("▦", "Профілі", "profiles"),
            ("◇", "Моди", "mods"),
            ("⚙", "Налаштування", "settings"),
        ]:
            item = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=48)
            item.pack(fill="x", padx=(6, 13), pady=3)
            ind = ctk.CTkFrame(item, width=4, height=24, corner_radius=2, fg_color="transparent")
            ind.pack(side="left", padx=(0, 4))
            btn = ctk.CTkButton(
                item, text=f"  {icon}     {label}", anchor="w", height=46,
                corner_radius=14, font=F(14, "bold"), fg_color="transparent",
                hover_color="#141d44", text_color=MUTED,
                border_spacing=12, command=lambda p=page: self._show_page(p))
            btn.pack(side="left", fill="x", expand=True)
            self.nav[page] = btn
            self.nav_ind[page] = ind

        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(expand=True, fill="both")
        chip = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=16,
                            border_width=1, border_color=BORDER)
        chip.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(chip, text="АКАУНТ", text_color=MUTED,
                     font=F(9, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        arow = ctk.CTkFrame(chip, fg_color="transparent")
        arow.pack(fill="x", padx=14, pady=(0, 14))
        self.side_avatar = ctk.CTkLabel(arow, text="P", width=36, height=36, corner_radius=18,
                    fg_color=ACCENT2, text_color=ON_ACCENT, font=F(14, "bold"))
        self.side_avatar.pack(side="left", padx=(0, 10))
        self.side_account = ctk.CTkLabel(arow, text="Офлайн", text_color=FG,
                    font=F(12, "bold"), wraplength=140, justify="left", anchor="w")
        self.side_account.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(self.sidebar, text=f"{config.APP_NAME}  ·  v{config.LAUNCHER_VERSION}",
                     text_color=DIM, font=F(10)).pack(padx=20, pady=(0, 18), anchor="w")

        self.content = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=34, pady=(20, 14))
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
            self.nav_ind[key].configure(fg_color=ACCENT if on else "transparent")
        if page == "home": self._home_page()
        elif page == "profiles": self._profiles_page()
        elif page == "mods": self._mods_page()
        else: self._settings_page()

    def _header(self, title, subtitle):
        ctk.CTkLabel(self.content, text=title, font=F(32, "bold"), text_color=FG).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self.content, text=subtitle, font=F(13), text_color=MUTED).grid(row=1, column=0, sticky="w", pady=(2, 14))

    def _card(self, parent=None, **kw):
        return ctk.CTkFrame(parent or self.content, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER, **kw)

    def _caption(self, parent, text):
        return ctk.CTkLabel(parent, text="▍" + text.upper(), text_color=ACCENT2, font=F(10, "bold"))

    def _btn(self, parent, text, command, secondary=True, **kw):
        base = dict(height=38, corner_radius=10, font=F(13, "bold"), command=command)
        if secondary: base.update(fg_color=PANEL_ALT, hover_color=BORDER, text_color=FG)
        else: base.update(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT)
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
        self._header(f"Привіт, {who}!" if self.mode_var.get() == "offline" else "Піймай свою хвилю.", "WAVE LAUNCHER  /  MINECRAFT JAVA EDITION")

        # Main launch panel
        hero = ctk.CTkFrame(self.content, fg_color=HERO, corner_radius=26,
                            border_width=1, border_color=BORDER)
        hero.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_columnconfigure(1, minsize=178)
        # Signature panel: animated wave.
        signature = ctk.CTkFrame(hero, fg_color="#08102a", corner_radius=22,
                                 border_width=1, border_color=BORDER, width=168, height=190)
        signature.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=(0, 22), pady=22)
        signature.grid_propagate(False)
        ctk.CTkLabel(signature, text="W", text_color=FG,
                     font=F(54, "bold")).pack(pady=(18, 0))
        ctk.CTkLabel(signature, text=f"WAVE  /  v{config.LAUNCHER_VERSION}", text_color=MUTED,
                     font=F(10, "bold")).pack(pady=(0, 6))
        self._wave = tk.Canvas(signature, width=150, height=62, bg="#08102a",
                               highlightthickness=0, bd=0)
        self._wave.pack(side="bottom", pady=(0, 14))
        self._wave_phase = 0.0
        self.root.after(60, self._animate_wave)
        ctk.CTkLabel(hero, text="WAVE LAUNCHER  /  ГОТОВО ДО ГРИ",
                     text_color=ACCENT_HOVER, font=F(11, "bold")).grid(
                         row=0, column=0, sticky="w", padx=30, pady=(27, 8))
        ctk.CTkLabel(hero, text="Менше налаштувань.\nБільше пригод.",
                     text_color=FG, font=F(31, "bold"), justify="left").grid(
                         row=1, column=0, sticky="w", padx=30)
        ctk.CTkLabel(hero, text="Обери версію, налаштуй пам’ять і повертайся у свій світ.",
                     text_color=MUTED, font=F(13), wraplength=590).grid(
                         row=2, column=0, sticky="w", padx=30, pady=(9, 0))
        self.play_btn = ctk.CTkButton(
            hero, text="▶   ЗАПУСТИТИ MINECRAFT", height=54, width=280,
            corner_radius=15, font=F(15, "bold"), fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color=ON_ACCENT, command=self._on_play)
        self.play_btn.grid(row=3, column=0, sticky="w", padx=30, pady=(18, 20))
        chips = ctk.CTkFrame(hero, fg_color="transparent")
        chips.grid(row=4, column=0, sticky="w", padx=30, pady=(0, 20))
        self.chip_labels = {}
        for key in ("ver", "ram", "client"):
            lab = ctk.CTkLabel(chips, text="", height=26, corner_radius=13, fg_color=ACCENT_SOFT,
                               text_color=ACCENT_HOVER, font=F(11, "bold"), padx=12)
            lab.pack(side="left", padx=(0, 8))
            self.chip_labels[key] = lab
        self._update_chips()
        self._pulse_step = 0
        self.root.after(80, self._pulse_play)

        controls = ctk.CTkFrame(self.content, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew")
        controls.grid_columnconfigure((0, 1), weight=1, uniform="c")
        version_card = self._card(controls)
        version_card.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ctk.CTkLabel(version_card, text="GAME VERSION", text_color=ACCENT,
                     font=F(10, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
        self.version_box = self._combo(version_card, variable=self.version_var,
                     values=[self.version_var.get()] if self.version_var.get() else [], state="readonly")
        self.version_box.pack(fill="x", padx=20, pady=(0, 20))

        ram_card = self._card(controls)
        ram_card.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        ctk.CTkLabel(ram_card, text="MEMORY ALLOCATION", text_color=ACCENT,
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

        status = ctk.CTkFrame(self.content, fg_color=HERO, corner_radius=17,
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

    def _update_chips(self, *_):
        try:
            labs = getattr(self, "chip_labels", None)
            if not labs or not labs["ver"].winfo_exists(): return
            labs["ver"].configure(text=f"●  {self.version_var.get() or '—'}")
            labs["ram"].configure(text=f"{int(self.ram_var.get())} GB RAM")
            labs["client"].configure(text="Rust-клієнт" if self.client_var.get() == "rust" else "Java Edition")
        except Exception:
            pass

    @staticmethod
    def _mix(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(a, b))

    def _pulse_play(self):
        """М'яка зміна кольору кнопки запуску між блакитним та індиго."""
        try:
            btn = getattr(self, "play_btn", None)
            if btn is None or not btn.winfo_exists():
                return
            if not self.busy and self.page == "home":
                t = (math.sin(self._pulse_step / 9) + 1) / 2
                btn.configure(fg_color=self._mix(ACCENT, ACCENT2, t * 0.55))
                self._pulse_step += 1
            self.root.after(80, self._pulse_play)
        except Exception:
            pass

    def _animate_wave(self):
        """Плавна анімація хвиль у фірмовій панелі."""
        try:
            c = getattr(self, "_wave", None)
            if c is None or not c.winfo_exists():
                return
            c.delete("all")
            w, h = 150, 62
            for i, (col, amp, off) in enumerate((("#1c3a7a", 9, 0.0), (ACCENT2, 7, 1.3), (ACCENT, 6, 2.6))):
                pts = []
                for x in range(0, w + 6, 6):
                    y = h * 0.55 + i * 6 + amp * math.sin(x / 17 + self._wave_phase + off)
                    pts += [x, y]
                c.create_line(*pts, fill=col, width=3, smooth=True)
            self._wave_phase += 0.22
            self.root.after(60, self._animate_wave)
        except Exception:
            pass

    def _profiles_page(self):
        self._header("Профілі", "Окремі налаштування для різних збірок Minecraft.")
        card = self._card(); card.grid(row=2, column=0, sticky="ew")
        self._caption(card, "Активний профіль").pack(anchor="w", padx=20, pady=(18, 6))
        self.profile_var = ctk.StringVar(value=self.active_profile)
        self.profile_box = self._combo(card, values=list(self.profiles), variable=self.profile_var, state="readonly", command=self._select_profile, width=320)
        self.profile_box.pack(anchor="w", padx=20, pady=(0, 14))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=20, pady=(0, 20))
        self._btn(row, "＋  Створити профіль", self._create_profile, secondary=False).pack(side="left", padx=(0, 8))
        self._btn(row, "Видалити профіль", self._delete_profile, fg_color="#4a1f3a", hover_color="#6a2a4e").pack(side="left")
        self._rust_card()
        ctk.CTkLabel(self.content, text="Профіль зберігає версію, папку гри та виділену RAM. Для ізоляції модів задайте окрему папку гри.", text_color=MUTED, font=F(12), wraplength=680, justify="left").grid(row=4, column=0, sticky="w", pady=16)

    def _rust_card(self):
        card = self._card(); card.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self._caption(card, "Клієнт гри").pack(anchor="w", padx=20, pady=(18, 6))
        seg = ctk.CTkSegmentedButton(card, values=["Java (офіційний)", "Rust (експериментальний)"], command=self._set_client,
                                     height=36, selected_color="#2a3a7a", selected_hover_color="#3a4d9a",
                                     unselected_color=PANEL_ALT, unselected_hover_color=BORDER, text_color=FG,
                                     fg_color=PANEL_ALT, font=F(13, "bold"))
        seg.pack(anchor="w", padx=20)
        seg.set("Rust (експериментальний)" if self.client_var.get() == "rust" else "Java (офіційний)")
        self._caption(card, "Шлях до Rust-клієнта (.exe)").pack(anchor="w", padx=20, pady=(16, 6))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=20)
        self._entry(row, textvariable=self.rust_exe_var, placeholder_text="напр. C:\\Games\\leafish.exe").pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._btn(row, "Обрати…", self._choose_rust_exe, width=100).pack(side="right")
        self._caption(card, "Аргументи запуску (необов’язково, {name} = нік)").pack(anchor="w", padx=20, pady=(14, 6))
        self._entry(card, textvariable=self.rust_args_var).pack(fill="x", padx=20)
        links = ctk.CTkFrame(card, fg_color="transparent"); links.pack(fill="x", padx=20, pady=(14, 8))
        self._btn(links, "Leafish (GitHub)", lambda: self._open_url("https://github.com/Lea-fish/Leafish/releases")).pack(side="left", padx=(0, 8))
        self._btn(links, "Stevenarella (GitHub)", lambda: self._open_url("https://github.com/iceiix/stevenarella")).pack(side="left")
        ctk.CTkLabel(card, text="Rust-клієнти — стороннє, експериментальне ПЗ: підтримують не всі версії й функції гри, "
                     "мають власний екран входу, а моди Java на них не працюють. Лаунчер лише запускає програму.",
                     text_color=MUTED, font=F(11), wraplength=640, justify="left").pack(anchor="w", padx=20, pady=(0, 18))

    def _set_client(self, value):
        self.client_var.set("rust" if value.startswith("Rust") else "java")
        self._update_chips()
        self._save_settings()

    def _choose_rust_exe(self):
        path = filedialog.askopenfilename(title="Оберіть Rust-клієнт", filetypes=[("Програма", "*.exe *"), ("Усі файли", "*.*")])
        if path: self.rust_exe_var.set(os.path.normpath(path)); self._save_settings()

    def _open_url(self, url):
        import webbrowser; webbrowser.open(url)

    def _mods_page(self):
        self._header("Менеджер модів", "Переглядай, вмикай і вимикай .jar-моди в папці активного профілю.")
        bar = ctk.CTkFrame(self.content, fg_color="transparent"); bar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self._btn(bar, "Відкрити папку mods", self._open_mods_folder, secondary=False).pack(side="left")
        self._btn(bar, "Оновити список", self._refresh_mods).pack(side="left", padx=8)
        self.mods_list = ctk.CTkScrollableFrame(self.content, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER, height=360, scrollbar_button_color=BORDER, scrollbar_button_hover_color=ACCENT2)
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
                                     selected_color="#2a3a7a", selected_hover_color="#3a4d9a", unselected_color=PANEL_ALT,
                                     unselected_hover_color=BORDER, text_color=FG, fg_color=PANEL_ALT, font=F(13, "bold"))
        seg.pack(anchor="w", padx=20)
        seg.set("Офлайн" if self.mode_var.get() == "offline" else "Microsoft")
        self._caption(card, "Нік для офлайн-режиму").pack(anchor="w", padx=20, pady=(18, 6))
        self._entry(card, textvariable=self.name_var, width=280).pack(anchor="w", padx=20)
        ctk.CTkCheckBox(card, text="Показувати снапшоти", variable=self.snap_var, command=self._load_versions, font=F(13),
                        fg_color=ACCENT, hover_color=ACCENT_HOVER, checkmark_color=ON_ACCENT, border_color=BORDER).pack(anchor="w", padx=20, pady=18)
        self._btn(card, "Зберегти налаштування", self._save_settings, secondary=False).pack(anchor="w", padx=20, pady=(0, 20))

    def _ram_changed(self, value):
        if hasattr(self, "ram_label"): self.ram_label.configure(text=f"{int(float(value))} GB"); self._update_chips()

    def _set_auth_mode(self, value):
        self.mode_var.set("offline" if value == "Офлайн" else "microsoft")
        self._refresh_account_label()

    def _select_profile(self, name):
        if name not in self.profiles: return
        self._capture_profile()
        self.active_profile = name
        self._apply_profile(self.profiles[name])
        if hasattr(self, "ram_label"): self.ram_label.configure(text=f"{self.ram_var.get()} GB")
        self._save_settings(); self._refresh_mods()

    def _profile_data(self):
        return {"version": self.version_var.get(), "game_dir": self.dir_var.get(), "ram_gb": int(self.ram_var.get()),
                "client": self.client_var.get(), "rust_exe": self.rust_exe_var.get().strip(),
                "rust_args": self.rust_args_var.get().strip()}

    def _apply_profile(self, prof):
        self.version_var.set(prof["version"]); self.dir_var.set(prof["game_dir"]); self.ram_var.set(prof["ram_gb"])
        self.client_var.set(prof.get("client", "java")); self.rust_exe_var.set(prof.get("rust_exe", ""))
        self.rust_args_var.set(prof.get("rust_args", ""))

    def _capture_profile(self):
        if self.active_profile in self.profiles:
            self.profiles[self.active_profile] = self._profile_data()

    def _create_profile(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Новий профіль", "Назва профілю:", parent=self.root)
        if not name: return
        name = name.strip()[:40]
        if not name: return
        if name in self.profiles:
            messagebox.showwarning("Профілі", "Профіль із такою назвою вже існує."); return
        self._capture_profile(); self.profiles[name] = self._profile_data()
        self.active_profile = name; self._save_settings(); self._show_page("profiles")

    def _delete_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo("Профілі", "Має залишитися хоча б один профіль."); return
        if not messagebox.askyesno("Видалити профіль", f"Видалити профіль «{self.active_profile}»? Файли гри не видалятимуться."): return
        del self.profiles[self.active_profile]; self.active_profile = next(iter(self.profiles)); self._apply_profile(self.profiles[self.active_profile])
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
        on_count = sum(1 for p in files if p.suffix.lower() == ".jar")
        ctk.CTkLabel(self.mods_list, text=f"УВІМКНЕНО  {on_count} / {len(files)}", text_color=ACCENT,
                     font=F(10, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
        for path in files:
            enabled = path.suffix.lower() == ".jar"
            row = ctk.CTkFrame(self.mods_list, fg_color=PANEL_ALT if enabled else PANEL, corner_radius=12,
                               border_width=1, border_color=BORDER)
            row.pack(fill="x", padx=8, pady=4)
            name = path.name[:-9] if not enabled else path.name
            ctk.CTkLabel(row, text=name, anchor="w", font=F(13, "bold" if enabled else "normal"),
                         text_color=FG if enabled else DIM).pack(side="left", fill="x", expand=True, padx=14, pady=12)
            sw = ctk.CTkSwitch(row, text="", width=46, progress_color=ACCENT, button_color=FG,
                               button_hover_color=ACCENT_HOVER, fg_color=BORDER,
                               command=lambda p=path: self._toggle_mod(p))
            if enabled: sw.select()
            sw.pack(side="right", padx=14)

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
        if hasattr(self, "side_avatar"):
            who = self.name_var.get().strip() if self.mode_var.get() == "offline" else (storage.load_account().get("name") or "")
            self.side_avatar.configure(text=(who[:1] or "?").upper())
        if hasattr(self, "logout_btn") and self.logout_btn.winfo_exists():
            if self.mode_var.get() == "offline": self.logout_btn.pack_forget()
            else: self.logout_btn.pack(side="right")

    def _on_play(self):
        if self.busy: return
        if self.client_var.get() == "rust":
            self._save_settings(); self.busy = True
            self.play_btn.configure(state="disabled", text="ЗАПУСК RUST…")
            threading.Thread(target=self._rust_worker, daemon=True).start()
            return
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

    def _rust_worker(self):
        try:
            self.post("status", "Запуск Rust-клієнта"); self.post("indeterminate")
            proc = game.launch_external(self.rust_exe_var.get(), self.rust_args_var.get(), self.name_var.get().strip())
            self.post("progress_reset"); self.post("status", "Rust-клієнт запущено")
            self.post("detail", "Увійди в акаунт у вікні клієнта. Лог: " + config.LOG_FILE)
            code = proc.wait()
            if code != 0: self.post("error", f"Rust-клієнт завершився з помилкою (код {code}).\nЛог: {config.LOG_FILE}")
        except Exception as exc:
            traceback.print_exc(); self.post("error", friendly_error(exc))
        finally: self.post("idle")

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
        if hasattr(self, "play_btn") and self.play_btn.winfo_exists(): self.play_btn.configure(state="normal", text="▶   ГРАТИ"); self._pulse_step = 0
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
