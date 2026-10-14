import streamlit as st
from supabase import create_client, Client
from datetime import date, datetime
from zoneinfo import ZoneInfo
from modules.mitarbeiter import render_mitarbeiter_verwaltung, ALL_MODULES
from modules.zeiterfassung import render_zeiterfassung
from modules.steuerberater import render_steuerberater_export
from modules.kunden import render_kunden_verwaltung
from modules.fahrzeuge import render_fahrzeug_verwaltung, render_fahrzeug_warnungen_sidebar
from modules.gebaeude import render_gebaeude_verwaltung
from modules.auftraege import render_auftraege_verwaltung
from modules.tv_dashboard import render_tv_dashboard
from modules.lager_verwaltung import render_lager_verwaltung
from modules.rechnungen import render_rechnungen_verwaltung  # <--- NEU HINZUGEFÜGT

st.set_page_config(
    page_title="Elektro-Enterprise Portal", 
    page_icon="⚡", 
    layout="wide"
)

# -----------------------------------------------------------------------------
# 1. Supabase Initialisierung & Zentrale Rechte-Hilfsfunktion
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

def hat_recht(modul_id, aktion="sehen"):
    """Zentrale Prüfung für feingranulare CRUD-Rechte (Sehen, Erstellen, Bearbeiten, Löschen)."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    
    rechte = user.get("rechte", [])
    recht_key = f"{modul_id}_{aktion}"
    return recht_key in rechte

# -----------------------------------------------------------------------------
# Direkter TV-Dashboard Check (?view=tv) - Vor dem Login-Check!
# -----------------------------------------------------------------------------
if st.query_params.get("view") == "tv":
    render_tv_dashboard(supabase)
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_data" not in st.session_state:
    st.session_state["user_data"] = None
if "show_profil" not in st.session_state:
    st.session_state["show_profil"] = False

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
                                f_rechte = rolle_info.get("erlaubte_menues") or [
                                    "1_sehen", "1_erstellen", "1_bearbeiten", "1_loeschen",
                                    "2_sehen", "2_erstellen", "2_bearbeiten", "2_loeschen",
                                    "3_sehen", "3_erstellen", "3_bearbeiten", "3_loeschen",
                                    "4_sehen", "4_erstellen", "4_bearbeiten", "4_loeschen",
                                    "5_sehen", "5_erstellen", "5_bearbeiten", "5_loeschen",
                                    "6_sehen", "6_erstellen", "6_bearbeiten", "6_loeschen",
                                    "7_sehen", "7_erstellen", "7_bearbeiten", "7_loeschen",
                                    "8_sehen", "8_erstellen", "8_loeschen",
                                    "9_sehen", "9_bearbeiten",
                                    "10_sehen", "10_exportieren",
                                    "11_sehen", "11_erstellen", "11_bearbeiten", "11_loeschen"
                                ]

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
                    update_payload = {
                        "vorname": new_vorname,
                        "nachname": new_nachname,
                        "email": new_email,
                        "telefon": new_telefon,
                        "adresse": new_adresse
                    }
                    supabase.table("mitarbeiter").update(update_payload).eq("id", user_id).execute()
                    st.session_state["user_data"]["name"] = f"{new_vorname} {new_nachname}".strip()
                    
                    st.success("✅ Ihre Daten wurden erfolgreich angepasst!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Speichern der Daten: {e}")

    with tab_passwort:
        with st.form("profil_passwort_form"):
            st.markdown("#### Passwort / PIN ändern")
            alt_passwort = st.text_input("Aktuelles Passwort / PIN", type="password")
            neues_passwort = st.text_input("Neues Passwort / PIN", type="password")
            neues_passwort_wwh = st.text_input("Neues Passwort wiederholen", type="password")

            submitted_pw = st.form_submit_button("Passwort jetzt ändern", type="primary", use_container_width=True)

            if submitted_pw:
                if not alt_passwort or not neues_passwort or not neues_passwort_wwh:
                    st.warning("Bitte füllen Sie alle Passwort-Felder aus.")
                elif neues_passwort != neues_passwort_wwh:
                    st.error("Die neuen Passwörter stimmen nicht überein.")
                elif len(neues_passwort) < 4:
                    st.error("Das neue Passwort muss mindestens 4 Zeichen lang sein.")
                else:
                    if str(current_data.get("pin_hash")) == str(alt_passwort):
                        try:
                            supabase.table("mitarbeiter").update({"pin_hash": neues_passwort}).eq("id", user_id).execute()
                            st.success("✅ Passwort erfolgreich angepasst!")
                        except Exception as e:
                            st.error(f"Fehler beim Ändern des Passworts: {e}")
                    else:
                        st.error("Das eingegebene aktuelle Passwort ist falsch.")

# -----------------------------------------------------------------------------
# 4. Hauptanwendung & Routing (Optimierte Sidebar-Anordnung mit Rechte-Check)
# -----------------------------------------------------------------------------
def render_app():
    user = st.session_state.get("user_data")
    if not user:
        st.session_state["authenticated"] = False
        st.rerun()
        return
    
    full_name = user.get("name", "Mitarbeiter")
    vorname = full_name.split()[0] if full_name else "Mitarbeiter"
    user_id = user["id"]

    st.sidebar.title("⚡ Elektro-Portal")
    st.sidebar.markdown(f"### Hallo, {vorname}! 👋")
    st.sidebar.write(f"**{full_name}**")
    st.sidebar.caption(f"Nr: {user.get('mitarbeiternummer', '-')} | Rolle: {user.get('rolle', '-')}")
    
    # --- 1. Schnell-Zeiterfassung ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### ⏱️ Schnell-Zeiterfassung")

    try:
        offen_res = supabase.table("zeiterfassung").select("*").eq("mitarbeiter_id", user_id).is_("ausstempeln", "null").execute()
        offener_eintrag = offen_res.data[0] if offen_res.data else None
    except Exception:
        offener_eintrag = None

    try:
        ma_res = supabase.table("mitarbeiter").select("standard_pause_minuten").eq("id", user_id).execute()
        std_pause = int(ma_res.data[0].get("standard_pause_minuten") or 30) if ma_res.data else 30
    except Exception:
        std_pause = 30

    if not offener_eintrag:
        st.sidebar.markdown("🔴 **Status:** Ausgestempelt")
        if st.sidebar.button("🟢 Einstempeln", use_container_width=True, type="primary"):
            try:
                jetzt = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec='seconds')
                supabase.table("zeiterfassung").insert({
                    "mitarbeiter_id": user_id,
                    "einstempeln": jetzt
                }).execute()
                st.success("Eingestempelt!")
                st.rerun()
            except Exception as e:
                st.error(f"Fehler: {e}")
    else:
        ein_dt_s = datetime.fromisoformat(offener_eintrag['einstempeln'].replace('Z', '+00:00'))
        if ein_dt_s.tzinfo is not None:
            ein_dt_s = ein_dt_s.astimezone(ZoneInfo("Europe/Berlin"))
            
        st.sidebar.markdown(f"🟢 **Status:** Eingestempelt seit {ein_dt_s.strftime('%H:%M')} Uhr")
        
        with st.sidebar.form("sidebar_ausstempeln_form"):
            sb_pause = st.number_input("Pause (Min)", min_value=0, max_value=120, value=std_pause, step=5)
            if st.form_submit_button("🔴 Ausstempeln", use_container_width=True, type="primary"):
                try:
                    jetzt_aus = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec='seconds')
                    supabase.table("zeiterfassung").update({
                        "ausstempeln": jetzt_aus,
                        "pause_minuten": sb_pause
                    }).eq("id", offener_eintrag["id"]).execute()
                    st.success("Ausgestempelt!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler: {e}")

    # --- 2. Hauptmenü / Modulauswahl mit feiner Rechteprüfung ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📂 Hauptmenü")

    extended_modules = {
        "1": "1. Mitarbeiterverwaltung",
        "2": "2. Lagerverwaltung",
        "3": "3. Zeiterfassung",
        "4": "4. Aufträge & Einsätze",
        "5": "5. Kundenverwaltung",
        "6": "6. Fahrzeugflotte",
        "7": "7. Gebäude",
        "8": "8. Dokumente",
        "9": "9. TV-Leitsystem",
        "10": "10. Steuerberater-Export",
        "11": "11. Rechnungen & Abrechnung"  # <--- HIER NEU HINZUGEFÜGT
    }

    # Nur Module anzeigen, für die der User das Recht "sehen" besitzt
    available_menus = {k: v for k, v in extended_modules.items() if hat_recht(k, "sehen")}

    if not available_menus:
        st.sidebar.warning("⚠️ Keine Menürechte zugewiesen.")
        selected_main = None
    else:
        selected_main = st.sidebar.selectbox(
            "Modul auswählen",
            options=list(available_menus.keys()),
            format_func=lambda x: available_menus[x],
            label_visibility="collapsed"
        )

    # --- 3. Flotten- & TÜV-Warnungen ---
    render_fahrzeug_warnungen_sidebar(supabase)

    # --- 4. Unten: Profil-Einstellungen & Abmelden-Button ---
    st.sidebar.markdown("---")
    
    if st.sidebar.button("👤 Mein Profil & Einstellungen", use_container_width=True):
        st.session_state["show_profil"] = True
        st.rerun()

    if st.sidebar.button("🚪 Abmelden", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user_data"] = None
        st.session_state["show_profil"] = False
        st.rerun()

    # --- Routing im Hauptbereich ---
    if st.session_state.get("show_profil", False):
        if st.button("⬅️ Zurück zum Hauptmenü"):
            st.session_state["show_profil"] = False
            st.rerun()
        render_mein_profil(supabase)
    else:
        if selected_main:
            # Schutz vor Direktzugriff, falls Modul nicht gesehen werden darf
            if not hat_recht(selected_main, "sehen"):
                st.error("⛔ Sie haben keine Berechtigung, dieses Modul aufzurufen.")
                return

            if selected_main == "1":
                render_mitarbeiter_verwaltung(supabase)
            elif selected_main == "2":
                render_lager_verwaltung(supabase)
            elif selected_main == "3":
                render_zeiterfassung(supabase)
            elif selected_main == "4":
                render_auftraege_verwaltung(supabase)
            elif selected_main == "5":
                render_kunden_verwaltung(supabase)
            elif selected_main == "6":
                render_fahrzeug_verwaltung(supabase)
            elif selected_main == "7":
                render_gebaeude_verwaltung(supabase)
            elif selected_main == "9":
                render_tv_dashboard(supabase)
            elif selected_main == "10":
                render_steuerberater_export(supabase)
            elif selected_main == "11":
                render_rechnungen_verwaltung(supabase)  # <--- HIER EINGEBUNDEN
            else:
                st.title(available_menus[selected_main])
                st.info("Dieses Modul wird als Nächstes ausgebaut.")

# -----------------------------------------------------------------------------
# Kontrollfluss
# -----------------------------------------------------------------------------
if not st.session_state.get("authenticated", False):
    render_login()
else:
    render_app()
