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

def classify_tempo(bpm: float):
    if bpm is None:
        return "Inconnu", "Tempo non estimé."
    if bpm < 80:
        return "Lent", "Plutôt adapté à des ambiances posées / introspectives."
    elif bpm < 110:
        return "Modéré", "Zone mid-tempo polyvalente (rap, pop, r&b)."
    elif bpm < 140:
        return "Rapide", "Énergie naturelle pour bangers, club, formats dynamiques."
    else:
        return "Très rapide", "Très intense, à manier avec soin pour ne pas fatiguer l’auditeur."


def classify_energy(avg_energy: float):
    if avg_energy is None:
        return "Inconnue", "Énergie non mesurée."
    if avg_energy < 0.15:
        return "Faible", "Titre plutôt doux / retenu, peu de punch perçu."
    elif avg_energy < 0.30:
        return "Moyenne", "Énergie modérée, laisse de la place à la voix / au texte."
    else:
        return "Élevée", "Titre assez puissant / agressif, bonne base pour formats dynamiques."


def classify_brightness(avg_centroid: float):
    if avg_centroid is None:
        return "Inconnue", "Brillance non mesurée."
    if avg_centroid < 1500:
        return "Sombre / chaud", "Spectre plutôt grave, ambiance feutrée ou lourde."
    elif avg_centroid < 3500:
        return "Équilibrée", "Équilibre entre graves et aigus, écoute confortable."
    else:
        return "Brillante", "Spectre très aigu, peut donner un côté agressif ou moderne."


def classify_dynamic(dynamic_range: float):
    if dynamic_range is None:
        return "Inconnue", "Dynamique non mesurée."
    if dynamic_range < 0.1:
        return "Très compressée", "Peu de variation, son 'collé', ressenti fort mais fatigant."
    elif dynamic_range < 0.25:
        return "Modérée", "Bonne présence avec quelques respirations."
    else:
        return "Respirante", "Beaucoup de variations, plus organique mais moins 'radio ready'."


def interpret_lyrics_profile(text_polarity: float, subjectivity: float, vocab_size: int):
    # Mood
    if text_polarity is None:
        mood_label = "Inconnu"
        mood_comment = "Impossible d'estimer le ton émotionnel du texte."
    elif text_polarity < -0.25:
        mood_label = "Sombre / négatif"
        mood_comment = "Thèmes plutôt tristes, en colère ou mélancoliques."
    elif text_polarity > 0.25:
        mood_label = "Lumineux / positif"
        mood_comment = "Thèmes plutôt optimistes, chaleureux ou confiants."
    else:
        mood_label = "Ambivalent / neutre"
        mood_comment = "Mélange de positif et de négatif ou ton plus descriptif."

    # Subjectivité
    if subjectivity is None:
        subj_label = "Inconnue"
        subj_comment = "Subjectivité non mesurée."
    elif subjectivity < 0.3:
        subj_label = "Plutôt factuel"
        subj_comment = "Texte plus descriptif / narratif que très introspectif."
    elif subjectivity < 0.6:
        subj_label = "Mixte"
        subj_comment = "Équilibre entre description et subjectivité personnelle."
    else:
        subj_label = "Très subjectif"
        subj_comment = "Texte très centré sur le ressenti et le vécu personnel."

    # Richesse lexicale (seuils heuristiques)
    if vocab_size is None:
        rich_label = "Inconnue"
        rich_comment = "Richesse lexicale non calculée."
    elif vocab_size < 150:
        rich_label = "Simple"
        rich_comment = "Vocabulaire resserré, bon pour la mémorisation / formats viraux."
    elif vocab_size < 400:
        rich_label = "Moyenne"
        rich_comment = "Assez de variété pour raconter quelque chose sans perdre l’auditeur."
    else:
        rich_label = "Élevée"
        rich_comment = "Vocabulaire dense, intéressant pour un public qui écoute les paroles."

    return (mood_label, mood_comment,
            subj_label, subj_comment,
            rich_label, rich_comment)


