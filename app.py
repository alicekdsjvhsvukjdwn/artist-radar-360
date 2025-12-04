import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import requests
import librosa
import numpy as np
import os
import plotly.express as px

# =========================================================
# 1. CONFIGURATION & CLÉS
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

# --- GESTION DE LA MÉMOIRE (NOUVEAU) ---
# On initialise la mémoire si elle n'existe pas
if 'search_done' not in st.session_state:
    st.session_state.search_done = False
if 'data' not in st.session_state:
    st.session_state.data = None

try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    lastfm_key = st.secrets["LASTFM_API_KEY"]
except Exception as e:
    st.error(f"⚠️ Erreur de clés API : {e}")
    st.stop()

# =========================================================
# 2. FONCTIONS
# =========================================================
def get_similar_artists_lastfm(artist_name):
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={artist_name}&api_key={lastfm_key}&format=json&limit=5"
        response = requests.get(url).json()
        artists = response['similarartists']['artist']
        return [a['name'] for a in artists]
    except:
        return []

def get_itunes_preview(artist_name):
    try:
        url = f"https://itunes.apple.com/search?term={artist_name}&media=music&entity=song&limit=5"
        response = requests.get(url).json()
        if response['resultCount'] > 0:
            for item in response['results']:
                if artist_name.lower() in item['artistName'].lower():
                    return {
                        'title': item['trackName'],
                        'preview_url': item['previewUrl'],
                        'cover': item['artworkUrl100']
                    }
            return {
                'title': response['results'][0]['trackName'],
                'preview_url': response['results'][0]['previewUrl'],
                'cover': response['results'][0]['artworkUrl100']
            }
        return None
    except:
        return None

def analyze_signal(preview_url):
    doc = requests.get(preview_url)
    filename = "temp_audio.m4a"
    with open(filename, 'wb') as f:
        f.write(doc.content)
    
    y, sr = librosa.load(filename, duration=30)
    
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    rms = librosa.feature.rms(y=y)[0]
    avg_energy = np.mean(rms)
    spec_cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
    dynamic_range = np.max(rms) - np.mean(rms)
    
    os.remove(filename)
    return tempo, avg_energy, spec_cent, dynamic_range, y

# =========================================================
# 3. INTERFACE
# =========================================================
st.title("🎹 Artist 360° Radar")

col_search, col_btn = st.columns([3, 1])
with col_search:
    query = st.text_input("Recherche", placeholder="Nom ou Lien Spotify")
with col_btn:
    st.write("") 
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# --- LOGIQUE DE MÉMOIRE ---
if search_btn:
    st.session_state.search_done = True # On se souvient qu'on a cliqué

# Si la recherche est activée (soit mtn, soit avant), on affiche le contenu
if st.session_state.search_done and query:
    
    st.divider()

    # --- IDENTIFICATION (On ne le fait que si on change d'artiste ou au premier clic) ---
    try:
        # On vérifie si on doit recharger les données (si c'est une nouvelle recherche)
        if st.session_state.data is None or st.session_state.data['query'] != query:
            
            # ... C'EST ICI QU'ON FAIT LA RECHERCHE SPOTIFY ...
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
            
            # ON SAUVEGARDE TOUT DANS LA MÉMOIRE
            st.session_state.data = {
                'query': query,
                'id': artist['id'],
                'name': artist['name'],
                'pop': artist['popularity'],
                'followers': artist['followers']['total'],
                'image': artist['images'][0]['url'] if artist['images'] else None,
                'url': artist['external_urls']['spotify']
            }

        # ON RECUPERE LES DONNÉES DEPUIS LA MÉMOIRE
        data = st.session_state.data
        
        # Header
        head_c1, head_c2 = st.columns([1, 4])
        with head_c1:
            if data['image']: st.image(data['image'], width=150)
        with head_c2:
            st.subheader(data['name'])
            st.markdown(f"[Ouvrir sur Spotify]({data['url']})")

    except Exception as e:
        st.error(f"Erreur Recherche : {e}")
        st.stop()

    st.divider()
    col_market, col_audio, col_semantic = st.columns(3)

    # -----------------------------------------------------
    # COLONNE 1 : MARCHÉ
    # -----------------------------------------------------
    with col_market:
        st.markdown("### 🟢 Marché & Business")
        col_kpi1, col_kpi2 = st.columns(2)
        col_kpi1.metric("Popularité", f"{data['pop']}/100")
        col_kpi2.metric("Followers", f"{data['followers']:,}")
        st.progress(data['pop'])
        st.write("---")
        
        # Label & Voisins (On les recharge à chaque fois, c'est rapide)
        try:
            albums = sp.artist_albums(data['id'], album_type='album,single', limit=5, country='FR')
            if albums['items']:
                label_txt = sp.album(albums['items'][0]['id'])['label']
                st.write(f"🏢 **Label :** {label_txt}")
        except: pass
        
        st.caption("Écosystème (Last.fm)")
        sims = get_similar_artists_lastfm(data['name'])
        if sims: st.write(", ".join(sims))

    # -----------------------------------------------------
    # COLONNE 2 : AUDIO
    # -----------------------------------------------------
    with col_audio:
        st.markdown("### 🟡 Physique du Signal")
        
        # Le bouton d'analyse
        if st.button("🔊 Analyser le Signal Audio"):
            
            with st.spinner("Téléchargement & Calculs mathématiques..."):
                preview_data = get_itunes_preview(data['name'])
                
                if preview_data:
                    st.image(preview_data['cover'], width=100)
                    st.caption(f"**{preview_data['title']}**")
                    st.audio(preview_data['preview_url'])
                    
                    tempo, rms, cent, dynamic, y = analyze_signal(preview_data['preview_url'])
                    
                    k1, k2 = st.columns(2)
                    k1.metric("Tempo", f"{int(tempo)} BPM")
                    k2.metric("Brillance", f"{int(cent)} Hz")
                    
                    st.write("---")
                    
                    st.markdown("**Visualisation & Dynamique**")
                    df_wave = pd.DataFrame({'Amplitude': y[::50]})
                    fig = px.line(df_wave, y="Amplitude", height=150)
                    fig.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                    fig.update_traces(line_color='#FFC300') 
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if dynamic < 0.05:
                        st.error("🧱 **Effet 'Mur de Son' (Brique)**")
                    else:
                        st.success("🌊 **Effet 'Dynamique' (Aéré)**")
                    
                else:
                    st.warning("Pas d'extrait iTunes trouvé.")
        else:
            st.info("Cliquez pour lancer l'analyse (30s de calcul)")

    # -----------------------------------------------------
    # COLONNE 3 : SÉMANTIQUE
    # -----------------------------------------------------
    with col_semantic:
        st.markdown("### 🔴 Image & Perception")
        st.info("Module Genius à venir...")