import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import requests
import librosa
import numpy as np
import os
import plotly.express as px # On utilise Plotly pour une belle onde

# =========================================================
# 1. CONFIGURATION & CLÉS
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

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
    
    # Calculs Physiques
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    rms = librosa.feature.rms(y=y)[0]
    avg_energy = np.mean(rms)
    spec_cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
    
    # Calcul de la Dynamique (Nouveau !)
    # Différence entre le son max et le son moyen
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

if search_btn and query:
    st.divider()

    # --- IDENTIFICATION ---
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

        artist_id = artist['id']
        name = artist['name']
        popularity = artist['popularity']
        followers = artist['followers']['total']
        image_url = artist['images'][0]['url'] if artist['images'] else None
        spotify_url = artist['external_urls']['spotify']
        
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
    # COLONNE 1 : MARCHÉ
    # -----------------------------------------------------
    with col_market:
        st.markdown("### 🟢 Marché & Business")
        col_kpi1, col_kpi2 = st.columns(2)
        col_kpi1.metric("Popularité", f"{popularity}/100")
        col_kpi2.metric("Followers", f"{followers:,}")
        st.progress(popularity)
        st.write("---")
        try:
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=5, country='FR')
            if albums['items']:
                label_txt = sp.album(albums['items'][0]['id'])['label']
                st.write(f"🏢 **Label :** {label_txt}")
        except: pass
        st.caption("Écosystème (Last.fm)")
        sims = get_similar_artists_lastfm(name)
        if sims: st.write(", ".join(sims))

    # -----------------------------------------------------
    # COLONNE 2 : AUDIO (OPTIMISÉE)
    # -----------------------------------------------------
    with col_audio:
        st.markdown("### 🟡 Physique du Signal")
        
        # Le bouton magique qui empêche le blocage
        if st.button("🔊 Analyser le Signal Audio"):
            
            with st.spinner("Téléchargement & Calculs mathématiques..."):
                preview_data = get_itunes_preview(name)
                
                if preview_data:
                    st.image(preview_data['cover'], width=100)
                    st.caption(f"**{preview_data['title']}**")
                    st.audio(preview_data['preview_url'])
                    
                    # Analyse
                    tempo, rms, cent, dynamic, y = analyze_signal(preview_data['preview_url'])
                    
                    # KPIs
                    k1, k2 = st.columns(2)
                    k1.metric("Tempo", f"{int(tempo)} BPM")
                    k2.metric("Brillance", f"{int(cent)} Hz")
                    
                    st.write("---")
                    
                    # INTERPRÉTATION DE L'ONDE (La plus-value)
                    st.markdown("**Visualisation & Dynamique**")
                    
                    # On utilise Plotly pour un beau graph
                    # On réduit les points (1 sur 50) pour que ça soit léger
                    df_wave = pd.DataFrame({'Amplitude': y[::50]})
                    fig = px.line(df_wave, y="Amplitude", height=150)
                    fig.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                    # Couleur Jaune "Spotify" ou "Radar"
                    fig.update_traces(line_color='#FFC300') 
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Explication Cognitive
                    if dynamic < 0.05:
                        st.error("🧱 **Effet 'Mur de Son' (Brique) :** Très compressé. Impact maximum, mais fatigue auditive rapide. Typique Pop/Radio.")
                    else:
                        st.success("🌊 **Effet 'Dynamique' (Aéré) :** Variations naturelles de volume. Plus 'organique' et respirant.")
                    
                else:
                    st.warning("Pas d'extrait iTunes trouvé.")
        else:
            st.info("Cliquez pour lancer l'analyse (30s de calcul)")

    # -----------------------------------------------------
    # COLONNE 3 : SÉMANTIQUE (Apparaît tout de suite mtn)
    # -----------------------------------------------------
    with col_semantic:
        st.markdown("### 🔴 Image & Perception")
        st.info("Le contenu s'affiche instantanément maintenant !")
        st.write("Module Genius à venir...")