def interpret_dissonance(audio_mood: float, text_polarity: float):
    """
    Retourne (score, label, commentaire) pour la dissonance audio/texte.
    """
    if (audio_mood is None) or (text_polarity is None):
        return None, "Non calculable", "Il manque soit l'analyse audio, soit l'analyse du texte."

    text_valence = (text_polarity + 1) / 2  # [-1,1] -> [0,1]
    dissonance = abs(audio_mood - text_valence)

    if dissonance < 0.2:
        label = "Très cohérent"
        comment = "Ambiance sonore et texte vont dans la même direction émotionnelle."
    elif dissonance < 0.4:
        label = "Cohérent avec nuances"
        comment = "Globalement aligné, avec quelques décalages intéressants."
    else:
        label = "Forte tension créative"
        comment = "Décalage marqué entre son et texte : peut devenir une vraie signature si c'est assumé."

    return dissonance, label, comment

def interpret_spotify_popularity(score: int):
    """
    Donne une étiquette lisible pour un score de popularité artiste Spotify.
    Heuristique simple sur 0-100.
    """
    if score is None:
        return "Inconnu", "Pas assez de données pour estimer la popularité."
    if score < 15:
        return "Sous les radars", "Profil très early, quasi invisible pour l’algorithme."
    elif score < 25:
        return "Émergent", "Commence à apparaître, mais encore peu de traction régulière."
    elif score < 50:
        return "En construction", "Base d’audience réelle, croissance possible si bien accompagnée."
    elif score < 75:
        return "En plein buzz", "Artiste bien installé·e, bon potentiel playlists & algorithme."
    else:
        return "Star / très établi", "Très forte traction, forte visibilité dans l’écosystème Spotify."


def interpret_genre_clarity(genres: list[str]):
    """
    Prend la liste de genres Spotify et renvoie (label, commentaire).
    On veut qualifier la clarté du positionnement.
    """
    n = len(genres or [])
    if n == 0:
        return "Aucun", "Spotify n’a pas encore assez de données pour catégoriser l’artiste."
    if n <= 2:
        return "Très ciblé", "Positionnement clair : une scène principale bien identifiée."
    elif n <= 5:
        return "Segmenté", "Quelques sous-genres, l’artiste navigue dans un même univers global."
    else:
        return "Éclaté", (
            "Beaucoup de micro-genres : soit l’artiste est très hybride, "
            "soit le positionnement perçu est flou."
        )

