import streamlit as st

st.header("Accounts settings")
st.write("Here you can manage all the accounts that you have added to Spotidalyfin.")

st.subheader("Spotify")
st.write("Here you can add or remove Spotify accounts.")
st.button("Add Spotify account")

st.subheader("TIDAL")
st.write("Here you can add or remove TIDAL accounts.")
st.button("Add TIDAL account")
