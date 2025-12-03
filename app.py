import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd

# =========================================================
# 1. CONFIGURATION & AUTHENTIFICATION
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    st.error("⚠️ Problème de connexion API. Vérifie tes clés.")
    st.stop()

# =========================================================
# 2. INTERFACE
# =========================================================
st.title("🎹 Artist 360° Radar")
st.markdown("### Module 1 : Marché & Business (Version Stable)")

col_search, col_btn = st.columns([3, 1])
with col_search:
    artist_name = st.text_input("Nom de l'artiste", placeholder="Ex: La Fève")
with col_btn:
    st.write("") 
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# =========================================================
# 3. LE MOTEUR SÉCURISÉ
# =========================================================
if search_btn and artist_name:
    st.divider()

    # --- BLOC A : RECHERCHE IDENTITÉ (CRITIQUE) ---
    # Si ça plante ici, on arrête tout (normal).
    try:
        results = sp.search(q=artist_name, type='artist', limit=1)
        if not results['artists']['items']:
            st.warning("Artiste introuvable.")
            st.stop() # On arrête proprement

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
            st.markdown(f"[Ouvrir sur Spotify]({spotify_url})")
            
    except Exception as e:
        st.error(f"Erreur lors de la recherche : {e}")
        st.stop()

    st.divider()
    
    # On prépare les colonnes pour l'affichage
    col_market, col_vide1, col_vide2 = st.columns(3)

    with col_market:
        st.markdown("### 🟢 Marché & Business")

        # --- BLOC B : AFFICHAGE KPIs (SIMPLE) ---
        st.caption("Performance")
        kpi1, kpi2 = st.columns(2)
        kpi1.metric("Popularité", f"{popularity}/100")
        kpi2.metric("Followers", f"{followers:,}")
        
        if popularity > 50:
            st.success("Statut : **Confirmé**")
        elif popularity > 20:
            st.info("Statut : **Développement**")
        else:
            st.write("Statut : **Démarrage**")
        
        st.write("---")

        # --- BLOC C : LE LABEL (SÉCURISÉ) ---
        # Si ce bloc plante, on affiche juste "Info non dispo"
        st.caption("Structure")
        try:
            albums = sp.artist_albums(artist_id, album_type='album,single', limit=1)
            if albums['items']:
                last_release = albums['items'][0]
                album_details = sp.album(last_release['id'])
                
                label = album_details['label']
                date = album_details['release_date']
                
                st.write(f"🏢 **Label :** {label}")
                st.write(f"📅 **Sortie :** {date}")
                
                # Détection simple
                if any(x in label for x in ["Universal", "Sony", "Warner"]):
                    st.success("Signature : **Major**")
                elif any(x in label for x in ["DistroKid", "TuneCore"]):
                    st.info("Signature : **Indépendant**")
            else:
                st.warning("Aucune sortie trouvée.")
        except Exception as e:
            st.warning("Infos Label indisponibles.")

        st.write("---")

        # --- BLOC D : LES VOISINS (CELUI QUI PLANTAIT) ---
        # Si ce bloc plante (Erreur 404), on l'ignore silencieusement.
        st.caption("Écosystème")
        try:
            related = sp.artist_related_artists(artist_id)
            if related['artists']:
                names = [a['name'] for a in related['artists'][:5]]
                st.write("Similaire à :")
                st.markdown(f"*{', '.join(names)}*")
            else:
                st.write("Pas encore de données 'Artistes Similaires'.")
        except Exception as e:
            st.info("Algorithme de recommandation insuffisant pour cet artiste.")

    # Les autres colonnes restent vides pour l'instant
    with col_vide1:
        st.write("Colonne Audio (à venir)")
    with col_vide2:
        st.write("Colonne Sémantique (à venir)")