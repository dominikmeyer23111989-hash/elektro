import streamlit as st
from supabase import create_client, Client
from datetime import date, datetime
from zoneinfo import ZoneInfo
from modules.mitarbeiter import render_mitarbeiter_verwaltung, ALL_MODULES
from modules.zeiterfassung import render_zeiterfassung
from modules.steuerberater import render_steuerberater_export

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
                
                submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)

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
                                f_rechte = rolle_info.get("erlaubte_menues") or ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

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

                btn_reset = st.form_submit_button("Passwort jetzt zurücksetzen", type="primary", use_container_width=True)

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
# 3. Eigene Daten ansehen & bearbeiten (Self-Service Profil)
# -----------------------------------------------------------------------------
def render_mein_profil(supabase):
    st.title("👤 Mein Profil & Einstellungen")
    st.caption("Hier können Sie Ihre persönlichen Stammdaten einsehen und anpassen.")

    user = st.session_state.get("user_data")
    user_id = user["id"]

    try:
        res = supabase.table("mitarbeiter").select("*, rollen(bezeichnung)").eq("id", user_id).execute()
        current_data = res.data[0] if res.data else {}
    except Exception:
        current_data = {}

    st.markdown("### 📋 Ihre aktuellen Stammdaten")
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Mitarbeiternummer", current_data.get("mitarbeiternummer", "-"))
    col_b.metric("Rolle im Betrieb", current_data.get("rollen", {}).get("bezeichnung", "-") if current_data.get("rollen") else "-")
    col_c.metric("Account-Status", "🟢 Aktiv" if current_data.get("ist_aktiv") else "🔴 Inaktiv")

    st.info("💡 **Hinweis:** Ihre Mitarbeiternummer und Ihre betriebliche Rolle können aus Sicherheitsgründen nur von Administratoren geändert werden.")

    st.markdown("---")

    tab_ansicht, tab_daten, tab_passwort = st.tabs(["👁️ Daten anzeigen", "📝 Daten bearbeiten", "🔒 Passwort / PIN ändern"])

    with tab_ansicht:
        st.markdown("#### Ihre hinterlegten Kontaktdaten")
        st.write(f"**Vorname:** {current_data.get('vorname', '-')}")
        st.write(f"**Nachname:** {current_data.get('nachname', '-')}")
        st.write(f"**E-Mail-Adresse:** {current_data.get('email', '-')}")
        st.write(f"**Telefonnummer:** {current_data.get('telefon', '-')}")
        st.write(f"**Anschrift:** {current_data.get('adresse', '-')}")
        st.write(f"**Geburtsdatum:** {current_data.get('geburtsdatum', '-')}")
        st.write(f"**Tätig seit:** {current_data.get('taetig_seit', '-')}")

    with tab_daten:
        with st.form("profil_daten_form"):
            st.markdown("#### Kontaktdaten anpassen")
            
            new_vorname = st.text_input("Vorname", value=current_data.get("vorname", ""))
            new_nachname = st.text_input("Nachname", value=current_data.get("nachname", ""))
            new_email = st.text_input("E-Mail-Adresse", value=current_data.get("email", ""))
            new_telefon = st.text_input("Telefonnummer", value=current_data.get("telefon", ""))
            new_adresse = st.text_area("Anschrift", value=current_data.get("adresse", ""))

            submitted_daten = st.form_submit_button("Änderungen speichern", type="primary", use_container_width=True)

            if submitted_daten:
                try:
                    update_payload =
