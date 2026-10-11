import streamlit as st
from supabase import create_client, Client
from datetime import date
from modules.mitarbeiter import render_mitarbeiter_verwaltung, ALL_MODULES

st.set_page_config(
    page_title="Elektro-Enterprise Portal", 
    page_icon="⚡", 
    layout="wide"
)

# -----------------------------------------------------------------------------
# 1. Supabase Initialisierung
# -----------------------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
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

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_data" not in st.session_state:
    st.session_state["user_data"] = None

# -----------------------------------------------------------------------------
# 2. Login- & Passwort-Wiederherstellungs-System
# -----------------------------------------------------------------------------
def render_login():
    st.title("⚡ Elektro-Enterprise System")
    st.caption("Willkommen! Bitte melden Sie sich an.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_reset = st.tabs(["🔑 Login", "🆘 Passwort vergessen"])

        # --- TAB 1: Login ---
        with tab_login:
            with st.form("login_form"):
                identifier = st.text_input("Mitarbeiternummer oder Vorname.Nachname", placeholder="z. B. 1000")
                password = st.text_input("Passwort / PIN", type="password")
                
                submitted = st.form_submit_button("Anmelden", type="primary", width="stretch")

                if submitted:
                    if not identifier or not password:
                        st.warning("Bitte füllen Sie alle Felder aus.")
                    else:
                        try:
                            res = supabase.table("mitarbeiter").select("*, rollen(*)").eq("ist_aktiv", True).eq("mitarbeiternummer", identifier).execute()
                            
                            if not res.data and "." in identifier:
                                parts = identifier.split(".", 1)
                                res = supabase.table("mitarbeiter").select("*, rollen(*)").eq("ist_aktiv", True).ilike("vorname", parts[0]).ilike("nachname", parts[1]).execute()

                            if not res.data:
                                st.error("Mitarbeiter nicht gefunden oder Konto inaktiv.")
                                return
                            
                            user_rec = res.data[0]
                            if str(user_rec.get("pin_hash")) == str(password):
                                rolle_info = user_rec.get("rollen") or {}
                                f_rolle = rolle_info.get("bezeichnung", "Admin")
                                f_ebene = rolle_info.get("ebene", "buero")
                                f_rechte = rolle_info.get("erlaubte_menues") or ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

                                st.session_state["authenticated"] = True
                                st.session_state["user_data"] = {
                                    "id": user_rec["id"],
                                    "mitarbeiternummer": user_rec.get("mitarbeiternummer", "-"),
                                    "name": f"{user_rec.get('vorname', '')} {user_rec.get('nachname', '')}".strip(),
                                    "rolle": f_rolle,
                                    "ebene": f_ebene,
                                    "rechte": f_rechte
                                }
                                st.success("Erfolgreich angemeldet!")
                                st.rerun()
                            else:
                                st.error("Ungültiges Passwort.")
                        except Exception as e:
                            st.error(f"Login-Fehler: {e}")

        # --- TAB 2: Autonomes Passwort-Zurücksetzen ---
        with tab_reset:
            st.markdown("##### Self-Service Wiederherstellung")
            st.caption("Setzen Sie Ihr Passwort direkt über Ihre Notfall-PIN oder Ihren Recovery-Code zurück.")

            with st.form("reset_form"):
                reset_ma_nr = st.text_input("Mitarbeiternummer *", placeholder="z. B. 1000")
                method = st.radio("Verifizierungsmethode", ["Notfall-PIN & Geburtsdatum", "Master-Recovery-Code"])
                
                if method == "Notfall-PIN & Geburtsdatum":
                    geburtsdatum = st.date_input("Geburtsdatum zur Verifizierung", value=date(1990, 1, 1), format="DD.MM.YYYY")
                    notfall_pin = st.text_input("Ihre 4-stellige Notfall-PIN", type="password")
                    secret_check = str(notfall_pin)
                else:
                    recovery_code = st.text_input("Master-Recovery-Code", placeholder="z. B. REC-1000-88")
                    secret_check = str(recovery_code)

                st.markdown("---")
                new_pw = st.text_input("Neues Passwort vergeben *", type="password")
                new_pw_confirm = st.text_input("Neues Passwort wiederholen *", type="password")

                btn_reset = st.form_submit_button("Passwort jetzt zurücksetzen", type="primary", width="stretch")

                if btn_reset:
                    if not reset_ma_nr or not new_pw or not secret_check:
                        st.warning("Bitte füllen Sie alle erforderlichen Felder aus.")
                    elif new_pw != new_pw_confirm:
                        st.error("Die eingegebenen Passwörter stimmen nicht überein.")
                    elif len(new_pw) < 4:
                        st.error("Das neue Passwort muss mindestens 4 Zeichen lang sein.")
                    else:
                        try:
                            res = supabase.table("mitarbeiter").select("*").eq("mitarbeiternummer", reset_ma_nr).eq("ist_aktiv", True).execute()
                            if not res.data:
                                st.error("Mitarbeiternummer ungültig.")
                                return
                            
                            ma_rec = res.data[0]
                            verified = False

                            if method == "Notfall-PIN & Geburtsdatum":
                                ma_geb = str(ma_rec.get("geburtsdatum", ""))
                                ma_pin = str(ma_rec.get("notfall_pin", ""))
                                if ma_geb == str(geburtsdatum) and ma_pin == notfall_pin and notfall_pin != "":
                                    verified = True
                            else:
                                ma_code = str(ma_rec.get("recovery_code", ""))
                                if ma_code == recovery_code and recovery_code != "":
                                    verified = True

                            if verified:
                                supabase.table("mitarbeiter").update({"pin_hash": new_pw}).eq("id", ma_rec["id"]).execute()
                                st.success("Ihr Passwort wurde erfolgreich geändert! Sie können sich jetzt anmelden.")
                            else:
                                st.error("Verifizierung fehlgeschlagen: Sicherheitsdaten falsch.")

                        except Exception as e:
                            st.error(f"Fehler beim Zurücksetzen: {e}")

# -----------------------------------------------------------------------------
# 3. Hauptanwendung & Routing
# -----------------------------------------------------------------------------
def render_app():
    user = st.session_state.get("user_data")
    if not user:
        st.session_state["authenticated"] = False
        st.rerun()
        return
    
    # Vorname extrahieren für persönliche Begrüßung
    full_name = user.get("name", "Mitarbeiter")
    vorname = full_name.split()[0] if full_name else "Mitarbeiter"

    st.sidebar.title("⚡ Elektro-Portal")
    st.sidebar.markdown(f"### Hallo, {vorname}! 👋")
    st.sidebar.write(f"**{full_name}**")
    st.sidebar.caption(f"Nr: {user.get('mitarbeiternummer', '-')} | Rolle: {user.get('rolle', '-')}")
    
    if st.sidebar.button("🚪 Abmelden", width="stretch"):
        st.session_state["authenticated"] = False
        st.session_state["user_data"] = None
        st.rerun()

    st.sidebar.markdown("---")

    # Menürechte auswerten
    allowed_menu_keys = user.get("rechte", [])
    available_menus = {k: v for k, v in ALL_MODULES.items() if k in allowed_menu_keys}

    if not available_menus:
        st.warning("Keine zugewiesenen Menürechte gefunden.")
        return

    selected_main = st.sidebar.selectbox(
        "Hauptmenü",
        options=list(available_menus.keys()),
        format_func=lambda x: available_menus[x]["title"]
    )

    # --- ROUTING DER MODULE ---
    if selected_main:
        if selected_main == "1":
            render_mitarbeiter_verwaltung(supabase)
        else:
            st.title(available_menus[selected_main]["title"])
            st.info("Dieses Modul wird als Nächstes ausgebaut.")

# -----------------------------------------------------------------------------
# Kontrollfluss
# -----------------------------------------------------------------------------
if not st.session_state.get("authenticated", False):
    render_login()
else:
    render_app()
