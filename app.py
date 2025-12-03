import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import requests # Pour parler à Last.fm

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
    
    # Clé Last.fm (Nouvelle !)
    lastfm_key = st.secrets["LASTFM_API_KEY"]
except Exception as e:
    st.error(f"⚠️ Manque des clés API dans les Secrets : {e}")
    st.stop()

# =========================================================
# 2. FONCTION RECUPERATION VOISINS (LAST.FM)
# =========================================================
def get_similar_artists_lastfm(artist_name):
    """Demande à Last.fm les artistes similaires"""
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={artist_name}&api_key={lastfm_key}&format=json&limit=5"
        response = requests.get(url).json()
        
        # On extrait juste les noms
        artists = response['similarartists']['artist']
        names = [a['name'] for a in artists]
        return names
    except:
        return []

# =========================================================
# 3. INTERFACE
# =========================================================
st.title("🎹 Artist 360° Radar")
st.markdown("### Module 1 : Marché & Business")

col_search, col_btn = st.columns([3, 1])
with col_search:
    query = st.text_input("Recherche", placeholder="Nom ou Lien Spotify")
with col_btn:
    st.write("") 
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# =========================================================
# 4. MOTEUR D'ANALYSE
# =========================================================
if search_btn and query:
    st.divider()

    try:
        # --- A. RECHERCHE SPOTIFY ---
        if "open.spotify.com" in query:
            artist_id = query.split("/artist/")[1].split("?")[0]
            artist = sp.artist(artist_id)
        else:
            results = sp.search(q=query, type='artist', limit=10, market='FR')
            if not results['artists']['items']:
                st.warning("Artiste introuvable.")
                st.stop()
            
            # Filtre intelligent
            items = results['artists']['items']
            candidates = [i for i in items if query.lower() in i['name'].lower()]
            if not candidates: candidates = items
            candidates.sort(key=lambda x: x['popularity'], reverse=True)
            artist = candidates[0]

        # --- B. EXTRACTION ---
        artist_id = artist['id']
        name = artist['name']
        popularity = artist['popularity']
        followers = artist['followers']['total']
        image_url = artist['images'][0]['url'] if artist['images'] else None
        spotify_url = artist['external_urls']['spotify']
        
        # Affichage En-tête
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
    col_market, col_vide1, col_vide2 = st.columns(3)

    with col_market:
        st.markdown("### 🟢 Marché & Business")

        # --- KPIs ---
        kpi1, kpi2 = st.columns(2)
        kpi1.metric("Popularité", f"{popularity}/100")
        kpi2.metric("Followers", f"{followers:,}")
        st.progress(popularity)
        st.write("---")

        # --- LABEL ---
        st.caption("Structure")
        try:
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=5, country='FR')
            if albums['items']:
                last = albums['items'][0]
                details = sp.album(last['id'])
                
                label_txt = details['label']
                st.write(f"🏢 **Label :** {label_txt}")
                st.write(f"📅 **Sortie :** {details['release_date']}")
                
                # Signature
                l = label_txt.lower()
                if any(x in l for x in ["universal", "sony", "warner", "polydor"]):
                    st.success("✅ **MAJOR**")
                elif any(x in l for x in ["distrokid", "tunecore", "believe"]):
                    st.info("🆓 **INDÉPENDANT**")
                else:
                    st.warning("⚖️ **STRUCTURE INDÉ**")
        except:
            st.write("Info Label indisponible")

        st.write("---")

        # --- ÉCOSYSTÈME (VIA LAST.FM) ---
        # C'est ici qu'on utilise la solution de secours !
        st.caption("Écosystème (Source : Last.fm)")
        
        similar_artists = get_similar_artists_lastfm(name)
        
        if similar_artists:
            st.write("Le public écoute aussi :")
            for n in similar_artists:
                st.write(f"• {n}")
        else:
            st.warning("Pas de données similaires trouvées.")

    with col_vide1: st.info("Audio (Semaine 2)")
    with col_vide2: st.info("Sémantique (Semaine 3)")