"""Gradio UI: build_demo() returns a gr.Blocks app for browsing samples.

UX:
 - "Load samples" button loads a page of samples (thumbnails + metadata)
 - Dropdown selects a sample id to inspect
 - Selected sample shows: large preview image, caption, and Plotly viewer area
 - "Load more" loads next page and appends to sample state
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import gradio as gr

from .backend import Backend
from .layout_decode import make_gradio_components, prepare_layout_components

if TYPE_CHECKING:
    from .config import GradioConfig


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
                if "selected" in dummy_rerender_text:
                    selected_idx = dummy_rerender_text.rsplit("_", maxsplit=1)[-1]
                    for idx, sample_gradio in enumerate(samples_gradio.values()):
                        sample_gradio.visible = True if selected_idx == "all" else (idx == int(selected_idx))
                        if selected_idx != "all" and idx != int(selected_idx):
                            sample_gradio.unrender()
                    return
                if dummy_rerender_text != "rerender":
                    return
                samples_gradio = create_samples_rows(samples=samples_state, samples_gradio=samples_gradio)

            def create_samples_rows(samples: list[dict], samples_gradio: dict[str, gr.Row]) -> dict[str, gr.Row]:
                for sample in samples:
                    if sample.get("id") in samples_gradio:
                        continue

                    with gr.Column(variant="panel", key=sample.get("id")) as sample_gradio:
                        gr.Markdown(f"### {sample.get('id', '')}")
                        make_gradio_components(
                            prepare_layout_components(cfg, sample.get("id")), cfg.results_folder / sample["id"]
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
                        show_label=True, label="Sample selector", choices=[], interactive=True
                    )
                with gr.Column(scale=2):
                    gallery = gr.Gallery(
                        label="Samples (thumbnails)", show_label=False, rows=1, columns=5, interactive=False
                    )

        def load_more(
            samples_state: list[dict],
            samples_imgs: list[str],
            samples_ids: list[str],
            offset_state: int,
            pagination_limit: int,
        ) -> None:
            more = backend.get_samples_metadata(
                offset=int(offset_state or 0), limit=int(pagination_limit or cfg.page_limit)
            )
            imgs = samples_imgs + [s["image"] for s in more]
            ids = samples_ids + [s["id"] for s in more]
            return (
                "rerender",
                samples_state + more,
                imgs,
                imgs,
                ids,
                offset_state + len(more),
                gr.update(choices=["all", *ids], value="all"),
            )

        load_more_btn.click(
            fn=load_more,
            inputs=[samples_state, samples_imgs, samples_ids, offset_state, pagination_limit],
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

        # Show single sample
        def show_sample(event: gr.SelectData, samples_ids: list) -> list:
            is_dropdown = isinstance(event.value, str)
            sample_id = event.value if is_dropdown else samples_ids[event.index]
            idx = event.index - (1 if is_dropdown else 0)
            return (
                gr.Dropdown(value=sample_id),
                gr.Gallery(selected_index=idx if sample_id != "all" else None),
                f"selected_{idx if sample_id != 'all' else 'all'}",
            )

        def show_all() -> list:
            return [gr.Dropdown(value="all"), "selected_all"]

        samples_dropdown.select(
            fn=show_sample, inputs=[samples_ids], outputs=[samples_dropdown, gallery, dummy_rerender_text]
        )
        gallery.select(fn=show_sample, inputs=[samples_ids], outputs=[samples_dropdown, gallery, dummy_rerender_text])
        gallery.preview_close(fn=show_all, outputs=[samples_dropdown, dummy_rerender_text])

    return demo
