"""Thumbnail Maker — a small cross-platform GUI (Windows / macOS / Linux).

Pick an input folder of photos and an output folder; the app batch-renders
1280x720 thumbnails from an editable SVG **template**. The title for each
thumbnail comes from the photo's file name ('feet-first.jpg' -> 'FEET FIRST'),
or from an optional CSV; the subtitle and chosen template apply to the batch.

Design lives in the template SVG (templates/*.svg), not in this code — pick a
different one or edit/duplicate to restyle. Settings persist between launches.
Run:  python app.py
"""

from __future__ import annotations

import glob
import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

import render
import settings
from version import __version__


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=14)
        self.master = master
        master.title(f"Thumbnail Maker {__version__}")
        master.minsize(920, 600)
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._cfg = settings.load()

        # State (seeded from saved settings)
        self.in_var = tk.StringVar(value=self._cfg.get("input_folder", ""))
        self.out_var = tk.StringVar(value=self._cfg.get("output_folder", ""))
        self.subtitle_var = tk.StringVar(value=self._cfg.get("subtitle", render.DEFAULT_SUBTITLE))
        self.template_var = tk.StringVar()
        self.csv_var = tk.StringVar(value=self._cfg.get("csv_path", ""))
        self.upper_var = tk.BooleanVar(value=self._cfg.get("uppercase", True))
        self.status_var = tk.StringVar(value="Pick an input folder to begin.")
        self._preview_imgtk = None
        self._worker = None
        self._templates: dict[str, str] = {}   # label -> path

        self._discover_templates()
        self._build_controls()
        self._build_preview()

        master.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.in_var.get():
            self._schedule_preview()

    # ---- templates ------------------------------------------------------
    def _discover_templates(self):
        """Populate label->path from built-in + remembered custom templates."""
        self._templates = {}
        paths = sorted(glob.glob(os.path.join(render.TEMPLATES_DIR, "*.svg")))
        for p in paths:
            self._register_template(p)
        for p in self._cfg.get("custom_templates", []):
            if os.path.exists(p):
                self._register_template(p)

        # Restore the previously-selected template, else the default.
        want = self._cfg.get("template_path")
        label = self._label_for_path(want) if want else None
        if not label:
            label = self._label_for_path(render.DEFAULT_TEMPLATE) or next(iter(self._templates), "")
        self.template_var.set(label)

    def _register_template(self, path: str) -> str:
        """Add a template, giving it a unique label; return the label."""
        path = os.path.abspath(path)
        for lbl, p in self._templates.items():
            if os.path.normcase(p) == os.path.normcase(path):
                return lbl  # already known
        base = os.path.splitext(os.path.basename(path))[0]
        label, i = base, 2
        while label in self._templates:
            label, i = f"{base} ({i})", i + 1
        self._templates[label] = path
        return label

    def _label_for_path(self, path: str | None) -> str | None:
        if not path:
            return None
        for lbl, p in self._templates.items():
            if os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(path)):
                return lbl
        return None

    def _template_path(self) -> str:
        return self._templates.get(self.template_var.get(), render.DEFAULT_TEMPLATE)

    # ---- layout ---------------------------------------------------------
    def _folder_row(self, r, label, var, cmd):
        ttk.Label(self, text=label).grid(row=r, column=0, sticky="w")
        row = ttk.Frame(self); row.grid(row=r + 1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse…", command=cmd).grid(row=0, column=1, padx=(6, 0))
        return r + 2

    def _build_controls(self):
        r = 0
        r = self._folder_row(r, "Input folder (photos)", self.in_var, self._pick_in)
        r = self._folder_row(r, "Output folder", self.out_var, self._pick_out)

        box = ttk.LabelFrame(self, text="Template & text", padding=10)
        box.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        box.columnconfigure(1, weight=1)

        # Template chooser: dropdown of known templates + Browse for any .svg.
        ttk.Label(box, text="Template (.svg)").grid(row=0, column=0, sticky="w", pady=2)
        self.template_combo = ttk.Combobox(box, textvariable=self.template_var,
                                            values=list(self._templates), state="readonly")
        self.template_combo.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=2)
        self.template_combo.bind("<<ComboboxSelected>>", lambda e: (self._save_settings(), self._schedule_preview()))
        ttk.Button(box, text="Browse…", command=self._pick_template).grid(row=0, column=2, sticky="w")

        ttk.Label(box, text="Subtitle").grid(row=1, column=0, sticky="w", pady=2)
        sub = ttk.Entry(box, textvariable=self.subtitle_var)
        sub.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=2)
        sub.bind("<KeyRelease>", lambda e: self._schedule_preview())

        # Optional CSV of per-photo titles/fields.
        ttk.Label(box, text="Titles CSV (optional)").grid(row=2, column=0, sticky="w", pady=2)
        csv_row = ttk.Frame(box); csv_row.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=2)
        csv_row.columnconfigure(0, weight=1)
        ttk.Entry(csv_row, textvariable=self.csv_var, state="readonly").grid(row=0, column=0, sticky="ew")
        ttk.Button(csv_row, text="Browse…", command=self._pick_csv).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(csv_row, text="Clear", command=self._clear_csv).grid(row=0, column=2, padx=(6, 0))

        ttk.Checkbutton(box, text="UPPERCASE", variable=self.upper_var,
                        command=lambda: (self._save_settings(), self._schedule_preview())
                        ).grid(row=3, column=1, sticky="w", padx=(6, 0))
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

    # ---- settings -------------------------------------------------------
    def _save_settings(self):
        self._cfg.update({
            "input_folder": self.in_var.get(),
            "output_folder": self.out_var.get(),
            "subtitle": self.subtitle_var.get(),
            "uppercase": bool(self.upper_var.get()),
            "template_path": self._template_path(),
            "custom_templates": self._custom_template_paths(),
            "csv_path": self.csv_var.get(),
        })
        settings.save(self._cfg)

    def _custom_template_paths(self) -> list[str]:
        builtin = {os.path.normcase(os.path.abspath(p))
                   for p in glob.glob(os.path.join(render.TEMPLATES_DIR, "*.svg"))}
        return [p for p in self._templates.values()
                if os.path.normcase(os.path.abspath(p)) not in builtin]

    def _on_close(self):
        self._save_settings()
        self.master.destroy()

    # ---- handlers -------------------------------------------------------
    def _pick_in(self):
        d = filedialog.askdirectory(title="Select input folder", initialdir=self.in_var.get() or None)
        if d:
            self.in_var.set(d)
            if not self.out_var.get():
                self.out_var.set(os.path.join(d, "thumbnails"))
            self._save_settings()
            self._schedule_preview()

    def _pick_out(self):
        d = filedialog.askdirectory(title="Select output folder", initialdir=self.out_var.get() or None)
        if d:
            self.out_var.set(d)
            self._save_settings()

    def _pick_template(self):
        p = filedialog.askopenfilename(title="Choose an SVG template",
                                       filetypes=[("SVG template", "*.svg")],
                                       initialdir=os.path.dirname(self._template_path()) or None)
        if p:
            label = self._register_template(p)
            self.template_combo.configure(values=list(self._templates))
            self.template_var.set(label)
            self._save_settings()
            self._schedule_preview()

    def _pick_csv(self):
        p = filedialog.askopenfilename(title="Choose a titles CSV",
                                       filetypes=[("CSV / spreadsheet", "*.csv *.tsv"), ("All files", "*.*")])
        if p:
            self.csv_var.set(p)
            self._save_settings()
            self._schedule_preview()

    def _clear_csv(self):
        self.csv_var.set("")
        self._save_settings()
        self._schedule_preview()

    def _overrides(self) -> dict[str, dict[str, str]]:
        path = self.csv_var.get()
        if path and os.path.exists(path):
            try:
                return render.load_titles_csv(path)
            except Exception as e:
                self.status_var.set(f"Could not read CSV: {e}")
        return {}

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
        self._save_settings()  # subtitle edits land here (debounced)
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
            overrides = self._overrides().get(os.path.basename(path))
            arg = overrides if overrides else render.title_from_filename(path)
            img = render.render_thumbnail(path, arg, self._current_style())
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

        self._save_settings()
        style = self._current_style()
        overrides = self._overrides()
        self.gen_btn.configure(state="disabled")
        self.progress.configure(maximum=len(images), value=0)
        self._errors = []

        def progress(done, total, name, err):
            if err:
                self._errors.append((name, err))
            self.after(0, lambda: self._on_progress(done, total, name))

        def work():
            written = render.batch_render(in_folder, out_folder, style,
                                          csv_overrides=overrides, progress=progress)
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
