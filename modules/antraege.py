import streamlit as st
from datetime import date
import pandas as pd

def render_antraege_modul(supabase):
    st.title("📋 4. Anträge & Urlaub")
    st.caption("Verwalten Sie Urlaubs- und Abwesenheitsanträge mit automatischer Kontingentprüfung.")

    user = st.session_state.get("user_data")
    user_id = user["id"]
    is_admin = user.get("rolle") in ["Admin", "Bauleiter", "Büro / Verwaltung"]

    # 1. Mitarbeiterdaten für Urlaubsanspruch laden
    try:
        ma_res = supabase.table("mitarbeiter").select("urlaubstage_gesamt").eq("id", user_id).execute()
        gesamt_urlaub = ma_res.data[0].get("urlaubstage_gesamt", 30) if ma_res.data else 30
    except Exception:
        gesamt_urlaub = 30

    # Bisher genommene / beantragte Urlaubstage in diesem Jahr berechnen
    current_year = date.today().year
    try:
        antraege_res = supabase.table("antraege").select("*").eq("mitarbeiter_id", user_id).execute()
        user_antraege = antraege_res.data or []
    except Exception:
        user_antraege = []

    berechnete_tage = 0
    for a in user_antraege:
        if a.get("art") == "Urlaub" and a.get("status") in ["genehmigt", "in_bearbeitung"]:
            try:
                start = date.fromisoformat(a.get("start_datum"))
                ende = date.fromisoformat(a.get("end_datum"))
                if start.year == current_year:
                    berechnete_tage += (ende - start).days + 1
            except Exception:
                pass

    rest_urlaub = max(0, gesamt_urlaub - berechnete_tage)

    # Oben: Metriken anzeigen
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Urlaubsanspruch gesamt", f"{gesamt_urlaub} Tage")
    col_m2.metric("Bereits beantragt / genommen", f"{berechnete_tage} Tage")
    col_m3.metric("Verbleibende Urlaubstage", f"{rest_urlaub} Tage", delta=f"{rest_urlaub} übrig")

    st.markdown("---")

    tab_neu, tab_meine, tab_admin = st.tabs([
        "➕ Neuen Antrag stellen", 
        "📄 Meine Anträge", 
        "⚙️ Alle Anträge verwalten (Admin)" if is_admin else "🔒 Antragsprüfung (Gesperrt)"
    ])

    # --- TAB 1: Antrag stellen ---
    with tab_neu:
        st.subheader("Urlaubs- oder Abwesenheitsantrag einreichen")
        
        with st.form("neuer_antrag_form"):
            art = st.selectbox("Art des Antrags", ["Urlaub", "Sonderurlaub", "Krankheitstag (Nachmeldung)", "Fortbildung", "Sonstiges"])
            col_d1, col_d2 = st.columns(2)
            start_datum = col_d1.date_input("Von Datum", value=date.today(), format="DD.MM.YYYY")
            end_datum = col_d2.date_input("Bis Datum", value=date.today(), format="DD.MM.YYYY")
            
            grund = st.text_area("Grund / Bemerkung (optional)")
            
            if st.form_submit_button("Antrag abschicken", type="primary", use_container_width=True):
                if start_datum > end_datum:
                    st.error("Das Startdatum kann nicht nach dem Enddatum liegen.")
                else:
                    try:
                        payload = {
                            "mitarbeiter_id": user_id,
                            "art": art,
                            "start_datum": str(start_datum),
                            "end_datum": str(end_datum),
                            "details": grund,
                            "status": "in_bearbeitung"
                        }
                        supabase.table("antraege").insert(payload).execute()
                        st.success("Antrag erfolgreich eingereicht! Status: 🟡 In Bearbeitung")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Einreichen: {e}")

    # --- TAB 2: Meine Anträge ---
    with tab_meine:
        st.subheader("Übersicht Ihrer Anträge")
        if user_antraege:
            for a in user_antraege:
                status = a.get("status")
                if status == "genehmigt":
                    status_badge = "🟢 Genehmigt"
                elif status == "abgelehnt":
                    status_badge = "🔴 Abgelehnt"
                else:
                    status_badge = "🟡 In Bearbeitung"

                with st.expander(f"{status_badge} | {a.get('art')} vom {a.get('start_datum')} bis {a.get('end_datum')}"):
                    st.write(f"**Details / Grund:** {a.get('details', '-')}")
                    if status == "abgelehnt" and a.get("ablehnungsgrund"):
                        st.error(f"**Ablehnungsgrund durch Vorgesetzte:** {a.get('ablehnungsgrund')}")
        else:
            st.info("Sie haben noch keine Anträge gestellt.")

    # --- TAB 3: Admin-Verwaltung ---
    with tab_admin:
        if not is_admin:
            st.warning("Sie haben keine Berechtigung, Anträge zu verwalten.")
        else:
            st.subheader("Alle eingereichten Anträge im Betrieb")
            try:
                all_res = supabase.table("antraege").select("*, mitarbeiter(vorname, nachname, mitarbeiternummer)").execute()
                all_antraege = all_res.data or []
            except Exception:
                all_antraege = []

            if all_antraege:
                for a in all_antraege:
                    ma_info = a.get("mitarbeiter") or {}
                    ma_name = f"{ma_info.get('vorname', '')} {ma_info.get('nachname', '')} (Nr: {ma_info.get('mitarbeiternummer', '-')})"
                    status = a.get("status")

                    if status == "genehmigt":
                        badge = "🟢 Genehmigt"
                    elif status == "abgelehnt":
                        badge = "🔴 Abgelehnt"
                    else:
                        badge = "🟡 In Bearbeitung"

                    with st.expander(f"{badge} | Antrag von {ma_name} ({a.get('art')}: {a.get('start_datum')} bis {a.get('end_datum')})"):
                        st.write(f"**Grund des Mitarbeiters:** {a.get('details', '-')}")
                        
                        with st.form(f"admin_antrag_{a['id']}"):
                            neu_status = st.selectbox(
                                "Status festlegen", 
                                ["in_bearbeitung", "genehmigt", "abgelehnt"],
                                index=0 if status == "in_bearbeitung" else (1 if status == "genehmigt" else 2)
                            )
                            ablehnung_grund = st.text_input("Ablehnungsgrund (nur bei Ablehnung erforderlich)", value=a.get("ablehnungsgrund", ""))

                            if st.form_submit_button("Antragsstatus speichern", type="primary"):
                                try:
                                    supabase.table("antraege").update({
                                        "status": neu_status,
                                        "ablehnungsgrund": ablehnung_grund if neu_status == "abgelehnt" else ""
                                    }).eq("id", a["id"]).execute()
                                    st.success("Antrag aktualisiert!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler: {e}")
            else:
                st.info("Keine Anträge im System vorhanden.")
