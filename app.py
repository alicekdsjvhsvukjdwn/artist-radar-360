import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd

# =========================================================
# 1. CONFIGURATION DE LA PAGE
# =========================================================
st.set_page_config(page_title="Artist 360° Radar", page_icon="🎹", layout="wide")

# =========================================================
# 2. CONNEXION API (AUTHENTIFICATION)
# =========================================================
try:
    # Récupération des clés dans le coffre-fort Streamlit
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    
    # Connexion à Spotify
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    st.error("⚠️ Erreur de connexion : Vérifie tes clés API dans les Secrets.")
    st.stop()

# =========================================================
# 3. INTERFACE UTILISATEUR (HEADER)
# =========================================================
st.title("🎹 Artist 360° Radar")
st.markdown("### Module 1 : Analyse Marché & Business Intelligence")

# Barre de recherche
col_search, col_btn = st.columns([3, 1])
with col_search:
    artist_name = st.text_input("Nom de l'artiste", placeholder="Ex: La Fève, Angèle, Freeze Corleone...")
with col_btn:
    st.write("") # Espace pour aligner
    st.write("")
    search_btn = st.button("Lancer l'audit 🚀")

# =========================================================
# 4. LOGIQUE D'ANALYSE (LE CERVEAU)
# =========================================================
if search_btn and artist_name:
    st.divider()
    
    try:
        # --- A. RECHERCHE DE L'ARTISTE ---
        results = sp.search(q=artist_name, type='artist', limit=1)
        
        if not results['artists']['items']:
            st.error("Artiste introuvable.")
            st.stop()
            
        artist = results['artists']['items'][0]
        artist_id = artist['id']

        # --- B. EXTRACTION DES DONNÉES IDENTITÉ ---
        name = artist['name']
        popularity = artist['popularity']            # Score 0-100
        followers = artist['followers']['total']     # Nombre d'abonnés
        genres = artist['genres']                    # Styles musicaux
        image_url = artist['images'][0]['url'] if artist['images'] else None
        spotify_url = artist['external_urls']['spotify']

        # --- C. EXTRACTION DES DONNÉES BUSINESS (Le Spyware) ---
        # On cherche le dernier album/single sorti pour voir le Copyright
        albums = sp.artist_albums(artist_id, album_type='album,single', limit=1)
        
        label_name = "Inconnu"
        release_date = "Inconnue"
        copyright_text = "N/A"
        
        if albums['items']:
            last_release = albums['items'][0]
            # ASTUCE : Il faut refaire une requête sur l'album précis pour avoir le Label
            album_details = sp.album(last_release['id'])
            
            label_name = album_details['label']
            release_date = album_details['release_date']
            if album_details['copyrights']:
                copyright_text = album_details['copyrights'][0]['text']

        # --- D. EXTRACTION DU RÉSEAU (Graphe Social) ---
        related_artists = sp.artist_related_artists(artist_id)
        related_names = []
        if related_artists['artists']:
            # On prend les 5 premiers noms
            related_names = [art['name'] for art in related_artists['artists'][:5]]

        # =========================================================
        # 5. AFFICHAGE DU DASHBOARD
        # =========================================================
        
        # --- EN-TÊTE ---
        head_c1, head_c2 = st.columns([1, 4])
        with head_c1:
            if image_url: st.image(image_url, width=150)
        with head_c2:
            st.subheader(f"Analyse de : {name}")
            if genres:
                st.markdown(f"**Genres détectés :** {', '.join(genres[:3])}")
            st.markdown(f"[Écouter sur Spotify]({spotify_url})")

        st.divider()

        # CRÉATION DES 3 COLONNES PRINCIPALES
        # (Pour l'instant, on ne remplit que la 1ère comme demandé)
        col_market, col_audio, col_semantic = st.columns(3)

        # ---------------------------------------------------------
        # COLONNE 1 : MARCHÉ & BUSINESS (Module Complet)
        # ---------------------------------------------------------
        with col_market:
            st.markdown("### 🟢 Marché & Business")
            
            # 1. INDICATEURS DE PERFORMANCE (KPIs)
            st.caption("Performance")
            kpi1, kpi2 = st.columns(2)
            kpi1.metric("Popularité", f"{popularity}/100")
            kpi2.metric("Followers", f"{followers:,}")
            
            # Analyse Cognitive du Ratio
            ratio = 0
            if followers > 0:
                # Ratio arbitraire pour l'exemple
                pass 
            
            if popularity > 80:
                st.success("Statut : **Mainstream / Star 🌟**")
            elif popularity > 50:
                st.info("Statut : **Confirmé / En croissance 📈**")
            elif popularity > 20:
                st.warning("Statut : **Émergent / Développement 🌱**")
            else:
                st.write("Statut : **Niche / Démarrage 🥚**")

            st.write("---")

            # 2. INTELLIGENCE ÉCONOMIQUE (Label & Sorties)
            st.caption("Structure & Juridique")
            st.write(f"🏢 **Label/Distrib :** {label_name}")
            st.write(f"📅 **Dernière sortie :** {release_date}")
            
            # Analyse automatique (Major vs Indé)
            majors = ["Universal", "Sony", "Warner", "Polydor", "Columbia", "RCA"]
            indies = ["DistroKid", "TuneCore", "Spinnup", "Ditto", "CD Baby"]
            
            # On vérifie si un mot-clé est dans le nom du label
            is_major = any(m in label_name for m in majors)
            is_indie = any(i in label_name for i in indies)

            if is_major:
                st.success("✅ **Signature Probable : MAJOR** (Gros Budget)")
            elif is_indie:
                st.info("🆓 **Signature : AUTO-PROD / INDÉ** (Liberté)")
            else:
                st.warning("🏢 **Signature : LABEL INDÉPENDANT** (Structure)")

            st.expander("Voir le Copyright légal").write(copyright_text)

            st.write("---")

            # 3. ÉCOSYSTÈME (Les voisins)
            st.caption("Graphe Social (Concurrents/Feats)")
            if related_names:
                # On affiche ça sous forme de petits tags
                st.write("L'algorithme l'associe à :")
                st.markdown(f"*{', '.join(related_names)}*")
            else:
                st.write("Pas assez de données réseau.")

        # ---------------------------------------------------------
        # COLONNE 2 : AUDIO (Vide pour l'instant)
        # ---------------------------------------------------------
        with col_audio:
            st.markdown("### 🟡 Signal Audio")
            st.info("Module en construction (Semaine 2)...")
            st.write("Ici s'afficheront : BPM, Énergie, Waveform.")

        # ---------------------------------------------------------
        # COLONNE 3 : SÉMANTIQUE (Vide pour l'instant)
        # ---------------------------------------------------------
        with col_semantic:
            st.markdown("### 🔴 Image & Perception")
            st.info("Module en construction (Semaine 3)...")
            st.write("Ici s'afficheront : Mots-clés, Sentiments, Tags.")

    except Exception as e:
        st.error(f"Une erreur technique est survenue : {e}")