import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import requests
import librosa
import numpy as np
import os
import plotly.express as px
import lyricsgenius
from textblob import TextBlob

# =========================================================
# 1. CONFIGURATION & CLÉS
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

# --- MÉMOIRE ---
if 'search_done' not in st.session_state:
    st.session_state.search_done = False
if 'data' not in st.session_state:
    st.session_state.data = None
if 'audio_analysis_done' not in st.session_state:
    st.session_state.audio_analysis_done = False
if 'nlp_analysis_done' not in st.session_state:
    st.session_state.nlp_analysis_done = False

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
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist={artist_name}&api_key={lastfm_key}&format=json"
        response = requests.get(url).json()
        ignore = ['seen live', 'under 2000 listeners', 'french', 'belgian', 'hip-hop', 'rap', 'trap', 'pop']
        tags = response['toptags']['tag']
        clean_tags = [t['name'] for t in tags if t['name'].lower() not in ignore]
        return clean_tags[:5]
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

def get_smart_lyrics(artist_name, song_title):
    """VERSION FORCE BRUTE : On cherche, on prend le premier ID, on télécharge."""
    try:
        genius = lyricsgenius.Genius(genius_token, verbose=False, remove_section_headers=True)
        
        # 1. On nettoie le titre pour la recherche (on enlève les feat)
        clean_title = song_title.split('(')[0].split('-')[0].strip()
        search_query = f"{artist_name} {clean_title}"
        
        # 2. On demande la liste des résultats (pas le song direct)
        request = genius.search_songs(search_query)
        
        # 3. On prend le premier résultat de la liste, PEU IMPORTE LE NOM DE L'ARTISTE
        if request and 'hits' in request and len(request['hits']) > 0:
            best_hit = request['hits'][0]['result']
            song_id = best_hit['id']
            
            # 4. On force le téléchargement via l'ID
            song = genius.song(song_id)
            return song
        
        return None
    except:
        return None

def analyze_lyrics_content(lyrics_text):
    blob = TextBlob(lyrics_text)
    sentiment = blob.sentiment.polarity
    words = lyrics_text.split()
    unique_words = set(words)
    complexity = len(unique_words) / len(words) if len(words) > 0 else 0
    return sentiment, complexity

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
    st.session_state.audio_analysis_done = False
    st.session_state.nlp_analysis_done = False

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
        c1, c2 = st.columns(2)
        c1.metric("Popularité", f"{data['pop']}/100")
        c2.metric("Followers", f"{data['followers']:,}")
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
        
        if st.button("🔊 Analyser l'Audio") or st.session_state.audio_analysis_done:
            st.session_state.audio_analysis_done = True 
            
            preview_data = get_itunes_preview(data['name'])
            if preview_data:
                st.image(preview_data['cover'], width=80)
                st.caption(f"**{preview_data['title']}**")
                st.audio(preview_data['preview_url'])
                
                # NOTE : Dans une vraie app, on mettrait ça en cache pour ne pas recalculer
                tempo, rms, cent, dynamic, y = analyze_signal(preview_data['preview_url'])
                
                # Correction BPM
                artist_genres = " ".join(data['genres']).lower()
                halftime_genres = ['trap', 'hip hop', 'rap', 'drill']
                bpm_final = int(tempo)
                if bpm_final > 130 and any(g in artist_genres for g in halftime_genres):
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

    # -----------------------------------------------------
    # COLONNE 3 : SÉMANTIQUE
    # -----------------------------------------------------
    with col_semantic:
        st.markdown("### 🔴 Sémantique")
        
        tags = get_lastfm_tags(data['name'])
        if tags:
            st.caption("Perception Public (Last.fm):")
            st.markdown(" ".join([f"`{t}`" for t in tags]))
        
        st.write("---")
        
        if st.button("🧠 Analyser les Textes") or st.session_state.nlp_analysis_done:
            st.session_state.nlp_analysis_done = True 
            
            preview = get_itunes_preview(data['name'])
            if preview:
                target_title = preview['title']
                
                # RECHERCHE FORCE BRUTE
                song = get_smart_lyrics(data['name'], target_title)
                
                if song:
                    st.write(f"Analyse de : **{song.title}**")
                    sentiment, complexity = analyze_lyrics_content(song.lyrics)
                    
                    st.subheader("Sentiment")
                    if sentiment > 0.05: st.success(f"Positif (+{sentiment:.2f})")
                    elif sentiment < -0.05: st.error(f"Sombre ({sentiment:.2f})")
                    else: st.warning(f"Neutre ({sentiment:.2f})")
                    
                    st.metric("Complexité Vocabulaire", f"{int(complexity*100)}%")
                    
                    with st.expander("Voir un extrait"):
                        st.write(song.lyrics[:300] + "...")
                else:
                    st.error(f"Échec total pour {target_title}.")
            else:
                st.warning("Titre non défini.")