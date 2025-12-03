import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import plotly.express as px

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

# --- CONNEXION SPOTIFY ---
try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    st.error("⚠️ Erreur de connexion : Vérifie tes clés dans les Secrets Streamlit.")
    st.stop()

# --- INTERFACE ---
st.title("🎹 Artist 360° Radar")
st.markdown("### Analyse Data & Cognitive en temps réel")

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
        # 1. Recherche de l'artiste
        results = sp.search(q=artist_name, type='artist', limit=1)
        
        if results['artists']['items']:
            artist = results['artists']['items'][0]
            artist_id = artist['id']
            
            # Données de base
            name = artist['name']
            popularity = artist['popularity']
            followers = artist['followers']['total']
            genres = artist['genres']
            image_url = artist['images'][0]['url'] if artist['images'] else None
            spotify_url = artist['external_urls']['spotify']

            # Affichage En-tête
            head_c1, head_c2 = st.columns([1, 4])
            with head_c1:
                if image_url: st.image(image_url, width=150)
            with head_c2:
                st.subheader(f"Analyse de : {name}")
                if genres: st.markdown(f"**Genres :** {', '.join(genres[:3])}")
                st.markdown(f"[Écouter sur Spotify]({spotify_url})")

            st.divider()

            # --- RÉCUPÉRATION DE L'ADN SONORE (NOUVEAU) ---
            # On récupère les 10 tops titres
            top_tracks = sp.artist_top_tracks(artist_id)
            track_ids = [track['id'] for track in top_tracks['tracks']]
            
            # On récupère les caractéristiques audio (Danceability, Energy, Valence...)
            audio_features = sp.audio_features(track_ids)
            df = pd.DataFrame(audio_features)
            
            # Calcul des moyennes (C'est là que tu fais des Stats !)
            avg_danceability = df['danceability'].mean()
            avg_energy = df['energy'].mean()
            avg_valence = df['valence'].mean() # Bonheur/Tristesse
            avg_tempo = df['tempo'].mean()

            # --- VISUALISATION DASHBOARD ---
            c1, c2, c3 = st.columns(3)

            # COLONNE 1 : DATA MARCHÉ & AUDIO
            with c1:
                st.markdown("### 🟢 Marché & Audio")
                
                # KPIs
                kpi1, kpi2 = st.columns(2)
                kpi1.metric("Popularité", f"{popularity}/100")
                kpi2.metric("Followers", f"{followers:,}")
                
                st.write("---")
                st.markdown("**🧬 ADN Sonore (Moyenne Top 10)**")
                
                # Graphique Radar (Spider Chart)
                categories = ['Dansant', 'Énergie', 'Positivité (Valence)']
                values = [avg_danceability, avg_energy, avg_valence]
                
                df_radar = pd.DataFrame(dict(
                    r=values,
                    theta=categories
                ))
                fig = px.line_polar(df_radar, r='r', theta='theta', line_close=True, range_r=[0,1])
                fig.update_traces(fill='toself')
                st.plotly_chart(fig, use_container_width=True)

                # Interprétation Cognitive (Automatique)
                st.info(f"❤️ **Analyse Émotionnelle :** L'indice de positivité est de **{avg_valence:.2f}/1**. "
                        f"{'Musique plutôt Joyeuse/Solaire ☀️' if avg_valence > 0.5 else 'Musique plutôt Mélancolique/Sombre 🌧️'}")

            # COLONNE 2 & 3
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