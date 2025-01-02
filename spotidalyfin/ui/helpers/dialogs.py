from dataclasses import dataclass
from typing import Callable, Literal

import streamlit as st
from streamlit.elements.lib.dialog import DialogWidth

from spotidalyfin.ui.helpers.ui import create_aligned_columns


class DialogStep:
    def __init__(self, title: str, content: Callable):
        self.title = title
        self.content = content

    def render(self):
        self.content()


@dataclass
class MultiStepDialog:
    name: str
    steps: list[DialogStep]
    show_progress_bar: bool = False
    show_progress_steps: bool = False
    progress_bar_position: Literal["top", "bottom", "before_buttons"] = "top"
    allow_back: bool = True
    width: DialogWidth = "small"

    def __post_init__(self):
        """Initialize session state for the dialog."""
        dialog_state = f"dialog{self.name}"
        if dialog_state not in st.session_state:
            st.session_state[dialog_state] = {"step": 0, "data": {}}

    @property
    def state(self):
        """Shortcut to access the dialog state in session state."""
        return st.session_state[f"dialog{self.name}"]

    def get_data(self) -> dict:
        return self.state["data"]

    def set_data(self, data: dict):
        self.state["data"] = data

    def get_key(self, key: str) -> any:
        return self.get_data().get(key)

    def set_key(self, key: str, value) -> None:
        self.state["data"][key] = value

    def get_current_step(self) -> int:
        return self.state["step"]

    def go_to_step(self, step: int):
        if 0 <= step < len(self.steps):
            self.state["step"] = step

    def next_step(self):
        self.go_to_step(self.get_current_step() + 1)

    def previous_step(self):
        self.go_to_step(self.get_current_step() - 1)

    def close(self):
        """Reset dialog state and rerun the app. This cannot be called from a callback."""
        self.state.update({"step": 0, "data": {}})
        st.rerun()

    def _render_progress(self):
        """Render the progress bar or step count."""
        current_step = self.get_current_step() + 1
        total_steps = len(self.steps)

        if self.show_progress_bar:
            st.progress(current_step / total_steps,
                        text=f"Step {current_step}/{total_steps}" if self.show_progress_steps else "")
        elif self.show_progress_steps:
            st.write(f"Step {current_step} of {total_steps}")

    def _render_buttons(self):
        """Render navigation buttons (Back, Next, Done)."""
        can_go_next = self.get_current_step() < (len(self.steps) - 1)
        can_go_back = self.allow_back and self.get_current_step() >= 1

        col1, col2 = create_aligned_columns(2)

        # Back button, only rendered if 0 < current_step < total_steps, we don't want it on first / finish steps
        if can_go_back and can_go_next:
            col1.button("Back", icon=":material/arrow_back_ios_new:", on_click=self.previous_step,
                        use_container_width=True)

        # Next button, only rendered if 0 <= current_step < total_steps, we don't want it on finish step
        if can_go_next:
            col2.button("Next", icon=":material/arrow_forward_ios:", on_click=self.next_step, use_container_width=True)

        # Done button, only rendered on last step
        if can_go_back and not can_go_next:  # Render Done button on the last step
            if st.button("Done", icon=":material/done:", use_container_width=True):
                self.close()

    def render(self):
        """Render the dialog with its current step and navigation."""

        @st.dialog(self.name, width=self.width)
        def _dialog():
            current_step = self.get_current_step()

            if current_step < len(self.steps):
                step = self.steps[current_step]

                # Render progress bar at the top, if configured
                if self.progress_bar_position == "top":
                    self._render_progress()

                # Render the current step
                st.subheader(step.title)
                step.render()

                # Render progress bar before buttons, if configured
                if self.progress_bar_position == "before_buttons":
                    self._render_progress()

                # Render navigation buttons
                self._render_buttons()

                # Render progress bar at the bottom, if configured
                if self.progress_bar_position == "bottom":
                    self._render_progress()

        _dialog()
