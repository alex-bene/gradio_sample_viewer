"""Filesystem and metadata helpers for the Gradio demo."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .layout_decode import get_first_path_exists

if TYPE_CHECKING:
    from .config import GradioConfig


logger = logging.getLogger(__name__)


class Backend:
    """Filesystem and metadata helpers for the Gradio demo."""

    def __init__(self, config: GradioConfig, project_root: Path) -> None:
        self.filename = config.filename
        self.results_path = config.results_folder
        self.project_root = project_root
        self.thumbnail_path = config.thumbnail_path
        self.filter_results_by_existance_of = config.filter_results_by_existance_of
        self.cached_path = (
            config.cache_folder if config.cache_folder is not None else Path.home() / ".cache" / "gradio_sample_viewer"
        )
        results_path_hash = (
            hashlib.sha256(
                (self.results_path.as_posix() + (self.filter_results_by_existance_of or "")).encode()
            ).hexdigest()
            if self.results_path is not None
            else "null"
        )
        self.cached_path = self.cached_path / f"{results_path_hash}.json"
        self.cached_path.parent.mkdir(parents=True, exist_ok=True)
        if self.cached_path.exists():
            with self.cached_path.open() as f:
                self.all_samples_dirs = [Path(p) for p in json.load(f)]
        else:
            self.discover_all_samples()

    def discover_all_samples(self) -> None:
        """Discover all results folders under `self.results_path`.

        Filters results by those containing `self.filter_results_by_existance_of` using rglob.
        """
        if self.results_path is None:
            logger.error("Results path is None")
            return

        if not self.results_path.exists():
            logger.error("Results path does not exist: %s", self.results_path)
            return

        logger.info("Loading results from %s", self.results_path)
        if self.filter_results_by_existance_of is not None:
            all_samples = sorted(self.results_path.rglob(self.filter_results_by_existance_of))
            all_samples_rel_path = [p.relative_to(self.results_path) for p in all_samples]
            all_samples_folders = [self.results_path / p.parts[0] for p in all_samples_rel_path]
        else:
            all_samples_folders = sorted(self.results_path.iterdir())
        logger.info("Found %d samples", len(all_samples_folders))
        with self.cached_path.open("w") as f:
            json.dump([p.as_posix() for p in all_samples_folders], f)

        self.all_samples_dirs = all_samples_folders

    def get_samples_metadata(self, offset: int = 0, limit: int = 10) -> list[dict[str, str]]:
        """Get samples metadata with pagination support.

        Args:
            offset (int, optional): Offset for pagination. Defaults to 0.
            limit (int, optional): Limit for pagination. Defaults to 10.

        Returns:
            list[dict]: List of sample metadata dictionaries containing "id" (str) and "image" (Path) keys.

        """
        try:
            results: list[dict] = []
            for sample_dir in self.all_samples_dirs[offset : offset + limit]:
                thumbnail_path = self.thumbnail_path
                if not isinstance(self.thumbnail_path, str):
                    thumbnail_path = get_first_path_exists(self.thumbnail_path["first_path_exists"], sample_dir)
                results.append({"id": sample_dir.name, "image": (thumbnail_path, sample_dir.name)})
        except Exception:
            logger.exception("Error listing samples")
            return []
        else:
            return results
