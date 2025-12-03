import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- CONFIG ---
st.set_page_config(page_title="Debug Mode", layout="wide")

try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    st.error(f"Erreur API : {e}")
    st.stop()

st.title("🕵️‍♀️ Inspecteur de Résultats Spotify")
st.write("Ce script affiche TOUT ce que Spotify renvoie pour une recherche, sans filtre.")

query = st.text_input("Recherche brute :", value="Angèle")

if st.button("Scanner"):
    st.divider()
    
    # 1. On demande 20 résultats sans filtre de marché (pour voir large)
    try:
        results = sp.search(q=query, type='artist', limit=20)
        items = results['artists']['items']
        
        st.write(f"🔎 **{len(items)} résultats trouvés** pour '{query}' :")
        
        # On teste chaque résultat un par un
        for i, item in enumerate(items):
            
            col1, col2, col3 = st.columns([1, 2, 2])
            
            with col1:
                if item['images']:
                    st.image(item['images'][0]['url'], width=80)
                else:
                    st.write("Pas d'image")
            
            with col2:
                st.subheader(f"{i+1}. {item['name']}")
                st.caption(f"ID : {item['id']}")
                st.write(f"Popularité : **{item['popularity']}**")
                st.write(f"Followers : {item['followers']['total']:,}")
                
            with col3:
                # LE TEST DE VÉRITÉ : On teste les voisins pour cet ID précis
                try:
                    related = sp.artist_related_artists(item['id'])
                    # Si ça marche, on affiche le nombre
                    count = len(related['artists'])
                    if count > 0:
                        st.success(f"✅ Voisins accessibles ({count})")
                        st.caption(f"Ex: {related['artists'][0]['name']}")
                    else:
                        st.warning("⚠️ Liste voisins vide (mais pas d'erreur)")
                except Exception as e:
                    # Si ça plante, on l'affiche en ROUGE
                    st.error(f"❌ CRASH VOISINS : {e}")

            st.divider()

    except Exception as e:
        st.error(f"Erreur globale : {e}")