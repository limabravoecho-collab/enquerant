#!/usr/bin/env python3
"""
enquerant_gui.py — Enquerant V2.0 Static Logic Crystal (SLC) Interface
================================================================================
Desktop Tkinter interface for the Enquerant (EQ) DEIE framework.
Powered by Substrate Primitives Formula System (SPFS) compute engine.
================================================================================
"""

import os
import re
import threading
import traceback
import psutil
import tkinter as tk
from tkinter import scrolledtext, messagebox
from typing import Optional
import io
from PIL import Image, ImageTk
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from app import EnquerantOrchestrator
from spfs_engine import SPFSEngine, SPFSCoreState


class EnquerantGUI:

    def _preprocess_math_text(self, text: str) -> str:
        """
        Safely detects and wraps raw standalone equations without mangling prose.
        """
        if "$" in text or "###" in text or "Seeker >" in text or "EnQuerant >" in text:
            return text
            
        # Only target pure equation lines or structured triple objects containing math syntax
        if any(sym in text for sym in ["rho_m", "rho_(de)", "(a)/(a)", "d rho", "ln rho"]) and not "maps directly to" in text:
            clean = text.replace("align", "").strip()
            return f"${clean}$"
            
        return text

    def _render_latex_inline(self, latex_expr: str) -> Optional[ImageTk.PhotoImage]:
        try:
            clean_expr = latex_expr.strip()
            if clean_expr.startswith("$") and clean_expr.endswith("$"):
                clean_expr = clean_expr[1:-1].strip()
            
            # Deep sanitization for Matplotlib mathtext engine compatibility
            clean_expr = clean_expr.replace(r"\Big", "").replace(r"\big", "")
            clean_expr = clean_expr.replace(r"\bigg", "").replace(r"\bigg", "")
            clean_expr = clean_expr.replace(r"\left", "").replace(r"\right", "")
            clean_expr = clean_expr.replace(r"\oint", r"\int")
            clean_expr = clean_expr.replace(r"\oplus", r"+")
            clean_expr = clean_expr.replace(r"\to", r"\rightarrow")
            clean_expr = clean_expr.replace(r"\text", r"\mathrm")
            clean_expr = clean_expr.replace(r"\le", r"\leqslant")
            clean_expr = clean_expr.replace(r"\text{", r"\mathrm{")
            clean_expr = clean_expr.replace(r"\propto", r"\sim")
            # mathtext has no \iff. Unhandled, the render returns None and the
            # whole expression falls through to the raw-LaTeX fallback.
            clean_expr = clean_expr.replace(r"\iff", r"\Leftrightarrow")

            fig = plt.figure(figsize=(0.01, 0.01))
            fig.patch.set_alpha(0.0)
            
            text_obj = fig.text(0, 0, f"${clean_expr}$", fontsize=11, color=self.colors["equation"])
            fig.canvas.draw()
            bbox = text_obj.get_window_extent(fig.canvas.get_renderer())
            
            if bbox.width == 0 or bbox.height == 0:
                plt.close(fig)
                return None

            fig.set_size_inches(bbox.width / fig.dpi, bbox.height / fig.dpi)
            text_obj.set_position((0, 0))
            
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, transparent=True, bbox_inches='tight', pad_inches=0.01)
            plt.close(fig)
            buf.seek(0)
            
            pil_img = Image.open(buf)
            if not hasattr(self, "_img_cache"):
                self._img_cache = []
            photo_img = ImageTk.PhotoImage(pil_img)
            self._img_cache.append(photo_img)
            return photo_img
        except Exception as e:
            # Fallback text representation if mathtext subset fails
            return None
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EnQuerant (EQ) V2.0 — Static Logic Crystal (SLC)")
        self.root.geometry("1420x920")
        self.root.minsize(850, 550)

        self.bot: Optional[EnquerantOrchestrator] = None
        self.is_streaming = False
        self._poll_handle: Optional[str] = None
        self._shutting_down = False

        self.colors = {
            "bg_dark": "#121417",
            "panel_dark": "#1b1f24",
            "input_bg": "#0d1117",
            "border": "#2d333b",
            "text_main": "#e6edf3",
            "text_muted": "#8b949e",
            "seeker": "#58a6ff",
            "guide": "#3fb950",
            "header": "#79c0ff",
            "bold": "#ffa657",
            "equation": "#d2a8ff",
            "system": "#e3b341",
            "button_exit": "#da3633",
            "button_send": "#238636",
            "btn_text": "#ffffff",
        }

        self.root.configure(bg=self.colors["bg_dark"])
        self._build_ui()
        self._init_engine_async()

    def _build_ui(self):
        header = tk.Frame(self.root, bg=self.colors["panel_dark"], height=46, bd=1, relief=tk.FLAT)
        header.pack(fill=tk.X, side=tk.TOP, padx=8, pady=(8, 4))

        title_label = tk.Label(header, text="ENQUERANT (EQ) V2.0", font=("DejaVu Sans", 12, "bold"), fg=self.colors["seeker"], bg=self.colors["panel_dark"])
        title_label.pack(side=tk.LEFT, padx=12, pady=8)

        sub_label = tk.Label(header, text="Static Logic Crystal (SLC) | SPFS Core Engine", font=("DejaVu Sans", 9), fg=self.colors["text_muted"], bg=self.colors["panel_dark"])
        sub_label.pack(side=tk.LEFT, padx=4, pady=8)

        self.engine_status_label = tk.Label(header, text="[ COLD-BOOTING CRYSTAL... ]", font=("DejaVu Sans Mono", 9, "bold"), fg=self.colors["system"], bg=self.colors["panel_dark"])
        self.engine_status_label.pack(side=tk.RIGHT, padx=12, pady=8)

        main_container = tk.Frame(self.root, bg=self.colors["bg_dark"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        chat_frame = tk.Frame(main_container, bg=self.colors["bg_dark"], bd=1, relief=tk.SOLID)
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("DejaVu Sans Mono", 11),
            bg=self.colors["input_bg"], fg=self.colors["text_main"],
            insertbackground=self.colors["seeker"], selectbackground=self.colors["border"],
            relief=tk.FLAT, bd=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)

        self.copy_btn = tk.Button(
            chat_frame, text="COPY", font=("DejaVu Sans Mono", 8, "bold"),
            bg=self.colors["panel_dark"], fg=self.colors["text_muted"],
            relief=tk.FLAT, bd=1, padx=8, pady=2, cursor="hand2", command=self.copy_chat_to_clipboard
        )

        def _show_copy_btn(event):
            self.copy_btn.place(relx=0.98, rely=0.02, anchor="ne")

        def _hide_copy_btn(event):
            x, y = chat_frame.winfo_pointerxy()
            bx, by = self.copy_btn.winfo_rootx(), self.copy_btn.winfo_rooty()
            bw, bh = self.copy_btn.winfo_width(), self.copy_btn.winfo_height()
            if not (bx <= x <= bx + bw and by <= y <= by + bh):
                self.copy_btn.place_forget()

        self.chat_display.bind("<Enter>", _show_copy_btn)
        chat_frame.bind("<Leave>", _hide_copy_btn)

        self.chat_display.tag_config("seeker", foreground=self.colors["seeker"], font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_config("guide", foreground=self.colors["guide"], font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_config("system", foreground=self.colors["system"], font=("DejaVu Sans Mono", 10))
        self.chat_display.tag_config("h1", foreground=self.colors["header"], font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_config("bold", foreground=self.colors["bold"], font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_config("equation", foreground=self.colors["equation"], font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_config("body", foreground=self.colors["text_main"])
        # A markdown horizontal rule is drawn by _insert_rule as an embedded
        # frame, so its width follows the window rather than a character count.
        self.chat_display.tag_config("tag_proprietary", foreground="#FFD700", font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_config("tag_dislocation", foreground="#00FF66", font=("DejaVu Sans Mono", 11, "bold"))
        self.chat_display.tag_raise("tag_proprietary")
        self.chat_display.tag_raise("tag_dislocation")

        sidebar = tk.Frame(main_container, bg=self.colors["panel_dark"], width=300, bd=1, relief=tk.FLAT)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        side_title = tk.Label(sidebar, text="SPFS SUBSTRATE TELEMETRY", font=("DejaVu Sans", 9, "bold"), fg=self.colors["text_muted"], bg=self.colors["panel_dark"])
        side_title.pack(anchor="w", padx=12, pady=(10, 6))

        self.telem_vars = {
            "master_f0": tk.StringVar(value="0.000000"),
            "nest_s": tk.StringVar(value="0.0"),
            "logic_f": tk.StringVar(value="1"),
            "polarity_delta_p": tk.StringVar(value="0.0000"),
            "recurrence_tick": tk.StringVar(value="0"),
            "negentropy_status": tk.StringVar(value="TRUE"),
            "negentropy_ratio": tk.StringVar(value="1.0000"),
            "ledger_balance": tk.StringVar(value="0.000000"),
            "ledger_stored": tk.StringVar(value="0.00"),
            "ledger_dissipated": tk.StringVar(value="0.00"),
            "active_whiteboard": tk.StringVar(value="STATIC_EQUILIBRIUM")
        }

        fields = [
            ("Master Formula (F_0):", "master_f0"),
            ("Nest Depth (s):", "nest_s"),
            ("Logic Tier (L_f):", "logic_f"),
            ("Polarity Vector (ΔP):", "polarity_delta_p"),
            ("Recurrence Tick (R):", "recurrence_tick"),
            ("Negentropy Bounded:", "negentropy_status"),
            ("Negentropy Ratio (stored/in):", "negentropy_ratio"),
            ("Conservation Balance:", "ledger_balance"),
            ("Ledger Stored (order):", "ledger_stored"),
            ("Ledger Dissipated (Ξ):", "ledger_dissipated"),
        ]

        for label_text, var_key in fields:
            lbl = tk.Label(sidebar, text=label_text, font=("DejaVu Sans", 8), fg=self.colors["text_muted"], bg=self.colors["panel_dark"])
            lbl.pack(anchor="w", padx=12, pady=(4, 0))
            val = tk.Label(sidebar, textvariable=self.telem_vars[var_key], font=("DejaVu Sans Mono", 9, "bold"), fg=self.colors["text_main"], bg=self.colors["panel_dark"], wraplength=270, justify=tk.LEFT)
            val.pack(anchor="w", padx=12, pady=(0, 2))

        aw_title = tk.Label(sidebar, text="Active Whiteboard (AW):", font=("DejaVu Sans", 8), fg=self.colors["text_muted"], bg=self.colors["panel_dark"])
        aw_title.pack(anchor="w", padx=12, pady=(10, 0))

        self.aw_label = tk.Label(
            sidebar, textvariable=self.telem_vars["active_whiteboard"], font=("DejaVu Sans Mono", 8),
            fg=self.colors["seeker"], bg=self.colors["input_bg"], wraplength=270, justify=tk.LEFT, relief=tk.FLAT, padx=8, pady=8
        )
        self.aw_label.pack(fill=tk.X, padx=12, pady=(4, 12))

        diag_frame = tk.Frame(sidebar, bg=self.colors["input_bg"], relief=tk.FLAT, padx=8, pady=8)
        diag_frame.pack(fill=tk.X, padx=12, pady=(4, 8))

        diag_title = tk.Label(diag_frame, text="CRYSTAL DIAGNOSTICS", font=("DejaVu Sans", 8, "bold"), fg=self.colors["text_muted"], bg=self.colors["input_bg"])
        diag_title.pack(anchor="w", pady=(0, 4))

        self.diag_vars = {
            "cpu_use": tk.StringVar(value="CPU: 0.0%"),
            "cache_use": tk.StringVar(value="RSS MEM: -- KB"),
            "ram_use": tk.StringVar(value="SYS RAM: -- %")
        }

        self.cpu_bar_lbl = tk.Label(diag_frame, textvariable=self.diag_vars["cpu_use"], font=("DejaVu Sans Mono", 8, "bold"), fg=self.colors["guide"], bg=self.colors["input_bg"])
        self.cpu_bar_lbl.pack(anchor="w")
        self.cache_lbl = tk.Label(diag_frame, textvariable=self.diag_vars["cache_use"], font=("DejaVu Sans Mono", 8), fg=self.colors["text_main"], bg=self.colors["input_bg"])
        self.cache_lbl.pack(anchor="w")
        self.ram_lbl = tk.Label(diag_frame, textvariable=self.diag_vars["ram_use"], font=("DejaVu Sans Mono", 8), fg=self.colors["text_main"], bg=self.colors["input_bg"])
        self.ram_lbl.pack(anchor="w")

        action_frame = tk.Frame(sidebar, bg=self.colors["panel_dark"])
        action_frame.pack(fill=tk.X, padx=12, pady=(4, 12))
        
        brief_btn = tk.Button(action_frame, text="SAVE BRIEF  (!brief)", font=("DejaVu Sans", 10, "bold"), bg=self.colors["button_send"], fg=self.colors["btn_text"], relief=tk.FLAT, pady=8, cursor="hand2", command=self.save_brief)
        brief_btn.pack(fill=tk.X, pady=(0, 10))

        reboot_btn = tk.Button(action_frame, text="Reboot Crystal", font=("DejaVu Sans", 8, "bold"), bg=self.colors["border"], fg=self.colors["text_main"], relief=tk.FLAT, pady=4, cursor="hand2", command=self.confirm_and_reboot)
        reboot_btn.pack(fill=tk.X, pady=(0, 4))
        clear_chat_btn = tk.Button(action_frame, text="Clear Chat Window", font=("DejaVu Sans", 8, "bold"), bg=self.colors["border"], fg=self.colors["text_main"], relief=tk.FLAT, pady=4, cursor="hand2", command=self.confirm_and_clear_chat)
        clear_chat_btn.pack(fill=tk.X)

        input_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=(4, 8))

        self.exit_btn = tk.Button(input_frame, text="EXIT", font=("DejaVu Sans", 9, "bold"), bg=self.colors["button_exit"], fg=self.colors["btn_text"], relief=tk.FLAT, padx=16, pady=6, cursor="hand2", command=self.confirm_and_exit)
        self.exit_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.input_entry = tk.Entry(input_frame, font=("DejaVu Sans Mono", 11), bg=self.colors["input_bg"], fg=self.colors["text_main"], insertbackground=self.colors["seeker"], relief=tk.FLAT, bd=6)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.input_entry.bind("<Return>", lambda event: self._on_send())

        self.send_btn = tk.Button(input_frame, text="SEND", font=("DejaVu Sans", 9, "bold"), bg=self.colors["button_send"], fg=self.colors["btn_text"], relief=tk.FLAT, padx=20, pady=6, cursor="hand2", command=self._on_send)
        self.send_btn.pack(side=tk.RIGHT)
        
    def copy_chat_to_clipboard(self):
        # dump() walks text and images in order, so the equation source can be
        # put back where its image sits.
        parts = []
        for kind, value, _ in self.chat_display.dump("1.0", tk.END, text=True, image=True):
            if kind == "text":
                parts.append(value)
            elif kind == "image":
                parts.append(getattr(self, "_math_source", {}).get(value, ""))
        text = "".join(parts).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.copy_btn.config(text="COPIED!", bg=self.colors["guide"], fg=self.colors["input_bg"])
        self.root.after(1200, lambda: self.copy_btn.config(text="COPY", bg=self.colors["panel_dark"], fg=self.colors["text_muted"]))

    def _init_engine_async(self):
        def worker():
            try:
                self.bot = EnquerantOrchestrator()
                self.root.after(0, self._on_engine_ready)
            except Exception as e:
                err_text = f"{type(e).__name__}: {e}"
                traceback.print_exc()
                self.root.after(0, lambda msg=err_text: self._on_engine_error(msg))
        threading.Thread(target=worker, daemon=True).start()

    def _on_engine_ready(self):
        self.engine_status_label.config(text="[ STATIC EQUILIBRIUM ]", fg=self.colors["guide"])
        import app as app_mod
        welcome_banner = app_mod.get_welcome_banner(self.bot)
        self._append_text(welcome_banner + "\n", tag="system")
        self._poll_substrate_telemetry()
        
    def _poll_substrate_telemetry(self):
        if self._shutting_down:
            return
        try:
            proc = psutil.Process()
            cpu_pct = proc.cpu_percent(interval=None)
            mem_info = proc.memory_info()
            rss_kb = mem_info.rss // 1024
            mem_pct = proc.memory_percent()
            bars = int(min(cpu_pct, 100) / 10)
            cpu_bar = "█" * bars + "░" * (10 - bars)
            self.diag_vars["cpu_use"].set(f"CPU: [{cpu_bar}] {cpu_pct:.1f}%")
            self.diag_vars["cache_use"].set(f"RSS MEM: {rss_kb:,} KB")
            self.diag_vars["ram_use"].set(f"SYS RAM: {mem_pct:.2f}%")
        except Exception:
            pass

        # Formula fields are owned by _update_telemetry (set once per computation).
        # This poll updates live process diagnostics only.
        if False:
            try:
                st = self.bot.spfs.state
            except Exception:
                pass

        self._poll_handle = self.root.after(1000, self._poll_substrate_telemetry)

    def _on_engine_error(self, err_msg: str):
        self.engine_status_label.config(text="[ BOOT FAILED ]", fg="#f85149")
        self._append_text(f"\n[ERROR INITIALIZING ENGINE]: {err_msg}\n\n", tag="system")

    def _insert_rule(self):
        """
        Draws a markdown horizontal rule as an embedded frame. A run of
        characters has a fixed width; a frame is managed by the geometry
        manager, so it spans the widget and follows a resize.
        """
        bar = tk.Frame(self.chat_display, height=1, bg=self.colors["border"])
        bar.pack_propagate(False)
        self.chat_display.window_create(tk.END, window=bar, stretch=0, padx=0, pady=6)
        if not hasattr(self, "_rules"):
            self._rules = []
        self._rules.append(bar)
        bar.config(width=max(self.chat_display.winfo_width() - 8, 1))
        self.chat_display.bind("<Configure>", self._resize_rules, add="+")

    def _resize_rules(self, event=None):
        w = max(self.chat_display.winfo_width() - 8, 1)
        for bar in getattr(self, "_rules", []):
            try:
                bar.config(width=w)
            except tk.TclError:
                pass

    def _append_text(self, text: str, tag: str = "body"):
        """
        Renders incoming text streams with strict separation between prose, headers,
        and inline math tokens, preventing style bleed.
        """
        self.chat_display.config(state=tk.NORMAL)
        
        if tag in ("seeker", "guide", "system"):
            # Inserted line by line rather than whole, so a separator line can
            # be drawn as a rule. The banner and the documentation files both
            # arrive on this path, and a single insert never sees a line.
            for i, line in enumerate(text.split("\n")):
                if i:
                    self.chat_display.insert(tk.END, "\n", tag)
                s = line.strip()
                if len(s) >= 3 and len(set(s)) == 1 and s[0] in "-=_*":
                    self._insert_rule()
                else:
                    self.chat_display.insert(tk.END, line, tag)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)
            return

        lines = text.split("\n")
        for line in lines:
            trimmed = line.strip()
            line_tag = "body"
            apply_card = False
            
            # A line of three or more -, =, _ or * is a horizontal rule. The
            # banner and the documentation files both use them as separators.
            if len(trimmed) >= 3 and len(set(trimmed)) == 1 and trimmed[0] in "-=_*":
                self._insert_rule()
                self.chat_display.insert(tk.END, "\n")
                continue

            if trimmed.startswith("### "):
                line_tag = "h1"
                line = trimmed[4:]
                apply_card = True
            elif trimmed.startswith("> *"):
                line_tag = "system"
                line = trimmed[2:].replace("*", "")
            elif trimmed.startswith("- ") or trimmed.startswith("• "):
                line = "  • " + trimmed[2:]

            line = self._preprocess_math_text(line)
            start_index = self.chat_display.index(tk.INSERT)
            
            # Tokenize safely, keeping prose and equations strictly separated
            tokens = re.split(r'(\$.*?\$|\*\*.*?\*\*)', line)
            for token in tokens:
                if not token:
                    continue
                if token.startswith("**") and token.endswith("**"):
                    # A label can carry math ("**1. Master Formula ($F_0$):**").
                    # Inserted whole it renders as raw source, so the label is
                    # split again and its math rendered inside the bold run.
                    for sub in re.split(r'(\$.*?\$)', token[2:-2]):
                        if not sub:
                            continue
                        if sub.startswith("$") and sub.endswith("$") and len(sub) > 2:
                            img = self._render_latex_inline(sub)
                            if img:
                                name = self.chat_display.image_create(tk.END, image=img)
                                if not hasattr(self, "_math_source"):
                                    self._math_source = {}
                                self._math_source[name] = sub
                                continue
                            sub = sub.replace("$", "")
                        self.chat_display.insert(tk.END, sub, ("bold",))
                elif token.startswith("$") and token.endswith("$") and len(token) > 2:
                    img_photo = self._render_latex_inline(token)
                    if img_photo:
                        # An image holds no text, so the clipboard would lose
                        # the equation. The source is kept against the image's
                        # widget name and restored on copy.
                        name = self.chat_display.image_create(tk.END, image=img_photo)
                        if not hasattr(self, "_math_source"):
                            self._math_source = {}
                        self._math_source[name] = token
                    else:
                        clean_fallback = token.replace("$", "").replace(r"\to", "→")
                        self.chat_display.insert(tk.END, clean_fallback, ("equation",))
                else:
                    # Clean prose text—ensures normal color and proper spacing
                    cleaned_token = token.replace("`", "").replace("*", "")
                    self.chat_display.insert(tk.END, cleaned_token, (line_tag,))
            
            self.chat_display.insert(tk.END, "\n", (line_tag,))
            
            if apply_card:
                end_index = self.chat_display.index(tk.INSERT)
                self.chat_display.tag_add("card_block", start_index, end_index)

        # Canonical Tkinter highlighter: search and tag target strings directly
        for pattern, tag_name in [
            ("[SPFS Proprietary]", "tag_proprietary"),
            ("[Potential Placeholder / Ontological Shift]", "tag_dislocation")
        ]:
            pos = "1.0"
            while True:
                pos = self.chat_display.search(pattern, pos, stopindex=tk.END)
                if not pos:
                    break
                end = f"{pos}+{len(pattern)}c"
                self.chat_display.tag_add(tag_name, pos, end)
                pos = end

        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def _update_telemetry(self, t: dict):
        self.telem_vars["master_f0"].set(str(t.get("F_0", "0.000000")))
        self.telem_vars["nest_s"].set(str(t.get("N_s", "0.0")))
        self.telem_vars["logic_f"].set(str(t.get("L_f", "1")))
        self.telem_vars["polarity_delta_p"].set(str(t.get("Delta_P", "0.0000")))
        self.telem_vars["recurrence_tick"].set(str(t.get("Recurrence_Tick", "0")))
        self.telem_vars["negentropy_status"].set("TRUE" if t.get("Negentropy_Bounded", True) else "FALSE")
        self.telem_vars["negentropy_ratio"].set(str(t.get("Negentropy_Ratio", "—")))
        self.telem_vars["ledger_balance"].set(str(t.get("Ledger_Balance", "—")))
        self.telem_vars["ledger_stored"].set(str(t.get("Ledger_Stored", "—")))
        self.telem_vars["ledger_dissipated"].set(str(t.get("Ledger_Dissipated", "—")))
        self.telem_vars["active_whiteboard"].set(t.get("algebraic_state", "STATIC_EQUILIBRIUM"))

    def _on_send(self):
        query = self.input_entry.get().strip()
        if not query or self.is_streaming or not self.bot:
            return
        self.input_entry.delete(0, tk.END)
        self.is_streaming = True
        self.send_btn.config(state=tk.DISABLED)

        self._append_text(f"Seeker > {query}\n\n", tag="seeker")
        self._append_text("EnQuerant >\n", tag="guide")

        def stream_worker():
            try:
                for packet in self.bot.stream_turn(query, chunk_delay=0.015):
                    if packet["type"] == "token":
                        self.root.after(0, lambda c=packet["content"]: self._append_text(c, tag="body"))
                    elif packet["type"] == "done":
                        self.root.after(0, lambda: self._append_text("\n", tag="body"))
                        self.root.after(0, lambda t=packet["telemetry"]: self._update_telemetry(t))
            except Exception as e:
                err_msg = f"\n[STREAM ERROR]: {e}\n\n"
                self.root.after(0, lambda msg=err_msg: self._append_text(msg, tag="system"))
            finally:
                if not self._shutting_down:
                    self.root.after(0, self._on_stream_complete)

        threading.Thread(target=stream_worker, daemon=True).start()

    def _on_stream_complete(self):
        self.is_streaming = False
        self.send_btn.config(state=tk.NORMAL)
        self.input_entry.focus_set()
    
    def save_brief(self):
        """Same as typing !brief: writes the last reading to briefs/."""
        if not self.bot or self.is_streaming:
            return
        self._append_text("Seeker > !brief\n\n", tag="seeker")
        self._append_text("EnQuerant >\n", tag="guide")
        self._append_text(self.bot._write_brief() + "\n\n", tag="body")

    def confirm_and_reboot(self):
        if messagebox.askyesno("Reboot Crystal", "Hot-reload substrate modules from disk and clear chat?"):
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)
            def worker():
                try:
                    if self.bot:
                        self.bot.close()
                    import importlib
                    import app as app_mod
                    import spfs_engine as spfs_mod
                    import crystal_loader as cl_mod
                    import cs_algebraic_parser as cs_mod
                    import active_whiteboard as aw_mod
                    for _mod in (spfs_mod, cl_mod, cs_mod, aw_mod, app_mod):
                        importlib.reload(_mod)
                    self.bot = app_mod.EnquerantOrchestrator()
                    self.root.after(0, self._on_engine_ready)
                except Exception as e:
                    self.root.after(0, lambda msg=str(e): self._on_engine_error(msg))
            threading.Thread(target=worker, daemon=True).start()

    def confirm_and_clear_chat(self):
        if messagebox.askyesno("Clear Chat Window", "Clear active chat transcript?"):
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)

    def confirm_and_exit(self):
        if messagebox.askyesno("Exit EnQuerant", "Terminate EnQuerant?"):
            self._shutting_down = True
            if self._poll_handle:
                self.root.after_cancel(self._poll_handle)
            if self.bot:
                self.bot.close()
            self.root.destroy()


def main():
    root = tk.Tk()
    app = EnquerantGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.confirm_and_exit)
    root.mainloop()


if __name__ == "__main__":
    main()
