import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import plotly.express as px
import requests
import librosa
import numpy as np
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

# --- CONNEXION SPOTIFY ---
try:
    sp_id = st.secrets["SPOTIPY_CLIENT_ID"]
    sp_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=sp_id, client_secret=sp_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except:
    st.error("⚠️ Clés Spotify manquantes.")
    st.stop()

# --- FONCTIONS AUDIO (Le Cœur du Réacteur) ---

def get_itunes_preview(artist_name):
    """Cherche l'extrait audio (30s) le plus pertinent sur iTunes"""
    # L'API iTunes ne demande pas de clé !
    url = f"https://itunes.apple.com/search?term={artist_name}&media=music&entity=song&limit=5"
    response = requests.get(url).json()
    
    if response['resultCount'] > 0:
        # On prend le premier résultat
        track = response['results'][0]
        return {
            'title': track['trackName'],
            'preview_url': track['previewUrl'], # Le lien vers le fichier audio
            'cover': track['artworkUrl100']
        }
    return None

def analyze_audio_signal(preview_url):
    """Télécharge et analyse le signal audio avec Librosa"""
    
    # 1. Téléchargement du fichier temporaire
    doc = requests.get(preview_url)
    with open("temp_audio.m4a", 'wb') as f:
        f.write(doc.content)
    
    # 2. Chargement dans Librosa (Transforme le son en tableau de chiffres)
    # y = le signal audio, sr = sample rate
    y, sr = librosa.load("temp_audio.m4a", duration=30)
    
    # 3. Calculs Physiques (Signal Processing)
    
    # A. Tempo (BPM)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    
    # B. Énergie (RMS - Root Mean Square) -> Volume/Puissance perçue
    rms = librosa.feature.rms(y=y)
    avg_energy = np.mean(rms)
    
    # C. "Brillance" (Spectral Centroid) -> Son étouffé vs Son clair/Aigu
    # Un centroid haut = son "brillant" (Pop/Electro). Bas = son "sombre" (Lo-fi/Trap).
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    avg_brightness = np.mean(spectral_centroids)
    
    # Nettoyage du fichier temporaire
    os.remove("temp_audio.m4a")
    
    return tempo, avg_energy, avg_brightness, y, sr

# --- INTERFACE ---
st.title("🎹 Artist 360° Radar")
st.markdown("### Analyse de Signal Audio Réel (Signal Processing)")

col1, col2 = st.columns([3, 1])
with col1:
    artist_name = st.text_input("Nom de l'artiste", placeholder="Ex: La Fève")
with col2:
    st.write("")
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

if search_btn and artist_name:
    st.divider()
    
    # 1. INFO ARTISTE (Spotify)
    results = sp.search(q=artist_name, type='artist', limit=1)
    if results['artists']['items']:
        artist = results['artists']['items'][0]
        st.subheader(f"Artiste : {artist['name']}")
        st.write(f"Popularité : {artist['popularity']}/100")
    
    st.divider()

    # 2. ANALYSE AUDIO (iTunes + Librosa)
    st.markdown("### 🧬 Analyse du Signal Audio (Extrait 30s)")
    
    with st.spinner("Téléchargement et analyse du signal en cours... (ça peut prendre 10s)"):
        preview_data = get_itunes_preview(artist_name)
        
        if preview_data and preview_data['preview_url']:
            col_audio_1, col_audio_2 = st.columns([1, 2])
            
            with col_audio_1:
                st.image(preview_data['cover'], width=150)
                st.caption(f"Titre analysé : **{preview_data['title']}**")
                # Lecteur Audio pour vérifier
                st.audio(preview_data['preview_url'])

            with col_audio_2:
                # Lancement de l'analyse Librosa
                tempo, energy, brightness, y, sr = analyze_audio_signal(preview_data['preview_url'])
                
                # Normalisation des valeurs pour l'affichage (c'est des maths approximatives pour la démo)
                norm_energy = min(energy * 1000, 100) # L'énergie est souvent toute petite, on multiplie
                norm_brightness = min(brightness / 50, 100) # Le centroid est souvent vers 2000-4000Hz
                
                # Affichage des KPIs
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Tempo (BPM)", f"{int(tempo)}")
                kpi2.metric("Énergie (RMS)", f"{norm_energy:.1f}/100")
                kpi3.metric("Brillance (Hz)", f"{int(brightness)}")
                
                st.info(f"**Interprétation Cognitive :** Un BPM de {int(tempo)} avec une brillance de {int(brightness)} Hz suggère une ambiance {'Dynamique/Claire' if brightness > 2500 else 'Sombre/Lourde'}.")

            # 3. VISUALISATION DE L'ONDE (Waveform)
            st.markdown("**Visualisation de l'Onde Sonore :**")
            # On réduit les points pour que le graph soit léger
            df_wave = pd.DataFrame(y[::100], columns=['Amplitude']) 
            st.line_chart(df_wave)

        else:
            st.warning("Aucun extrait audio disponible sur iTunes pour cet artiste.")