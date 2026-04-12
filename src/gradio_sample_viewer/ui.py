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
from uuid import uuid4

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


def resolve_selection_state(
    requested_selection: str | list[str] | tuple[str, ...] | None,
    sample_ids: list[str],
    *,
    default_to_first_sample: bool = False,
) -> tuple[list[str], list[str], str, int | None]:
    """Resolve dropdown values, selected ids, render token and gallery index."""
    values = _coerce_selection(requested_selection)
    if default_to_first_sample and not values and sample_ids:
        values = [sample_ids[0]]

    if SELECT_ALL in values:
        return [SELECT_ALL], list(sample_ids), SELECT_ALL, None
    if SELECT_NONE in values:
        return [SELECT_NONE], [], SELECT_NONE, None

    selected_ids = [sample_id for sample_id in values if sample_id in sample_ids]
    dropdown_values = list(selected_ids)

    if not selected_ids:
        selection_token = SELECT_NONE
    elif sample_ids and len(selected_ids) == len(sample_ids):
        selection_token = SELECT_ALL
    else:
        index_by_id = {sample_id: idx for idx, sample_id in enumerate(sample_ids)}
        selected_indices = [str(index_by_id[selected_id]) for selected_id in selected_ids if selected_id in index_by_id]
        selection_token = SELECT_NONE if not selected_indices else ",".join(selected_indices)

    gallery_index = None
    if len(selected_ids) == 1:
        try:
            gallery_index = sample_ids.index(selected_ids[0])
        except ValueError:
            gallery_index = None

    return dropdown_values, selected_ids, selection_token, gallery_index


def _new_render_trigger(prefix: str) -> str:
    """Generate a unique render trigger so gr.render runs on every UI event."""
    return f"{prefix}_{uuid4().hex}"


def maybe_notify_load_more_empty(existing_sample_ids: list[str], new_samples: list[dict[str, Any]]) -> None:
    """Show a modal when load-more yields nothing useful."""
    if new_samples:
        return
    if existing_sample_ids:
        gr.Warning("No more samples are available to load.", title="No more samples", duration=5)
        return
    gr.Warning("No samples were found in the results folder.", title="No samples found")


def maybe_notify_refresh_empty(discovered_sample_count: int, loaded_sample_count: int) -> None:
    """Show a modal when a full refresh still leaves the UI empty."""
    if discovered_sample_count == 0 or loaded_sample_count == 0:
        gr.Warning("No samples were found in the results folder.", title="No samples found")


