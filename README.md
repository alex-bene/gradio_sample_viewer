# Gradio Sample Viewer

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/alex-bene/gradio_sample_viewer/main.svg)](https://results.pre-commit.ci/latest/github/alex-bene/gradio_sample_viewer/main)
[![Development Status](https://img.shields.io/badge/status-beta-orange)](https://github.com/alex-bene/gradio_sample_viewer)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A repository implementing high-level visualization gradio-based app for quickly showing off results.

## Installation

You can install `gradio_sample_viewer` directly from GitHub:

```bash
pip install git+https://github.com/alex-bene/gradio_sample_viewer.git
```

Or if you are using `uv`:

```bash
uv add git+https://github.com/alex-bene/gradio_sample_viewer.git
```

## Usage

The app is configured via a YAML file. Your config is merged on top of the bundled `base_cfg.yaml`, so you only need to override what you care about.

Run the viewer with:

```bash
python -m gradio_sample_viewer.app path/to/config.yaml
```

CLI overrides are supported via OmegaConf dotlist syntax:

```bash
uv run gradio-sample-viewer path/to/config.yaml launch_options.server_port=7878 page_limit=20
```

Or launch it from Python:

```python
from gradio_sample_viewer.config import launch_viewer

launch_viewer("path/to/config.yaml", server_port=7860)
```

Example config:

```yaml
app_title: My Sample Viewer
results_folder: /absolute/path/to/results
filter_results_by_existance_of: must_exist.json
thumbnail_path: ${first_path_exists:image.png,thumbnail.png}
thumbnail_max_size: 512
image_max_size: 1280
layout:
  - type: Row
    components:
      - type: Column
        scale: 2
        components:
          - type: Markdown
            label: Sample ID
            value: "Current sample: ${sample_folder_name}"
          - type: Image
            value: image.png
          - type: Markdown
            label: Action Description
            value:
              load_contents: true
              load_path: detection.json
              indices: [human_action]
      - type: Column
        scale: 3
        components:
          - type: Model3D
            value: ${first_path_exists:mesh.obj,mesh_good.obj,mesh_bad.obj}
launch_options:
  server_name: 0.0.0.0
  server_port: 7832
```

Notes:
1. `filter_results_by_existance_of` searches recursively (so subdirectory paths like `predictions/must_exist.json` work), but the sample folder remains the top-level folder under `results_folder` (that is, `results_folder/<sample_id>`), not the matched subdirectory.
2. `${first_path_exists:...}` is a general path resolver and can be used for any path value (for example `thumbnail_path` or layout `value` paths) to pick the first existing file per sample folder.
3. `${sample_folder_name}` is replaced with the current sample folder name when rendering each sample layout.
4. `thumbnail_max_size` and `image_max_size` downsample images to a max side length while preserving aspect ratio.
5. In `layout`, any `value` paths are resolved relative to the sample folder `results_folder/<sample_id>` unless you provide absolute paths.
6. The sample selector supports multi-select plus special values `all` and `none`.
7. `Full samples search` performs a full rescan, temporarily disables its button while running, and refreshes the sample list when complete.
8. On initial load (and after full refresh), the first discovered sample is selected by default.
9. In a value, if `load_contents` is `true`, then we try to load the contents of the file and, for dicts or pandas dataframes, we optionally select the specified item following the indices list.

## Development

To contribute to this project, please ensure you have `uv` installed.

1. Clone the repository:

   ```bash
   git clone https://github.com/alex-bene/gradio_sample_viewer.git
   cd gradio_sample_viewer
   ```

2. Install dependencies and pre-commit hooks:

   ```bash
   uv sync
   uv run pre-commit install
   ```

3. Run checks manually (optional):
   ```bash
   uv run ruff check
   uv run ruff format
   ```

This project uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting. We use [pre-commit](https://pre-commit.com/) hooks to ensure code quality.

- **Local**: Hooks run before every commit (requires `pre-commit install`).
- **GitHub Actions**: Runs on every push to **auto-fix** issues on all branches.
- **pre-commit.ci**: Runs on every push to **check** code quality (fixes are handled by the GitHub Action).

## License

This project is licensed under the [MIT License](LICENSE).
