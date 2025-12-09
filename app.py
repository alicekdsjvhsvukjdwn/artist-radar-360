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
from bs4 import BeautifulSoup # NOUVEL OUTIL DE SCRAPING
import re # Pour nettoyer le texte

# =========================================================
# 1. CONFIGURATION & CLÉS
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

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

class SongResult:
    def __init__(self, title, lyrics):
        self.title = title
        self.lyrics = lyrics

def scrape_genius_manually(url):
    """Fonction de secours qui va lire le HTML directement"""
    try:
        page = requests.get(url)
        html = BeautifulSoup(page.text, 'html.parser')
        
        # Genius cache les paroles dans des divs avec un attribut 'data-lyrics-container'
        lyrics_divs = html.find_all("div", attrs={"data-lyrics-container": "true"})
        
        if lyrics_divs:
            lyrics = ""
            for div in lyrics_divs:
                # On remplace les <br> par des sauts de ligne
                lyrics += div.get_text(separator="\n")
            
            # Petit nettoyage (enlève les trucs entre crochets comme [Refrain])
            lyrics = re.sub(r'\[.*?\]', '', lyrics)
            # Enlève les lignes vides multiples
            lyrics = re.sub(r'\n\s*\n', '\n', lyrics)
            return lyrics.strip()
        else:
            return None
    except Exception as e:
        return None

def get_smart_lyrics(artist_name, song_title):
    try:
        genius = lyricsgenius.Genius(genius_token, verbose=False)
        
        clean_title = song_title.split('(')[0].split('-')[0].strip()
        search_query = f"{artist_name} {clean_title}"
        
        # 1. On cherche l'URL de la chanson via l'API (ça, ça marche)
        response = genius.search_songs(search_query)
        
        if response and 'hits' in response and len(response['hits']) > 0:
            top_hit = response['hits'][0]['result']
            found_title = top_hit['title']
            song_url = top_hit['url'] # On récupère l'URL de la page Genius
            
            # 2. On utilise notre Scraper Manuel sur cette URL
            lyrics_text = scrape_genius_manually(song_url)
            
            if lyrics_text:
                return SongResult(found_title, lyrics_text)
            else:
                # Si le manuel échoue, on tente la méthode classique (au cas où)
                try:
                    song = genius.song(top_hit['id'])
                    return SongResult(found_title, song.lyrics)
                except:
                    return None
        return None

    except Exception as e:
        return None

# (Les autres fonctions restent identiques)
def get_lastfm_tags(artist_name):
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist={artist_name}&api_key={lastfm_key}&format=json"
        response = requests.get(url).json()
        ignore = ['seen live', 'under 2000 listeners', 'french', 'belgian', 'hip-hop', 'rap', 'pop', 'trap']
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

    # COLONNE 1
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

    # COLONNE 2
    with col_audio:
        st.markdown("### 🟡 Physique du Signal")
        if st.button("🔊 Analyser l'Audio") or st.session_state.audio_analysis_done:
            st.session_state.audio_analysis_done = True 
            preview_data = get_itunes_preview(data['name'])
            if preview_data:
                st.image(preview_data['cover'], width=80)
                st.caption(f"**{preview_data['title']}**")
                st.audio(preview_data['preview_url'])
                tempo, rms, cent, dynamic, y = analyze_signal(preview_data['preview_url'])
                artist_genres = " ".join(data['genres']).lower()
                bpm_final = int(tempo)
                if bpm_final > 130 and any(g in artist_genres for g in ['trap', 'rap', 'hip hop']):
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

    # COLONNE 3
    with col_semantic:
        st.markdown("### 🔴 Sémantique")
        tags = get_lastfm_tags(data['name'])
        if tags: st.markdown(" ".join([f"`{t}`" for t in tags]))
        st.write("---")
        
        if st.button("🧠 Analyser les Textes") or st.session_state.nlp_analysis_done:
            st.session_state.nlp_analysis_done = True 
            preview = get_itunes_preview(data['name'])
            if preview:
                target_title = preview['title']
                
                # RECHERCHE AVEC SCRAPER MANUEL
                with st.spinner("Téléchargement des paroles (Scraping)..."):
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
                    st.error(f"Paroles introuvables pour {target_title}.")
            else:
                st.warning("Titre non défini.")


# ... (Tes imports habituels : st, spotipy, pandas, plotly.graph_objects as go) ...
import plotly.graph_objects as go # Il faut ajouter cet import en haut !

# =========================================================
# MODULE : STYLE BENCHMARKER
# =========================================================
st.divider()
st.markdown("### ⚔️ Le Duel : Ton Son vs La Tendance")
st.caption("Compare ton titre aux Hits actuels d'un genre précis.")

col_input1, col_input2, col_go = st.columns([2, 2, 1])

with col_input1:
    target_track_name = st.text_input("Ton Titre (à tester)", placeholder="Ex: La Fève - MAUVAIS PAYEUR")
with col_input2:
    target_genre = st.text_input("Le Style Visé", placeholder="Ex: french hip hop, hyperpop, techno...")
with col_go:
    st.write("")
    st.write("")
    btn_compare = st.button("Comparer ⚔️")

