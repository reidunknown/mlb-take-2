import streamlit as st
from update_game import update_games
from tracker import track_games
from app import show_ui  # Rename your app's Streamlit logic to a function

def main():
    st.title("MLB Daily Lock Tracker")

    # Step 1: Run data prep scripts
    with st.spinner("Updating games..."):
        update_games()

    with st.spinner("Tracking game results..."):
        track_games()

    # Step 2: Show Streamlit UI
    show_ui()

if __name__ == "__main__":
    main()
