import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="Artist 360° Radar",
    page_icon="🎹",
    layout="wide"
)

# Titre et présentation
st.title("🎹 Artist 360° Radar")
st.markdown("### L'outil d'analyse Data & Sciences Cognitives pour les artistes.")

# Zone de recherche
col1, col2 = st.columns([3, 1])
with col1:
    artist_name = st.text_input("Entrez le nom d'un artiste :", placeholder="Ex: La Fève, Angèle...")
with col2:
    st.write("") # Espace vide pour aligner
    st.write("") 
    search_btn = st.button("Lancer l'audit 🚀")

# Simulation de résultat (pour voir si ça marche)
if search_btn and artist_name:
    st.divider()
    st.subheader(f"📊 Résultat pour : {artist_name}")
    st.info("Ceci est une version démo. Les connexions API (Spotify/YouTube) arriveront bientôt !")
    
    # Création des 3 colonnes vides pour le futur
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 🟢 Marché (Spotify)")
        st.metric(label="Popularité", value="--/100")
    with c2:
        st.markdown("### 🟡 Social (YouTube)")
        st.metric(label="Sentiment", value="--")
    with c3:
        st.markdown("### 🔴 Presse (Web)")
        st.metric(label="Image", value="--")