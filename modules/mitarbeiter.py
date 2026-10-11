# --- TAB 4: Urlaub & Anträge (Integriert mit Ampelsystem, Kontingent & Benachrichtigung) ---
    with tab_urlaub:
        st.subheader("🏖️ Urlaubs- & Abwesenheitsanträge")

        # 1. Prüfen, ob offene Anträge existieren (für Benachrichtigungen)
        try:
            all_antraege_res = supabase.table("antraege").select("*, mitarbeiter(vorname, nachname, mitarbeiternummer)").execute()
            all_antraege = all_antraege_res.data or []
        except Exception:
            all_antraege = []

        offene_antraege = [a for a in all_antraege if a.get("status") == "in_bearbeitung"]
        anzahl_offen = len(offene_antraege)

        # Benachrichtigungs-Banner für Admins / Vorgesetzte
        if is_admin and anzahl_offen > 0:
            st.warning(f"🔔 **Benachrichtigung:** Es gibt **{anzahl_offen} neue/offene Anträge**, die auf Ihre Prüfung warten!")

        # Urlaubsanspruch des eingeloggten Benutzers laden
        try:
            ma_res = supabase.table("mitarbeiter").select("urlaubstage_gesamt").eq("id", user_id).execute()
            gesamt_urlaub = ma_res.data[0].get("urlaubstage_gesamt", 30) if ma_res.data else 30
        except Exception:
            gesamt_urlaub = 30

        current_year = date.today().year
        try:
            user_antraege = [a for a in all_antraege if a.get("mitarbeiter_id") == user_id]
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

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Urlaubsanspruch gesamt", f"{gesamt_urlaub} Tage")
        col_m2.metric("Bereits beantragt / genommen", f"{berechnete_tage} Tage")
        col_m3.metric("Verbleibende Urlaubstage", f"{rest_urlaub} Tage", delta=f"{rest_urlaub} übrig")

        st.markdown("---")

        sub_tab_neu, sub_tab_meine, sub_tab_admin = st.tabs([
            "➕ Neuen Antrag stellen", 
            "📄 Meine Anträge", 
            f"⚙️ Anträge prüfen ({anzahl_offen} offen)" if is_admin else "🔒 Admin-Ansicht (Gesperrt)"
        ])

        with sub_tab_neu:
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
                            supabase.table("antraege").insert({
                                "mitarbeiter_id": user_id,
                                "art": art,
                                "start_datum": str(start_datum),
                                "end_datum": str(end_datum),
                                "details": grund,
                                "status": "in_bearbeitung"
                            }).execute()
                            st.success("Antrag erfolgreich eingereicht! Vorgesetzte wurden benachrichtigt (Status: 🟡 In Bearbeitung).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

        with sub_tab_meine:
            if user_antraege:
                for a in user_antraege:
                    status = a.get("status")
                    badge = "🟢 Genehmigt" if status == "genehmigt" else ("🔴 Abgelehnt" if status == "abgelehnt" else "🟡 In Bearbeitung")
                    with st.expander(f"{badge} | {a.get('art')} vom {a.get('start_datum')} bis {a.get('end_datum')}"):
                        st.write(f"**Details:** {a.get('details', '-')}")
                        if status == "abgelehnt" and a.get("ablehnungsgrund"):
                            st.error(f"**Ablehnungsgrund:** {a.get('ablehnungsgrund')}")
            else:
                st.info("Keine Anträge vorhanden.")

        with sub_tab_admin:
            if is_admin:
                if all_antraege:
                    for a in all_antraege:
                        ma = a.get("mitarbeiter") or {}
                        ma_name = f"{ma.get('vorname', '')} {ma.get('nachname', '')} (Nr: {ma.get('mitarbeiternummer', '-')})"
                        status = a.get("status")
                        badge = "🟢 Genehmigt" if status == "genehmigt" else ("🔴 Abgelehnt" if status == "abgelehnt" else "🟡 In Bearbeitung")

                        with st.expander(f"{badge} | {ma_name} - {a.get('art')} ({a.get('start_datum')} bis {a.get('end_datum')})"):
                            st.write(f"**Grund:** {a.get('details', '-')}")
                            with st.form(f"admin_antrag_{a['id']}"):
                                neu_status = st.selectbox("Status", ["in_bearbeitung", "genehmigt", "abgelehnt"], index=["in_bearbeitung", "genehmigt", "abgelehnt"].index(status))
                                ablehnung_grund = st.text_input("Ablehnungsgrund (bei Rot erforderlich)", value=a.get("ablehnungsgrund", ""))
                                if st.form_submit_button("Status speichern", type="primary"):
                                    supabase.table("antraege").update({
                                        "status": neu_status,
                                        "ablehnungsgrund": ablehnung_grund if neu_status == "abgelehnt" else ""
                                    }).eq("id", a["id"]).execute()
                                    st.success("Antrag aktualisiert!")
                                    st.rerun()
                else:
                    st.info("Keine Anträge im System.")
