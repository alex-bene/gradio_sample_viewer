"""Gradio Viewer - Browse and visualize results with configurable layouts."""

import sys

from .config import GradioConfig, launch_viewer, load_config

__all__ = ["GradioConfig", "launch_viewer", "load_config"]


def main() -> None:
    """CLI entry point for gradio-sample-viewer."""
    if len(sys.argv) < 2:
        print("Usage: gradio-sample-viewer <config.yaml>")  # noqa: T201
        sys.exit(1)
    launch_viewer(sys.argv[1])
