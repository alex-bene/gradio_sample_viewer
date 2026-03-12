"""Gradio UI: build_demo() returns a gr.Blocks app for browsing samples.

UX:
 - "Load samples" button loads a page of samples (thumbnails + metadata)
 - Dropdown selects a sample id to inspect
 - Selected sample shows: large preview image, caption, and Plotly viewer area
 - "Load more" loads next page and appends to sample state
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import gradio as gr

from .backend import Backend
from .layout_decode import make_gradio_components, prepare_layout_components

if TYPE_CHECKING:
    from .config import GradioConfig

SELECT_ALL = "all"
SELECT_NONE = "none"


def _coerce_selection(selection: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if selection is None:
        return []
    if isinstance(selection, str):
        return [selection]
    return [str(choice) for choice in selection]


def normalize_sample_selection(
    selection: str | list[str] | tuple[str, ...] | None, sample_ids: list[str]
) -> tuple[list[str], list[str]]:
    """Normalize dropdown selection and derive active sample ids to render."""
    values = _coerce_selection(selection)
    if SELECT_ALL in values:
        return [SELECT_ALL], list(sample_ids)
    if SELECT_NONE in values:
        return [SELECT_NONE], []

    selected_ids = [sample_id for sample_id in values if sample_id in sample_ids]
    return selected_ids, selected_ids


def selection_to_gallery_index(
    dropdown_values: list[str], selected_ids: list[str], sample_ids: list[str]
) -> int | None:
    """Return gallery selected index when exactly one concrete sample id is selected."""
    if dropdown_values in ([SELECT_ALL], [SELECT_NONE]) or len(selected_ids) != 1:
        return None

    try:
        return sample_ids.index(selected_ids[0])
    except ValueError:
        return None


def selected_ids_to_selection_token(selected_ids: list[str], sample_ids: list[str]) -> str:
    """Convert selected sample ids to render token based on sample index positions."""
    if not selected_ids:
        return SELECT_NONE
    if sample_ids and len(selected_ids) == len(sample_ids):
        return SELECT_ALL

    index_by_id = {sample_id: idx for idx, sample_id in enumerate(sample_ids)}
    selected_indices = [str(index_by_id[selected_id]) for selected_id in selected_ids if selected_id in index_by_id]
    return SELECT_NONE if not selected_indices else ",".join(selected_indices)


def build_demo(cfg: GradioConfig) -> gr.Blocks:  # noqa: PLR0915
    """Build the Gradio demo app."""
    demo = gr.Blocks(title=cfg.app_title)
    backend = Backend(cfg, project_root=Path())

    with demo:
        samples_state = gr.State([])
        samples_gradio = gr.State({})
        samples_imgs = gr.State([])
        samples_ids = gr.State([])
        offset_state = gr.State(0)

        gr.Markdown("# HOIGen results viewer")

        # Sample Visualization
        with gr.Column():
            gr.Markdown("## Samples")
            ## Necessary patch because `gr.render` does not work when using a `gr.State.change` as a trigger
            dummy_rerender_text = gr.Textbox(visible=False)
            dummy_rerender_text.change(lambda: "", inputs=[], outputs=dummy_rerender_text)

            @gr.render(
                inputs=[samples_state, samples_gradio, dummy_rerender_text],
                triggers=[dummy_rerender_text.change],
                trigger_mode="once",
            )
            def render_samples(
                samples_state: list[dict], samples_gradio: dict[str, gr.Row], dummy_rerender_text: str
            ) -> None:
                for sample_gradio in samples_gradio.values():
                    sample_gradio.unrender().render()

                if dummy_rerender_text == "rerender":
                    samples_gradio = create_samples_rows(samples=samples_state, samples_gradio=samples_gradio)
                    return

                if not dummy_rerender_text.startswith("selected_"):
                    return

                samples_gradio = create_samples_rows(samples=samples_state, samples_gradio=samples_gradio)
                selected_token = dummy_rerender_text.rsplit("_", maxsplit=1)[-1]
                if selected_token == SELECT_ALL:
                    selected_indices = set(range(len(samples_gradio)))
                elif selected_token == SELECT_NONE:
                    selected_indices = set()
                else:
                    selected_indices = {
                        int(selected_index) for selected_index in selected_token.split(",") if selected_index.isdigit()
                    }

                for idx, sample_gradio in enumerate(samples_gradio.values()):
                    sample_gradio.visible = idx in selected_indices
                    if idx not in selected_indices:
                        sample_gradio.unrender()

            def create_samples_rows(samples: list[dict], samples_gradio: dict[str, gr.Row]) -> dict[str, gr.Row]:
                if cfg.results_folder is None:
                    return samples_gradio

                for sample in samples:
                    if sample.get("id") in samples_gradio:
                        continue

                    with gr.Column(variant="panel", key=sample.get("id")) as sample_gradio:
                        gr.Markdown(f"### {sample.get('id', '')}")
                        make_gradio_components(
                            prepare_layout_components(cfg, sample.get("id")),
                            cfg.results_folder / sample["id"],
                            image_max_size=cfg.image_max_size,
                        )
                        samples_gradio[sample.get("id")] = sample_gradio
                return samples_gradio

        # Pagination settings, samples loading and sample selector
        with gr.Column(variant="panel"):
            gr.Markdown("## Setting and sample selection")
            with gr.Row(equal_height=True):
                with gr.Column(scale=1), gr.Column():
                    with gr.Accordion("Settings", open=False):
                        pagination_limit = gr.Slider(
                            1, 50, step=1, value=cfg.page_limit, label="Pagination limit", show_label=True
                        )
                        search_samples_btn = gr.Button("Full samples search")
                    load_more_btn = gr.Button("Load more")
                    samples_dropdown = gr.Dropdown(
                        show_label=True,
                        label="Sample selector",
                        choices=[],
                        value=[],
                        multiselect=True,
                        interactive=True,
                    )
                with gr.Column(scale=2):
                    gallery = gr.Gallery(
                        label="Samples (thumbnails)", show_label=False, rows=1, columns=5, interactive=False
                    )

        def load_more(
            samples_state: list[dict[str, Any]],
            samples_imgs: list[Any],
            samples_ids: list[str],
            samples_dropdown: str | list[str] | None,
            offset_state: int,
            pagination_limit: int,
        ) -> tuple[str, list[dict[str, Any]], list[Any], gr.Gallery, list[str], int, gr.Dropdown]:
            more = backend.get_samples_metadata(
                offset=int(offset_state or 0), limit=int(pagination_limit or cfg.page_limit)
            )
            updated_samples_state = samples_state + more
            updated_imgs = samples_imgs + [s["image"] for s in more]
            updated_ids = samples_ids + [s["id"] for s in more]

            requested_selection = samples_dropdown
            if not _coerce_selection(requested_selection) and not samples_ids and updated_ids:
                requested_selection = [updated_ids[0]]

            dropdown_values, selected_ids = normalize_sample_selection(requested_selection, updated_ids)
            selection_token = selected_ids_to_selection_token(selected_ids, updated_ids)
            gallery_index = selection_to_gallery_index(dropdown_values, selected_ids, updated_ids)

            return (
                f"selected_{selection_token}",
                updated_samples_state,
                updated_imgs,
                gr.Gallery(value=updated_imgs, selected_index=gallery_index),
                updated_ids,
                offset_state + len(more),
                gr.update(choices=[SELECT_ALL, SELECT_NONE, *updated_ids], value=dropdown_values),
            )

        load_more_btn.click(
            fn=load_more,
            inputs=[samples_state, samples_imgs, samples_ids, samples_dropdown, offset_state, pagination_limit],
            outputs=[
                dummy_rerender_text,
                samples_state,
                samples_imgs,
                gallery,
                samples_ids,
                offset_state,
                samples_dropdown,
            ],
            queue=False,
        )

        # Re-search for samples
        search_samples_btn.click(fn=backend.discover_all_samples)

        def on_dropdown_change(
            samples_dropdown: str | list[str] | None, samples_ids: list[str]
        ) -> tuple[gr.Dropdown, gr.Gallery, str]:
            dropdown_values, selected_ids = normalize_sample_selection(samples_dropdown, samples_ids)
            selection_token = selected_ids_to_selection_token(selected_ids, samples_ids)
            gallery_index = selection_to_gallery_index(dropdown_values, selected_ids, samples_ids)
            return (
                gr.Dropdown(value=dropdown_values),
                gr.Gallery(selected_index=gallery_index),
                f"selected_{selection_token}",
            )

        def on_gallery_select(event: gr.SelectData, samples_ids: list[str]) -> tuple[gr.Dropdown, gr.Gallery, str]:
            if event.index is None or event.index >= len(samples_ids):
                return gr.skip(), gr.skip(), gr.skip()
            sample_id = samples_ids[event.index]
            return (gr.Dropdown(value=[sample_id]), gr.Gallery(selected_index=event.index), f"selected_{event.index}")

        samples_dropdown.change(
            fn=on_dropdown_change,
            inputs=[samples_dropdown, samples_ids],
            outputs=[samples_dropdown, gallery, dummy_rerender_text],
            queue=False,
        )
        gallery.select(
            fn=on_gallery_select,
            inputs=[samples_ids],
            outputs=[samples_dropdown, gallery, dummy_rerender_text],
            queue=False,
        )

    return demo
