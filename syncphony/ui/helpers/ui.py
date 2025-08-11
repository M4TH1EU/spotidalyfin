# Function to display subheader with icon on either side
import base64
from pathlib import Path
from typing import Iterable, List
from uuid import uuid4

import streamlit as st


def _element_custom_icon(element: str, text, icon_path, icon_position='left', img_size=24) -> None:
    """Display a title/text element with an icon (supported: svg/png/jpeg) on either side.

    Parameters
    ----------
    element : str
        The HTML element to use for the text, one of 'h1', 'h2', 'h3', 'p', etc.
    text : str
        The text to display in the subheader.
    icon_path : str
        The path to the icon image file. Supported formats: svg, png, jpeg.
    icon_position : str, optional
        The position of the icon relative to the text, either 'left' or 'right', by default 'left'.
    img_size : int, optional
        The size of the icon image in pixels, by default 24.
    """
    suffix = Path(icon_path).suffix[1:]
    img_base64 = base64.b64encode(Path(icon_path).read_bytes()).decode()
    img_html = f"<img src='data:image/{'svg+xml' if suffix == "svg" else suffix};base64,{img_base64}' height='{img_size}px'>"

    # HTML code for the subheader with icon and text
    subheader_html = f"""
        <{element} style="display: flex; align-items: center; gap: 10px;">
            {img_html if icon_position == 'left' else ""}{text}{img_html if icon_position == 'right' else ""}
        </{element}>
        """

    # Display the HTML using Streamlit
    st.markdown(subheader_html, unsafe_allow_html=True)


def title_custom_icon(text, icon_path, icon_position='left', img_size=24) -> None:
    """Display a title with an icon (supported: svg/png/jpeg) on either side. See _element_custom_icon for more details."""
    _element_custom_icon('h1', text, icon_path, icon_position, img_size)


def subheader_custom_icon(text, icon_path, icon_position='left', img_size=24) -> None:
    """Display a subheader with an icon (supported: svg/png/jpeg) on either side. See _element_custom_icon for more details."""
    _element_custom_icon('h3', text, icon_path, icon_position, img_size)


def create_aligned_columns(spec=3, horizontal_alignment="center", vertical_alignment="center", **kwargs) -> List:
    """Create centered columns in Streamlit.

    Parameters
    ----------
    spec : int or Iterable of numbers
        Controls the number and width of columns to insert. Can be one of:

        - An integer that specifies the number of columns. All columns have equal
          width in this case.
        - An Iterable of numbers (int or float) that specify the relative width of
          each column. E.g. ``[0.7, 0.3]`` creates two columns where the first
          one takes up 70% of the available with and the second one takes up 30%.
          Or ``[1, 2, 3]`` creates three columns where the second one is two times
          the width of the first one, and the third one is three times that width.

    horizontal_alignment : str, optional, by default "center"
        The horizontal alignment of the content in the columns, one of "left", "center",
        or "right".

    vertical_alignment : str, optional, by default "center"
        The vertical alignment of the content in the columns, one of "top", "center",
        or "bottom".

    **kwargs
        Additional keyword arguments to pass to `st.columns`.
        see https://docs.streamlit.io/library/api-reference/layout/st.columns

    Returns
    -------
    list[st.delta_generator.DeltaGenerator]
        A list of Streamlit column objects.

    Example
    -------
    col1, col2, col3 = create_aligned_columns(3, border=True, vertical_alignment="center")
    """

    # Generate a unique key for the container
    container_key = f"aligned_{uuid4().hex}"

    # Generate the CSS scoped to this container
    style = f"""
    <style>
        .st-key-{container_key} > div:nth-child(1) > div:nth-child(n) {{
            text-align: {horizontal_alignment};
        }}
    </style>
    """

    # Apply the scoped CSS
    st.markdown(style, unsafe_allow_html=True)

    # Create the container and columns
    with st.container(key=container_key):
        return st.columns(spec, vertical_alignment=vertical_alignment, **kwargs)


def display_table(
        data: List[List],
        columns: int | Iterable[int] = None,
        text: str = "",
        border: bool = True,
        header: bool = True,
        align: str = "left",
        gap: str = "small",
        vertical_alignment: str = "center"
) -> None:
    """Enhanced table display with more formatting options.

    Args:
        data: List of rows containing either strings/numbers or callable factory functions for streamlit objects
        columns: Number of columns or list of column widths
        text: Header text
        border: Show border around table
        header: First row is header row
        align: Text alignment ("left", "center", "right")
        gap: Gap between columns ("small", "medium", "large")
        vertical_alignment: Vertical alignment of columns ("top", "center", "bottom")
    """
    with st.container(border=border):
        if text:
            st.write(text)

        # Determine columns setup
        if not columns:
            num_columns = len(data[0]) if data else 1
            columns = [1] * num_columns
        elif isinstance(columns, int):
            num_columns = columns
            columns = [1] * num_columns
        else:
            num_columns = len(columns)

        cols = create_aligned_columns(
            spec=columns,
            horizontal_alignment=align,
            vertical_alignment=vertical_alignment,
            gap=gap
        )

        # Display data
        for row_idx, row in enumerate(data):
            for col_idx, value in enumerate(row):
                if col_idx < num_columns:
                    with cols[col_idx]:
                        if callable(value):
                            # Execute the factory function to create and render the streamlit element
                            value()
                        elif isinstance(value, (str, int, float)):
                            if header and row_idx == 0:
                                st.markdown(f"**{value}**")
                            else:
                                if "<" in value and ">" in value:
                                    st.html(value)
                                else:
                                    st.write(value)


def inline_code_html(text: str, color: str) -> str:
    """Create an inline code HTML element with custom color. Recreates the Streamlit `st.code` element.

    Args:
        text: The text to display in the inline code block.
        color: The color of the text in the inline code block.

    Returns:
        str: The HTML code for the inline code block.
    """
    if color == "primary":
        color = st.get_option("theme.primaryColor")
    elif color == "secondary":
        color = st.get_option("theme.secondaryColor")

    return """
    <code style="color: {color}; font-family: 'Source Code Pro'; font-size: 0.75em; background: rgb(252,251,254); border-radius: 0.25em; margin: 0px;">
        {text}
        </code>
    """.format(text=text, color=color)
