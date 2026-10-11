import streamlit as st
import extra_streamlit_components as stx
from supabase import create_client, Client

st.set_page_config(page_title="Elektro-Enterprise Portal", page_icon="⚡", layout="wide")

# -----------------------------------------------------------------------------
# 1. Supabase Initialisierung
# -----------------------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# Session State Initialisierung
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None
if "kiosk_mode" not in st.session_state:
    st.session_state.kiosk_mode = False

# -----------------------------------------------------------------------------
# 2. Login-System (Standard & Kiosk & Passwort-Reset)
# -----------------------------------------------------------------------------
def render_login():
    st.title("⚡ Elektro-Enterprise System")
    
    tab_standard, tab_kiosk, tab_reset = st.tabs(["Büro / Außendienst Login", "⏱️ Kiosk / Terminal-Stempeluhr", "🔑 Passwort vergessen"])
    
    with tab_standard:
        with st.form("standard_login"):
            identifier = st.text_input("Mitarbeiternummer oder Vorname.Nachname")
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", type="primary")
            
            if submitted:
                # E-Mail aus Mitarbeiternummer/Name auflösen (oder direkte Auth-Abfrage)
                # supabase.auth.sign_in_with_password({"email": user_email, "password": password})
                st.session_state.authenticated = True
                st.session_state.user_data = {
                    "name": "Dominik Meyer",
                    "rolle": "Admin",
                    "ebene": "buero",
                    "rechte": ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
                }
                st.rerun()

    with tab_kiosk:
        st.subheader("Schnellanmeldung Werkstatt / Lager")
        mitarbeiternr = st.text_input("Mitarbeiternummer")
        pin = st.text_input("4-stellige PIN", type="password", max_chars=4)
        if st.button("Kiosk Einloggen"):
            st.session_state.authenticated = True
            st.session_state.kiosk_mode = True
            st.session_state.user_data = {
                "name": "Monteur Max",
                "rolle": "Monteur",
                "ebene": "kiosk",
                "rechte": ["2", "3", "6"] # Nur Lager, Zeiterfassung, Fahrzeuge
            }
            st.rerun()

    with tab_reset:
        st.subheader("Passwort zurücksetzen")
        st.caption("Ein Link zum Zurücksetzen wird an Ihre registrierte E-Mail-Adresse gesendet (DSGVO-konform).")
        reset_email = st.text_input("Ihre Dienst-E-Mail-Adresse")
        if st.button("Sicherheits-Link anfordern"):
            try:
                # supabase.auth.reset_password_for_email(reset_email)
                st.success("Falls ein Konto mit dieser E-Mail existiert, wurde eine Nachricht gesendet.")
            except Exception as e:
                st.error(f"Fehler: {e}")

# -----------------------------------------------------------------------------
# 3. Hauptanwendung & Dynamische Sidebar
# -----------------------------------------------------------------------------
def render_app():
    user = st.session_state.user_data
    
    # Sidebar
    st.sidebar.title("⚡ Elektro-Portal")
    st.sidebar.write(f"Angemeldet: **{user['name']}**")
    st.sidebar.caption(f"Rolle: {user['rolle']} | Ebene: {user['ebene'].upper()}")
    
    if st.sidebar.button("Abmelden"):
        st.session_state.authenticated = False
        st.session_state.kiosk_mode = False
        st.rerun()

    st.sidebar.markdown("---")

    # Menüstruktur definieren
    menu_structure = {
        "1": {"title": "👨‍💼 1. Mitarbeiterverwaltung", "sub": ["Übersicht", "Rollen & Rechte", "Qualifikationen"]},
        "2": {"title": "📦 2. Lagerverwaltung", "sub": ["Materialbestand", "Werkzeug-Tracking", "Nachbestellungen"]},
        "3": {"title": "⏱️ 3. Zeiterfassung", "sub": ["Stundenzettel", "Kiosk-Stempeluhr", "Urlaubsplaner"]},
        "4": {"title": "📋 4. Aufträge", "sub": ["Auftragsliste", "Regieberichte", "Bautagebuch"]},
        "5": {"title": "👥 5. Kunden", "sub": ["Kundenstamm", "Objektadressen"]},
        "6": {"title": "🚛 6. Fahrzeuge", "sub": ["Fuhrparkübersicht", "Mängelmeldungen", "TÜV-Kanal"]},
        "7": {"title": "🏢 7. Gebäude", "sub": ["Anlagenregister", "Messprotokolle (DGUV V3)"]},
        "8": {"title": "📁 8. Dokumente", "sub": ["Schaltpläne", "Normen & Vorlagen"]},
        "9": {"title": "💶 9. Finanzen", "sub": ["Rechnungen & Angebote", "Nachkalkulation"]}
    }

    # Sidebar-Filterung nach Rollenrechten
    allowed_menu_keys = user.get("rechte", [])
    available_menus = {k: v for k, v in menu_structure.items() if k in allowed_menu_keys}

    selected_main = st.sidebar.selectbox(
        "Hauptmenü wählen",
        options=list(available_menus.keys()),
        format_func=lambda x: available_menus[x]["title"]
    )

    if selected_main:
        sub_options = available_menus[selected_main]["sub"]
        selected_sub = st.sidebar.radio("Untermenü", sub_options)
        
        # Hauptbereich Rendering
        st.title(available_menus[selected_main]["title"])
        st.subheader(f"Bereich: {selected_sub}")
        
        # Routing-Logik für die Module
        if selected_main == "3" and selected_sub == "Kiosk-Stempeluhr":
            render_stempeluhr_kiosk()
        else:
            st.info(f"Modul `{available_menus[selected_main]['title']} -> {selected_sub}` geladen.")

def render_stempeluhr_kiosk():
    st.card = st.container()
    st.card.subheader("⏱️ Schnellerfassung Kommen / Gehen")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 Kommen", use_container_width=True):
            st.success("Arbeitsbeginn erfasst!")
    with col2:
        if st.button("🔴 Gehen", use_container_width=True):
            st.warning("Arbeitsende erfasst!")

# -----------------------------------------------------------------------------
# 4. App-Startpunkt
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    render_login()
else:
    render_app()
