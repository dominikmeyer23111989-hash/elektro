import streamlit as st
from modules.db import supabase

def render_login():
    st.title("⚡ Elektro-Enterprise System")
    st.caption("Bitte melden Sie sich mit Ihren Zugangsdaten an.")

    with st.form("login_form", clear_on_submit=False):
        identifier = st.text_input("Mitarbeiternummer oder Vorname.Nachname", placeholder="z.B. 1004 oder max.mustermann")
        password = st.text_input("Passwort / PIN", type="password")
        
        submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)

        if submitted:
            if not identifier or not password:
                st.warning("Bitte füllen Sie beide Felder aus.")
                return

            try:
                # 1. Mitarbeiter anhand von Mitarbeiternummer oder Vorname.Nachname suchen
                # In Produktion: Abfrage über Supabase-DB
                # res = supabase.table("mitarbeiter").select("*, rollen(*)").or_(f"mitarbeiternummer.eq.{identifier},login_name.eq.{identifier}").execute()

                # Dummy-Authentifizierung / Platzhalter zur Demonstration:
                st.session_state.authenticated = True
                st.session_state.user_data = {
                    "id": "demo-uuid",
                    "name": "Dominik Meyer",
                    "mitarbeiternummer": identifier,
                    "rolle": "Admin",
                    "ebene": "buero",
                    "rechte": ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
                }
                st.success("Erfolgreich angemeldet!")
                st.rerun()

            except Exception as e:
                st.error(f"Anmeldung fehlgeschlagen: {e}")

    # Hinweis für vergessenes Passwort (DSGVO-konform ohne E-Mail)
    st.info("💡 **Passwort oder PIN vergessen?** Bitte wenden Sie sich an die Administrator-Ebene / Ihr Büro, um Ihre Zugangsdaten zurückzusetzen.")
