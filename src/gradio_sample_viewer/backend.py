"""Filesystem and metadata helpers for the Gradio demo."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .image_utils import load_resized_image
from .layout_decode import get_first_path_exists

if TYPE_CHECKING:
    from PIL.Image import Image

    from .config import GradioConfig


logger = logging.getLogger(__name__)


def _dedupe_paths_in_order(paths: list[Path]) -> list[Path]:
    """Return paths without duplicates while preserving discovery order."""
    deduped_paths: list[Path] = []
    seen_paths: set[Path] = set()

    for path in paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        deduped_paths.append(path)

    return deduped_paths


def _relative_sample_id(results_path: Path, sample_dir: Path) -> str:
    """Return a stable sample id relative to the configured results root."""
    return sample_dir.relative_to(results_path).as_posix()


class Backend:
    """Filesystem and metadata helpers for the Gradio demo."""

    def __init__(self, config: GradioConfig, project_root: Path) -> None:
        self.filename = config.filename
        self.results_path = config.results_folder
        self.project_root = project_root
        self.thumbnail_path = config.thumbnail_path
        self.thumbnail_max_size = config.thumbnail_max_size
        self.filter_results_by_existance_of = config.filter_results_by_existance_of
        self.filter_results_parents_up = config.filter_results_parents_up
        self.all_samples_dirs: list[Path] = []
        self.cached_path = (
            config.cache_folder if config.cache_folder is not None else Path.home() / ".cache" / "gradio_sample_viewer"
        )
        results_path_hash = (
            hashlib.sha256(
                (
                    self.results_path.as_posix()
                    + (self.filter_results_by_existance_of or "")
                    + str(self.filter_results_parents_up)
                ).encode()
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
            all_matches = sorted(self.results_path.rglob(self.filter_results_by_existance_of))
            all_samples_folders = _dedupe_paths_in_order([self._resolve_sample_dir(match) for match in all_matches])
        else:
            all_samples_folders = sorted(self.results_path.iterdir())
        logger.info("Found %d samples", len(all_samples_folders))
        with self.cached_path.open("w") as f:
            json.dump([p.as_posix() for p in all_samples_folders], f)

        self.all_samples_dirs = all_samples_folders

    def _resolve_sample_dir(self, match_path: Path) -> Path:
        """Resolve the sample directory from a matched filter file path."""
        if self.results_path is None:
            msg = "Results path is None."
            raise ValueError(msg)

        sample_dir = match_path.parent
        for _ in range(self.filter_results_parents_up):
            sample_dir = sample_dir.parent

        try:
            _relative_sample_id(self.results_path, sample_dir)
        except ValueError as exc:
            msg = (
                f"`filter_results_parents_up={self.filter_results_parents_up}` climbs above results_folder "
                f"for match {match_path}."
            )
            raise ValueError(msg) from exc

        return sample_dir

    def get_samples_metadata(
        self, offset: int = 0, limit: int = 10
    ) -> tuple[list[dict[str, str | tuple[Image, str]]], int]:
        """Get samples metadata with pagination support.

        Args:
            offset (int, optional): Offset for pagination. Defaults to 0.
            limit (int, optional): Limit for pagination. Defaults to 10.

        Returns:
            tuple[list[dict], int]: Successful sample metadata rows plus source entries consumed.

        """
        source_dirs = self.all_samples_dirs[offset : offset + limit]
        try:
            results: list[dict] = []
            for sample_dir in source_dirs:
                sample_metadata = self._build_sample_metadata(sample_dir)
                if sample_metadata is not None:
                    results.append(sample_metadata)
        except Exception:
            logger.exception("Error listing samples")
            return [], len(source_dirs)
        else:
            return results, len(source_dirs)

    def _build_sample_metadata(self, sample_dir: Path) -> dict[str, str | tuple[Image, str]] | None:
        """Build metadata for one sample, returning None when thumbnail loading fails."""
        try:
            thumbnail_path = self.thumbnail_path
            if not isinstance(self.thumbnail_path, (str, Path)):
                thumbnail_path = get_first_path_exists(self.thumbnail_path["first_path_exists"], sample_dir)

            thumbnail_file = Path(thumbnail_path)
            if not thumbnail_file.is_absolute():
                thumbnail_file = sample_dir / thumbnail_file

            thumbnail_image = load_resized_image(thumbnail_file, self.thumbnail_max_size)
        except Exception:
            logger.exception("Error loading thumbnail for sample: %s", sample_dir)
            return None
        else:
            if self.results_path is None:
                msg = "Results path is None."
                raise ValueError(msg)
            sample_id = _relative_sample_id(self.results_path, sample_dir)
            return {"id": sample_id, "image": (thumbnail_image, sample_id)}
