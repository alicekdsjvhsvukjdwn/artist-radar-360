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
    st.info("Charge d’abord un artiste dans la section au-dessus.")
else:
    data = st.session_state.artist_data

    # -----------------------------------------------------
    # 2.0 – Récupération & filtrage des titres
    # -----------------------------------------------------
    try:
        top_resp = sp.artist_top_tracks(data["id"], country="FR")
        tracks_raw = top_resp.get("tracks", [])
    except Exception:
        tracks_raw = []

    # Garder en priorité les titres où l'artiste courant est dans les artistes du track
    tracks = [
        t for t in tracks_raw
        if any(a.get("id") == data["id"] for a in t.get("artists", []))
    ]

    # Si après filtrage y'a plus rien, on retombe sur la liste brute
    if not tracks:
        tracks = tracks_raw

    if not tracks:
        st.warning("Aucun titre exploitable trouvé pour cet artiste.")
    else:
        # On utilise un selectbox sur des indices pour éviter les problèmes de labels/état
        labels = [
            f"{t['name']} – {t['album']['name']}" for t in tracks
        ]

        selected_index = st.selectbox(
            "Choisis un titre",
            options=list(range(len(tracks))),
            format_func=lambda i: labels[i]
        )

        track = tracks[selected_index]

        # -------------------------------------------------
        # 2.1 — Carte d’identité rapide du titre
        # -------------------------------------------------
        info_col1, info_col2 = st.columns([1, 3])
        with info_col1:
            if track.get("album", {}).get("images"):
                st.image(track["album"]["images"][0]["url"], width=120)
        with info_col2:
            st.markdown(f"**{track['name']}**")
            st.caption(track["album"]["name"])
            # Affichage du player si un preview existe
            if track.get("preview_url"):
                st.audio(track["preview_url"], format="audio/mp4")

        # Variables pour la dissonance
        audio_valence = None
        text_polarity = None

        # -------------------------------------------------
        # 2.2 — ADN sonore
        # -------------------------------------------------
        st.subheader("🧬 ADN sonore")
        features = None
        audio_error = None

        # 1) Tentative avec Spotify Audio Features
        try:
            af_list = sp.audio_features([track["id"]])
            if af_list and af_list[0]:
                features = af_list[0]
        except Exception as e:
            audio_error = str(e)
            features = None

        if features is not None:
            audio_valence = features.get("valence")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("BPM", int(features.get("tempo", 0)))
            c2.metric("Énergie", round(features.get("energy", 0), 2))
            c3.metric("Dansabilité", round(features.get("danceability", 0), 2))
            c4.metric("Valence", round(features.get("valence", 0), 2))

            radar_df = pd.DataFrame({
                "Feature": ["Énergie", "Dansabilité", "Valence", "Acoustique"],
                "Valeur": [
                    features.get("energy", 0),
                    features.get("danceability", 0),
                    features.get("valence", 0),
                    features.get("acousticness", 0)
                ]
            })

            fig_radar = px.line_polar(
                radar_df,
                r="Valeur",
                theta="Feature",
                line_close=True,
                range_r=[0, 1]
            )
            fig_radar.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_radar, use_container_width=True)

        else:
            # Debug doux si vraiment Spotify fait nimp
            if audio_error:
                st.info("Spotify ne fournit pas d’Audio Features pour ce titre.")
            # Fallback : analyse simple du preview si dispo (sinon rien)
            if track.get("preview_url"):
                try:
                    resp = requests.get(track["preview_url"])
                    tmp_name = "temp_preview.m4a"
                    with open(tmp_name, "wb") as f:
                        f.write(resp.content)

                    y, sr = librosa.load(tmp_name, duration=30)
                    os.remove(tmp_name)

                    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                    rms = librosa.feature.rms(y=y)[0]

                    avg_energy = float(np.mean(rms))

                    c1, c2 = st.columns(2)
                    c1.metric("BPM (approx)", int(tempo))
                    c2.metric("Énergie moyenne", round(avg_energy, 4))

                    df_wave = pd.DataFrame({"Amplitude": y[::200]})
                    fig_wave = px.line(df_wave, y="Amplitude", title="Waveform (extrait)")
                    fig_wave.update_layout(height=200, showlegend=False)
                    st.plotly_chart(fig_wave, use_container_width=True)

                except Exception:
                    st.warning("Impossible d’analyser le preview audio.")
            else:
                st.info("Spotify ne fournit ni Audio Features ni preview pour ce titre.")

        # -------------------------------------------------
        # 2.3 — Texte & charge émotionnelle
        # -------------------------------------------------
        st.subheader("📝 Texte & charge émotionnelle")

        try:
            song = genius.search_song(track["name"], data["name"])
        except Exception:
            song = None

        if song and getattr(song, "lyrics", None):
            raw_lyrics = song.lyrics
            clean_lyrics = re.sub(r"\[.*?\]", "", raw_lyrics)

            blob = TextBlob(clean_lyrics)
            text_polarity = float(blob.sentiment.polarity)
            subjectivity = float(blob.sentiment.subjectivity)

            words = [w for w in blob.words if w.isalpha()]
            vocab_size = len(set([w.lower() for w in words]))

            c1, c2, c3 = st.columns(3)
            c1.metric("Polarité (−1 à 1)", round(text_polarity, 2))
            c2.metric("Subjectivité", round(subjectivity, 2))
            c3.metric("Richesse lexicale", vocab_size)

            with st.expander("Voir un extrait des paroles"):
                st.text("\n".join(clean_lyrics.split("\n")[:15]))
        else:
            st.info("Paroles introuvables ou non exploitables sur Genius.")

        # -------------------------------------------------
        # 2.4 — Dissonance créative
        # -------------------------------------------------
        st.subheader("⚖️ Dissonance créative")

        if (audio_valence is not None) and (text_polarity is not None):
            text_valence = (text_polarity + 1) / 2
            dissonance = abs(audio_valence - text_valence)

            st.metric("Score de dissonance", round(dissonance, 2))

            if dissonance > 0.4:
                st.success("🎭 Forte tension créative entre son et texte.")
            else:
                st.info("🎯 Cohérence émotionnelle forte entre son et texte.")
        else:
            st.info("Données insuffisantes pour calculer la dissonance (son ou texte manquant).")

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
