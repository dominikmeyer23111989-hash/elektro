import streamlit as st
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

def hat_recht(modul_id, aktion="sehen"):
    """Prüft über die app.py-Logik, ob das Recht vorliegt."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_zeiterfassung(supabase):
    st.title("⏱️ 3. Zeiterfassung & Arbeitszeiten")
    st.caption("Erfassen Sie Ihre Arbeitszeit per Klick. Die Soll-Stunden und individuellen Pausen sind aus Ihrer Personalakte hinterlegt.")

    if not hat_recht("3", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Zeiterfassungs-Modul aufzurufen.")
        return

    user = st.session_state.get("user_data", {})
    user_id = user.get("id")
    
    darf_erstellen = hat_recht("3", "erstellen")
    darf_bearbeiten = hat_recht("3", "bearbeiten")
    is_admin = darf_bearbeiten or (user.get("rolle") in ["Admin", "Bauleiter", "Büro / Verwaltung"])

    # 1. Mitarbeiter-Stammdaten & wochentägliche Soll-Zeiten laden
    try:
        ma_res = supabase.table("mitarbeiter").select("wochenstunden, standard_pause_minuten, vorname, nachname, mitarbeiternummer, soll_mo, soll_di, soll_mi, soll_do, soll_fr").eq("id", user_id).execute()
        ma_data = ma_res.data[0] if ma_res.data else {}
        wochenstunden = float(ma_data.get("wochenstunden", 40.0))
        standard_pause = int(ma_data.get("standard_pause_minuten") or 30)
    except Exception:
        ma_data = {}
        wochenstunden = 40.0
        standard_pause = 30

    # Heutiges Tages-Soll dynamisch nach Wochentag ermitteln (Mo=0, ..., Fr=4)
    heute_wochentag = datetime.now(ZoneInfo("Europe/Berlin")).weekday()
    soll_mapping = {
        0: float(ma_data.get("soll_mo", 8.0)),
        1: float(ma_data.get("soll_di", 8.0)),
        2: float(ma_data.get("soll_mi", 8.0)),
        3: float(ma_data.get("soll_do", 8.0)),
        4: float(ma_data.get("soll_fr", 6.0)),
        5: 0.0,
        6: 0.0
    }
    tages_soll = soll_mapping.get(heute_wochentag, 8.0)

    # 2. Aktuellen Stempel-Status des Users prüfen
    try:
        offen_res = supabase.table("zeiterfassung").select("*").eq("mitarbeiter_id", user_id).is_("ausstempeln", "null").execute()
        offener_eintrag = offen_res.data[0] if offen_res.data else None
    except Exception:
        offener_eintrag = None

    # Oben: Metriken anzeigen
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Wochenstunden (Soll)", f"{wochenstunden} Std.")
    col_m2.metric("Heutiges Tages-Soll", f"{tages_soll:.1f} Std.")
    col_m3.metric("Ihre Standard-Pause", f"{standard_pause} Min.")
    
    if offener_eintrag:
        ein_dt = datetime.fromisoformat(offener_eintrag["einstempeln"].replace('Z', '+00:00'))
        if ein_dt.tzinfo is not None:
            ein_dt = ein_dt.astimezone(ZoneInfo("Europe/Berlin"))
        status_text = f"🟢 Eingestempelt seit {ein_dt.strftime('%H:%M Uhr')}"
    else:
        status_text = "🔴 Ausgestempelt"
        
    col_m4.metric("Aktueller Status", status_text)

    st.markdown("---")

    tab_stempeln, tab_historie, tab_admin = st.tabs([
        "⚡ Zeiterfassung (Stempeluhr)", 
        "📊 Meine Zeitschranken & Auswertung", 
        "⚙️ Alle Mitarbeiter-Zeiten (Admin)" if is_admin else "🔒 Admin-Ansicht (Gesperrt)"
    ])

    # --- TAB 1: Stempeluhr ---
    with tab_stempeln:
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            st.subheader("Stempeluhr")
            if not darf_erstellen:
                st.info("ℹ️ Ihr Account hat nur Leserechte. Sie können sich nicht selbst ein- oder ausstempeln.")
            elif not offener_eintrag:
                st.info("Sie sind aktuell **nicht** eingestempelt.")
                if st.button("🟢 Jetzt Einstempeln", type="primary", use_container_width=True):
                    try:
                        jetzt = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec='seconds')
                        supabase.table("zeiterfassung").insert({
                            "mitarbeiter_id": user_id,
                            "einstempeln": jetzt
                        }).execute()
                        st.success("Erfolgreich eingestempelt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Einstempeln: {e}")
            else:
                ein_dt_s = datetime.fromisoformat(offener_eintrag['einstempeln'].replace('Z', '+00:00'))
                if ein_dt_s.tzinfo is not None:
                    ein_dt_s = ein_dt_s.astimezone(ZoneInfo("Europe/Berlin"))
                
                st.success(f"Eingestempelt um: {ein_dt_s.strftime('%H:%M:%S Uhr')}")
                
                with st.form("ausstempeln_form"):
                    pause = st.number_input("Pause (in Minuten)", min_value=0, max_value=180, value=standard_pause, step=5)
                    notiz = st.text_input("Tätigkeitsnotiz / Baustelle (optional)")
                    
                    if st.form_submit_button("🔴 Jetzt Ausstempeln", type="primary", use_container_width=True):
                        try:
                            jetzt_aus = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec='seconds')
                            supabase.table("zeiterfassung").update({
                                "ausstempeln": jetzt_aus,
                                "pause_minuten": pause,
                                "notiz": notiz
                            }).eq("id", offener_eintrag["id"]).execute()
                            st.success("Erfolgreich ausgestempelt! Schicht wurde gespeichert.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Ausstempeln: {e}")

        with col_s2:
            st.subheader("💡 Hinweise zur Zeiterfassung")
            st.markdown(f"""
            - Ihre **individuelle Standard-Pause** ist auf **{standard_pause} Minuten** eingestellt.
            - Das heutige Tages-Soll beträgt aufgrund Ihres hinterlegten Wochenmodells **{tages_soll:.1f} Stunden**.
            - Sie können den Pausenwert vor dem Ausstempeln jederzeit anpassen.
            """)

    # --- TAB 2: Historie & Ist/Soll-Vergleich ---
    with tab_historie:
        st.subheader("Ihre erfassten Arbeitszeiten")
        try:
            hist_res = supabase.table("zeiterfassung").select("*").eq("mitarbeiter_id", user_id).order("einstempeln", desc=True).execute()
            eintraege = hist_res.data or []
        except Exception:
            eintraege = []

        if eintraege:
            gesamt_ist_stunden = 0.0
            display_data = []
            
            for e in eintraege:
                ein = datetime.fromisoformat(e["einstempeln"].replace('Z', '+00:00'))
                if ein.tzinfo is not None:
                    ein = ein.astimezone(ZoneInfo("Europe/Berlin"))
                
                aus_str = e.get("ausstempeln")
                
                if aus_str:
                    aus = datetime.fromisoformat(aus_str.replace('Z', '+00:00'))
                    if aus.tzinfo is not None:
                        aus = aus.astimezone(ZoneInfo("Europe/Berlin"))
                        
                    dauer_sec = (aus - ein).total_seconds() - (e.get("pause_minuten", 0) * 60)
                    netto_stunden = max(0.0, dauer_sec / 3600.0)
                    gesamt_ist_stunden += netto_stunden
                    status_str = "Beendet"
                    aus_anzeige = aus.strftime("%d.%m.%Y %H:%M")
                else:
                    netto_stunden = 0.0
                    status_str = "🟢 Läuft aktiv..."
                    aus_anzeige = "-"

                display_data.append({
                    "Datum": ein.strftime("%d.%m.%Y"),
                    "Einstempeln": ein.strftime("%H:%M"),
                    "Ausstempeln": aus_anzeige,
                    "Pause (Min)": e.get("pause_minuten", 0),
                    "Netto Stunden": round(netto_stunden, 2),
                    "Notiz": e.get("notiz", "-"),
                    "Status": status_str
                })

            st.metric("Gesamte erfasste Netto-Stunden (Historie)", f"{round(gesamt_ist_stunden, 2)} Std.")
            st.markdown("---")
            st.dataframe(pd.DataFrame(display_data), use_container_width=True)
        else:
            st.info("Bislang noch keine Zeiteinträge vorhanden.")

    # --- TAB 3: Admin-Ansicht ---
    with tab_admin:
        if is_admin:
            st.subheader("Übersicht aller Mitarbeiter-Zeiten")
            try:
                all_hist = supabase.table("zeiterfassung").select("*, mitarbeiter(vorname, nachname, mitarbeiternummer)").order("einstempeln", desc=True).limit(100).execute()
                all_data = all_hist.data or []
            except Exception:
                all_data = []

            if all_data:
                admin_display = []
                for e in all_data:
                    ma = e.get("mitarbeiter") or {}
                    ein = datetime.fromisoformat(e["einstempeln"].replace('Z', '+00:00'))
                    if ein.tzinfo is not None:
                        ein = ein.astimezone(ZoneInfo("Europe/Berlin"))
                        
                    aus_str = e.get("ausstempeln")
                    netto_stunden = 0.0
                    
                    if aus_str:
                        aus = datetime.fromisoformat(aus_str.replace('Z', '+00:00'))
                        if aus.tzinfo is not None:
                            aus = aus.astimezone(ZoneInfo("Europe/Berlin"))
                            
                        netto_stunden = max(0.0, ((aus - ein).total_seconds() - (e.get("pause_minuten", 0) * 60)) / 3600.0)
                        aus_anzeige = aus.strftime("%d.%m.%Y %H:%M")
                    else:
                        aus_anzeige = "Aktiv"

                    admin_display.append({
                        "Mitarbeiter": f"{ma.get('vorname', '')} {ma.get('nachname', '')} (Nr: {ma.get('mitarbeiternummer', '-')})",
                        "Datum": ein.strftime("%d.%m.%Y"),
                        "Von": ein.strftime("%H:%M"),
                        "Bis": aus_anzeige,
                        "Pause": f"{e.get('pause_minuten', 0)}m",
                        "Netto Std.": round(netto_stunden, 2),
                        "Notiz": e.get("notiz", "-")
                    })
                st.dataframe(pd.DataFrame(admin_display), use_container_width=True)
            else:
                st.info("Keine Zeiteinträge im System.")
