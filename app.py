import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

# --- CONNEXION SPOTIFY (Invisible) ---
try:
    # On récupère les clés depuis le coffre-fort Streamlit
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    
    # On initialise la connexion
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    st.error("⚠️ Erreur de connexion : Vérifie tes clés dans les Secrets Streamlit.")
    st.stop()

# --- INTERFACE ---
st.title("🎹 Artist 360° Radar")
st.markdown("### Analyse Data & Cognitive en temps réel")

# Barre de recherche
col1, col2 = st.columns([3, 1])
with col1:
    artist_name = st.text_input("Nom de l'artiste", placeholder="Ex: La Fève")
with col2:
    st.write("")
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# --- LOGIQUE D'ANALYSE ---
if search_btn and artist_name:
    st.divider()
    
    try:
        # 1. Recherche de l'artiste sur Spotify
        results = sp.search(q=artist_name, type='artist', limit=1)
        
        if results['artists']['items']:
            artist = results['artists']['items'][0]
            
            # Récupération des données
            name = artist['name']
            popularity = artist['popularity']
            followers = artist['followers']['total']
            genres = artist['genres']
            image_url = artist['images'][0]['url'] if artist['images'] else None
            spotify_url = artist['external_urls']['spotify']

            # Affichage En-tête
            head_c1, head_c2 = st.columns([1, 4])
            with head_c1:
                if image_url:
                    st.image(image_url, width=150)
            with head_c2:
                st.subheader(f"Analyse de : {name}")
                if genres:
                    st.markdown(f"**Genres :** {', '.join(genres[:3])}")
                st.markdown(f"[Écouter sur Spotify]({spotify_url})")

            st.divider()

            # Dashboard
            c1, c2, c3 = st.columns(3)

            # COLONNE 1 : SPOTIFY
            with c1:
                st.markdown("### 🟢 Marché (Spotify)")
                st.metric(label="Popularité", value=f"{popularity}/100")
                
                # Interprétation Data
                if popularity > 80: status = "🌟 Star"
                elif popularity > 50: status = "📈 Confirmé"
                elif popularity > 20: status = "🌱 Émergent"
                else: status = "🥚 Niche"
                
                st.info(f"Statut : **{status}**")
                st.write(f"Followers : **{followers:,}**")

            # COLONNE 2 & 3 (Vides pour l'instant)
            with c2:
                st.markdown("### 🟡 Social (YouTube)")
                st.warning("À venir...")
            with c3:
                st.markdown("### 🔴 Presse (Web)")
                st.warning("À venir...")

        else:
            st.error("Artiste introuvable.")

    except Exception as e:
        st.error(f"Erreur technique : {e}")