def build_demo(cfg: GradioConfig) -> gr.Blocks:  # noqa: PLR0915
    """Build the Gradio demo app."""
    demo = gr.Blocks(title=cfg.app_title)
    backend = Backend(cfg, project_root=Path())

    with demo:
        samples_state = gr.State([])
        samples_gradio = gr.State({})
        samples_imgs = gr.State([])
        samples_ids = gr.State([])
        selected_ids_state = gr.State([])
        offset_state = gr.State(0)

        gr.Markdown("# HOIGen results viewer")

        # Sample Visualization
        with gr.Column():
            gr.Markdown("## Samples")
            ## Necessary patch because `gr.render` does not work when using a `gr.State.change` as a trigger
            dummy_rerender_text = gr.Textbox(visible=False)
            dummy_rerender_text.change(lambda: "", inputs=[], outputs=dummy_rerender_text)

            @gr.render(
                inputs=[samples_state, samples_gradio, selected_ids_state, dummy_rerender_text],
                triggers=[dummy_rerender_text.change],
                trigger_mode="once",
            )
            def render_samples(
                samples_state: list[dict],
                samples_gradio: dict[str, gr.Row],
                selected_ids: list[str],
                dummy_rerender_text: str,
            ) -> None:
                samples_gradio = create_samples_rows(samples=samples_state, samples_gradio=samples_gradio)
                if not dummy_rerender_text:
                    return

                selected_ids_set = set(selected_ids)
                for sample_id, sample_gradio in samples_gradio.items():
                    sample_gradio.visible = sample_id in selected_ids_set
                    if sample_id in selected_ids_set:
                        sample_gradio.unrender().render()

            def create_samples_rows(samples: list[dict], samples_gradio: dict[str, gr.Row]) -> dict[str, gr.Row]:
                if cfg.results_folder is None:
                    return samples_gradio

                for sample in samples:
                    sample_id = str(sample.get("id"))
                    if sample_id in samples_gradio:
                        continue

                    with gr.Column(variant="panel", key=sample_id, render=False, visible=False) as sample_gradio:
                        gr.Markdown(f"### {sample_id}")
                        make_gradio_components(
                            prepare_layout_components(cfg, sample_id),
                            cfg.results_folder / Path(sample_id),
                            image_max_size=cfg.image_max_size,
                        )
                        samples_gradio[sample_id] = sample_gradio
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
            selected_ids_state: list[str],
            samples_dropdown: str | list[str] | None,
            offset_state: int,
            pagination_limit: int,
        ) -> tuple[str, list[dict[str, Any]], list[Any], gr.Gallery, list[str], list[str], int, gr.Dropdown]:
            more, consumed_count = backend.get_samples_metadata(
                offset=int(offset_state or 0), limit=int(pagination_limit or cfg.page_limit)
            )
            maybe_notify_load_more_empty(samples_ids, more)
            updated_samples_state = samples_state + more
            updated_imgs = samples_imgs + [s["image"] for s in more]
            updated_ids = samples_ids + [s["id"] for s in more]
            requested_selection = samples_dropdown if samples_dropdown is not None else selected_ids_state

            dropdown_values, selected_ids, _, gallery_index = resolve_selection_state(
                requested_selection, updated_ids, default_to_first_sample=not samples_ids
            )

            return (
                _new_render_trigger("load_more"),
                updated_samples_state,
                updated_imgs,
                gr.Gallery(value=updated_imgs, selected_index=gallery_index),
                updated_ids,
                selected_ids,
                offset_state + consumed_count,
                gr.update(choices=[SELECT_ALL, SELECT_NONE, *updated_ids], value=dropdown_values),
            )

        load_more_btn.click(
            fn=load_more,
            inputs=[
                samples_state,
                samples_imgs,
                samples_ids,
                selected_ids_state,
                samples_dropdown,
                offset_state,
                pagination_limit,
            ],
            outputs=[
                dummy_rerender_text,
                samples_state,
                samples_imgs,
                gallery,
                samples_ids,
                selected_ids_state,
                offset_state,
                samples_dropdown,
            ],
            queue=True,
        )

        # Re-search for samples
        def on_refresh_start() -> gr.Button:
            return gr.Button(value="Full samples search (running...)", interactive=False)

        def refresh_samples_from_scratch(
            pagination_limit: int,
        ) -> tuple[
            str, list[dict[str, Any]], dict[str, gr.Row], list[Any], gr.Gallery, list[str], list[str], int, gr.Dropdown
        ]:
            gr.Info("Running full samples search...", duration=10, title="Refreshing samples")
            backend.discover_all_samples()

            refreshed_samples, consumed_count = backend.get_samples_metadata(
                offset=0, limit=int(pagination_limit or cfg.page_limit)
            )
            refreshed_imgs = [sample["image"] for sample in refreshed_samples]
            refreshed_ids = [sample["id"] for sample in refreshed_samples]
            dropdown_values, selected_ids, _, gallery_index = resolve_selection_state(
                None, refreshed_ids, default_to_first_sample=True
            )
            gr.Success(
                f"Full samples search complete: found {len(backend.all_samples_dirs)} samples.",
                duration=5,
                title="Samples refreshed",
            )
            maybe_notify_refresh_empty(
                discovered_sample_count=len(backend.all_samples_dirs), loaded_sample_count=len(refreshed_samples)
            )

            return (
                _new_render_trigger("refresh"),
                refreshed_samples,
                {},
                refreshed_imgs,
                gr.Gallery(value=refreshed_imgs, selected_index=gallery_index),
                refreshed_ids,
                selected_ids,
                consumed_count,
                gr.update(choices=[SELECT_ALL, SELECT_NONE, *refreshed_ids], value=dropdown_values),
            )

        def on_refresh_end() -> gr.Button:
            return gr.Button(value="Full samples search", interactive=True)

        search_samples_btn.click(fn=on_refresh_start, inputs=[], outputs=[search_samples_btn], queue=False).then(
            fn=refresh_samples_from_scratch,
            inputs=[pagination_limit],
            outputs=[
                dummy_rerender_text,
                samples_state,
                samples_gradio,
                samples_imgs,
                gallery,
                samples_ids,
                selected_ids_state,
                offset_state,
                samples_dropdown,
            ],
            show_progress="hidden",
            queue=True,
        ).then(fn=on_refresh_end, inputs=[], outputs=[search_samples_btn], queue=False)

        def on_dropdown_change(
            samples_dropdown: str | list[str] | None, samples_ids: list[str]
        ) -> tuple[gr.Dropdown, gr.Gallery, str, list[str]]:
            dropdown_values, selected_ids, _, gallery_index = resolve_selection_state(samples_dropdown, samples_ids)
            return (
                gr.Dropdown(value=dropdown_values),
                gr.Gallery(selected_index=gallery_index),
                _new_render_trigger("dropdown"),
                selected_ids,
            )

        def on_gallery_select(
            event: gr.SelectData, samples_ids: list[str]
        ) -> tuple[gr.Dropdown, gr.Gallery, str, list[str]]:
            if not isinstance(event.index, int) or event.index >= len(samples_ids):
                return gr.skip(), gr.skip(), gr.skip(), gr.skip()
            if not event.selected:
                return gr.skip(), gr.skip(), gr.skip(), gr.skip()

            sample_id = samples_ids[event.index]
            return (
                gr.Dropdown(value=[sample_id]),
                gr.Gallery(selected_index=event.index),
                _new_render_trigger("gallery"),
                [sample_id],
            )

        samples_dropdown.select(
            fn=on_dropdown_change,
            inputs=[samples_dropdown, samples_ids],
            outputs=[samples_dropdown, gallery, dummy_rerender_text, selected_ids_state],
            queue=False,
        )
        gallery.select(
            fn=on_gallery_select,
            inputs=[samples_ids],
            outputs=[samples_dropdown, gallery, dummy_rerender_text, selected_ids_state],
            queue=False,
        )

    return demo
