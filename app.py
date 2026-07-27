"""Thumbnail Maker — a small cross-platform GUI (Windows / macOS / Linux).

Pick an input folder of photos and an output folder; the app batch-renders
1280x720 thumbnails from an editable SVG **template**. The title for each
thumbnail comes from the photo's file name ('feet-first.jpg' -> 'FEET FIRST');
the subtitle and the chosen template apply to the whole batch.

Design lives in the template SVG (templates/*.svg), not in this code — duplicate
and edit one to restyle. Run:  python app.py
"""

from __future__ import annotations

import glob
import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

import render
from version import __version__


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=14)
        self.master = master
        master.title(f"Thumbnail Maker {__version__}")
        master.minsize(900, 560)
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # State
        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.subtitle_var = tk.StringVar(value=render.DEFAULT_SUBTITLE)
        self.template_var = tk.StringVar()
        self.upper_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Pick an input folder to begin.")
        self._preview_imgtk = None
        self._worker = None
        self._templates: dict[str, str] = {}   # label -> path

        self._discover_templates()
        self._build_controls()
        self._build_preview()

    # ---- templates ------------------------------------------------------
    def _discover_templates(self):
        self._templates = {}
        for path in sorted(glob.glob(os.path.join(render.TEMPLATES_DIR, "*.svg"))):
            self._templates[os.path.splitext(os.path.basename(path))[0]] = path
        if not self.template_var.get() and self._templates:
            default_label = os.path.splitext(os.path.basename(render.DEFAULT_TEMPLATE))[0]
            self.template_var.set(default_label if default_label in self._templates
                                  else next(iter(self._templates)))

    def _template_path(self) -> str:
        return self._templates.get(self.template_var.get(), render.DEFAULT_TEMPLATE)

    # ---- layout ---------------------------------------------------------
    def _build_controls(self):
        r = 0
        ttk.Label(self, text="Input folder (photos)").grid(row=r, column=0, sticky="w"); r += 1
        row = ttk.Frame(self); row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.in_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse…", command=self._pick_in).grid(row=0, column=1, padx=(6, 0)); r += 1

        ttk.Label(self, text="Output folder").grid(row=r, column=0, sticky="w"); r += 1
        row = ttk.Frame(self); row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.out_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse…", command=self._pick_out).grid(row=0, column=1, padx=(6, 0)); r += 1

        style_box = ttk.LabelFrame(self, text="Template & text", padding=10)
        style_box.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        style_box.columnconfigure(1, weight=1)

        ttk.Label(style_box, text="Template").grid(row=0, column=0, sticky="w", pady=2)
        self.template_combo = ttk.Combobox(style_box, textvariable=self.template_var,
                                           values=list(self._templates), state="readonly")
        self.template_combo.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=2)
        self.template_combo.bind("<<ComboboxSelected>>", lambda e: self._schedule_preview())
        ttk.Button(style_box, text="Add…", command=self._pick_template).grid(row=0, column=2, sticky="w")

        ttk.Label(style_box, text="Subtitle").grid(row=1, column=0, sticky="w", pady=2)
        sub = ttk.Entry(style_box, textvariable=self.subtitle_var)
        sub.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=2)
        sub.bind("<KeyRelease>", lambda e: self._schedule_preview())

        ttk.Checkbutton(style_box, text="UPPERCASE", variable=self.upper_var,
                        command=self._schedule_preview).grid(row=2, column=1, sticky="w", padx=(6, 0))
        r += 1

        act = ttk.Frame(self); act.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        act.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(act, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.gen_btn = ttk.Button(act, text="Generate thumbnails", command=self._generate)
        self.gen_btn.grid(row=0, column=1); r += 1

        footer = ttk.Frame(self); footer.grid(row=r, column=0, columnspan=2, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var, foreground="#555").grid(row=0, column=0, sticky="w")
        ttk.Label(footer, text=f"v{__version__}", foreground="#999").grid(row=0, column=1, sticky="e")
        self._controls_last_row = r

    def _build_preview(self):
        box = ttk.LabelFrame(self, text="Preview (first image)", padding=8)
        box.grid(row=0, column=2, rowspan=self._controls_last_row + 1, sticky="nsew", padx=(14, 0))
        self.columnconfigure(2, weight=0)
        self.preview_label = ttk.Label(box, text="No preview yet", anchor="center",
                                       width=52, background="#222", foreground="#ccc")
        self.preview_label.grid(sticky="nsew")
        box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)

    # ---- handlers -------------------------------------------------------
    def _pick_in(self):
        d = filedialog.askdirectory(title="Select input folder")
        if d:
            self.in_var.set(d)
            if not self.out_var.get():
                self.out_var.set(os.path.join(d, "thumbnails"))
            self._schedule_preview()

    def _pick_out(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.out_var.set(d)

    def _pick_template(self):
        p = filedialog.askopenfilename(title="Choose an SVG template",
                                       filetypes=[("SVG template", "*.svg")])
        if p:
            label = os.path.splitext(os.path.basename(p))[0]
            self._templates[label] = p
            self.template_combo.configure(values=list(self._templates))
            self.template_var.set(label)
            self._schedule_preview()

    def _current_style(self) -> render.Style:
        return render.Style(
            template_path=self._template_path(),
            subtitle=self.subtitle_var.get(),
            uppercase=self.upper_var.get(),
        )

    def _schedule_preview(self, *_):
        if getattr(self, "_preview_job", None):
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(300, self._render_preview)

    def _render_preview(self):
        self._preview_job = None
        folder = self.in_var.get()
        if not folder or not os.path.isdir(folder):
            return
        images = render.list_images(folder)
        if not images:
            self.preview_label.configure(image="", text="No images found in input folder")
            self._preview_imgtk = None
            return
        try:
            path = images[0]
            img = render.render_thumbnail(path, render.title_from_filename(path), self._current_style())
            preview = img.resize((480, 270), Image.LANCZOS)
            self._preview_imgtk = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self._preview_imgtk, text="")
        except Exception as e:
            self.preview_label.configure(image="", text=f"Preview error:\n{e}")
            self._preview_imgtk = None

    def _generate(self):
        if self._worker and self._worker.is_alive():
            return
        in_folder, out_folder = self.in_var.get(), self.out_var.get()
        if not in_folder or not os.path.isdir(in_folder):
            self.status_var.set("Please choose a valid input folder."); return
        if not out_folder:
            self.status_var.set("Please choose an output folder."); return
        images = render.list_images(in_folder)
        if not images:
            self.status_var.set("No images found in the input folder."); return

        style = self._current_style()
        self.gen_btn.configure(state="disabled")
        self.progress.configure(maximum=len(images), value=0)
        self._errors = []

        def progress(done, total, name, err):
            if err:
                self._errors.append((name, err))
            self.after(0, lambda: self._on_progress(done, total, name))

        def work():
            written = render.batch_render(in_folder, out_folder, style, progress=progress)
            self.after(0, lambda: self._on_done(len(written), out_folder))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _on_progress(self, done, total, name):
        self.progress.configure(value=done)
        self.status_var.set(f"Rendering {done}/{total}: {name}")

    def _on_done(self, count, out_folder):
        self.gen_btn.configure(state="normal")
        msg = f"Done. Wrote {count} thumbnail(s) to {out_folder}."
        if getattr(self, "_errors", None):
            msg += f"  ({len(self._errors)} skipped — see console.)"
            for name, err in self._errors:
                print(f"[skip] {name}: {err}")
        self.status_var.set(msg)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
