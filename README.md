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
thumbnail_path: ${first_path_exists:input_image.png,thumbnail.png}
layout:
  - type: Row
    components:
      - type: Column
        scale: 2
        components:
          - type: Image
            value: input_image.png
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
            value: mesh_initial.obj
launch_options:
  server_name: 0.0.0.0
  server_port: 7832
```

Notes:
1. `filter_results_by_existance_of` limits samples to those containing a specific file.
2. `thumbnail_path` can be a single relative path or a `${first_path_exists:...}` resolver to pick the first file that exists per sample folder.
3. In `layout`, any `value` paths are resolved relative to each sample folder unless you provide absolute paths.
4. In a value, if `load_contets` is `true`, then we try to load the contents of the file and, for dicts or pandas dataframes, we optionally select the specified item following the indeces list.

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
