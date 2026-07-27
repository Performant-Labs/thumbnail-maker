# Architecture: front end / back end boundary

Thumbnail Maker is split into a **UI-free core library** and one or more **thin
frontends** that consume it. The core knows how to render thumbnails, manage
templates, discover images, and persist raw settings. It knows nothing about
tkinter, widgets, threads, or preview scaling. Frontends (the tkinter GUI in
`app.py`, the `cli.py` command line) hold only presentation and I/O glue and
depend **only** on `core`'s documented public surface.

```
            +---------------------------+       +---------------------------+
            |        frontends          |       |        frontends          |
            |  app.py  (tkinter GUI)    |       |  cli.py  (command line)   |
            +-------------+-------------+        +-------------+-------------+
                          \                                   /
                           \        depend only on           /
                            \       core's public API       /
                             v                             v
                    +-----------------------------------------------+
                    |                    core/                       |
                    |  render / batch / layout   (rendering)        |
                    |  Style, fields, progress   (types)            |
                    |  TemplateLibrary           (classification)   |
                    |  list_images / title_from_filename (discovery)|
                    |  config load/save/dir      (persistence)      |
                    |  svgtemplate engine        (internal)         |
                    +-----------------------------------------------+
```

## Design rules

- **No UI in core.** `core` imports no `tkinter` and no `PIL.ImageTk`. Renders
  return PIL `Image` objects or write files — never Tk objects. A headless test
  asserts `tkinter` is absent from `core`'s import graph.
- **The frontend owns presentation only.** Widgets, dialogs, threading, preview
  scaling, dropdown grouping headers, and the settings *schema* (which keys, the
  per-tab structure) live in the frontend. The storage *primitive* is core.
- **Behavior is unchanged.** Templates, the render contract, output file naming
  (`<stem>_thumb.jpg`), and the on-disk settings location/format are identical to
  before the split.

## Public API (`core`)

Everything below is re-exported from `core` and listed in `core.__all__`.
Anything not listed (e.g. the `svgtemplate` engine, `core.resources` internals)
is internal and may change.

### Types

- **`Style`** (dataclass) — batch-wide render settings. Fields:
  `template_path: str`, `subtitle: str`, `uppercase: bool = True`,
  `font_files: list[str]`. Defaults point at the bundled editorial template and
  the bundled Playfair Display font.
- **`ProgressCallback`** — type alias for `Callable[[int, int, str, str | None], None]`,
  the batch progress signature `(done, total, name, error)`. `error` is `None` on
  success, else a message string; the batch keeps going past a failed file.

### Rendering

- **`render_thumbnail(photo_path, title_or_fields, style) -> PIL.Image.Image`** —
  render one thumbnail. `title_or_fields` is a plain title `str` or a dict of
  field overrides (`{"title": ..., "subtitle": ..., <custom tokens>}`).
- **`render_layout(style, fields=None) -> PIL.Image.Image`** — render the
  template's layout: placeholder title/subtitle text plus a labeled `PHOTO` box,
  so a frontend can preview where everything lands before a photo is chosen.
- **`batch_render(input_folder, output_folder, style, csv_overrides=None,
  quality=90, progress=None) -> list[str]`** — render every image in
  `input_folder` to `output_folder`, writing `<stem>_thumb.jpg`. Calls
  `progress(done, total, name, error)` per file if given; returns the list of
  written output paths. A bad input file is skipped (reported via `error`) rather
  than aborting the run.

### Titles, fields, image discovery

- **`title_from_filename(path) -> str`** — `feet-first.jpg` -> `FEET FIRST`
  (case applied later by `Style.uppercase`).
- **`list_images(folder) -> list[str]`** — sorted absolute paths of the images in
  a folder (extensions in `IMAGE_EXTS`).
- **`load_titles_csv(csv_path) -> dict[str, dict[str, str]]`** — parse an optional
  per-photo overrides CSV keyed by `filename`.
- **`placeholder_fields(subtitle, uppercase) -> dict[str, str]`** — the field
  dict used to render a layout preview before a real title exists.

### Template library / classification

- **`TemplateLibrary`** — manages the set of available templates by label,
  classifies each as **built-in** (shipped in `templates/`) or **custom** (a path
  the user browsed to), and resolves labels to paths. Methods: `register(path)`,
  `add(path)`, `labels()`, `is_builtin(path)`, `builtin_labels()`,
  `custom_labels()`, `custom_paths()`, `path_for_label(label)`,
  `label_for_path(path)`. The GUI's grouped-dropdown headers/indentation are
  presentation and stay in the frontend.
- **`builtin_template_paths() -> list[str]`** — the templates shipped in
  `templates/`.

### Resource constants

- **`DEFAULT_TEMPLATE`** — path to `templates/editorial.svg`.
- **`TEMPLATES_DIR`** — the bundled `templates/` directory.
- **`FONT_PATH`** — path to the bundled `fonts/PlayfairDisplay-VF.ttf`.
- **`IMAGE_EXTS`** — the set of recognized image extensions.
- **`DEFAULT_SUBTITLE`** — the default subtitle string.

### Config / settings persistence

Exposed under `core.config` (and the load/save/dir primitives are re-exported at
the top level as noted):

- **`config.config_dir() -> str`** — per-user config directory (created if
  needed). Windows `%APPDATA%\ThumbnailMaker`, macOS
  `~/Library/Application Support/ThumbnailMaker`, Linux `~/.config/ThumbnailMaker`.
- **`config.settings_path() -> str`** — the `settings.json` path within it.
- **`config.load() -> dict`** — load the settings dict (empty dict on any error).
- **`config.save(data: dict) -> None`** — persist the settings dict (never raises).

The *schema* of that dict (per-tab `single`/`batch` blocks, `custom_templates`,
`active_tab`, …) is owned by the frontend; core only provides the untyped
key/value storage primitive.

## Resource resolution

`templates/` and `fonts/` sit at the repository root next to `core/`. In source,
core resolves them relative to the repo root (the parent of the `core/` package);
under a PyInstaller frozen build they are unpacked to `sys._MEIPASS`. Only the
bundled `fonts/PlayfairDisplay-VF.ttf` is available at render time
(`skip_system_fonts=True`, `font-family="Playfair Display"`).

## The template / render contract

A template is an ordinary SVG. See `core/svgtemplate.py` and
`templates/editorial.svg`:

1. **Text tokens** — `{{title}}` and `{{subtitle}}` (and any other `{{field}}`
   filled from a CSV) are substituted with XML-escaped values.
2. **Photo region** — exactly one element with `id="photo"` is replaced by the
   input image, cover-cropped (`preserveAspectRatio="xMidYMid slice"`), preserving
   any transform.
3. **Auto-fit text** — a `<text>` with `data-fit="true"` (+ `data-max-width`,
   `data-max-lines`, optional `data-line-height`) shrinks and wraps: its
   `font-size` is treated as the maximum.

## Writing an alternate frontend

Import `core`, build a `Style`, and call the rendering functions — that is the
entire dependency. `cli.py` is a complete worked example in ~100 lines. A
frontend must not import `svgtemplate` directly or reach into `core` internals;
everything it needs is in `core.__all__` and `core.config`.
