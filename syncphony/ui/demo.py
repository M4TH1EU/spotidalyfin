import streamlit as st

# Title of the page
st.title("Streamlit Component Demo")

# Displaying basic text
st.write(
    "This page demonstrates a variety of Streamlit components to help you build interactive and visually appealing applications.")

# === Text Components ===
# Displaying Markdown
st.markdown("""
### Markdown Example
This is an example of **Markdown**. You can use it to format your text. 
- Create bullet points
- Add links like [Streamlit](https://www.streamlit.io)
- Include code blocks:
```python
import streamlit as st
st.write('Hello, World!')
```
""")

# === Buttons ===
st.subheader("Buttons")
if st.button("Click Me"):
    st.write("You clicked the button!")
else:
    st.write("You haven't clicked the button yet.")

# === Sliders ===
st.subheader("Sliders")
slider_value = st.slider("Choose a value", 0, 100, 50)
st.write(f"Slider value: {slider_value}")

# Slider with steps and custom labels
step_slider = st.slider("Choose a step value", min_value=0, max_value=100, value=50, step=5)
st.write(f"Step slider value: {step_slider}")

# === Text Inputs ===
st.subheader("Text Inputs")
text_input = st.text_input("Enter some text", "Hello Streamlit!")
st.write(f"Text input: {text_input}")

# === Multiline Text Input ===
multiline_input = st.text_area("Enter multi-line text", "Type your content here\nAnother line of text")
st.write("Multi-line input:")
st.write(multiline_input)

# === Number Inputs ===
st.subheader("Number Inputs")
number_input = st.number_input("Pick a number", min_value=1, max_value=10, value=5)
st.write(f"Selected number: {number_input}")

# === Checkboxes ===
st.subheader("Checkboxes")
checkbox = st.checkbox("I agree to the terms and conditions")
st.write(f"Checkbox status: {checkbox}")

# === Radio Buttons ===
st.subheader("Radio Buttons")
radio_button = st.radio("Select an option", ["Option 1", "Option 2", "Option 3"])
st.write(f"Selected option: {radio_button}")

# === Selectbox ===
st.subheader("Selectbox")
selectbox = st.selectbox("Select your favorite fruit", ["Apple", "Banana", "Cherry"])
st.write(f"Your favorite fruit: {selectbox}")

# === File Uploader ===
st.subheader("File Uploader")
uploaded_file = st.file_uploader("Upload a file", type=["csv", "txt", "xlsx"])
if uploaded_file is not None:
    st.write(f"File {uploaded_file.name} uploaded.")
    if uploaded_file.name.endswith("csv"):
        # Read the file into a DataFrame
        # df = pd.read_csv(uploaded_file)
        # st.write(df.head())  # Display the first few rows of the DataFrame
        pass

# === Date Input ===
st.subheader("Date Input")
# date_input = st.date_input("Pick a date", pd.to_datetime('2024-01-01'))
# st.write(f"Selected date: {date_input}")

# === Time Input ===
st.subheader("Time Input")
# time_input = st.time_input("Pick a time", pd.to_datetime('12:30').time())
# st.write(f"Selected time: {time_input}")

# === Progress Bar ===
st.subheader("Progress Bar")
progress = st.progress(45)

# === File Download ===
st.subheader("Download a File")
st.write("Click the button below to download a simple CSV file.")
download_button = st.download_button(
    label="Download CSV",
    data="col1,col2\n1,2\n3,4\n5,6\n",  # Simple CSV data
    file_name="example.csv",
    mime="text/csv",
)
st.write("Click the button to download a sample CSV file.")

# === Maps ===
st.subheader("Maps")
st.write("You can display **maps** using latitude and longitude.")
# st.map(pd.DataFrame({
#     'lat': [37.7749, 40.7128],
#     'lon': [-122.4194, -74.0060]
# }, columns=["lat", "lon"]))

# === Audio Player ===
st.subheader("Audio Player")
st.write("You can embed audio using Streamlit's audio player.")
audio_file = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
st.audio(audio_file)

# === Image Display ===
st.subheader("Image Display")
st.write("You can also display images in your app.")
image_file = "https://www.streamlit.io/images/brand/streamlit-mark-color.png"
st.image(image_file, caption="Streamlit Logo", use_column_width=True)

# === HTML and Iframes ===
st.subheader("Embedding HTML and Iframes")
st.write("You can embed custom HTML content or iframes into your Streamlit app.")
st.markdown("""
<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560" height="315" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
""", unsafe_allow_html=True)

# === Expander ===
st.subheader("Expander")
with st.expander("Click to Expand"):
    st.write(
        "This section is hidden until you click to expand it. It's useful for adding extra details or content that isn't immediately needed.")
    st.write("You can also include interactive elements here, like sliders, buttons, or graphs.")

# === Columns Layout ===
st.subheader("Columns Layout")
col1, col2, col3 = st.columns(3)
col1.write("This is column 1")
col2.write("This is column 2")
col3.write("This is column 3")

# === Multi-Select ===
st.subheader("Multi-Select")
multi_select = st.multiselect("Select multiple options", ["Apple", "Banana", "Cherry", "Date"])
st.write(f"Selected options: {multi_select}")

# Final note
st.write(
    "This demo includes many useful Streamlit components. Explore the official Streamlit documentation to discover even more components and customization options!")
