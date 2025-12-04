import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import requests # Pour Last.fm et iTunes
import librosa  # Pour l'analyse audio
import numpy as np # Pour les maths
import os # Pour gérer les fichiers temporaires

# =========================================================
# 1. CONFIGURATION & CLÉS
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

try:
    # Clés Spotify
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    # Clé Last.fm
    lastfm_key = st.secrets["LASTFM_API_KEY"]
except Exception as e:
    st.error(f"⚠️ Erreur de clés API : {e}")
    st.stop()

# =========================================================
# 2. FONCTIONS (LE CERVEAU)
# =========================================================

def get_similar_artists_lastfm(artist_name):
    """Récupère les voisins via Last.fm"""
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={artist_name}&api_key={lastfm_key}&format=json&limit=5"
        response = requests.get(url).json()
        artists = response['similarartists']['artist']
        return [a['name'] for a in artists]
    except:
        return []

def get_itunes_preview(artist_name):
    """Cherche un extrait 30s sur iTunes"""
    try:
        # Recherche iTunes standard
        url = f"https://itunes.apple.com/search?term={artist_name}&media=music&entity=song&limit=5"
        response = requests.get(url).json()
        
        if response['resultCount'] > 0:
            # On prend le premier résultat qui correspond à l'artiste
            for item in response['results']:
                if artist_name.lower() in item['artistName'].lower():
                    return {
                        'title': item['trackName'],
                        'preview_url': item['previewUrl'],
                        'cover': item['artworkUrl100']
                    }
            # Si pas de correspondance exacte, on prend le premier
            return {
                'title': response['results'][0]['trackName'],
                'preview_url': response['results'][0]['previewUrl'],
                'cover': response['results'][0]['artworkUrl100']
            }
        return None
    except:
        return None

def analyze_signal(preview_url):
    """Télécharge et analyse le signal audio avec Librosa"""
    # 1. Téléchargement du fichier temporaire
    doc = requests.get(preview_url)
    filename = "temp_audio.m4a"
    with open(filename, 'wb') as f:
        f.write(doc.content)
    
    # 2. Chargement dans Librosa (Le moment lourd)
    # y = signal brut, sr = sample rate
    y, sr = librosa.load(filename, duration=30)
    
    # 3. Calculs Physiques
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    rms = np.mean(librosa.feature.rms(y=y))           # Énergie (Volume)
    spec_cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)) # Brillance
    
    # 4. Nettoyage
    os.remove(filename)
    
    return tempo, rms, spec_cent, y

# =========================================================
# 3. INTERFACE
# =========================================================
st.title("🎹 Artist 360° Radar")
st.markdown("### Outil d'Analyse Business & Cognitive")

col_search, col_btn = st.columns([3, 1])
with col_search:
    query = st.text_input("Recherche", placeholder="Nom ou Lien Spotify")
with col_btn:
    st.write("") 
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# =========================================================
# 4. EXÉCUTION
# =========================================================
if search_btn and query:
    st.divider()

    # --- A. IDENTIFICATION SPOTIFY ---
    try:
        if "open.spotify.com" in query:
            artist_id = query.split("/artist/")[1].split("?")[0]
            artist = sp.artist(artist_id)
        else:
            results = sp.search(q=query, type='artist', limit=10, market='FR')
            if not results['artists']['items']:
                st.warning("Artiste introuvable.")
                st.stop()
            items = results['artists']['items']
            candidates = [i for i in items if query.lower() in i['name'].lower()]
            if not candidates: candidates = items
            candidates.sort(key=lambda x: x['popularity'], reverse=True)
            artist = candidates[0]

        # Extraction Data
        artist_id = artist['id']
        name = artist['name']
        popularity = artist['popularity']
        followers = artist['followers']['total']
        image_url = artist['images'][0]['url'] if artist['images'] else None
        spotify_url = artist['external_urls']['spotify']
        
        # Header
        head_c1, head_c2 = st.columns([1, 4])
        with head_c1:
            if image_url: st.image(image_url, width=150)
        with head_c2:
            st.subheader(name)
            st.markdown(f"[Ouvrir sur Spotify]({spotify_url})")

    except Exception as e:
        st.error(f"Erreur Recherche : {e}")
        st.stop()

    st.divider()
    col_market, col_audio, col_semantic = st.columns(3)

    # -----------------------------------------------------
    # COLONNE 1 : MARCHÉ (Module Fini)
    # -----------------------------------------------------
    with col_market:
        st.markdown("### 🟢 Marché & Business")
        col_kpi1, col_kpi2 = st.columns(2)
        col_kpi1.metric("Popularité", f"{popularity}/100")
        col_kpi2.metric("Followers", f"{followers:,}")
        st.progress(popularity)
        
        st.write("---")
        st.caption("Structure")
        try:
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=5, country='FR')
            if albums['items']:
                last = albums['items'][0]
                details = sp.album(last['id'])
                st.write(f"🏢 **Label :** {details['label']}")
                st.write(f"📅 **Sortie :** {details['release_date']}")
            else:
                st.write("Pas de sortie récente.")
        except:
            st.write("Info Label non dispo.")
            
        st.write("---")
        st.caption("Écosystème (Last.fm)")
        sims = get_similar_artists_lastfm(name)
        if sims:
            st.write(", ".join(sims))
        else:
            st.write("Pas de données similaires.")

    # -----------------------------------------------------
    # COLONNE 2 : AUDIO (NOUVEAU !)
    # -----------------------------------------------------
    with col_audio:
        st.markdown("### 🟡 Physique du Signal")
        
        with st.spinner("Analyse du signal audio (iTunes + Librosa)..."):
            preview_data = get_itunes_preview(name)
            
            if preview_data:
                # 1. Le Player
                st.image(preview_data['cover'], width=100)
                st.caption(f"Titre analysé : {preview_data['title']}")
                st.audio(preview_data['preview_url'])
                
                # 2. L'Analyse Mathématique
                tempo, rms, cent, y = analyze_signal(preview_data['preview_url'])
                
                # Normalisation pour affichage (0-100)
                score_energy = min(rms * 200, 100) 
                score_bright = min(cent / 50, 100)
                
                # 3. Affichage KPIs
                kpi_a1, kpi_a2 = st.columns(2)
                kpi_a1.metric("Tempo (BPM)", f"{int(tempo)}")
                kpi_a2.metric("Brillance", f"{int(cent)} Hz")
                
                # 4. Interprétation Cognitive
                st.caption("Interprétation Cognitive :")
                if tempo > 120:
                    st.success("⚡ **Stimulant (Haut Arousal)**")
                elif tempo < 90:
                    st.info("🌙 **Apaisant (Bas Arousal)**")
                else:
                    st.warning("😐 **Modéré (Radio Standard)**")
                
                # 5. La Waveform (Visuel)
                st.markdown("**Onde Sonore (30s)**")
                # On allège les données pour le graph (1 point sur 100)
                st.line_chart(y[::100], height=100, color="#FFC300")
                
            else:
                st.warning("Aucun extrait audio disponible sur iTunes.")

    # -----------------------------------------------------
    # COLONNE 3 : SÉMANTIQUE (Vide)
    # -----------------------------------------------------
    with col_semantic:
        st.markdown("### 🔴 Image & Perception")
        st.info("Semaine 3 : NLP & Genius")