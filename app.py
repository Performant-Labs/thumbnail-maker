"""Thumbnail Maker — a small cross-platform GUI (Windows / macOS / Linux).

Two independent tools live in tabs:

* **Single** — craft one thumbnail from one photo with a title you type.
* **Batch** — turn a whole folder of photos into thumbnails (titles from file
  names or a CSV).

Both use the same fields (template, subtitle, uppercase, …) but keep their own,
separate values. The design itself comes from an editable SVG template
(templates/*.svg). Settings persist between launches. Run:  python app.py
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

PREVIEW_W, PREVIEW_H = 480, 270


# ---------------------------------------------------------------------------
# Shared base for both tabs
# ---------------------------------------------------------------------------

class BasePanel(ttk.Frame):
    """Common fields (template / subtitle / uppercase) + live preview.

    Subclasses add their own input/output rows and an action button, and
    implement `_preview_source()` and `settings_dict()`.
    """

    def __init__(self, master, app: "App", cfg: dict):
        super().__init__(master, padding=14)
        self.app = app
        self.columnconfigure(1, weight=1)

        self.subtitle_var = tk.StringVar(value=cfg.get("subtitle", render.DEFAULT_SUBTITLE))
        self.template_var = tk.StringVar(value=app.label_for_path(cfg.get("template_path")))
        self.upper_var = tk.BooleanVar(value=cfg.get("uppercase", True))
        self.status_var = tk.StringVar(value="")
        self._preview_imgtk = None
        self._preview_job = None
        self.template_combo: ttk.Combobox | None = None

    # ---- shared row builders (return next grid row) ----
    def _template_row(self, r):
        ttk.Label(self, text="Template (.svg)").grid(row=r, column=0, sticky="w", pady=2)
        row = ttk.Frame(self); row.grid(row=r, column=1, sticky="ew", pady=2)
        row.columnconfigure(0, weight=1)
        self.template_combo = ttk.Combobox(row, textvariable=self.template_var,
                                           values=self.app.template_labels(), state="readonly")
        self.template_combo.grid(row=0, column=0, sticky="ew")
        self.template_combo.bind("<<ComboboxSelected>>",
                                 lambda e: (self.app.save_settings(), self._schedule_preview()))
        ttk.Button(row, text="Browse…", command=self._pick_template).grid(row=0, column=1, padx=(6, 0))
        return r + 1

    def _subtitle_row(self, r):
        ttk.Label(self, text="Subtitle").grid(row=r, column=0, sticky="w", pady=2)
        e = ttk.Entry(self, textvariable=self.subtitle_var)
        e.grid(row=r, column=1, sticky="ew", pady=2)
        e.bind("<KeyRelease>", lambda ev: self._schedule_preview())
        return r + 1

    def _uppercase_row(self, r):
        ttk.Checkbutton(self, text="UPPERCASE", variable=self.upper_var,
                        command=lambda: (self.app.save_settings(), self._schedule_preview())
                        ).grid(row=r, column=1, sticky="w", pady=2)
        return r + 1

    def _preview_row(self, r):
        box = ttk.LabelFrame(self, text="Preview", padding=8)
        box.grid(row=r, column=0, columnspan=2, sticky="nsew", pady=(8, 4))
        self.rowconfigure(r, weight=1)
        self.preview_label = ttk.Label(box, text="No preview yet", anchor="center",
                                       background="#222", foreground="#ccc",
                                       width=52)
        self.preview_label.grid(sticky="nsew")
        box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
        return r + 1

    def _status_row(self, r):
        ttk.Label(self, textvariable=self.status_var, foreground="#555").grid(
            row=r, column=0, columnspan=2, sticky="w")
        return r + 1

    def _folder_row(self, r, label, var, cmd):
        ttk.Label(self, text=label).grid(row=r, column=0, sticky="w", pady=2)
        row = ttk.Frame(self); row.grid(row=r, column=1, sticky="ew", pady=2)
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse…", command=cmd).grid(row=0, column=1, padx=(6, 0))
        return r + 1

    # ---- template handling ----
    def refresh_templates(self):
        if self.template_combo is not None:
            self.template_combo.configure(values=self.app.template_labels())

    def _pick_template(self):
        p = filedialog.askopenfilename(title="Choose an SVG template",
                                       filetypes=[("SVG template", "*.svg")],
                                       initialdir=os.path.dirname(self._template_path()) or None)
        if p:
            label = self.app.add_template(p)   # refreshes every tab's dropdown
            self.template_var.set(label)
            self.app.save_settings()
            self._schedule_preview()

    def _template_path(self) -> str:
        return self.app.template_path(self.template_var.get())

    def _current_style(self) -> render.Style:
        return render.Style(template_path=self._template_path(),
                            subtitle=self.subtitle_var.get(),
                            uppercase=self.upper_var.get())

    # ---- preview ----
    def _schedule_preview(self, *_):
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(300, self._render_preview)

    def _render_preview(self):
        self._preview_job = None
        self.app.save_settings()  # debounced text edits land here
        src = self._preview_source()
        if src is None:
            self.preview_label.configure(image="", text=self._empty_preview_text())
            self._preview_imgtk = None
            return
        photo_path, arg = src
        try:
            img = render.render_thumbnail(photo_path, arg, self._current_style())
            preview = img.resize((PREVIEW_W, PREVIEW_H), Image.LANCZOS)
            self._preview_imgtk = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self._preview_imgtk, text="")
        except Exception as e:
            self.preview_label.configure(image="", text=f"Preview error:\n{e}")
            self._preview_imgtk = None

    # ---- to be provided by subclasses ----
    def _preview_source(self):
        raise NotImplementedError

    def _empty_preview_text(self) -> str:
        return "No preview yet"

    def settings_dict(self) -> dict:
        return {
            "subtitle": self.subtitle_var.get(),
            "uppercase": bool(self.upper_var.get()),
            "template_path": self._template_path(),
        }


# ---------------------------------------------------------------------------
# Single thumbnail tab
# ---------------------------------------------------------------------------

class SinglePanel(BasePanel):
    def __init__(self, master, app, cfg):
        super().__init__(master, app, cfg)
        self.image_var = tk.StringVar(value=cfg.get("input_image", ""))
        self.title_var = tk.StringVar(value=cfg.get("title", ""))
        self.out_var = tk.StringVar(value=cfg.get("output_folder", ""))

        r = 0
        r = self._image_row(r)
        ttk.Label(self, text="Title").grid(row=r, column=0, sticky="w", pady=2)
        te = ttk.Entry(self, textvariable=self.title_var)
        te.grid(row=r, column=1, sticky="ew", pady=2)
        te.bind("<KeyRelease>", lambda e: self._schedule_preview()); r += 1
        r = self._subtitle_row(r)
        r = self._template_row(r)
        r = self._uppercase_row(r)
        r = self._folder_row(r, "Output folder", self.out_var, self._pick_out)
        self.make_btn = ttk.Button(self, text="Create thumbnail", command=self._create)
        self.make_btn.grid(row=r, column=1, sticky="w", pady=(4, 4)); r += 1
        r = self._preview_row(r)
        r = self._status_row(r)

        if self.image_var.get():
            self._schedule_preview()

    def _image_row(self, r):
        ttk.Label(self, text="Photo").grid(row=r, column=0, sticky="w", pady=2)
        row = ttk.Frame(self); row.grid(row=r, column=1, sticky="ew", pady=2)
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.image_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse…", command=self._pick_image).grid(row=0, column=1, padx=(6, 0))
        return r + 1

    def _pick_image(self):
        exts = " ".join(f"*{e}" for e in sorted(render.IMAGE_EXTS))
        p = filedialog.askopenfilename(title="Choose a photo",
                                       filetypes=[("Images", exts), ("All files", "*.*")],
                                       initialdir=os.path.dirname(self.image_var.get()) or None)
        if p:
            self.image_var.set(p)
            if not self.title_var.get():
                self.title_var.set(render.title_from_filename(p))
            if not self.out_var.get():
                self.out_var.set(os.path.dirname(p))
            self.app.save_settings()
            self._schedule_preview()

    def _pick_out(self):
        d = filedialog.askdirectory(title="Select output folder", initialdir=self.out_var.get() or None)
        if d:
            self.out_var.set(d)
            self.app.save_settings()

    def _title_or_filename(self) -> str:
        img = self.image_var.get()
        return self.title_var.get().strip() or (render.title_from_filename(img) if img else "")

    def _preview_source(self):
        img = self.image_var.get()
        if not img or not os.path.isfile(img):
            return None
        return img, self._title_or_filename()

    def _empty_preview_text(self):
        return "Choose a photo to preview"

    def _create(self):
        img = self.image_var.get()
        out_dir = self.out_var.get()
        if not img or not os.path.isfile(img):
            self.status_var.set("Please choose a photo."); return
        if not out_dir:
            self.status_var.set("Please choose an output folder."); return
        try:
            os.makedirs(out_dir, exist_ok=True)
            result = render.render_thumbnail(img, self._title_or_filename(), self._current_style())
            stem = os.path.splitext(os.path.basename(img))[0]
            out_path = os.path.join(out_dir, f"{stem}_thumb.jpg")
            result.save(out_path, "JPEG", quality=90)
            self.status_var.set(f"Saved {out_path}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    def settings_dict(self):
        d = super().settings_dict()
        d.update({"input_image": self.image_var.get(),
                  "title": self.title_var.get(),
                  "output_folder": self.out_var.get()})
        return d


# ---------------------------------------------------------------------------
# Batch tab
# ---------------------------------------------------------------------------

class BatchPanel(BasePanel):
    def __init__(self, master, app, cfg):
        super().__init__(master, app, cfg)
        self.in_var = tk.StringVar(value=cfg.get("input_folder", ""))
        self.out_var = tk.StringVar(value=cfg.get("output_folder", ""))
        self.csv_var = tk.StringVar(value=cfg.get("csv_path", ""))
        self._worker = None

        r = 0
        r = self._folder_row(r, "Input folder (photos)", self.in_var, self._pick_in)
        r = self._folder_row(r, "Output folder", self.out_var, self._pick_out)
        r = self._subtitle_row(r)
        r = self._template_row(r)
        r = self._csv_row(r)
        r = self._uppercase_row(r)

        act = ttk.Frame(self); act.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(4, 4))
        act.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(act, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.gen_btn = ttk.Button(act, text="Generate thumbnails", command=self._generate)
        self.gen_btn.grid(row=0, column=1); r += 1

        r = self._preview_row(r)
        r = self._status_row(r)

        if self.in_var.get():
            self._schedule_preview()

    def _csv_row(self, r):
        ttk.Label(self, text="Titles CSV (optional)").grid(row=r, column=0, sticky="w", pady=2)
        row = ttk.Frame(self); row.grid(row=r, column=1, sticky="ew", pady=2)
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.csv_var, state="readonly").grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse…", command=self._pick_csv).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(row, text="Clear", command=self._clear_csv).grid(row=0, column=2, padx=(6, 0))
        return r + 1

    def _pick_in(self):
        d = filedialog.askdirectory(title="Select input folder", initialdir=self.in_var.get() or None)
        if d:
            self.in_var.set(d)
            if not self.out_var.get():
                self.out_var.set(os.path.join(d, "thumbnails"))
            self.app.save_settings()
            self._schedule_preview()

    def _pick_out(self):
        d = filedialog.askdirectory(title="Select output folder", initialdir=self.out_var.get() or None)
        if d:
            self.out_var.set(d)
            self.app.save_settings()

    def _pick_csv(self):
        p = filedialog.askopenfilename(title="Choose a titles CSV",
                                       filetypes=[("CSV / spreadsheet", "*.csv *.tsv"), ("All files", "*.*")])
        if p:
            self.csv_var.set(p)
            self.app.save_settings()
            self._schedule_preview()

    def _clear_csv(self):
        self.csv_var.set("")
        self.app.save_settings()
        self._schedule_preview()

    def _overrides(self):
        path = self.csv_var.get()
        if path and os.path.exists(path):
            try:
                return render.load_titles_csv(path)
            except Exception as e:
                self.status_var.set(f"Could not read CSV: {e}")
        return {}

    def _preview_source(self):
        folder = self.in_var.get()
        if not folder or not os.path.isdir(folder):
            return None
        images = render.list_images(folder)
        if not images:
            return None
        path = images[0]
        overrides = self._overrides().get(os.path.basename(path))
        return path, (overrides if overrides else render.title_from_filename(path))

    def _empty_preview_text(self):
        return "Choose an input folder with images"

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

        self.app.save_settings()
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

    def settings_dict(self):
        d = super().settings_dict()
        d.update({"input_folder": self.in_var.get(),
                  "output_folder": self.out_var.get(),
                  "csv_path": self.csv_var.get()})
        return d


# ---------------------------------------------------------------------------
# Application shell (owns the template library + persistence)
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"Thumbnail Maker {__version__}")
        root.minsize(560, 640)
        self._cfg = settings.load()

        # Template library shared by both tabs (selection stays per-tab).
        self._templates: dict[str, str] = {}
        for p in sorted(glob.glob(os.path.join(render.TEMPLATES_DIR, "*.svg"))):
            self._register(p)
        for p in self._cfg.get("custom_templates", []):
            if os.path.exists(p):
                self._register(p)

        outer = ttk.Frame(root, padding=8)
        outer.pack(fill="both", expand=True)
        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        self.single = SinglePanel(nb, self, self._cfg.get("single", {}))
        self.batch = BatchPanel(nb, self, self._cfg.get("batch", {}))
        nb.add(self.single, text="  Single  ")
        nb.add(self.batch, text="  Batch  ")
        self.notebook = nb
        try:
            nb.select(int(self._cfg.get("active_tab", 0)))
        except (tk.TclError, ValueError):
            pass

        ttk.Label(outer, text=f"v{__version__}", foreground="#999").pack(anchor="e", pady=(4, 0))
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- template library ----
    def _register(self, path: str) -> str:
        path = os.path.abspath(path)
        for lbl, p in self._templates.items():
            if os.path.normcase(p) == os.path.normcase(path):
                return lbl
        base = os.path.splitext(os.path.basename(path))[0]
        label, i = base, 2
        while label in self._templates:
            label, i = f"{base} ({i})", i + 1
        self._templates[label] = path
        return label

    def add_template(self, path: str) -> str:
        label = self._register(path)
        for panel in (getattr(self, "single", None), getattr(self, "batch", None)):
            if panel is not None:
                panel.refresh_templates()
        return label

    def template_labels(self) -> list[str]:
        return list(self._templates)

    def template_path(self, label: str) -> str:
        return self._templates.get(label, render.DEFAULT_TEMPLATE)

    def label_for_path(self, path: str | None) -> str:
        if path:
            for lbl, p in self._templates.items():
                if os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(path)):
                    return lbl
        # default
        for lbl, p in self._templates.items():
            if os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(render.DEFAULT_TEMPLATE)):
                return lbl
        return next(iter(self._templates), "")

    def _custom_template_paths(self) -> list[str]:
        builtin = {os.path.normcase(os.path.abspath(p))
                   for p in glob.glob(os.path.join(render.TEMPLATES_DIR, "*.svg"))}
        return [p for p in self._templates.values()
                if os.path.normcase(os.path.abspath(p)) not in builtin]

    # ---- persistence ----
    def save_settings(self):
        try:
            active = self.notebook.index("current")
        except tk.TclError:
            active = 0
        self._cfg.update({
            "single": self.single.settings_dict(),
            "batch": self.batch.settings_dict(),
            "custom_templates": self._custom_template_paths(),
            "active_tab": active,
        })
        settings.save(self._cfg)

    def _on_close(self):
        self.save_settings()
        self.root.destroy()


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
