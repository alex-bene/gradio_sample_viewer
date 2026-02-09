"""Configuration for the Gradio demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf


@dataclass
class GradioConfig:
    """Configuration dataclass for the Gradio demo."""

    launch_options: dict[str, Any]
    results_folder: Path | None
    layout: list
    thumbnail_path: Any
    filter_results_by_existance_of: str | None = None
    filename: str | None = None
    app_title: str = "Samples viewer"
    page_limit: int = 10
    cache_folder: Path | None = None

    def __post_init__(self) -> None:
        """Initialize cache_folder if not provided."""
        if self.cache_folder is None:
            self.cache_folder = Path.home() / ".cache" / "hoigen3d" / "gradio_app"
        if not isinstance(self.thumbnail_path, (str, Path)) and not (
            isinstance(self.thumbnail_path, dict)
            and "first_path_exists" in self.thumbnail_path
            and isinstance(self.thumbnail_path["first_path_exists"], list)
            and isinstance(self.thumbnail_path["first_path_exists"][0], (str, Path))
        ):
            msg = "`thumbnail_path` must be a string."
            raise TypeError(msg)


def _ensure_resolvers_registered() -> None:
    """Register custom OmegaConf resolvers if not already registered."""
    if not OmegaConf.has_resolver("sample_folder_name"):
        OmegaConf.register_new_resolver("sample_folder_name", lambda: "${sample_folder_name}")
    if not OmegaConf.has_resolver("first_path_exists"):
        OmegaConf.register_new_resolver(
            "first_path_exists", lambda *args: {"first_path_exists": [s.strip() for s in args]}
        )


def load_config(config_path: str | Path) -> GradioConfig:
    """Load a GradioConfig from any YAML file path.

    The user's config is merged on top of the bundled base_cfg.yaml,
    so only overrides need to be specified.

    Args:
        config_path: Path to a YAML configuration file.

    Returns:
        A validated GradioConfig instance.

    """
    _ensure_resolvers_registered()

    config_path = Path(config_path)
    if not config_path.exists():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    # Load base_cfg.yaml from the package
    base_cfg_path = Path(__file__).parent / "config" / "base_cfg.yaml"
    base_cfg = OmegaConf.load(base_cfg_path)

    # Remove Hydra-specific keys from base
    for key in ["defaults", "hydra"]:
        if key in base_cfg:
            del base_cfg[key]

    # Load user's config
    user_cfg = OmegaConf.load(config_path)

    # Remove Hydra keys from user config too (if copied from old configs)
    for key in ["defaults", "hydra"]:
        if key in user_cfg:
            del user_cfg[key]

    # Merge: base + user config
    merged = OmegaConf.merge(base_cfg, user_cfg)

    # Merge with structured config to enable type conversion
    schema = OmegaConf.structured(GradioConfig)
    typed_cfg = OmegaConf.merge(schema, merged)

    # Convert to dataclass (validates + resolves ${} interpolation)
    return OmegaConf.to_object(typed_cfg)


def launch_viewer(config_path: str | Path, **launch_overrides: Any) -> None:
    """Launch the Gradio viewer with configuration from a YAML file.

    Args:
        config_path: Path to a YAML configuration file.
        **launch_overrides: Optional overrides for launch options
            (server_name, server_port, share, etc.)

    Example:
        from gradio_app import launch_viewer
        launch_viewer('/path/to/my_config.yaml', server_port=8080)

    """
    from .ui import build_demo  # noqa: PLC0415

    cfg = load_config(config_path)

    launch_options = dict(cfg.launch_options)
    launch_options.update(launch_overrides)

    demo = build_demo(cfg)
    demo.launch(**launch_options, allowed_paths=[cfg.results_folder])
