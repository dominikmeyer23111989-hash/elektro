import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from zoneinfo import ZoneInfo

def format_de_zeit(iso_string):
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo("Europe/Berlin"))
        return dt.strftime('%d.%m.%Y - %H:%M Uhr')
    except Exception:
        return str(iso_string)[:16]

def render_tv_dashboard(supabase):
    # Prüfen, ob wir uns im reinen TV-Modus (?view=tv) befinden
    is_tv_mode = st.query_params.get("view") == "tv"

    # Wenn wir im normalen Portal-Modus sind (nicht TV): Konfiguration & Link-Anzeige
    if not is_tv_mode:
        st.title("🖥️ TV- & Monitor-Leitsystem (Dashboard)")
        st.caption("Konfigurieren Sie hier die Ansicht für Ihren zweiten Monitor oder den Werkstatt-Fernseher.")

        # Konfiguration im Hauptbereich statt Sidebar
        with st.expander("⚙️ Dashboard-Einstellungen anpassen", expanded=True):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                selected_statuses = st.multiselect(
                    "Anzuzeigende Auftrags-Status",
                    options=["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"],
                    default=["Offener Auftrag", "In Bearbeitung"],
                    key="cfg_status"
                )
                refresh_sec = st.slider("Aktualisierungs-Intervall (Sekunden)", min_value=10, max_value=120, value=30, step=5, key="cfg_refresh")
            
            with col_e2:
                show_fz = st.checkbox("🚐 Zugewiesenes Fahrzeug anzeigen", value=True, key="cfg_fz")
                show_tm = st.checkbox("👷 Einsatz-Team anzeigen", value=True, key="cfg_tm")
                show_arb = st.checkbox("⚡ Auszuführende Arbeiten anzeigen", value=True, key="cfg_arb")

        # Konfiguration in Session State speichern, damit das Dashboard darauf zugreifen kann
        st.session_state["tv_config"] = {
            "status_filter": selected_statuses,
            "show_fahrzeug": show_fz,
            "show_team": show_tm,
            "show_arbeiten": show_arb,
            "refresh_sekunden": refresh_sec
        }

        st.markdown("---")
        st.subheader("📺 Schnellstart für externe Bildschirme")
        
        # Aktuelle URL ermitteln (Fallback auf Standard, falls Streamlit Cloud URL)
        current_url = "https://elektro-kmcdkbpue9vbok3q4vnurj.streamlit.app/?view=tv"
        
        st.info(f"💡 **Merkhilfe für den Fernseher:** Tippen Sie im Browser Ihres Smart-TVs oder des zweiten Geräts folgende Adresse ein:\n\n`{current_url}`")

        # Button zum Öffnen in einem neuen Fenster für den zweiten Monitor am PC
        tv_url_path = "/?view=tv"
        components.html(f"""
            <div style="margin-top: 10px;">
                <a href="{tv_url_path}" target="_blank" style="background-color: #FF4B4B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-family: sans-serif; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
                    🖥️ Dashboard in neuem Fenster öffnen (für 2. Monitor)
                </a>
            </div>
        """, height=60)

        st.markdown("### 👀 Live-Vorschau (Aktuelle Ansicht)")
        st.markdown("---")

    # Konfiguration laden (mit Standardwerten falls direkt aufgerufen)
    cfg = st.session_state.get("tv_config", {
        "status_filter": ["Offener Auftrag", "In Bearbeitung"],
        "show_fahrzeug": True,
        "show_team": True,
        "show_arbeiten": True,
        "refresh_sekunden": 30
    })

    # Das eigentliche Live-Leitsystem (läuft im TV-Modus oder als Vorschau im Portal)
    @st.fragment(run_every=cfg["refresh_sekunden"])
    def render_live_content():
        st.markdown("""
            <style>
                .tv-header { font-size: 2.8rem; font-weight: bold; color: #FF4B4B; text-align: center; margin-bottom: 5px; }
                .tv-sub { font-size: 1.2rem; text-align: center; color: #A0A0A0; margin-bottom: 25px; }
                .order-card { background-color: #161A22; padding: 22px; border-radius: 12px; margin-bottom: 20px; border-left: 8px solid #FF4B4B; color: #FFFFFF; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
                .order-in-prog { border-left-color: #FFA500 !important; }
                .order-done { border-left-color: #00CC66 !important; }
                .order-title { font-size: 1.6rem; font-weight: bold; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
                .order-detail { font-size: 1.2rem; margin-bottom: 8px; }
                .badge-offen { background-color: #FF4B4B; color: white; padding: 4px 10px; border-radius: 6px; font-size: 1rem; }
                .badge-prog { background-color: #FFA500; color: white; padding: 4px 10px; border-radius: 6px; font-size: 1rem; }
                .badge-done { background-color: #00CC66; color: white; padding: 4px 10px; border-radius: 6px; font-size: 1rem; }
            </style>
        """, unsafe_allow_html=True)

        if is_tv_mode:
            st.markdown('<div class="tv-header">⚡ ELEKTRO-ENTERPRISE — Live-Leitsystem</div>', unsafe_allow_html=True)
        
        current_time = datetime.now(ZoneInfo("Europe/Berlin")).strftime('%d.%m.%Y, %H:%M:%S Uhr')
        st.markdown(f'<div class="tv-sub">Einsatzübersicht | Letzte Aktualisierung: {current_time} (Auto-Refresh alle {cfg["refresh_sekunden"]} Sek.)</div>', unsafe_allow_html=True)
        st.markdown("---")

        selected_statuses = cfg["status_filter"]
        if not selected_statuses:
            st.warning("Keine Status-Filter ausgewählt.")
            return

        try:
            res = supabase.table("auftraege").select("*, kunden(*), gebaeude(*), fahrzeuge(*)").in_("status", selected_statuses).order("termin_um").execute()
            auftraege = res.data or []
        except Exception as e:
            st.error(f"Fehler beim Laden der Live-Daten: {e}")
            auftraege = []

        if not auftraege:
            st.markdown("<h2 style='text-align: center; color: #808080; margin-top: 50px;'>🎉 Aktuell sind keine Aufträge mit diesen Filtern vorhanden.</h2>", unsafe_allow_html=True)
            return

        col1, col2 = st.columns(2)

        for idx, a in enumerate(auftraege):
            target_col = col1 if idx % 2 == 0 else col2
            
            try:
                team_res = supabase.table("auftrag_mitarbeiter").select("mitarbeiter(vorname, nachname)").eq("auftrag_id", a["id"]).execute()
                team_names = ", ".join([f"{t['mitarbeiter']['vorname']} {t['mitarbeiter']['nachname']}" for t in team_res.data if t.get("mitarbeiter")])
            except Exception:
                team_names = "Nicht zugewiesen"

            kunde = a.get("kunden") or {}
            gebaeude = a.get("gebaeude") or {}
            fahrzeug = a.get("fahrzeuge") or {}

            k_name = f"{kunde.get('vorname', '')} {kunde.get('nachname', '')}".strip() or a.get("freitext_kunde") or "Spontankunde"
            g_adr = f"{gebaeude.get('strasse', '')} {gebaeude.get('hausnummer', '')}, {gebaeude.get('ort', '')}" if gebaeude else a.get("freitext_ort") or "Keine Objektadresse"
            
            f_marke = fahrzeug.get('marke') or fahrzeug.get('titel') or ''
            f_kennz = fahrzeug.get('kennzeichen') or ''
            f_info = f"{f_marke} ({f_kennz})" if f_kennz else (f_marke or "Kein Fahrzeug")
            
            status = a.get("status")
            if status == "In Bearbeitung":
                card_class = "order-card order-in-prog"
                badge = '<span class="badge-prog">🟡 In Bearbeitung</span>'
            elif status == "Erledigt":
                card_class = "order-card order-done"
                badge = '<span class="badge-done">🟢 Erledigt</span>'
            else:
                card_class = "order-card"
                badge = '<span class="badge-offen">🔴 Offener Auftrag</span>'

            arbeiten_html = f'<div class="order-detail"><b>⚡ Arbeiten:</b> {a.get("arbeiten")}</div>' if cfg["show_arbeiten"] else ""
            team_html = f'<div class="order-detail"><b>👷 Team:</b> {team_names}</div>' if cfg["show_team"] else ""
            fahrzeug_html = f'<div class="order-detail"><b>🚐 Fahrzeug:</b> {f_info}</div>' if cfg["show_fahrzeug"] else ""

            with target_col:
                st.markdown(f"""
                    <div class="{card_class}">
                        <div class="order-title">
                            <span>#{a.get('auftragsnummer')}</span>
                            <span>{badge}</span>
                        </div>
                        <div class="order-detail"><b>👤 Kunde:</b> {k_name}</div>
                        <div class="order-detail"><b>📍 Objekt:</b> {g_adr}</div>
                        {arbeiten_html}
                        <div class="order-detail"><b>🕒 Termin:</b> {format_de_zeit(a.get('termin_um'))}</div>
                        {team_html}
                        {fahrzeug_html}
                    </div>
                """, unsafe_allow_html=True)

    render_live_content()
