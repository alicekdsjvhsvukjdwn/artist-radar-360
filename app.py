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
st.markdown("### Module 1 : Marché & Business (Mode Debug)")

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

        # B. FILTRAGE INTELLIGENT
        # On cherche le match le plus proche
        selected_artist = None
        
        # Stratégie 1 : Match exact du nom (ex: "Angèle" == "Angèle")
        for item in items:
            if item['name'].lower() == artist_name.lower():
                selected_artist = item
                break
        
        # Stratégie 2 : Si pas de match exact, on prend le plus populaire qui contient le nom
        if not selected_artist:
            candidates = [i for i in items if artist_name.lower() in i['name'].lower()]
            if candidates:
                candidates.sort(key=lambda x: x['popularity'], reverse=True)
                selected_artist = candidates[0]
            else:
                # Stratégie 3 : On prend le #1 de la liste (Désespoir)
                selected_artist = items[0]

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
            # --- DEBUG : AFFICHE L'ID ---
            st.code(f"Spotify ID utilisé : {artist_id}") 
            st.caption("Si cet ID est '3Vvs253wKOgu1IKkBaoZ7Z', c'est la vraie Angèle.")

    except Exception as e:
        st.error(f"Erreur CRITIQUE Recherche : {e}")
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
            else:
                st.warning("Aucune sortie.")
        except Exception as e:
            st.error(f"Erreur Label : {e}")

        st.write("---")

        # --- ÉCOSYSTÈME (LA PARTIE QUI PLANTAIT) ---
        st.caption("Écosystème (Voisins)")
        try:
            # On tente la requête brute sans filtre
            related = sp.artist_related_artists(artist_id)
            
            if related['artists']:
                names = [a['name'] for a in related['artists'][:5]]
                st.success("✅ Données récupérées !")
                st.write("Similaire à :")
                for n in names:
                    st.write(f"• {n}")
            else:
                st.warning("⚠️ La liste renvoyée par Spotify est vide (0 voisins).")
                
        except Exception as e:
            # AFFICHE L'ERREUR EN ROUGE
            st.error(f"🚨 ERREUR TECHNIQUE PRÉCISE : {e}")
            st.caption("Copie-colle ce message rouge à ton assistant.")

    with col_vide1: st.info("Audio (À venir)")
    with col_vide2: st.info("Sémantique (À venir)")