@st.cache_data
def enrich_similar_with_spotify(similar_list):
    """
    Prend la liste Last.fm d'artistes similaires
    et renvoie un DataFrame avec :
    - Artiste
    - Similarité_Lastfm
    - Popularité_Spotify
    - Followers_Spotify
    """
    rows = []
    for a in similar_list:
        name = a.get("name", "")
        match = float(a.get("match", 0) or 0.0)
        if not name:
            continue

        sp_artist = search_best_artist(name)
        if sp_artist is None:
            rows.append({
                "Artiste": name,
                "Similarité_Lastfm": match,
                "Popularité_Spotify": None,
                "Followers_Spotify": None,
            })
        else:
            rows.append({
                "Artiste": name,
                "Similarité_Lastfm": match,
                "Popularité_Spotify": sp_artist.get("popularity"),
                "Followers_Spotify": sp_artist.get("followers", {}).get("total"),
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)

@st.cache_data
def load_spotify_dataset():
    """
    Charge le dataset local de tracks avec audio features.
    Adapter le chemin si ton fichier a un autre nom.
    """
    df = pd.read_csv("data/spotify_tracks.csv")
    return df

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
    1.3 Écosystème & perception (Last.fm + voisins Spotify)
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

    pop_score = data["popularity"]
    pop_label, pop_comment = interpret_spotify_popularity(pop_score)
    genre_label, genre_comment = interpret_genre_clarity(data["genres"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Popularité Spotify (0-100)", pop_score, help=pop_comment)
    c2.metric("Followers", f"{data['followers']:,}")
    c3.metric("Positionnement genres", genre_label, help=genre_comment)

    st.caption(
        "📌 Lecture rapide : "
        f"{pop_label.lower()} – score basé surtout sur les écoutes récentes, "
        "le volume de streams et l’engagement dans Spotify."
    )

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

    dates, titles, types, total_tracks_list = [], [], [], []

    for item in albums.get("items", []):
        release_date = item.get("release_date")
        if release_date:
            dates.append(release_date)
            titles.append(item.get("name", "Sans titre"))
            album_type = item.get("album_type", "other")  # "album" / "single"
            types.append(album_type)
            total_tracks_list.append(item.get("total_tracks", 1) or 1)

    if dates:
        df_timeline = pd.DataFrame({
            "Date": pd.to_datetime(dates),
            "Titre": titles,
            "Type": types,
            "Nb_pistes": total_tracks_list,
        }).sort_values("Date")

        # Scatter 1D : y=1, coloré par type (album / single)
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

        # Stats sur les objets de sortie
        nb_singles = (df_timeline["Type"] == "single").sum()
        nb_albums = (df_timeline["Type"] == "album").sum()
        total_tracks = int(df_timeline["Nb_pistes"].sum())

        c_obj1, c_obj2, c_obj3 = st.columns(3)
        c_obj1.metric("Singles recensés", nb_singles)
        c_obj2.metric("Albums recensés", nb_albums)
        c_obj3.metric("Titres estimés (pistes d'albums + singles)", total_tracks)

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

                jours_par_sortie = int(round(median_gap))
                sorties_par_an = 365.0 / median_gap if median_gap > 0 else None

                # Période couverte
                date_min = df_sorted["Date"].min()
                date_max = df_sorted["Date"].max()
                nb_days_range = (date_max - date_min).days or 1
                nb_years_range = nb_days_range / 365.0
                tracks_per_year = total_tracks / nb_years_range if nb_years_range > 0 else None

                c_gap1, c_gap2, c_gap3 = st.columns(3)
                c_gap1.metric(
                    "Rythme moyen de sortie",
                    f"1 sortie tous les ~{jours_par_sortie} jours"
                )
                if sorties_par_an:
                    c_gap2.metric(
                        "Sorties estimées / an",
                        f"{sorties_par_an:.1f}"
                    )
                if tracks_per_year:
                    c_gap3.metric(
                        "Titres estimés / an",
                        f"{tracks_per_year:.1f}"
                    )

                st.caption(
                    f"(Médiane des intervalles entre sorties : {median_gap:.1f} jours ; "
                    f"moyenne : {mean_gap:.1f} jours ; période analysée ~{nb_years_range:.1f} ans.)"
                )
        else:
            st.caption(
                "Rythme moyen de sortie non calculable (trop peu de sorties ou dates identiques)."
            )

    else:
        st.info("Aucune sortie détectée pour construire une timeline.")

    # --- 1.3 ÉCOSYSTÈME & PERCEPTION (VIBE CHECK) ---------------------------
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

    # ----- Nuage de tags (bar chart horizontale) ----------------------------
    with col_tags:
        st.markdown("**Nuage de tags Last.fm (perception du public)**")

        if tags:
            df_tags = pd.DataFrame({
                "Tag": [t.get("name", "") for t in tags],
                "Poids": [int(t.get("count", 0)) for t in tags],
            })

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

    # ----- Artistes similaires enrichis -------------------------------------
    with col_sim:
        st.markdown("**Artistes similaires (voisinage Last.fm x Spotify)**")

        if similar:
            df_sim = enrich_similar_with_spotify(similar)

            if df_sim.empty:
                st.info("Pas assez de données pour enrichir les artistes similaires.")
            else:
                st.dataframe(
                    df_sim[["Artiste", "Similarité_Lastfm", "Popularité_Spotify", "Followers_Spotify"]],
                    use_container_width=True,
                    hide_index=True,
                )

                df_plot = df_sim.dropna(
                    subset=["Popularité_Spotify", "Followers_Spotify"]
                ).copy()

                if not df_plot.empty:
                    fig_sim = px.scatter(
                        df_plot,
                        x="Followers_Spotify",
                        y="Popularité_Spotify",
                        hover_name="Artiste",
                        size="Similarité_Lastfm",
                        title="Positionnement des voisins (Spotify)",
                    )
                    fig_sim.update_xaxes(type="log", title="Followers (log)")
                    fig_sim.update_yaxes(title="Popularité Spotify (0-100)")
                    st.plotly_chart(fig_sim, use_container_width=True)

                    my_pop = data["popularity"]
                    my_followers = data["followers"]
                    avg_pop_neighbors = df_plot["Popularité_Spotify"].mean()
                    avg_follow_neighbors = df_plot["Followers_Spotify"].mean()

                    st.caption(
                        f"Artiste analysé·e : {my_followers:,} followers, popularité {my_pop} "
                        f"vs moyenne voisins ≈ {int(avg_follow_neighbors):,} followers "
                        f"et {avg_pop_neighbors:.1f} de popularité."
                    )

                st.markdown("**Idées d’usage :**")
                st.markdown(
                    "- Cibles de featuring réalistes (voisinage direct).\n"
                    "- Playlists / médias qui programment déjà ces artistes.\n"
                    "- Publicités ciblées sur les audiences de ces voisins (lookalike)."
                )
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
    2.4 Synthèse & pistes d'action
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

    # Variables pour la synthèse finale
    audio_mood = None
    tempo = None
    avg_energy = None
    avg_centroid = None
    dynamic_range = None
    text_polarity = None
    subjectivity = None
    vocab_size = None

    # 2.1 Physique du signal (ADN sonore)
    st.markdown("#### 2.1 Physique du signal (ADN sonore)")

    itunes_data = get_itunes_preview_for_track(artist_name, track_title)

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

            # Interprétation textuelle
            tempo_label, tempo_comment = classify_tempo(tempo)
            energy_label, energy_comment = classify_energy(avg_energy)
            bright_label, bright_comment = classify_brightness(avg_centroid)
            dyn_label, dyn_comment = classify_dynamic(dynamic_range)

            with st.expander("Lecture audio en clair"):
                st.markdown(
                    f"- **Tempo** : {tempo_label} – {tempo_comment}\n"
                    f"- **Énergie** : {energy_label} – {energy_comment}\n"
                    f"- **Brillance** : {bright_label} – {bright_comment}\n"
                    f"- **Dynamique** : {dyn_label} – {dyn_comment}"
                )

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

        (mood_label, mood_comment,
         subj_label, subj_comment,
         rich_label, rich_comment) = interpret_lyrics_profile(
            text_polarity, subjectivity, vocab_size
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Polarité (-1 à 1)", round(text_polarity, 2))
        c2.metric("Subjectivité", round(subjectivity, 2))
        c3.metric("Richesse lexicale (vocabulaire unique)", vocab_size)

        with st.expander("Lecture texte en clair"):
            st.markdown(
                f"- **Ton général** : {mood_label} – {mood_comment}\n"
                f"- **Subjectivité** : {subj_label} – {subj_comment}\n"
                f"- **Richesse lexicale** : {rich_label} – {rich_comment}"
            )

        with st.expander("Voir un extrait des paroles analysées"):
            st.text("\n".join(lyrics_text.split("\n")[:15]))
    else:
        st.info("Aucune parole disponible pour l’instant.")

    st.divider()

    # 2.3 Score de dissonance audio vs texte
    st.markdown("#### 2.3 Score de dissonance (audio vs texte)")

    diss_score, diss_label, diss_comment = interpret_dissonance(audio_mood, text_polarity)

    if diss_score is None:
        st.info(diss_comment)
    else:
        st.metric("Score de dissonance (0-1)", round(diss_score, 2))
        if diss_score > 0.4:
            st.success(f"🎭 {diss_label} – {diss_comment}")
        else:
            st.info(f"🎯 {diss_label} – {diss_comment}")

    # 2.4 Synthèse & pistes d'action
    st.divider()
    st.markdown("#### 2.4 Synthèse & pistes d'action")

    bullets = []

    # Synthèse audio
    if tempo is not None and avg_energy is not None:
        tempo_label, _ = classify_tempo(tempo)
        energy_label, _ = classify_energy(avg_energy)
        bullets.append(
            f"- **Audio** : tempo {tempo_label.lower()} avec énergie {energy_label.lower()}."
        )

    # Synthèse texte
    if text_polarity is not None:
        mood_label, _, subj_label, _, rich_label, _ = interpret_lyrics_profile(
            text_polarity, subjectivity, vocab_size
        )
        bullets.append(
            f"- **Texte** : ton plutôt {mood_label.lower()}, "
            f"subjectivité {subj_label.lower()}, richesse {rich_label.lower()}."
        )

    # Synthèse dissonance
    if diss_score is not None:
        bullets.append(
            f"- **Relation son / texte** : {diss_label.lower()} (score ≈ {diss_score:.2f})."
        )

    if bullets:
        st.markdown("\n".join(bullets))

        st.markdown("**Pistes possibles :**")
        suggestions = []

        # Exemples de règles simples
        if tempo and tempo > 120 and text_polarity is not None and text_polarity < -0.2:
            suggestions.append(
                "- Mélancolie dansante : assumer le contraste clip / visuel pour en faire une signature."
            )
        if avg_energy and avg_energy < 0.15:
            suggestions.append(
                "- Énergie faible : si tu vises playlists dynamiques ou formats courts, "
                "envisage de renforcer la batterie / la basse / la saturation."
            )
        if vocab_size and vocab_size > 400:
            suggestions.append(
                "- Vocabulaire très riche : parfait pour un public qui écoute les textes, "
                "mais pense à un hook simple pour ne pas perdre les gens."
            )
        if diss_score is not None and diss_score < 0.2 and text_polarity is not None and text_polarity > 0.2:
            suggestions.append(
                "- Son et texte très positifs : idéal pour des campagnes feel-good, pubs, ou synchros lumineuses."
            )

        if suggestions:
            for s in suggestions:
                st.markdown(s)
        else:
            st.caption(
                "Pas de recommandation spécifique générée automatiquement ici, "
                "mais les métriques ci-dessus donnent déjà une base solide pour discuter DA / mix / storytelling."
            )
    else:
        st.caption(
            "Synthèse impossible : il manque soit l'analyse audio, soit l'analyse texte."
        )
        
# -------------------------------------
# PAGE 3 : LE COMPARATEUR (DATASET OFFLINE)
# -------------------------------------
def render_page_comparateur():
    """
    Version offline : comparaison d'un titre à la moyenne de son style
    en utilisant le dataset Kaggle local qui contient déjà les audio features.
    """
    st.markdown("### 📄 PAGE 3 – LE COMPARATEUR")
    st.caption("Comparer un titre à la moyenne statistique de son style à partir d'un dataset local (Spotify Tracks Dataset).")

    # Charger le dataset
    df = load_spotify_dataset()

    # === NOMS DE COLONNES DU DATASET KAGGLE ===
    COL_TRACK = "track_name"
    COL_ARTIST = "artists"
    COL_GENRE = "track_genre"
    COL_ENERGY = "energy"
    COL_DANCE = "danceability"
    COL_VALENCE = "valence"
    COL_ACOUSTIC = "acousticness"
    COL_LOUDNESS = "loudness"
    COL_DURATION = "duration_ms"
    COL_POP = "popularity"

    # ----------------- 3.1 Sélection du titre de référence -----------------
    st.markdown("#### 🎯 3.1 Choisir un titre de référence dans le dataset")

    track_query = st.text_input(
        "Recherche (titre ou artiste) :",
        placeholder="Tape un bout de titre ou de nom d'artiste (ex : 'Travis', 'Drake', 'Eminem')",
        key="offline_track_query"
    )

    if not track_query.strip():
        st.info("Commence par taper un bout de titre ou d'artiste pour filtrer le dataset.")
        return

    # Filtrage simple : titre OU artiste contient la requête
    mask = (
        df[COL_TRACK].str.contains(track_query, case=False, na=False) |
        df[COL_ARTIST].str.contains(track_query, case=False, na=False)
    )
    results = df[mask].copy()

    if results.empty:
        st.warning("Aucun titre trouvé dans le dataset pour cette requête.")
        return

    # Pour ne pas exploser l'UI : limiter à 50
    if len(results) > 50:
        results = results.head(50)

    # Créer un label lisible
    def make_label(row):
        name = str(row[COL_TRACK])
        artist = str(row[COL_ARTIST])
        genre = str(row[COL_GENRE])
        return f"{name} – {artist} [{genre}]"

    options = results.index.tolist()
    labels = {idx: make_label(results.loc[idx]) for idx in options}

    selected_idx = st.selectbox(
        "Sélectionne ton titre dans la liste :",
        options=options,
        format_func=lambda idx: labels[idx],
        key="offline_track_select"
    )

    my_row = results.loc[selected_idx]

    st.markdown(
        f"**Titre sélectionné :** {my_row[COL_TRACK]} – {my_row[COL_ARTIST]}  "
        f"(genre détecté : `{my_row[COL_GENRE]}`)"
    )

    st.divider()

    # ----------------- 3.2 Style / scène de référence -----------------
    st.markdown("#### 🎨 3.2 Style / scène de référence")

    default_genre = my_row[COL_GENRE]

    # Liste de genres possibles
    genres_unique = sorted(df[COL_GENRE].dropna().unique().tolist())

    selected_genre = st.selectbox(
        "Choisis le style de référence (pour la moyenne) :",
        options=genres_unique,
        index=genres_unique.index(default_genre) if default_genre in genres_unique else 0,
        key="offline_genre_select"
    )

    df_style = df[df[COL_GENRE] == selected_genre].copy()

    if df_style.empty:
        st.warning("Aucun morceau dans le dataset pour ce style de référence.")
        return

    st.caption(f"{len(df_style)} titres trouvés dans le dataset pour le style `{selected_genre}`.")

    st.divider()

    # ----------------- 3.3 Radar de compétitivité -----------------
    st.markdown("#### 🕸️ 3.3 Radar de compétitivité")

    # Moyennes du style
    avg_stats = {
        "Énergie": float(df_style[COL_ENERGY].mean()),
        "Dansabilité": float(df_style[COL_DANCE].mean()),
        "Valence": float(df_style[COL_VALENCE].mean()),
        "Acoustique": float(df_style[COL_ACOUSTIC].mean()),
        # Normalisation simple de la loudness sur [-60, 0] → [0, 1]
        "Puissance (Loudness)": float((df_style[COL_LOUDNESS].mean() + 60) / 60),
    }

    # Stats de TON titre
    my_stats = {
        "Énergie": float(my_row[COL_ENERGY]),
        "Dansabilité": float(my_row[COL_DANCE]),
        "Valence": float(my_row[COL_VALENCE]),
        "Acoustique": float(my_row[COL_ACOUSTIC]),
        "Puissance (Loudness)": float((my_row[COL_LOUDNESS] + 60) / 60),
    }

    categories = list(avg_stats.keys())

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=list(avg_stats.values()),
        theta=categories,
        fill='toself',
        name=f"Moyenne '{selected_genre}'",
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
        # Popularité dans le dataset
        try:
            my_pop = float(my_row[COL_POP])
            avg_pop = float(df_style[COL_POP].mean())
        except Exception:
            my_pop = None
            avg_pop = None

        if my_pop is not None:
            st.metric("Popularité (dataset)", f"{my_pop:.0f}/100")
        if avg_pop is not None:
            st.metric(f"Popularité moyenne du style", f"{avg_pop:.0f}/100")

    with c_chart:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ----------------- 3.4 Diagnostic automatique -----------------
    st.markdown("#### 💡 3.4 Diagnostic automatique")

    msgs = []

    # Durée
    avg_duration = df_style[COL_DURATION].mean() / 1000
    my_duration = my_row[COL_DURATION] / 1000
    diff_dur = my_duration - avg_duration

    if diff_dur > 30:
        msgs.append(
            f"⏱️ Ton titre est **plus long** que la moyenne du style "
            f"({int(my_duration)}s vs {int(avg_duration)}s). "
            "Tu peux envisager de raccourcir l'intro ou la fin."
        )
    elif diff_dur < -30:
        msgs.append(
            f"⏱️ Ton titre est **plus court** que la moyenne du style "
            f"({int(my_duration)}s vs {int(avg_duration)}s). "
            "C'est intéressant pour le replay, mais vérifie que la narration est complète."
        )

    # Énergie
    if my_stats["Énergie"] < avg_stats["Énergie"] - 0.15:
        msgs.append(
            "⚡ Énergie en-dessous de la moyenne du style. "
            "Si tu vises la scène / réseaux, regarde la dynamique (drums, transients, saturation)."
        )
    elif my_stats["Énergie"] > avg_stats["Énergie"] + 0.15:
        msgs.append(
            "⚡ Titre plus énergique que la moyenne. "
            "Ça peut te démarquer, mais attention à la fatigue d'écoute."
        )

    # Dansabilité
    if my_stats["Dansabilité"] < avg_stats["Dansabilité"] - 0.15:
        msgs.append(
            "💃 Groove moins dansant que la moyenne. "
            "Check les patterns de drums, la basse et le placement rythmique."
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
            "Ton titre est globalement aligné avec les codes statistiques du style. "
            "Tu peux te permettre d'expérimenter sur d'autres dimensions (structure, texte, visuel)."
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
