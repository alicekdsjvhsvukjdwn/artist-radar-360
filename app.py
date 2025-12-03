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
    st.error(f"⚠️ CRASH CONNEXION : {e}")
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
        # A. RECHERCHE LARGE (20 résultats)
        results = sp.search(q=artist_name, type='artist', limit=20, market='FR')
        
        if not results['artists']['items']:
            st.warning("Aucun artiste trouvé.")
            st.stop()

        items = results['artists']['items']

        # B. FILTRAGE ET TRI (LA CORRECTION EST ICI)
        # 1. On ne garde que ceux dont le nom contient ce qu'on cherche
        candidates = []
        for item in items:
            if artist_name.lower() in item['name'].lower():
                candidates.append(item)
        
        # (Si on n'a rien trouvé avec le filtre, on garde la liste brute par sécurité)
        if not candidates:
            candidates = items

        # 2. TRI PAR POPULARITÉ (CRUCIAL)
        # On met le plus populaire tout en haut de la liste (Index 0)
        candidates.sort(key=lambda x: x['popularity'], reverse=True)

        # 3. SÉLECTION DU GAGNANT
        selected_artist = candidates[0]

        # C. EXTRACTION
        artist_id = selected_artist['id']
        name = selected_artist['name']
        popularity = selected_artist['popularity']
        followers = selected_artist['followers']['total']
        image_url = selected_artist['images'][0]['url'] if selected_artist['images'] else None
        spotify_url = selected_artist['external_urls']['spotify']
        
        # D. AFFICHAGE EN-TÊTE + DEBUG ID
        head_c1, head_c2 = st.columns([1, 4])
        with head_c1:
            if image_url: st.image(image_url, width=150)
        with head_c2:
            st.subheader(name)
            st.markdown(f"[Ouvrir sur Spotify]({spotify_url})")
            
            # CHECK ID : Si c'est la vraie, ça doit matcher
            target_id = '3Vvs253wKOgu1IKkBaoZ7Z'
            st.caption(f"ID Trouvé : {artist_id}")
            if artist_id == target_id:
                st.success("✅ C'est la VRAIE Angèle !")
            elif name == "Angèle":
                st.warning("⚠️ Attention, homonyme détecté (Popularité faible).")

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
        st.write("---")

        # --- LABEL ---
        st.caption("Structure")
        try:
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=1, country='FR')
            if albums['items']:
                last = albums['items'][0]
                details = sp.album(last['id'])
                st.write(f"🏢 **Label :** {details['label']}")
                st.write(f"📅 **Dernière Sortie :** {details['release_date']}")
                
                # Détection signature
                label_txt = details['label'].lower()
                if any(x in label_txt for x in ["universal", "sony", "warner", "polydor", "columbia"]):
                    st.success("Signature : **MAJOR**")
                elif any(x in label_txt for x in ["distrokid", "tunecore", "spinnup"]):
                    st.info("Signature : **AUTO-PROD**")
                else:
                    st.warning("Signature : **INDÉPENDANT**")

            else:
                st.warning("Aucune sortie.")
        except Exception as e:
            st.error(f"Erreur Label : {e}")

        st.write("---")

        # --- ÉCOSYSTÈME ---
        st.caption("Écosystème (Voisins)")
        try:
            related = sp.artist_related_artists(artist_id)
            
            if related['artists']:
                names = [a['name'] for a in related['artists'][:5]]
                st.write("Similaire à :")
                for n in names:
                    st.write(f"• {n}")
            else:
                st.info("Pas de données 'Artistes Similaires' (Trop petit ou bug Spotify).")
                
        except Exception as e:
            st.error(f"Erreur Technique : {e}")

    with col_vide1: st.info("Audio (Semaine 2)")
    with col_vide2: st.info("Sémantique (Semaine 3)")