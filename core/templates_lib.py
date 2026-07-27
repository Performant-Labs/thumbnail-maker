"""Template library management and built-in/custom classification.

This is domain logic, not presentation: it manages the set of available
templates keyed by a stable label, resolves labels to filesystem paths, and
classifies each template as **built-in** (shipped in ``templates/``) or
**custom** (a path the user browsed to). Frontends layer their own presentation
on top (the GUI's grouped dropdown with headers/indentation, the CLI's
``--template`` name lookup).
"""

from __future__ import annotations

import glob
import os

from .resources import DEFAULT_TEMPLATE, TEMPLATES_DIR


def builtin_template_paths(templates_dir: str = TEMPLATES_DIR) -> list[str]:
    """Absolute paths of the ``*.svg`` templates shipped in ``templates_dir``."""
    return sorted(
        os.path.abspath(p) for p in glob.glob(os.path.join(templates_dir, "*.svg"))
    )


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class TemplateLibrary:
    """A label -> path registry that classifies built-in vs custom templates.

    Labels are derived from the file stem; collisions get a ``" (2)"`` suffix.
    Registration is idempotent by normalized path.
    """

    def __init__(self, templates_dir: str = TEMPLATES_DIR,
                 default_template: str = DEFAULT_TEMPLATE):
        self._templates: dict[str, str] = {}
        self._templates_dir = templates_dir
        self._default_template = default_template

    # ---- population ----
    def load_builtins(self) -> None:
        """Register every template shipped in the templates directory."""
        for p in builtin_template_paths(self._templates_dir):
            self.register(p)

    def register(self, path: str) -> str:
        """Add ``path`` if not already present; return its label either way."""
        path = os.path.abspath(path)
        for lbl, p in self._templates.items():
            if _norm(p) == _norm(path):
                return lbl
        base = os.path.splitext(os.path.basename(path))[0]
        label, i = base, 2
        while label in self._templates:
            label, i = f"{base} ({i})", i + 1
        self._templates[label] = path
        return label

    # ``add`` reads better at call sites that mean "add this new one".
    add = register

    # ---- lookup ----
    def labels(self) -> list[str]:
        return list(self._templates)

    def path_for_label(self, label: str) -> str:
        """Resolve a label to its path, falling back to the default template."""
        return self._templates.get(label, self._default_template)

    def label_for_path(self, path: str | None) -> str:
        """Return the label for ``path`` (or for the default template)."""
        if path:
            for lbl, p in self._templates.items():
                if _norm(p) == _norm(path):
                    return lbl
        for lbl, p in self._templates.items():
            if _norm(p) == _norm(self._default_template):
                return lbl
        return next(iter(self._templates), "")

    # ---- classification ----
    def builtin_paths(self) -> set[str]:
        """Normalized paths currently considered built-in."""
        return {_norm(p) for p in builtin_template_paths(self._templates_dir)}

    def is_builtin(self, path: str) -> bool:
        return _norm(path) in self.builtin_paths()

    def builtin_labels(self) -> list[str]:
        return [lbl for lbl, p in self._templates.items() if self.is_builtin(p)]

    def custom_labels(self) -> list[str]:
        return [lbl for lbl, p in self._templates.items() if not self.is_builtin(p)]

    def custom_paths(self) -> list[str]:
        builtin = self.builtin_paths()
        return [p for p in self._templates.values() if _norm(p) not in builtin]
