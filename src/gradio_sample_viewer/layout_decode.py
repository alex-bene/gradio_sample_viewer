"""Decode layout yaml and prepare for Gradio."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd
import plotly.io as pio
from omegaconf import OmegaConf

from .config import GradioConfig


@lru_cache
def load_file(filepath: str | Path) -> Any:
    """Load file contents based on suffix and cache results for performance."""
    filepath = Path(filepath)
    if filepath.suffix == ".json":
        with filepath.open() as f:
            return json.load(f)
    elif filepath.suffix == ".csv":
        return pd.read_csv(filepath, index_col=0)
    elif filepath.suffix == ".txt":
        with filepath.open() as f:
            return f.read()
    else:
        msg = f"Unsupported file suffix: {filepath.suffix}."
        raise NotImplementedError(msg)


def get_first_path_exists(path_candidates: list[str | Path], sample_folder: Path) -> str | Path:
    """Get the first path that exists in a list of `path_candidates` relative to `sample_folder`."""
    for path in path_candidates:
        full_path = Path(path)
        # If path is not absolute, assume it is relative to sample_folder
        full_path = sample_folder / path if not full_path.is_absolute() else Path(path)
        if full_path.exists():
            return full_path

    return path_candidates[0]


def load_layout_files(data: dict | list, sample_name: str, results_folder: Path) -> Any:  # noqa: PLR0911, PLR0912
    """Recursively traverse data and load if from file if load_contents=True."""
    if isinstance(data, list):
        return [load_layout_files(d, sample_name, results_folder) for d in data]

    # `data` should be a dict or list (but we handled the list case above)
    if not isinstance(data, dict):
        msg = f"Expected dict or list, got {type(data)}."
        raise TypeError(msg)

    # Search for first path that exists if requested
    if "first_path_exists" in data:
        return get_first_path_exists(data["first_path_exists"], results_folder / sample_name)

    # If you don't have to load contents, just return with recursion
    if not data.get("load_contents", False):
        return {
            k: v if not isinstance(v, (dict, list)) else load_layout_files(v, sample_name, results_folder)
            for k, v in data.items()
        }

    # Load contents
    ## Load path should always be present
    if "load_path" not in data:
        msg = f"Expected 'load_path' in {data} that has `load_contents=True`."
        raise ValueError(msg)

    ## Paths are assumed to be relative to results_folder unless they are absolute
    load_path = Path(data["load_path"])
    if not load_path.is_absolute():
        load_path = results_folder / sample_name / load_path
    if not load_path.exists():
        msg = f"Expected {load_path} to exist, but it doesn't."
        raise FileNotFoundError(msg)

    ## Load file contents
    file_contents = load_file(load_path)

    ## If no indices are provided, return file contents
    indices = data.get("indices", None)
    if indices in (None, []):
        return file_contents

    ## Indeces are only supported for dict and DataFrame
    if not isinstance(file_contents, (dict, pd.DataFrame)):
        msg = "`indeces` key is only valid for dict or DataFrame."
        raise TypeError(msg)

    ## Apply indices for dict
    if isinstance(file_contents, dict):
        if not file_contents:
            return None
        to_return = file_contents
        for index_key in indices:
            to_return = to_return.get(index_key, None)
            if to_return is None:
                return None
        return to_return

    ## Apply indices for DataFrame
    if file_contents.empty:
        return None

    to_return: pd.DataFrame = file_contents
    for index_key in indices:
        to_return = to_return.loc[index_key]

    return to_return


def prepare_layout_components(cfg: GradioConfig, folder_name: str) -> list:
    """Prepare layout components for Gradio.

    Replaces {sample_folder} with the actual sample folder.
    Loads contents from files if load_contents=True.
    """
    layout = json.loads(json.dumps(cfg.layout).replace("${sample_folder_name}", folder_name))
    return load_layout_files(layout, folder_name, cfg.results_folder)


def create_gradio_component_by_name(name: str, sample_folder: Path | str | None = None, **kwargs: dict) -> gr.Component:
    """Create Gradio component based on name and kwargs."""

    # Since paths are assumed to be relative to sample_folder, we need to change the working directory to be the
    # sample_folder such that any paths are resolved by gradio correctly
    ## NOTE: we could PROBABLY do this in the backed such that whenever gradio asks for a file, the backend resolves
    ## it relative to the sample_folder
    def _resolve_relative_path(value: Any, sample_folder: Path | str | None) -> Any:
        if sample_folder is None:
            return value
        if not isinstance(value, (str, Path)):
            return value
        if "://" in str(value):
            return value
        path_value = Path(value)
        if path_value.is_absolute():
            return value
        candidate = Path(sample_folder) / path_value
        return candidate if candidate.exists() else value

    current_working_dir = Path.cwd()
    if sample_folder is not None:
        sample_folder = Path(sample_folder)
        os.chdir(sample_folder)

    if "value" in kwargs:
        kwargs["value"] = _resolve_relative_path(kwargs["value"], sample_folder)

    if name == "Plot":
        value = kwargs.pop("value")
        value = pio.from_json(json.dumps(value))
        component = gr.Plot(value=value, **kwargs)
    else:
        component = getattr(gr, name)(**kwargs)

    # Reset working directory after creating component
    os.chdir(current_working_dir)

    return component


def make_gradio_components(layout: list | dict, sample_folder: Path | str | None = None) -> None:
    """Recursively create Gradio components from layout configuration."""
    if isinstance(layout, dict) and "components" in layout:
        components = layout.pop("components")
        name = layout.pop("type")
        with_context = create_gradio_component_by_name(name, sample_folder=sample_folder, **layout)
        with with_context:
            make_gradio_components(components, sample_folder)
    elif isinstance(layout, list):
        for component in layout:
            make_gradio_components(component, sample_folder)
    else:
        name = layout.pop("type")
        create_gradio_component_by_name(name, sample_folder=sample_folder, **layout)


if __name__ == "__main__":
    cfg_yaml = Path(__file__).with_name("layout.yaml")
    cfg = OmegaConf.structured(GradioConfig)
    file_cfg = OmegaConf.load(cfg_yaml)
    cfg = OmegaConf.merge(cfg, file_cfg)
    cfg: GradioConfig = OmegaConf.to_object(cfg)

    sample_folder = Path(
        "/home/abenetatos/GitRepos/hoigen-3d/jz_mount_hoigen_results/-29QoTMZuO0-0:00:22.022-0:00:24.065"
    )
    layout = prepare_layout_components(cfg, sample_folder)

    print(OmegaConf.to_yaml(layout))  # noqa: T201
    print(make_gradio_components(layout))  # noqa: T201