if btn_compare and target_track_name and target_genre:
    
    with st.spinner(f"Analyse du marché '{target_genre}' en cours..."):
        try:
            # 1. ANALYSE DE TON SON (CIBLE)
            # On cherche le son
            res_target = sp.search(q=target_track_name, type='track', limit=1)
            if not res_target['tracks']['items']:
                st.error("Ton titre est introuvable.")
                st.stop()
            
            my_track = res_target['tracks']['items'][0]
            my_features = sp.audio_features(my_track['id'])[0]
            
            # 2. ANALYSE DU MARCHÉ (RÉFÉRENCE)
            # On cherche les 50 tracks les plus populaires de ce genre
            # La requête "genre:nom_du_genre" est puissante
            res_genre = sp.search(q=f'genre:"{target_genre}"', type='track', limit=50)
            
            if not res_genre['tracks']['items']:
                st.error(f"Aucun hit trouvé pour le genre '{target_genre}'. Essaie un autre nom (ex: 'pop', 'trap', 'house').")
                st.stop()
                
            genre_tracks = res_genre['tracks']['items']
            
            # On récupère les IDs pour avoir les features
            genre_ids = [t['id'] for t in genre_tracks]
            # Spotify limite à 100 ids par appel, ça passe
            genre_features_list = sp.audio_features(genre_ids)
            
            # On nettoie (enlève les None)
            genre_features_list = [f for f in genre_features_list if f]
            
            # 3. CALCUL DES MOYENNES (DATA SCIENCE)
            df_genre = pd.DataFrame(genre_features_list)
            
            avg_stats = {
                'Energy': df_genre['energy'].mean(),
                'Danceability': df_genre['danceability'].mean(),
                'Valence': df_genre['valence'].mean(),
                'Acousticness': df_genre['acousticness'].mean(),
                # On normalise la Loudness (qui est en négatif genre -5dB) pour le graph
                # Astuce : (Loudness + 60) / 60 pour avoir un truc entre 0 et 1
                'Puissance (Loudness)': (df_genre['loudness'].mean() + 60) / 60
            }
            
            my_stats = {
                'Energy': my_features['energy'],
                'Danceability': my_features['danceability'],
                'Valence': my_features['valence'],
                'Acousticness': my_features['acousticness'],
                'Puissance (Loudness)': (my_features['loudness'] + 60) / 60
            }

            # 4. VISUALISATION RADAR (SPIDER CHART)
            categories = list(avg_stats.keys())
            
            fig = go.Figure()

            # La zone "Marché" (Moyenne)
            fig.add_trace(go.Scatterpolar(
                r=list(avg_stats.values()),
                theta=categories,
                fill='toself',
                name=f'Moyenne {target_genre}',
                line_color='gray',
                opacity=0.5
            ))

            # La ligne "Ton Son"
            fig.add_trace(go.Scatterpolar(
                r=list(my_stats.values()),
                theta=categories,
                fill='toself',
                name='Ton Son',
                line_color='#1DB954' # Vert Spotify
            ))

            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                showlegend=True,
                title=f"Comparatif : {my_track['name']} vs Top 50 {target_genre}"
            )
            
            # 5. AFFICHAGE RÉSULTATS
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.image(my_track['album']['images'][0]['url'], width=150)
                st.metric("Ta Popularité", f"{my_track['popularity']}/100")
                
                # Moyenne popularité du genre
                avg_pop = sum([t['popularity'] for t in genre_tracks]) / len(genre_tracks)
                st.metric(f"Moyenne du Top {target_genre}", f"{int(avg_pop)}/100")
                
                delta_pop = my_track['popularity'] - avg_pop
                if delta_pop >= -10:
                    st.success("✅ Tu es dans la norme des Hits !")
                else:
                    st.warning("⚠️ Tu es en dessous des standards du genre.")

            with c2:
                st.plotly_chart(fig, use_container_width=True)
                
            # 6. CONSEILS AUTOMATISÉS (PREDICTION)
            st.subheader("💡 Conseils Stratégiques")
            
            # Durée
            avg_duration = df_genre['duration_ms'].mean() / 1000
            my_duration = my_features['duration_ms'] / 1000
            diff_duration = my_duration - avg_duration
            
            if diff_duration > 30:
                st.error(f"⏱️ **Durée :** Ton son est trop long ({int(my_duration)}s). La moyenne du genre est à {int(avg_duration)}s. Coupe {int(diff_duration)}s pour optimiser le replay.")
            elif diff_duration < -30:
                st.warning(f"⏱️ **Durée :** Ton son est très court. C'est bien pour TikTok, mais vérifie qu'il est assez construit.")
            else:
                st.success(f"⏱️ **Durée :** Parfaite ({int(my_duration)}s). Tu es pile dans le standard.")
                
            # Energie
            if my_stats['Energy'] < avg_stats['Energy'] - 0.2:
                st.info(f"⚡ **Énergie :** Ton mixage manque de peps comparé aux hits. Pense à compresser ou saturer plus.")
            
            # Danceability
            if my_stats['Danceability'] < avg_stats['Danceability'] - 0.2:
                st.info(f"💃 **Rythme :** Ton son est moins 'dansant' que la moyenne. Attention si tu vises les clubs.")

        except Exception as e:
            st.error(f"Erreur lors de l'analyse comparative : {e}")