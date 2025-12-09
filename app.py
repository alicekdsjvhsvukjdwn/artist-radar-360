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

col_search, col_btn = st.columns([4, 1])

with col_btn:
    load_artist = st.button("Charger")

if load_artist and query:
    try:
        result = sp.search(q=query, type="artist", limit=1)

        if result["artists"]["items"]:
            artist = result["artists"]["items"][0]

            st.session_state.artist_data = {
                "id": artist["id"],
                "name": artist["name"],
                "genres": artist["genres"],
                "followers": artist["followers"]["total"],
                "popularity": artist["popularity"],
                "image": artist["images"][0]["url"] if artist["images"] else None,
                "url": artist["external_urls"]["spotify"]
            }

            st.session_state.artist_loaded = True
        else:
            st.warning("Aucun artiste trouvé.")

    except Exception as e:
        st.error("Erreur lors du chargement de l’artiste.")


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


# =========================================================
# MODULE 2 — LE LABO (Audio & Texte)
# =========================================================
st.divider()
st.header("🧪 LE LABO")
st.caption("Analyse audio & sémantique — pas pour juger, pour comprendre")

if not st.session_state.artist_loaded:
    st.info("Charge un artiste pour lancer l’analyse.")
else:
    data = st.session_state.artist_data

    # -----------------------------------------------------
    # Sélection d’un titre
    # -----------------------------------------------------
    tracks = sp.artist_top_tracks(data["id"], country="FR")["tracks"]

    if not tracks:
        st.warning("Aucun titre analysable.")
    else:
        track_names = [t["name"] for t in tracks]
        selected_track_name = st.selectbox("Choisis un titre", track_names)

        track = next(t for t in tracks if t["name"] == selected_track_name)

        # -------------------------------------------------
        # 2.1 — Analyse Audio (Spotify Audio Features)
        # -------------------------------------------------
        st.subheader("🎚️ ADN sonore")

        try:
            af = sp.audio_features([track["id"]])
            features = af[0] if af and af[0] else None
        except Exception:
            features = None

        if features is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("BPM", int(features["tempo"]))
            c2.metric("Énergie", round(features["energy"], 2))
            c3.metric("Dansabilité", round(features["danceability"], 2))
            c4.metric("Valence", round(features["valence"], 2))

            radar_df = pd.DataFrame({
                "Feature": ["Énergie", "Dansabilité", "Valence", "Acoustique"],
                "Valeur": [
                    features["energy"],
                    features["danceability"],
                    features["valence"],
                    features["acousticness"]
                ]
            })

            fig = px.line_polar(
                radar_df,
                r="Valeur",
                theta="Feature",
                line_close=True,
                range_r=[0, 1]
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Spotify ne fournit pas d’Audio Features pour ce titre.")


        # -------------------------------------------------
        # 2.3 — Dissonance créative (son vs texte)
        # -------------------------------------------------
        st.subheader("⚖️ Dissonance créative")

        if features and "polarity" in locals():
            dissonance = abs(features["valence"] - ((polarity + 1) / 2))

            st.metric("Score de dissonance", round(dissonance, 2))

            if dissonance > 0.4:
                st.success("🎭 Forte tension créative (joie sonore / texte sombre ou inverse).")
            else:
                st.info("🎯 Alignement émotionnel classique (cohérence forte).")
        else:
            st.info("Données insuffisantes pour calculer la dissonance.")

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
