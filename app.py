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
        # --- CORRECTION 1 : ON AJOUTE market='FR' ---
        # Ça force Spotify à chercher l'artiste populaire en France
        results = sp.search(q=artist_name, type='artist', limit=1, market='FR')
        
        if not results['artists']['items']:
            st.warning("Artiste introuvable.")
            st.stop()

        artist = results['artists']['items'][0]
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
            # On affiche l'ID pour vérifier qu'on a la bonne Angèle
            st.caption(f"Spotify ID: {artist_id}") 
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
            # On cherche aussi sur le marché FR pour être cohérent
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=1, country='FR')
            if albums['items']:
                last_release = albums['items'][0]
                album_details = sp.album(last_release['id'])
                st.write(f"🏢 **Label :** {album_details['label']}")
                st.write(f"📅 **Sortie :** {album_details['release_date']}")
            else:
                st.warning("Aucune sortie trouvée.")
        except Exception as e:
            st.warning(f"Infos Label indisponibles : {e}")

        st.write("---")

        # --- CORRECTION 2 : DEBUGGAGE VOISINS ---
        st.caption("Écosystème")
        try:
            related = sp.artist_related_artists(artist_id)
            
            if related['artists']:
                names = [a['name'] for a in related['artists'][:5]]
                st.write("Similaire à :")
                # On met des puces pour que ce soit lisible
                for n in names:
                    st.write(f"• {n}")
            else:
                # Si la liste est vide mais sans erreur technique
                st.warning("Spotify ne renvoie aucun artiste similaire (Liste vide).")
                
        except Exception as e:
            # ICI on affiche l'erreur technique exacte en rouge
            st.error(f"BUG TECHNIQUE : {e}")

    # Colonnes vides
    with col_vide1: st.info("Colonne Audio (Semaine 2)")
    with col_vide2: st.info("Colonne Sémantique (Semaine 3)")