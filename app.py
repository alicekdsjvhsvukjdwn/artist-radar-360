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

# --- MÉMOIRE ---
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
    
    # Analyse
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

if search_btn:
    st.session_state.search_done = True

if st.session_state.search_done and query:
    
    st.divider()

    try:
        # Rechargement des données si nouvelle recherche
        if st.session_state.data is None or st.session_state.data['query'] != query:
            
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
            
            # --- MISE EN MÉMOIRE (AVEC GENRES !) ---
            st.session_state.data = {
                'query': query,
                'id': artist['id'],
                'name': artist['name'],
                'pop': artist['popularity'],
                'followers': artist['followers']['total'],
                'genres': artist['genres'], # IMPORTANT : On garde les genres
                'image': artist['images'][0]['url'] if artist['images'] else None,
                'url': artist['external_urls']['spotify']
            }

        data = st.session_state.data
        
        # Header
        head_c1, head_c2 = st.columns([1, 4])
        with head_c1:
            if data['image']: st.image(data['image'], width=150)
        with head_c2:
            st.subheader(data['name'])
            # Affiche les genres pour info
            if data['genres']:
                st.caption(f"Genres détectés : {', '.join(data['genres'][:3])}")
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
    # COLONNE 2 : AUDIO (INTELLIGENCE CONTEXTUELLE)
    # -----------------------------------------------------
    with col_audio:
        st.markdown("### 🟡 Physique du Signal")
        
        if st.button("🔊 Analyser le Signal Audio"):
            
            with st.spinner("Analyse croisée Audio + Genres..."):
                preview_data = get_itunes_preview(data['name'])
                
                if preview_data:
                    st.image(preview_data['cover'], width=100)
                    st.caption(f"**{preview_data['title']}**")
                    st.audio(preview_data['preview_url'])
                    
                    tempo, rms, cent, dynamic, y = analyze_signal(preview_data['preview_url'])
                    
                    # --- CORRECTION BPM INTELLIGENTE ---
                    # On convertit les genres en une seule chaine minuscule pour chercher dedans
                    artist_genres = " ".join(data['genres']).lower()
                    
                    # Liste des genres "Lents" qui sont souvent détectés en double
                    halftime_genres = ['trap', 'hip hop', 'rap', 'drill', 'r&b', 'lo-fi', 'urban']
                    
                    # Liste des genres "Rapides" (qu'on ne touche surtout pas)
                    fast_genres = ['drum and bass', 'dnb', 'jungle', 'techno', 'house', 'trance', 'punk', 'metal', 'footwork']
                    
                    bpm_machine = int(tempo)
                    bpm_final = bpm_machine
                    correction_msg = ""
                    
                    if bpm_machine > 130:
                        # Est-ce que c'est du Rap/Trap ?
                        is_halftime = any(g in artist_genres for g in halftime_genres)
                        # Est-ce que c'est explicitement du rapide ?
                        is_fast = any(g in artist_genres for g in fast_genres)
                        
                        if is_halftime and not is_fast:
                            # C'est de la Trap détectée rapide -> On divise
                            bpm_final = int(bpm_machine / 2)
                            correction_msg = f"💡 Correction Cognitive : Le signal indique {bpm_machine} BPM, mais le genre ({', '.join([g for g in halftime_genres if g in artist_genres])}) suggère un ressenti 'Half-Time' à {bpm_final} BPM."
                        elif is_fast:
                            # C'est de la DnB -> On garde le rapide
                            bpm_final = bpm_machine
                            correction_msg = "✅ Tempo Rapide confirmé par le genre."
                        else:
                            # C'est de la Pop ou autre -> On affiche le doute
                            correction_msg = f"ℹ️ Tempo ambigu : Techniquement {bpm_machine} BPM. Ressenti variable selon la danse."

                    # Affichage
                    k1, k2 = st.columns(2)
                    k1.metric("Tempo (Ressenti)", f"{bpm_final} BPM")
                    k2.metric("Brillance", f"{int(cent)} Hz")
                    
                    st.write("---")
                    
                    # Waveform
                    st.markdown("**Visualisation & Dynamique**")
                    df_wave = pd.DataFrame({'Amplitude': y[::50]})
                    fig = px.line(df_wave, y="Amplitude", height=150)
                    fig.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                    fig.update_traces(line_color='#FFC300') 
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if dynamic < 0.05:
                        st.error("🧱 **Mur de Son (Compressé)**")
                    else:
                        st.success("🌊 **Dynamique (Aéré)**")
                        
                    # Affichage du message d'intelligence
                    if correction_msg:
                        st.info(correction_msg)
                    
                else:
                    st.warning("Pas d'extrait iTunes trouvé.")
        else:
            st.info("Cliquez pour lancer l'analyse (30s de calcul)")

    with col_semantic:
        st.markdown("### 🔴 Image & Perception")
        st.info("Module Genius à venir...")