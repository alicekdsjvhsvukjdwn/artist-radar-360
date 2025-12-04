import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import requests
import librosa
import numpy as np
import os
import plotly.express as px
import lyricsgenius # Pour les paroles
from textblob import TextBlob # Pour l'analyse de sentiment

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
    genius_token = st.secrets["GENIUS_ACCESS_TOKEN"]
except Exception as e:
    st.error(f"⚠️ Erreur de clés API : {e}")
    st.stop()

# =========================================================
# 2. FONCTIONS
# =========================================================
def get_lastfm_tags(artist_name):
    """Récupère les émotions/styles via Last.fm"""
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist={artist_name}&api_key={lastfm_key}&format=json"
        response = requests.get(url).json()
        tags = response['toptags']['tag']
        # On nettoie les tags inutiles (seen live, etc)
        ignore = ['seen live', 'under 2000 listeners', 'french', 'belgian']
        clean_tags = [t['name'] for t in tags if t['name'].lower() not in ignore]
        return clean_tags[:5] # Top 5 tags
    except:
        return []

def get_itunes_preview(artist_name):
    try:
        url = f"https://itunes.apple.com/search?term={artist_name}&media=music&entity=song&limit=5"
        response = requests.get(url).json()
        if response['resultCount'] > 0:
            # On cherche une correspondance
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

def analyze_lyrics(artist_name, song_title):
    """Télécharge les paroles et analyse le sentiment"""
    try:
        genius = lyricsgenius.Genius(genius_token, verbose=False)
        # On cherche la chanson
        song = genius.search_song(song_title, artist_name)
        
        if song:
            lyrics = song.lyrics
            # Nettoyage basique (On enlève [Chorus], [Verse 1])
            clean_lyrics = lyrics.replace("[Chorus]", "").replace("[Verse]", "")
            
            # Analyse Sentiment (TextBlob)
            # Note: TextBlob marche mieux en Anglais, mais détecte quand même les émotions universelles
            blob = TextBlob(clean_lyrics)
            sentiment = blob.sentiment.polarity # De -1 (Négatif) à +1 (Positif)
            
            # Complexité (Nb de mots uniques / Nb total)
            words = clean_lyrics.split()
            unique_words = set(words)
            complexity = len(unique_words) / len(words) if len(words) > 0 else 0
            
            return sentiment, complexity, clean_lyrics[:200] + "..." # On renvoie un extrait
        else:
            return None, None, None
    except:
        return None, None, None

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
            
            st.session_state.data = {
                'query': query,
                'id': artist['id'],
                'name': artist['name'],
                'pop': artist['popularity'],
                'followers': artist['followers']['total'],
                'genres': artist['genres'],
                'image': artist['images'][0]['url'] if artist['images'] else None,
                'url': artist['external_urls']['spotify']
            }

        data = st.session_state.data
        
        head_c1, head_c2 = st.columns([1, 4])
        with head_c1:
            if data['image']: st.image(data['image'], width=150)
        with head_c2:
            st.subheader(data['name'])
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

    # -----------------------------------------------------
    # COLONNE 2 : AUDIO
    # -----------------------------------------------------
    with col_audio:
        st.markdown("### 🟡 Physique du Signal")
        if st.button("🔊 Analyser l'Audio"):
            with st.spinner("Analyse du signal..."):
                preview_data = get_itunes_preview(data['name'])
                if preview_data:
                    st.image(preview_data['cover'], width=80)
                    st.caption(f"**{preview_data['title']}**")
                    st.audio(preview_data['preview_url'])
                    
                    tempo, rms, cent, dynamic, y = analyze_signal(preview_data['preview_url'])
                    
                    # Correction BPM
                    artist_genres = " ".join(data['genres']).lower()
                    halftime_genres = ['trap', 'hip hop', 'rap', 'drill', 'r&b']
                    fast_genres = ['dnb', 'techno', 'house', 'punk']
                    
                    bpm_final = int(tempo)
                    if bpm_final > 130 and any(g in artist_genres for g in halftime_genres) and not any(g in artist_genres for g in fast_genres):
                        bpm_final = int(bpm_final / 2)

                    k1, k2 = st.columns(2)
                    k1.metric("Tempo", f"{bpm_final} BPM")
                    k2.metric("Brillance", f"{int(cent)} Hz")
                    
                    st.write("---")
                    df_wave = pd.DataFrame({'Amplitude': y[::50]})
                    fig = px.line(df_wave, y="Amplitude", height=100)
                    fig.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                    fig.update_traces(line_color='#FFC300') 
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Pas d'extrait iTunes.")
        else:
            st.info("Cliquez pour analyser le son")

    # -----------------------------------------------------
    # COLONNE 3 : SÉMANTIQUE (NLP + GENIUS)
    # -----------------------------------------------------
    with col_semantic:
        st.markdown("### 🔴 Sémantique & Perception")
        
        # 1. TAGS PERCEPTION (Last.fm) - Chargement immédiat
        tags = get_lastfm_tags(data['name'])
        if tags:
            st.caption("Le public perçoit cet artiste comme :")
            # Affichage sous forme de "Chips"
            st.markdown(" ".join([f"`{t}`" for t in tags]))
        else:
            st.write("Pas de tags de perception.")
            
        st.write("---")
        
        # 2. ANALYSE PAROLES (Bouton pour éviter la lenteur)
        if st.button("🧠 Analyser les Textes (NLP)"):
            with st.spinner("Lecture des paroles sur Genius..."):
                # On cherche le titre le plus connu trouvé sur iTunes pour être cohérent
                preview = get_itunes_preview(data['name'])
                if preview:
                    song_title = preview['title']
                    st.write(f"Analyse du texte de : **{song_title}**")
                    
                    sentiment, complexity, snippet = analyze_lyrics(data['name'], song_title)
                    
                    if sentiment is not None:
                        # Jauge de Sentiment (-1 Triste / +1 Joyeux)
                        st.subheader("Sentiment Global")
                        if sentiment > 0.1:
                            st.success(f"Positif / Joyeux (+{sentiment:.2f})")
                        elif sentiment < -0.1:
                            st.error(f"Négatif / Sombre ({sentiment:.2f})")
                        else:
                            st.warning(f"Neutre ({sentiment:.2f})")
                            
                        # Métrique Complexité
                        st.metric("Richesse du Vocabulaire", f"{int(complexity*100)}%", help="Pourcentage de mots uniques")
                        
                        with st.expander("Voir un extrait des paroles"):
                            st.write(snippet)
                    else:
                        st.warning("Paroles non trouvées sur Genius.")
                else:
                    st.warning("Impossible de définir quel titre analyser.")
        else:
            st.info("Cliquez pour l'analyse cognitive des textes")