import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Elektro-Enterprise Portal", page_icon="⚡", layout="wide")

# -----------------------------------------------------------------------------
# 1. Supabase Initialisierung (aus st.secrets)
# -----------------------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
    # Prüft flexibel auf verschachtelte oder flache Secrets
    if "supabase" in st.secrets:
        url = st.secrets["supabase"]["SUPABASE_URL"]
        key = st.secrets["supabase"]["SUPABASE_KEY"]
    else:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        
    return create_client(url, key)

try:
    supabase = get_supabase()
except Exception as e:
    st.error(f"Fehler bei der Verbindung zu Supabase: {e}")

# Session State Initialisierung
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None

# -----------------------------------------------------------------------------
# 2. Login-System
# -----------------------------------------------------------------------------
def render_login():
    st.title("⚡ Elektro-Enterprise System")
    st.caption("Willkommen! Bitte melden Sie sich an.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            identifier = st.text_input("Mitarbeiternummer oder Vorname.Nachname", placeholder="z. B. 1004 oder max.mustermann")
            password = st.text_input("Passwort / PIN", type="password")
            
            submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)

            if submitted:
                if not identifier or not password:
                    st.warning("Bitte füllen Sie alle Felder aus.")
                else:
                    # Platzhalter-Authentifizierung (wird später mit Supabase-Tabelle abgeglichen)
                    st.session_state.authenticated = True
                    st.session_state.user_data = {
                        "name": identifier,
                        "rolle": "Administrator",
                        "ebene": "buero",
                        "rechte": ["1", "2", "3", "4", "5", "6", "7", "8", "9"] # Zugriff auf alle 9 Menüs
                    }
                    st.success("Erfolgreich angemeldet!")
                    st.rerun()

        st.info("💡 **Passwort vergessen?** Bitte wenden Sie sich an die Büro-Administration, um Ihr Passwort oder Ihre PIN zurücksetzen zu lassen.")

# -----------------------------------------------------------------------------
# 3. Hauptanwendung & Dynamische Sidebar
# -----------------------------------------------------------------------------
def render_app():
    user = st.session_state.user_data
    
    # Sidebar Header
    st.sidebar.title("⚡ Elektro-Portal")
    st.sidebar.write(f"Angemeldet: **{user['name']}**")
    st.sidebar.caption(f"Rolle: {user['rolle']}")
    
    if st.sidebar.button("🚪 Abmelden", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.rerun()

    st.sidebar.markdown("---")

    # 9 Menüpunkte mit ihren Untermenüs
    menu_structure = {
        "1": {"title": "👨‍💼 1. Mitarbeiterverwaltung", "sub": ["Mitarbeiterübersicht", "Rollen & Rechte", "Qualifikationen / Scheine"]},
        "2": {"title": "📦 2. Lagerverwaltung", "sub": ["Materialbestand", "Werkzeug-Tracking", "Bestellungen"]},
        "3": {"title": "⏱️ 3. Zeiterfassung", "sub": ["Stundenzettel", "⏱️ Stempeluhr", "Urlaubsplaner"]},
        "4": {"title": "📋 4. Aufträge", "sub": ["Auftragsübersicht", "Regieberichte", "Bautagebuch", "Abnahmen"]},
        "5": {"title": "👥 5. Kunden", "sub": ["Kundenstamm", "Objektadressen", "Ansprechpartner"]},
        "6": {"title": "🚛 6. Fahrzeuge", "sub": ["Fuhrparkliste", "Mängelmeldung", "TÜV & Wartung"]},
        "7": {"title": "🏢 7. Gebäude", "sub": ["Anlagenregister", "Messprotokolle (DGUV V3)"]},
        "8": {"title": "📁 8. Dokumente", "sub": ["Schaltpläne", "Normen & Vorlagen"]},
        "9": {"title": "💶 9. Finanzen / Monitor", "sub": ["Rechnungen & Angebote", "Nachkalkulation", "🖥️ Kiosk / Baustellen-Monitor"]}
    }

    # Menü-Filterung nach Rollenrechten
    allowed_menu_keys = user.get("rechte", [])
    available_menus = {k: v for k, v in menu_structure.items() if k in allowed_menu_keys}

    selected_main = st.sidebar.selectbox(
        "Hauptmenü",
        options=list(available_menus.keys()),
        format_func=lambda x: available_menus[x]["title"]
    )

    if selected_main:
        sub_options = available_menus[selected_main]["sub"]
        selected_sub = st.sidebar.radio("Untermenü", sub_options)
        
        # Hauptbereich Rendering
        st.title(available_menus[selected_main]["title"])
        st.subheader(f"Bereich: {selected_sub}")
        
        st.info(f"Modul `{available_menus[selected_main]['title']} ➔ {selected_sub}` ist bereit für die Logik.")

# -----------------------------------------------------------------------------
# 4. App-Startpunkt
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    render_login()
else:
    render_app()
