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
# MODULE 2 — LE LABO (Audio & Texte, via iTunes + fallback)
# =========================================================
st.divider()
st.header("🧪 LE LABO")
st.caption("Analyse audio & sémantique — pas pour juger, pour comprendre")

if not st.session_state.artist_loaded:
    st.info("Charge d’abord un·e artiste dans la section au-dessus.")
else:
    data = st.session_state.artist_data
    artist_name = data["name"]

    # -----------------------------------------------------
    # 2.0 – Récupération des titres (toujours via Spotify)
    # -----------------------------------------------------
    try:
        top_resp = sp.artist_top_tracks(data["id"], country="FR")
        tracks_raw = top_resp.get("tracks", [])
    except Exception:
        tracks_raw = []

    tracks = [
        t for t in tracks_raw
        if any(a.get("id") == data["id"] for a in t.get("artists", []))
    ] or tracks_raw

    if not tracks:
        st.warning("Aucun titre exploitable trouvé pour cet artiste.")
    else:
        labels = [f"{t['name']} – {t['album']['name']}" for t in tracks]

        selected_index = st.selectbox(
            "Choisis un titre",
            options=list(range(len(tracks))),
            format_func=lambda i: labels[i],
            key="labo_track_select"
        )

        track = tracks[selected_index]
        track_title = track["name"]

        # -------------------------------------------------
        # 2.1 – iTunes : preview 30s + analyse audio
        # -------------------------------------------------
        st.subheader("🧬 ADN sonore")

        def get_itunes_preview_for_track(artist_name: str, track_title: str):
            try:
                term = f"{artist_name} {track_title}"
                params = {
                    "term": term,
                    "media": "music",
                    "entity": "song",
                    "limit": 5
                }
                resp = requests.get("https://itunes.apple.com/search", params=params)
                data_it = resp.json()
                if data_it.get("resultCount", 0) == 0:
                    return None

                # On essaie de matcher au mieux artiste + titre
                def norm(s):
                    return re.sub(r"[^a-z0-9]", "", s.lower())

                n_artist = norm(artist_name)
                n_title = norm(track_title)

                best = None
                for item in data_it["results"]:
                    a_ok = n_artist in norm(item.get("artistName", ""))
                    t_ok = n_title in norm(item.get("trackName", ""))
                    if a_ok and t_ok:
                        best = item
                        break
                if best is None:
                    best = data_it["results"][0]

                return {
                    "title": best.get("trackName"),
                    "artist": best.get("artistName"),
                    "preview_url": best.get("previewUrl"),
                    "cover": best.get("artworkUrl100")
                }
            except Exception:
                return None

        itunes_data = get_itunes_preview_for_track(artist_name, track_title)

        audio_mood = None  # proxy d'humeur audio (0-1)

        info_col1, info_col2 = st.columns([1, 3])
        with info_col1:
            # Pochette iTunes si dispo, sinon album Spotify
            if itunes_data and itunes_data.get("cover"):
                st.image(itunes_data["cover"], width=120)
            elif track.get("album", {}).get("images"):
                st.image(track["album"]["images"][0]["url"], width=120)
        with info_col2:
            st.markdown(f"**{track_title}**")
            st.caption(track["album"]["name"])
            if itunes_data and itunes_data.get("preview_url"):
                st.audio(itunes_data["preview_url"])
            elif track.get("preview_url"):
                st.audio(track["preview_url"])

        if itunes_data and itunes_data.get("preview_url"):
            try:
                resp = requests.get(itunes_data["preview_url"])
                tmp_name = "temp_preview.m4a"
                with open(tmp_name, "wb") as f:
                    f.write(resp.content)

                # 30 secondes max
                y, sr = librosa.load(tmp_name, duration=30)
                os.remove(tmp_name)

                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                rms = librosa.feature.rms(y=y)[0]
                spec_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]

                avg_energy = float(np.mean(rms))
                avg_centroid = float(np.mean(spec_centroid))
                dynamic_range = float(np.max(rms) - np.min(rms))

                # Proxy d'humeur audio (0-1) : tempo + brillance normalisés
                tempo_norm = float(np.clip((tempo - 60) / (180 - 60), 0, 1))  # 60-180 bpm
                bright_norm = float(np.clip((avg_centroid - 1000) / (6000 - 1000), 0, 1))
                audio_mood = (tempo_norm + bright_norm) / 2

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("BPM (approx)", int(tempo))
                c2.metric("Énergie moyenne", round(avg_energy, 4))
                c3.metric("Brillance moyenne", int(avg_centroid))
                c4.metric("Dynamique", round(dynamic_range, 4))

                # Waveform rapide
                df_wave = pd.DataFrame({"Amplitude": y[::200]})
                fig_wave = px.line(df_wave, y="Amplitude", title="Waveform (preview 30s)")
                fig_wave.update_layout(height=200, showlegend=False)
                st.plotly_chart(fig_wave, use_container_width=True)

            except Exception:
                st.warning("Impossible d’analyser le preview audio (problème réseau ou format).")
        else:
            st.info("Aucun extrait iTunes 30s trouvé pour ce titre.")

        # -------------------------------------------------
        # 2.2 – Paroles : Genius + fallback manuel
        # -------------------------------------------------
        st.subheader("📝 Texte & charge émotionnelle")

        lyrics_text = None
        text_polarity = None

        # 1) Tentative auto via ta fonction de scraping intelligent
        try:
            song = get_smart_lyrics(artist_name, track_title)
        except Exception:
            song = None

        if song and getattr(song, "lyrics", None):
            lyrics_text = song.lyrics
        else:
            st.info("Paroles introuvables automatiquement. Tu peux les coller ci-dessous si tu veux une analyse.")
            manual = st.text_area(
                "Colle les paroles ici (optionnel) :",
                key="manual_lyrics_input"
            )
            if manual.strip():
                lyrics_text = manual.strip()

        if lyrics_text:
            blob = TextBlob(lyrics_text)
            text_polarity = float(blob.sentiment.polarity)
            subjectivity = float(blob.sentiment.subjectivity)

            words = [w for w in blob.words if w.isalpha()]
            vocab_size = len(set([w.lower() for w in words]))

            c1, c2, c3 = st.columns(3)
            c1.metric("Polarité (−1 à 1)", round(text_polarity, 2))
            c2.metric("Subjectivité", round(subjectivity, 2))
            c3.metric("Richesse lexicale", vocab_size)

            with st.expander("Voir un extrait des paroles analysées"):
                st.text("\n".join(lyrics_text.split("\n")[:15]))
        else:
            st.info("Aucune parole disponible pour l’instant.")

        # -------------------------------------------------
        # 2.3 – Dissonance créative (audio vs texte)
        # -------------------------------------------------
        st.subheader("⚖️ Dissonance créative")

        if (audio_mood is not None) and (text_polarity is not None):
            # polarité texte [-1,1] → [0,1]
            text_valence = (text_polarity + 1) / 2
            dissonance = abs(audio_mood - text_valence)

            st.metric("Score de dissonance (0-1)", round(dissonance, 2))

            if dissonance > 0.4:
                st.success("🎭 Forte tension créative entre ambiance sonore et contenu du texte.")
            else:
                st.info("🎯 Cohérence émotionnelle globale entre son et texte.")
        else:
            st.info("Données insuffisantes pour calculer la dissonance (audio ou texte manquant).")

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
