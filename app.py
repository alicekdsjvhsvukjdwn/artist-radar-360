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
st.markdown("### Module 1 : Marché & Business (Version Auto-Repair)")

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

    selected_artist = None
    related_artists_data = None # Pour stocker les voisins si on les trouve

    with st.spinner("Recherche et vérification de l'intégrité des données..."):
        try:
            # A. RECHERCHE LARGE
            results = sp.search(q=artist_name, type='artist', limit=10, market='FR')
            items = results['artists']['items']

            if not items:
                st.warning("Aucun artiste trouvé.")
                st.stop()

            # B. TRI PAR POPULARITÉ
            # On garde ceux qui matchent le nom
            candidates = [i for i in items if artist_name.lower() in i['name'].lower()]
            if not candidates: candidates = items # Fallback
            
            candidates.sort(key=lambda x: x['popularity'], reverse=True)

            # C. BOUCLE DE "SELF-HEALING" (C'est ici la magie)
            # On teste les candidats un par un pour trouver celui qui n'est pas bugué
            for candidate in candidates:
                try:
                    # LE TEST CRITIQUE : Est-ce qu'on peut accéder à ses voisins ?
                    # Si ça plante ici, on passe au 'except' et on essaie le suivant
                    test_related = sp.artist_related_artists(candidate['id'])
                    
                    # Si on arrive ici, c'est que l'artiste est VALIDE
                    selected_artist = candidate
                    related_artists_data = test_related # On garde les données pour ne pas refaire la requête
                    break # On sort de la boucle, on a trouvé le bon !
                
                except Exception:
                    # Si erreur (404 ou autre), on ignore ce candidat et on continue la boucle
                    continue
            
            # Si après la boucle on a rien trouvé de valide, on prend le premier par défaut (tant pis)
            if not selected_artist:
                selected_artist = candidates[0]
                st.error("⚠️ Impossible de trouver un profil 100% fonctionnel. Affichage du profil par défaut (risque d'erreurs).")

            # D. EXTRACTION DES DONNÉES FINALES
            artist_id = selected_artist['id']
            name = selected_artist['name']
            popularity = selected_artist['popularity']
            followers = selected_artist['followers']['total']
            image_url = selected_artist['images'][0]['url'] if selected_artist['images'] else None
            spotify_url = selected_artist['external_urls']['spotify']
            
            # Affichage En-tête
            head_c1, head_c2 = st.columns([1, 4])
            with head_c1:
                if image_url: st.image(image_url, width=150)
            with head_c2:
                st.subheader(name)
                st.caption(f"ID Validé : {artist_id}")
                st.markdown(f"[Ouvrir sur Spotify]({spotify_url})")
                
                # Check Angèle
                if artist_id == '3Vvs253wKOgu1IKkBaoZ7Z':
                    st.success("✅ Profil Officiel Certifié (Vraie Angèle)")

        except Exception as e:
            st.error(f"Erreur Critique : {e}")
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
                st.write(f"📅 **Sortie :** {details['release_date']}")
            else:
                st.warning("Aucune sortie.")
        except Exception as e:
            st.warning("Info Label indisponible")

        st.write("---")

        # --- ÉCOSYSTÈME ---
        st.caption("Écosystème (Voisins)")
        # Ici on utilise les données qu'on a DÉJÀ récupérées pendant le test (optimisation)
        if related_artists_data and related_artists_data['artists']:
            names = [a['name'] for a in related_artists_data['artists'][:5]]
            st.write("Similaire à :")
            for n in names:
                st.write(f"• {n}")
        else:
            st.info("Pas d'artistes similaires trouvés.")

    with col_vide1: st.info("Audio (Semaine 2)")
    with col_vide2: st.info("Sémantique (Semaine 3)")