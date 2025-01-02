from dataclasses import dataclass
from typing import Callable, Literal, Any

import streamlit as st
from streamlit.elements.lib.dialog import DialogWidth

from spotidalyfin.ui.helpers.ui import create_aligned_columns


@dataclass
class DialogContext:
    """A class to manage shared data between dialog steps.

    The DialogContext provides a centralized way to store and access data
    across different steps of a dialog. It maintains state throughout the
    entire dialog lifecycle. It acts just like a Python dictionary.

    Example:
        ```python
        def step_content(context: DialogContext):
            # Set a value
            context.set("user_name", "John")

            # Get a value with default
            name = context.get("user_name", "Guest")

            # Check if value exists
            if context.has("user_age"):
                st.write(f"Age: {context.get('user_age')}")
        ```
    """
    def __init__(self):
        self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def has(self, key: str) -> bool:
        return key in self._data

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


@dataclass
class DialogStep:
    """A class representing a single step in a multistep dialog.

    Each step contains content to display, optional validation logic,
    and navigation control logic.

    Args:
        title: The title displayed at the top of the step.
        content: Function that renders the step's content. Receives DialogContext.
        validation_func: Optional function to validate step data before proceeding.
        next_button_text: Optional custom text for the next button.
        next_button_icon: Optional custom icon for the next button.

    Example:
        ```python
        def show_user_info(context: DialogContext):
            name = st.text_input("Name")
            context.set("name", name)

        def validate_user_info(context: DialogContext) -> tuple[bool, str]:
            if not context.get("name"):
                return False, "Name is required"
            return True, ""

        step = DialogStep(
            title="User Information",
            content=show_user_info,
            validation_func=validate_user_info,
            next_button_text="Save"
        )
        ```
    """
    title: str
    content: Callable[[DialogContext], None]
    validation_func: Callable[[DialogContext], tuple[bool, str]] = None
    next_button_text: str = None
    next_button_icon: str = None

    def __post_init__(self):
        # Default validation that always passes
        if self.validation_func is None:
            self.validation_func = lambda ctx: (True, "")

    def validate(self, context: DialogContext) -> tuple[bool, str]:
        """Run validation with dialog context

        Parameters:
            context (DialogContext): Dialog context with data from shared steps
        Returns:
            (bool, str): Tuple with validation result and error message
        """
        return self.validation_func(context)

    def render(self, context: DialogContext):
        """Render step content with dialog context"""
        self.content(context)


@dataclass
class MultiStepDialog:
    """A multistep dialog system for handling step-by-step user interactions.

    This dialog system allows for creating sequential steps with validation, data sharing
    between steps, and progress tracking. Each step can access shared context data and
    validate user input before proceeding.

    Example:
        ```python
        def step1_content(context: DialogContext):
            name = st.text_input("Your name")
            context.set("name", name)

        def step2_content(context: DialogContext):
            st.write(f"Hello {context.get('name', 'User')}!")
            age = st.number_input("Your age", min_value=0, max_value=150)
            context.set("age", age)

        def validate_step1(context: DialogContext) -> tuple[bool, str]:
            if not context.get("name"):
                return False, "Please enter your name"
            return True, ""

        def validate_step2(context: DialogContext) -> tuple[bool, str]:
            if context.get("age", 0) <= 0:
                return False, "Please enter your age"
            return True, ""

        # Create steps
        step1 = DialogStep(
            title="Step 1: Name",
            content=step1_content,
            validation_func=validate_step1
        )

        step2 = DialogStep(
            title="Step 2: Age",
            content=step2_content,
            validation_func=validate_step2
        )

        # Create and show dialog
        dialog = MultiStepDialog(
            name="User Info",
            steps=[step1, step2]
        )

        if st.button("Open Dialog"):
            dialog.render()
        ```

    The above example demonstrates:
    - Step content functions receiving dialog context
    - Validation functions with custom error messages
    - Data sharing between steps using context
    - Progress tracking with a progress bar
    - Input validation before proceeding to next step

    Each step can access data from previous steps through the context object,
    allowing for a seamless flow of information throughout the dialog process.
    """

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
            st.session_state[dialog_state] = {
                "step": 0,
                "context": DialogContext(),
                "error": ""
            }

    def get_context(self) -> DialogContext:
        """Get the dialog context"""
        return self.state["context"]

    @property
    def state(self) -> dict:
        """Shortcut to access the dialog state in session state."""
        return st.session_state[f"dialog{self.name}"]

    def get_current_step(self) -> int:
        return self.state["step"]

    def go_to_step(self, step: int):
        if 0 <= step < len(self.steps):
            self.state["step"] = step

    def next_step(self):
        """Attempt to proceed to next step with validation"""
        current_step = self.steps[self.get_current_step()]
        is_valid, error_message = current_step.validate(self.get_context())

        if is_valid:
            self.state["error"] = ""  # Clear error message
            self.go_to_step(self.get_current_step() + 1)
        else:
            self.state["error"] = error_message

    def previous_step(self):
        self.state["error"] = ""  # Clear error message
        self.go_to_step(self.get_current_step() - 1)

    def close(self):
        """Reset dialog state and rerun the app. This cannot be called from a callback."""
        self.state.update(step=0)
        st.rerun()

    def _render_progress(self):
        """Render the progress bar or step count."""
        current_step = self.get_current_step()
        total_steps = len(self.steps)

        if self.show_progress_bar:
            st.progress(current_step / (total_steps - 1),
                        text=f"Step {current_step + 1}/{total_steps}" if self.show_progress_steps else "")
        elif self.show_progress_steps:
            st.write(f"Step {current_step + 1} of {total_steps}")

    def _render_buttons(self, step: DialogStep):
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
            next_label = step.next_button_text or "Next"
            next_icon = step.next_button_icon or ":material/arrow_forward_ios:"

            col2.button(next_label, icon=next_icon, on_click=self.next_step, use_container_width=True)

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

                # Display error message if any
                if self.state.get("error"):
                    st.error(self.state["error"])

                # Render progress bar at the top, if configured
                if self.progress_bar_position == "top":
                    self._render_progress()

                # Render the current step
                st.subheader(step.title)
                step.render(self.get_context())

                # Render progress bar before buttons, if configured
                if self.progress_bar_position == "before_buttons":
                    self._render_progress()

                # Render navigation buttons
                self._render_buttons(step)

                # Render progress bar at the bottom, if configured
                if self.progress_bar_position == "bottom":
                    self._render_progress()

        _dialog()
