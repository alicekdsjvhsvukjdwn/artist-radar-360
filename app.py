import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd

# =========================================================
# 1. CONFIGURATION
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    st.error("⚠️ Problème de connexion API.")
    st.stop()

# =========================================================
# 2. INTERFACE
# =========================================================
st.title("🎹 Artist 360° Radar")
st.markdown("### Module 1 : Marché & Business")

col_search, col_btn = st.columns([3, 1])
with col_search:
    artist_name = st.text_input("Nom de l'artiste", placeholder="Ex: Angèle")
with col_btn:
    st.write("") 
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# =========================================================
# 3. MOTEUR D'ANALYSE
# =========================================================
if search_btn and artist_name:
    st.divider()

    try:
        # --- CORRECTION MAJEURE : RECHERCHE INTELLIGENTE ---
        # 1. On demande les 5 premiers résultats (pas juste 1)
        results = sp.search(q=artist_name, type='artist', limit=5, market='FR')
        
        if not results['artists']['items']:
            st.warning("Artiste introuvable.")
            st.stop()

        # 2. TRI PAR POPULARITÉ (Le fix est ici !)
        # On trie la liste pour prendre l'artiste qui a le plus gros score de popularité
        # Ça évite de tomber sur une "Angèle" inconnue qui a 0 followers
        items = results['artists']['items']
        items.sort(key=lambda x: x['popularity'], reverse=True)
        artist = items[0] # On prend le gagnant (la Star)

        # Extraction des données
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
            # On affiche les genres pour confirmer que c'est la bonne personne
            if artist['genres']:
                st.caption(f"Genres : {', '.join(artist['genres'][:3])}")
            st.markdown(f"[Ouvrir sur Spotify]({spotify_url})")
            
    except Exception as e:
        st.error(f"Erreur recherche : {e}")
        st.stop()

    st.divider()
    col_market, col_vide1, col_vide2 = st.columns(3)

    with col_market:
        st.markdown("### 🟢 Marché & Business")

        # --- KPIs ---
        st.caption("Performance")
        kpi1, kpi2 = st.columns(2)
        kpi1.metric("Popularité", f"{popularity}/100")
        kpi2.metric("Followers", f"{followers:,}")
        
        st.write("---")

        # --- LABEL ---
        st.caption("Structure")
        try:
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=1, country='FR')
            if albums['items']:
                last_release = albums['items'][0]
                album_details = sp.album(last_release['id'])
                st.write(f"🏢 **Label :** {album_details['label']}")
                st.write(f"📅 **Sortie :** {album_details['release_date']}")
            else:
                st.warning("Aucune sortie trouvée.")
        except Exception as e:
            st.warning(f"Infos Label indisponibles.")

        st.write("---")

        # --- ÉCOSYSTÈME ---
        st.caption("Écosystème")
        try:
            related = sp.artist_related_artists(artist_id)
            
            if related['artists']:
                names = [a['name'] for a in related['artists'][:5]]
                st.write("Similaire à :")
                for n in names:
                    st.write(f"• {n}")
            else:
                st.warning("Pas assez de données pour l'écosystème.")
                
        except Exception as e:
            st.warning("Données 'Artistes Similaires' non accessibles pour cet ID.")

    # Colonnes vides
    with col_vide1: st.info("Colonne Audio (Semaine 2)")
    with col_vide2: st.info("Colonne Sémantique (Semaine 3)")