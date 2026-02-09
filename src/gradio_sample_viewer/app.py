"""CLI entry point for the Gradio demo."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from .config import launch_viewer
except ImportError:  # pragma: no cover - allows running as a script
    src_root = Path(__file__).resolve().parents[1]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from gradio_sample_viewer.config import launch_viewer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app.py <config.yaml>")  # noqa: T201
        sys.exit(1)
    launch_viewer(sys.argv[1])
