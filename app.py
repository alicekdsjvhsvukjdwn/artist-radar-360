# =========================================================
# PROJET 2 – Artist Performance & Strategy Dashboard
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
from urllib.parse import quote


# =========================================================
# CONFIGURATION GÉNÉRALE
# =========================================================
st.set_page_config(
    page_title="Artist Performance & Strategy Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- Session State (commun à tous les modules)
DEFAULT_STATE = {
    "artist_loaded": False,
    "artist_data": None,
    "audio_done": False,
    "lyrics_done": False,
}

for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =========================================================
# CONFIGURATION APIS (Spotify / Genius / Last.fm, etc.)
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
except Exception:
    st.error("Erreur de configuration API (Spotify / Genius / Last.fm). Vérifie les secrets.")
    st.stop()


# =========================================================
# FONCTIONS UTILITAIRES GLOBALES
# =========================================================

def _norm_text(s: str) -> str:
    """Normalise un texte pour comparer les noms (minuscules, sans accents, sans caractères spéciaux)."""
    if not s:
        return ""
    s = s.lower()
    # Option simple : enlever tout sauf lettres/chiffres
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _parse_spotify_artist_id_from_query(query: str):
    """
    Si l'utilisateur colle un lien Spotify d'artiste,
    on extrait l'ID directement.
    """
    if not query:
        return None
    # Exemple : https://open.spotify.com/artist/4W63Zz1gVQpFDuBt06yQhg?si=...
    m = re.search(r"open\.spotify\.com/artist/([a-zA-Z0-9]+)", query)
    if m:
        return m.group(1)
    return None


def search_best_artist(query: str):
    """
    Retourne le meilleur artiste Spotify pour une requête donnée,
    en évitant le piège du 'premier résultat au hasard'.

    Stratégie :
    1. Si lien Spotify -> on récupère directement l'artiste par ID.
    2. Sinon :
       - on cherche jusqu'à 10 artistes,
       - on privilégie :
         a) nom EXACT (normalisé),
         b) nom qui commence par la requête,
         c) nom qui contient la requête,
         d) sinon : artiste le plus populaire.
    """
    if not query:
        return None

    # 1) Cas lien Spotify copie-collé
    artist_id = _parse_spotify_artist_id_from_query(query)
    if artist_id:
        try:
            return sp.artist(artist_id)
        except Exception:
            return None

    # 2) Cas recherche par nom
    try:
        res = sp.search(q=query, type="artist", limit=10)
        items = res.get("artists", {}).get("items", [])
    except Exception:
        return None

    if not items:
        return None

    q_norm = _norm_text(query)

    # a) Nom exact
    exact_matches = [
        a for a in items
        if _norm_text(a.get("name", "")) == q_norm
    ]
    if exact_matches:
        # s'il y en a plusieurs, on prend le plus populaire
        return sorted(exact_matches, key=lambda a: a.get("popularity", 0), reverse=True)[0]

    # b) Nom qui commence par la requête normalisée
    startswith_matches = [
        a for a in items
        if _norm_text(a.get("name", "")).startswith(q_norm)
    ]
    if startswith_matches:
        return sorted(startswith_matches, key=lambda a: a.get("popularity", 0), reverse=True)[0]

    # c) Nom qui contient la requête normalisée
    contains_matches = [
        a for a in items
        if q_norm in _norm_text(a.get("name", ""))
    ]
    if contains_matches:
        return sorted(contains_matches, key=lambda a: a.get("popularity", 0), reverse=True)[0]

    # d) Fallback : prendre le plus populaire parmi les résultats
    return sorted(items, key=lambda a: a.get("popularity", 0), reverse=True)[0]


def get_any_lyrics(artist_name: str, track_title: str):
    """
    Essaie de récupérer des paroles depuis l'API lyrics.ovh.
    Retourne un string (paroles) ou None.
    """
    try:
        clean_title = re.sub(r"\(.*?\)", "", track_title)
        clean_title = clean_title.split("-")[0].strip()

        def fetch(a, t):
            url = f"https://api.lyrics.ovh/v1/{quote(a)}/{quote(t)}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                txt = data.get("lyrics")
                if txt and "No lyrics found" not in txt:
                    return txt.strip()
            return None

        txt = fetch(artist_name, clean_title)
        if txt:
            return txt

        short_artist = artist_name.split()[-1]
        txt = fetch(short_artist, clean_title)
        if txt:
            return txt

    except Exception:
        pass

    return None


def get_itunes_preview_for_track(artist_name: str, track_title: str):
    """
    Récupère un preview iTunes (30s) pour un titre donné.
    Retourne dict {title, artist, preview_url, cover} ou None.
    """
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

LASTFM_ROOT = "https://ws.audioscrobbler.com/2.0/"


def get_lastfm_artist_tags(artist_name: str, limit: int = 20):
    """
    Récupère les top tags Last.fm pour un artiste donné.
    Retourne une liste de dicts [{'name': ..., 'count': ...}, ...]
    ou une liste vide si rien.
    """
    try:
        params = {
            "method": "artist.getTopTags",
            "artist": artist_name,
            "api_key": LASTFM_KEY,
            "format": "json",
            "autocorrect": 1,
        }
        resp = requests.get(LASTFM_ROOT, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tags = data.get("toptags", {}).get("tag", [])

        if not tags:
            return []

        # Last.fm renvoie parfois un dict quand il n'y a qu'un tag
        if isinstance(tags, dict):
            tags = [tags]

        # Trier par count décroissant et limiter
        tags_sorted = sorted(
            tags,
            key=lambda t: int(t.get("count", 0)),
            reverse=True
        )
        return tags_sorted[:limit]

    except Exception:
        return []


def get_lastfm_similar_artists(artist_name: str, limit: int = 10):
    """
    Récupère des artistes similaires depuis Last.fm.
    Retourne une liste de dicts [{'name': ..., 'match': ..., 'url': ...}, ...]
    ou une liste vide si rien.
    """
    try:
        params = {
            "method": "artist.getSimilar",
            "artist": artist_name,
            "api_key": LASTFM_KEY,
            "format": "json",
            "autocorrect": 1,
            "limit": limit,
        }
        resp = requests.get(LASTFM_ROOT, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        similar = data.get("similarartists", {}).get("artist", [])

        if not similar:
            return []

        if isinstance(similar, dict):
            similar = [similar]

        return similar[:limit]

    except Exception:
        return []


# =========================================================
# UI GLOBALE : TITRE + BARRE LATERALE
# =========================================================

st.title("📊 Artist Performance & Strategy Dashboard")
st.caption("Prototype data x musique – audit, analyse produit, benchmark et tendances marché.")

st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Aller à :",
    [
        "1. Audit artiste",
        "2. Labo d'analyse (son + texte)",
        "3. Comparateur & contexte",
        "4. Prédicteur de tendance"
    ]
)

# =========================================================
# BARRE DE RECHERCHE ARTISTE (partagée entre pages)
# =========================================================

st.subheader("🔍 Sélection d'un artiste (base de travail)")

query = st.text_input(
    "Artiste (nom ou lien Spotify)",
    placeholder="Ex : Laylow, Angèle, PNL...",
    key="artist_search_query"
)

col_search, col_btn = st.columns([4, 1])
with col_btn:
    load_artist = st.button("Charger l'artiste")

if load_artist and query:
    artist = search_best_artist(query)
    if artist is None:
        st.warning("Aucun artiste pertinent trouvé pour cette requête.")
        st.session_state.artist_loaded = False
        st.session_state.artist_data = None
    else:
        st.session_state.artist_data = {
            "id": artist["id"],
            "name": artist["name"],
            "genres": artist["genres"],
            "followers": artist["followers"]["total"],
            "popularity": artist["popularity"],
            "image": artist["images"][0]["url"] if artist.get("images") else None,
            "url": artist["external_urls"]["spotify"]
        }
        st.session_state.artist_loaded = True

# =========================================================
# FONCTIONS DE RENDU PAR PAGE
# =========================================================

# =========================================================
# PAGE 1 : L'AUDIT ARTISTE
# =========================================================
def render_page_audit():
    """
    PAGE 1 – Diagnostic carrière
    1.1 Baromètre de notoriété
    1.2 Timeline de consistance (le grind)
    1.3 Écosystème & perception (TODO Last.fm)
    """
    if not st.session_state.artist_loaded:
        st.info("Commence par charger un·e artiste au-dessus.")
        return

    data = st.session_state.artist_data

    st.markdown("### 📄 PAGE 1 – L'AUDIT ARTISTE")
    st.caption("Radiographie de la santé de carrière à l'instant T.")

    st.divider()

    # --- HEADER ARTISTE ------------------------------------------------------
    col1, col2 = st.columns([1, 3])
    with col1:
        if data["image"]:
            st.image(data["image"], width=170)
    with col2:
        st.subheader(data["name"])
        if data["genres"]:
            st.caption(", ".join(data["genres"][:3]))
        st.markdown(f"[Voir sur Spotify ↗]({data['url']})")

    st.divider()

    # --- 1.1 BAROMÈTRE DE NOTORIÉTÉ -----------------------------------------
    st.markdown("#### 1.1 Baromètre de notoriété")
    c1, c2, c3 = st.columns(3)
    c1.metric("Popularité Spotify", data["popularity"])
    c2.metric("Followers", f"{data['followers']:,}")
    c3.metric("Nb genres associés", len(data["genres"]))

    st.caption("👉 Vue rapide : niche, émergent ou déjà bien installé·e.")

    # --- 1.2 TIMELINE DE CONSISTANCE (LE GRIND) ------------------------------
    st.markdown("#### 1.2 Timeline de consistance (le grind)")

    # Récupération des sorties (albums + singles)
    try:
        albums = sp.artist_albums(
            data["id"],
            album_type="single,album",
            limit=50,
            country="FR"
        )
    except Exception:
        albums = {"items": []}

    dates, titles, types = [], [], []

    for item in albums.get("items", []):
        release_date = item.get("release_date")
        if release_date:
            dates.append(release_date)
            titles.append(item.get("name", "Sans titre"))
            # "album_type" vaut typiquement "album" ou "single"
            album_type = item.get("album_type", "other")
            types.append(album_type)

    if dates:
        df_timeline = pd.DataFrame({
            "Date": pd.to_datetime(dates),
            "Titre": titles,
            "Type": types
        }).sort_values("Date")

        # Scatter 1D : on met tout sur y=1, coloré par type
        fig = px.scatter(
            df_timeline,
            x="Date",
            y=[1] * len(df_timeline),
            color="Type",
            hover_name="Titre",
            labels={"y": ""}
        )
        fig.update_yaxes(visible=False)
        fig.update_layout(
            height=220,
            margin=dict(l=0, r=0, t=30, b=0),
            legend_title_text="Type de sortie"
        )

        # 🔴 Albums en rouge, 🔵 singles en bleu clair, le reste en gris
        fig.for_each_trace(
            lambda trace: (
                trace.update(marker=dict(color="red", size=10))
                if trace.name == "album"
                else trace.update(marker=dict(color="#66b3ff", size=8))
                if trace.name == "single"
                else trace.update(marker=dict(color="lightgray", size=8))
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        # --- RYTHME MOYEN DE SORTIE ------------------------------------------
        df_sorted = df_timeline.sort_values("Date").copy()
        df_sorted["delta_days"] = df_sorted["Date"].diff().dt.days

        deltas = df_sorted["delta_days"].dropna()

        if not deltas.empty and (deltas > 0).any():
            # On enlève les éventuels 0 jours (sorties le même jour)
            deltas_pos = deltas[deltas > 0]

            if deltas_pos.empty:
                st.caption(
                    "Rythme moyen de sortie : toutes les sorties sont le même jour "
                    "(compilations, rééditions ou dataset limité)."
                )
            else:
                median_gap = float(deltas_pos.median())
                mean_gap = float(deltas_pos.mean())

                # On prend la médiane comme indicateur principal (plus robuste)
                jours_par_sortie = int(round(median_gap))
                sorties_par_an = 365.0 / median_gap if median_gap > 0 else None

                c_gap1, c_gap2 = st.columns(2)
                c_gap1.metric(
                    "Rythme moyen de sortie",
                    f"1 sortie tous les ~{jours_par_sortie} jours"
                )
                if sorties_par_an:
                    c_gap2.metric(
                        "Sorties estimées / an",
                        f"{sorties_par_an:.1f}"
                    )

                st.caption(
                    f"(Médiane des intervalles entre sorties : {median_gap:.1f} jours ; "
                    f"moyenne : {mean_gap:.1f} jours.)"
                )
        else:
            st.caption(
                "Rythme moyen de sortie non calculable (trop peu de sorties ou dates identiques)."
            )

    else:
        st.info("Aucune sortie détectée pour construire une timeline.")

    # --- 1.3 ÉCOSYSTÈME & PERCEPTION (VIBE CHECK) --------------------------
    st.markdown("#### 1.3 Écosystème & perception (vibe check)")

    artist_name = data["name"]

    # Récupération Last.fm
    tags = get_lastfm_artist_tags(artist_name, limit=15)
    similar = get_lastfm_similar_artists(artist_name, limit=8)

    if not tags and not similar:
        st.info(
            "Aucune donnée exploitable trouvée sur Last.fm pour cet artiste "
            "(peu ou pas de tags / artistes similaires)."
        )
        return

    col_tags, col_sim = st.columns(2)

    # ----- Nuage de tags (version bar chart horizontale) --------------------
    with col_tags:
        st.markdown("**Nuage de tags Last.fm (perception du public)**")

        if tags:
            df_tags = pd.DataFrame({
                "Tag": [t.get("name", "") for t in tags],
                "Poids": [int(t.get("count", 0)) for t in tags],
            })

            # On affiche les tags les plus forts en haut
            df_tags_sorted = df_tags.sort_values("Poids", ascending=True)

            fig_tags = px.bar(
                df_tags_sorted,
                x="Poids",
                y="Tag",
                orientation="h",
            )
            fig_tags.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig_tags, use_container_width=True)

            top_labels = ", ".join(
                df_tags.sort_values("Poids", ascending=False)["Tag"].head(5)
            )
            st.caption(f"🧠 Comment le public le catégorise : {top_labels}")
        else:
            st.info("Aucun tag significatif trouvé pour cet artiste sur Last.fm.")

    # ----- Artistes similaires (liste) --------------------------------------
    with col_sim:
        st.markdown("**Artistes similaires (voisinage Last.fm)**")

        if similar:
            sim_names = [a.get("name", "") for a in similar]
            sim_match = [float(a.get("match", 0)) for a in similar]
            sim_urls = [a.get("url", "") for a in similar]

            df_sim = pd.DataFrame({
                "Artiste": sim_names,
                "Similarité": sim_match,
                "Lien": sim_urls,
            })

            # On n'affiche que nom + similarité, lien cliquable dans un tableau markdown simple
            st.dataframe(
                df_sim[["Artiste", "Similarité"]],
                use_container_width=True,
                hide_index=True,
            )

            # petite liste de liens en dessous
            st.markdown("Artistes à explorer :")
            for name, url in zip(sim_names, sim_urls):
                if url:
                    st.markdown(f"- [{name}]({url})")
                else:
                    st.markdown(f"- {name}")
        else:
            st.info("Pas assez de données Last.fm pour lister des artistes similaires.")

    st.caption(
        "👉 À lire comme : est-ce que ces tags/voisins collent à l'image que l'artiste revendique "
        "et aux genres Spotify affichés plus haut ?"
    )



# -----------------------------------
# PAGE 2 : LE LABO D'ANALYSE (PRODUIT)
# -----------------------------------
def render_page_labo():
    """
    PAGE 2 – Analyse du produit (son + texte)
    2.1 Physique du signal (ADN sonore)
    2.2 Analyse sémantique (paroles)
    2.3 Score de dissonance (audio vs texte)
    """
    if not st.session_state.artist_loaded:
        st.info("Charge d’abord un·e artiste pour accéder au labo.")
        return

    data = st.session_state.artist_data
    artist_name = data["name"]

    st.markdown("### 📄 PAGE 2 – LE LABO D'ANALYSE")
    st.caption("Analyse audio & sémantique – pas pour juger, pour comprendre le produit.")

    # 2.0 – Sélection d'un titre (toujours via Spotify)
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
        return

    labels = [f"{t['name']} – {t['album']['name']}" for t in tracks]

    selected_index = st.selectbox(
        "Choisis un titre à analyser",
        options=list(range(len(tracks))),
        format_func=lambda i: labels[i],
        key="labo_track_select"
    )

    track = tracks[selected_index]
    track_title = track["name"]

    st.divider()

    # 2.1 Physique du signal (ADN sonore)
    st.markdown("#### 2.1 Physique du signal (ADN sonore)")

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
            c2.metric("Énergie moyenne (RMS)", round(avg_energy, 4))
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

    st.divider()

    # 2.2 Analyse sémantique (NLP)
    st.markdown("#### 2.2 Analyse sémantique des paroles")

    lyrics_text = None
    text_polarity = None

    # Tentatives automatiques via lyrics.ovh
    lyrics_text = get_any_lyrics(artist_name, track_title)

    # Fallback manuel
    if not lyrics_text:
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

        # Richesse lexicale simple
        tokens = re.findall(r"\b\w+\b", lyrics_text.lower())
        vocab_size = len(set(tokens)) if tokens else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Polarité (-1 à 1)", round(text_polarity, 2))
        c2.metric("Subjectivité", round(subjectivity, 2))
        c3.metric("Richesse lexicale", vocab_size)

        with st.expander("Voir un extrait des paroles analysées"):
            st.text("\n".join(lyrics_text.split("\n")[:15]))
    else:
        st.info("Aucune parole disponible pour l’instant.")

    st.divider()

    # 2.3 Score de dissonance audio vs texte
    st.markdown("#### 2.3 Score de dissonance (audio vs texte)")

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


# -------------------------------------
# PAGE 3 : LE COMPARATEUR (BENCHMARKING)
# -------------------------------------
def render_page_comparateur():
    """
    PAGE 3 – Comparateur & benchmarking
    3.1 Radar de compétitivité (ton titre vs moyenne du style)
    3.2 Diagnostic automatique (phrases conseils)
    TODO: ajouter plus tard un vrai comparatif multi-artistes / multi-tracks.
    """
    if not st.session_state.artist_loaded:
        st.info("Charge d’abord un·e artiste pour accéder au comparateur.")
        return

    st.markdown("### 📄 PAGE 3 – LE COMPARATEUR")
    st.caption("Situer un titre par rapport aux codes statistiques d'un style.")

    st.markdown("#### 🎯 Comparer un titre à un style")

    col_left, col_mid, col_right = st.columns([3, 2, 1])

    with col_left:
        track_query = st.text_input(
            "Titre de référence",
            value="",
            placeholder="Ex : Angèle – Balance ton quoi",
            key="ctx_track_query"
        )

    with col_mid:
        genre_query = st.text_input(
            "Style / scène ciblée",
            value="",
            placeholder="Ex : french pop, pop, techno, rap français...",
            key="ctx_genre_query"
        )

    with col_right:
        st.write("")
        st.write("")
        btn_compare = st.button("Analyser le contexte")

    if not btn_compare:
        return

    # Vérifs basiques
    if not track_query or not genre_query:
        st.warning("Remplis le **titre de référence** et le **style ciblé**.")
        return

    # 3.1 Titre de référence
    res_track = sp.search(q=track_query, type="track", limit=1, market="FR")
    items = res_track.get("tracks", {}).get("items", [])
    if not items:
        st.error("Titre introuvable sur Spotify. Essaie un format `Artiste – Titre` ou un autre morceau.")
        return

    my_track = items[0]

    try:
        feats_list = sp.audio_features([my_track["id"]])
        my_features = feats_list[0] if feats_list and feats_list[0] else None
    except Exception:
        my_features = None

    if my_features is None:
        st.error("Spotify ne fournit pas d’Audio Features pour ce titre de référence.")
        return

    # 3.2 Paysage du style (titres de comparaison)
    res_genre = sp.search(
        q=f'genre:"{genre_query}"',
        type="track",
        limit=50,
        market="FR"
    )
    genre_items = res_genre.get("tracks", {}).get("items", [])

    # Fallback : recherche libre si genre précis ne marche pas
    if not genre_items:
        res_genre_free = sp.search(
            q=genre_query,
            type="track",
            limit=50,
            market="FR"
        )
        genre_items = res_genre_free.get("tracks", {}).get("items", [])

    if not genre_items:
        st.error(
            f"Aucun titre trouvé pour le style '{genre_query}'. "
            "Essaie un terme plus simple (ex : 'pop', 'trap', 'house', 'rap français')."
        )
        return

    genre_ids = [t["id"] for t in genre_items]

    try:
        genre_features_raw = sp.audio_features(genre_ids)
        genre_features = [f for f in genre_features_raw if f]
    except Exception:
        genre_features = []

    if not genre_features:
        st.error("Spotify ne fournit pas d’Audio Features pour les titres de ce style.")
        return

    df_genre = pd.DataFrame(genre_features)

    # 3.3 Radar de compétitivité
    st.subheader("🕸️ Radar de compétitivité")

    avg_stats = {
        "Énergie": float(df_genre["energy"].mean()),
        "Dansabilité": float(df_genre["danceability"].mean()),
        "Valence": float(df_genre["valence"].mean()),
        "Acoustique": float(df_genre["acousticness"].mean()),
        "Puissance (Loudness)": float((df_genre["loudness"].mean() + 60) / 60),
    }

    my_stats = {
        "Énergie": float(my_features["energy"]),
        "Dansabilité": float(my_features["danceability"]),
        "Valence": float(my_features["valence"]),
        "Acoustique": float(my_features["acousticness"]),
        "Puissance (Loudness)": float((my_features["loudness"] + 60) / 60),
    }

    categories = list(avg_stats.keys())

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=list(avg_stats.values()),
        theta=categories,
        fill='toself',
        name=f"Moyenne '{genre_query}'",
        opacity=0.4
    ))

    fig.add_trace(go.Scatterpolar(
        r=list(my_stats.values()),
        theta=categories,
        fill='toself',
        name="Ton titre",
        opacity=0.8
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=True,
        height=450
    )

    c_info, c_chart = st.columns([1, 2])
    with c_info:
        if my_track.get("album", {}).get("images"):
            st.image(my_track["album"]["images"][0]["url"], width=140)
        st.markdown(f"**{my_track['name']}**")
        st.caption(my_track["artists"][0]["name"])
        st.metric("Popularité du titre", f"{my_track['popularity']}/100")

        avg_pop = sum(t["popularity"] for t in genre_items) / len(genre_items)
        st.metric(f"Popularité moyenne du style", f"{int(avg_pop)}/100")

    with c_chart:
        st.plotly_chart(fig, use_container_width=True)

    # 3.4 Diagnostic automatisé
    st.subheader("💡 Diagnostic automatisé")

    msgs = []

    # Durée
    avg_duration = df_genre["duration_ms"].mean() / 1000
    my_duration = my_features["duration_ms"] / 1000
    diff_dur = my_duration - avg_duration

    if diff_dur > 30:
        msgs.append(
            f"⏱️ Ton titre est **long** ({int(my_duration)}s) "
            f"vs moyenne du style ({int(avg_duration)}s). "
            "Tu peux envisager de raccourcir l’intro ou la fin."
        )
    elif diff_dur < -30:
        msgs.append(
            f"⏱️ Ton titre est **court** ({int(my_duration)}s). "
            "C’est intéressant pour le replay, mais vérifie que la narration est complète."
        )

    # Énergie
    if my_stats["Énergie"] < avg_stats["Énergie"] - 0.15:
        msgs.append(
            "⚡ Énergie en-dessous de la moyenne du style. "
            "Si tu vises la scène / TikTok, regarde la dynamique (drums, transients, saturation)."
        )
    elif my_stats["Énergie"] > avg_stats["Énergie"] + 0.15:
        msgs.append(
            "⚡ Titre plus énergique que la moyenne. "
            "Ça peut te démarquer, mais attention à la fatigue d’écoute."
        )

    # Dansabilité
    if my_stats["Dansabilité"] < avg_stats["Dansabilité"] - 0.15:
        msgs.append(
            "💃 Groove moins dansant que la moyenne. "
            "Si tu vises clubs / réseaux, check pattern de drums, basse, placement rythmique."
        )

    # Valence (mood)
    if my_stats["Valence"] < avg_stats["Valence"] - 0.2:
        msgs.append(
            "🌫️ Ambiance plus sombre que le standard du style. "
            "Ça peut créer une niche émotionnelle intéressante."
        )
    elif my_stats["Valence"] > avg_stats["Valence"] + 0.2:
        msgs.append(
            "🌞 Ambiance plus lumineuse que la moyenne. "
            "Si le marché est plutôt dark, tu peux jouer la carte contre-pied."
        )

    if not msgs:
        st.success(
            "Ton titre est globalement aligné avec les codes du style. "
            "Tu peux te permettre d’expérimenter sur d’autres dimensions (structure, texte, visuel)."
        )
    else:
        for m in msgs:
            st.write(m)

    # TODO : plus tard, ajouter un bloc “Vue label”
    # avec une interprétation business : risque, potentiel, priorisation, etc.


# --------------------------------------------
# PAGE 4 : LE PRÉDICTEUR DE TENDANCE (SQUELETTE)
# --------------------------------------------
def render_page_predictor():
    """
    PAGE 4 – Prédicteur de tendance (squelette)
    4.1 Score "TikTok Potential"
    4.2 Météo du marché (analyse Top 50)
    Pour l'instant, uniquement structure & placeholders.
    """
    st.markdown("### 📄 PAGE 4 – LE PRÉDICTEUR DE TENDANCE")
    st.caption("Esquisser des signaux sur la viralité potentielle et l'humeur du marché.")

    st.markdown("#### 4.1 Score 'TikTok Potential' (squelette)")
    st.info(
        "TODO :\n"
        "- Sélection ou saisie d'un titre (comme dans le labo / comparateur)\n"
        "- Calculer une note sur 100 basée sur : intro courte, drop rapide, "
        "durée totale, répétitivité des paroles, BPM, etc.\n"
        "- Afficher la répartition des critères + un commentaire interprétatif."
    )

    st.markdown("#### 4.2 Météo du marché (Top 50)")
    st.info(
        "TODO :\n"
        "- Utiliser l'API Spotify pour charger une playlist de référence "
        "(ex : Top 50 France).\n"
        "- Calculer : BPM moyen, valence moyenne, énergie moyenne, etc.\n"
        "- Afficher un petit 'bulletin météo' du marché : "
        "\"Rapide & sombre\", \"Lent & lumineux\", etc."
    )

    # TODO plus tard :
    # - Ajouter des graphes de tendance dans le temps (si données historiques)
    # - Relier cette météo aux décisions label : quand sortir tel type de track.


# =========================================================
# ROUTAGE DES PAGES
# =========================================================

st.divider()

if page == "1. Audit artiste":
    render_page_audit()
elif page == "2. Labo d'analyse (son + texte)":
    render_page_labo()
elif page == "3. Comparateur & contexte":
    render_page_comparateur()
elif page == "4. Prédicteur de tendance":
    render_page_predictor()
