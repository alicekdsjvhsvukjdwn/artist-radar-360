# =========================================================
# ATELIER LUCIDE – Streamlit App
# =========================================================

# UI & Data
import streamlit as st
import pandas as pd
import numpy as np

# APIs
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import lyricsgenius

# Audio / NLP
import librosa
from textblob import TextBlob

# Viz
import plotly.express as px
import plotly.graph_objects as go

# Utils
import os
import re
from bs4 import BeautifulSoup

# =========================================================
# CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="ATELIER LUCIDE",
    page_icon="🎛️",
    layout="wide"
)

# Session State
DEFAULT_STATE = {
    "artist_loaded": False,
    "artist_data": None,
    "audio_done": False,
    "lyrics_done": False
}

for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# APIs
# =========================================================
try:
    sp = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=st.secrets["SPOTIPY_CLIENT_ID"],
            client_secret=st.secrets["SPOTIPY_CLIENT_SECRET"]
        )
    )
    genius = lyricsgenius.Genius(
        st.secrets["GENIUS_ACCESS_TOKEN"],
        verbose=False
    )
    LASTFM_KEY = st.secrets["LASTFM_API_KEY"]
except Exception as e:
    st.error("Erreur configuration API")
    st.stop()

# =========================================================
# MODULE 1 — LE MIROIR
# =========================================================
st.title("🎛️ ATELIER LUCIDE")
st.caption("Laboratoire créatif assisté par la data")

query = st.text_input(
    "Artiste",
    placeholder="Nom de l'artiste ou lien Spotify"
)

if st.session_state.artist_loaded:
    data = st.session_state.artist_data

    st.divider()

    # --- Header artiste
    col1, col2 = st.columns([1, 3])

    with col1:
        if data["image"]:
            st.image(data["image"], width=170)

    with col2:
        st.subheader(data["name"])
        if data["genres"]:
            st.caption(", ".join(data["genres"][:3]))
        st.markdown(f"[Spotify ↗]({data['url']})")

    st.divider()

    # --- Indicateurs de présence
    c1, c2, c3 = st.columns(3)
    c1.metric("Auditeurs / intérêt", data["popularity"])
    c2.metric("Followers", f"{data['followers']:,}")
    c3.metric("Genres détectés", len(data["genres"]))

    # --- Continuité créative
    st.subheader("🧭 Continuité créative")

    albums = sp.artist_albums(
        data["id"],
        album_type="single,album",
        limit=20,
        country="FR"
    )

    dates, titles = [], []

    for item in albums["items"]:
        if item["release_date"]:
            dates.append(item["release_date"])
            titles.append(item["name"])

    if dates:
        df_timeline = pd.DataFrame({
            "Date": pd.to_datetime(dates),
            "Sortie": titles
        }).sort_values("Date")

        fig = px.scatter(
            df_timeline,
            x="Date",
            y=[1]*len(df_timeline),
            hover_name="Sortie"
        )
        fig.update_yaxes(visible=False)
        fig.update_layout(height=200)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune sortie détectée.")


# --- Indicateurs
c1, c2, c3 = st.columns(3)
c1.metric("Auditeurs / intérêt", data["popularity"])
c2.metric("Followers", f"{data['followers']:,}")
c3.metric("Genres détectés", len(data["genres"]))

st.subheader("🧭 Continuité créative")

albums = sp.artist_albums(
    data["id"],
    album_type="single,album",
    limit=20,
    country="FR"
)

dates = []
titles = []

for item in albums["items"]:
    dates.append(item["release_date"])
    titles.append(item["name"])

df_timeline = pd.DataFrame({
    "Date": pd.to_datetime(dates),
    "Sortie": titles
}).sort_values("Date")

fig = px.scatter(
    df_timeline,
    x="Date",
    y=[1]*len(df_timeline),
    hover_name="Sortie"
)
fig.update_yaxes(visible=False)
fig.update_layout(height=200)

st.plotly_chart(fig, use_container_width=True)

# =========================================================
# MODULE 2 — LE LABO (Audio & Texte)
# =========================================================
st.divider()
st.header("🧪 LE LABO")
st.info("Analyse du son et du texte (à implémenter ici)")

# =========================================================
# MODULE 3 — LE CONTEXTE
# =========================================================
st.divider()
st.header("🧩 LE CONTEXTE")
st.info("Paysage musical et positionnement")

# =========================================================
# MODULE 4 — L'ARTISTE
# =========================================================
st.divider()
st.header("🧠 L’ARTISTE")
st.info("Profil créatif & alignement")
