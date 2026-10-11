import streamlit as st
from supabase import create_client, Client
from modules.mitarbeiter import render_mitarbeiter_verwaltung

st.set_page_config(page_title="Elektro-Enterprise Portal", page_icon="⚡", layout="wide")

@st.cache_resource
def get_supabase() -> Client:
    if "supabase" in st.secrets:
        url = st.secrets["supabase"]["SUPABASE_URL"]
        key = st.secrets["supabase"]["SUPABASE_KEY"]
    else:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None

# ... [render_login bleibt unverändert] ...

def render_app():
    user = st.session_state.user_data
    
    st.sidebar.title("⚡ Elektro-Portal")
    st.sidebar.write(f"Angemeldet: **{user['name']}**")
    st.sidebar.caption(f"Nr: {user['mitarbeiternummer']} | Rolle: {user['rolle']}")
    
    if st.sidebar.button("🚪 Abmelden", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.rerun()

    st.sidebar.markdown("---")

    menu_structure = {
        "1": {"title": "👨‍💼 1. Mitarbeiterverwaltung", "sub": ["Verwaltung"]},
        "2": {"title": "📦 2. Lagerverwaltung", "sub": ["Materialbestand"]},
        "3": {"title": "⏱️ 3. Zeiterfassung", "sub": ["Stundenzettel"]},
        "4": {"title": "📋 4. Aufträge", "sub": ["Auftragsübersicht"]},
        "5": {"title": "👥 5. Kunden", "sub": ["Kundenstamm"]},
        "6": {"title": "🚛 6. Fahrzeuge", "sub": ["Fuhrparkliste"]},
        "7": {"title": "🏢 7. Gebäude", "sub": ["Anlagenregister"]},
        "8": {"title": "📁 8. Dokumente", "sub": ["Schaltpläne"]},
        "9": {"title": "💶 9. Finanzen / Monitor", "sub": ["Rechnungen"]}
    }

    allowed_menu_keys = user.get("rechte", [])
    available_menus = {k: v for k, v in menu_structure.items() if k in allowed_menu_keys}

    selected_main = st.sidebar.selectbox(
        "Hauptmenü",
        options=list(available_menus.keys()),
        format_func=lambda x: available_menus[x]["title"]
    )

    if selected_main:
        if selected_main == "1":
            # Hier das Mitarbeiterverwaltungs-Modul ausführen
            render_mitarbeiter_verwaltung(supabase)
        else:
            st.title(available_menus[selected_main]["title"])
            st.info("Dieses Modul wird als Nächstes ausgebaut.")

if not st.session_state.authenticated:
    render_login()
else:
    render_app()
