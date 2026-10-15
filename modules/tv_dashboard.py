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

def hat_recht(modul_id, aktion="sehen"):
    """Prüft über die app.py-Logik, ob das Recht vorliegt."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_tv_dashboard(supabase):
    # Prüfen, ob wir uns im reinen TV-Modus (?view=tv) befinden
    is_tv_mode = st.query_params.get("view") == "tv"

    # Im normalen Portal-Modus prüfen wir das Recht "9_sehen"
    if not is_tv_mode:
        if not hat_recht("9", "sehen"):
            st.error("⛔ Sie haben keine Berechtigung, das TV-Leitsystem aufzurufen.")
            return

        st.title("🖥️ TV- & Monitor-Leitsystem (Dashboard)")
        st.caption("Konfigurieren Sie hier die Ansicht für Ihren zweiten Monitor oder den Werkstatt-Fernseher.")

        darf_bearbeiten = hat_recht("9", "bearbeiten")
        if not darf_bearbeiten:
            st.info("ℹ️ Ihr Account hat nur Leserechte für dieses Modul. Die Einstellungen können nur von Administratoren geändert werden.")

        # Konfiguration im Hauptbereich statt Sidebar
        with st.expander("⚙️ Dashboard-Einstellungen anpassen", expanded=True):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                selected_statuses = st.multiselect(
                    "Anzuzeigende Auftrags-Status",
                    options=["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"],
                    default=["Offener Auftrag", "In Bearbeitung"],
                    key="cfg_status",
                    disabled=not darf_bearbeiten
                )
                refresh_sec = st.slider("Aktualisierungs-Intervall (Sekunden)", min_value=10, max_value=120, value=30, step=5, key="cfg_refresh", disabled=not darf_bearbeiten)
            
            with col_e2:
                show_fz = st.checkbox("🚐 Zugewiesenes Fahrzeug anzeigen", value=True, key="cfg_fz", disabled=not darf_bearbeiten)
                show_tm = st.checkbox("👷 Einsatz-Team anzeigen", value=True, key="cfg_tm", disabled=not darf_bearbeiten)
                show_arb = st.checkbox("⚡ Auszuführende Arbeiten anzeigen", value=True, key="cfg_arb", disabled=not darf_bearbeiten)
                show_rech = st.checkbox("💶 Offene Rechnungen anzeigen", value=True, key="cfg_rech", disabled=not darf_bearbeiten)
                show_lager = st.checkbox("📦 Lager-Bestandswarnungen anzeigen", value=True, key="cfg_lager", disabled=not darf_bearbeiten)

        # Konfiguration in Session State speichern
        st.session_state["tv_config"] = {
            "status_filter": selected_statuses,
            "show_fahrzeug": show_fz,
            "show_team": show_tm,
            "show_arbeiten": show_arb,
            "show_rechnungen": show_rech,
            "show_lager": show_lager,
            "refresh_sekunden": refresh_sec
        }

        st.markdown("---")
        st.subheader("📺 Schnellstart für externe Bildschirme")
        
        current_url = "https://elektro-kmcdkbpue9vbok3q4vnurj.streamlit.app/?view=tv"
        
        st.info(f"💡 **Merkhilfe für den Fernseher:** Tippen Sie im Browser Ihres Smart-TVs oder des zweiten Geräts folgende Adresse ein:\n\n`{current_url}`")

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
        "show_rechnungen": True,
        "show_lager": True,
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
                
                .side-card { background-color: #1E232F; padding: 16px; border-radius: 10px; margin-bottom: 15px; color: #FFFFFF; border-left: 5px solid #007BFF; }
                .side-card-warn { border-left-color: #FF4B4B !important; }
            </style>
        """, unsafe_allow_html=True)

        if is_tv_mode:
            st.markdown('<div class="tv-header">⚡ ELEKTRO-ENTERPRISE — Live-Leitsystem</div>', unsafe_allow_html=True)
        
        current_time = datetime.now(ZoneInfo("Europe/Berlin")).strftime('%d.%m.%Y, %H:%M:%S Uhr')
        st.markdown(f'<div class="tv-sub">Einsatzübersicht, Rechnungen & Lager | Letzte Aktualisierung: {current_time} (Auto-Refresh alle {cfg["refresh_sekunden"]} Sek.)</div>', unsafe_allow_html=True)
        st.markdown("---")

        # Daten aus Supabase laden
        try:
            # 1. Aufträge
            selected_statuses = cfg["status_filter"]
            if selected_statuses:
                res_a = supabase.table("auftraege").select("*, kunden(*), gebaeude(*), fahrzeuge(*)").in_("status", selected_statuses).order("termin_um").execute()
                auftraege = res_a.data or []
            else:
                auftraege = []

            # 2. Rechnungen (Offen)
            rechnungen = []
            if cfg["show_rechnungen"]:
                res_r = supabase.table("rechnungen").select("*").eq("status", "Offen").order("erstellt_am", desc=True).limit(6).execute()
                rechnungen = res_r.data or []

            # 3. Lagerwarnungen (Bestand <= Sollbestand)
            lager_warnungen = []
            if cfg["show_lager"]:
                res_m = supabase.table("lager_material").select("*").order("bezeichnung").execute()
                alle_m = res_m.data or []
                lager_warnungen = [m for m in alle_m if int(m.get('ist_bestand', 0)) <= int(m.get('soll_bestand', 0))]
        except Exception as e:
            st.error(f"Fehler beim Laden der Live-Daten: {e}")
            auftraege, rechnungen, lager_warnungen = [], [], []

        # Layout-Aufteilung: Links Aufträge, Rechts (optional) Rechnungen & Lagerwarnungen
        has_sidebar_content = cfg["show_rechnungen"] or cfg["show_lager"]

        if has_sidebar_content:
            col_main, col_side = st.columns([2.2, 1])
        else:
            col_main = st.container()

        with col_main:
            st.markdown("### 📋 Aktuelle Aufträge")
            if not auftraege:
                st.markdown("<h4 style='color: #808080;'>Keine Aufträge mit diesen Filtern vorhanden.</h4>", unsafe_allow_html=True)
            else:
                # Unterteilung der Aufträge in zwei Unterspalten für schöne Grid-Ansicht
                sub_c1, sub_c2 = st.columns(2)
                for idx, a in enumerate(auftraege):
                    target_sub_col = sub_c1 if idx % 2 == 0 else sub_c2
                    
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

                    with target_sub_col:
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

        if has_sidebar_content:
            with col_side:
                # 1. Offene Rechnungen anzeigen
                if cfg["show_rechnungen"]:
                    st.markdown("### 💶 Offene Rechnungen")
                    if not rechnungen:
                        st.success("✅ Keine offenen Rechnungen.")
                    else:
                        for r in rechnungen:
                            st.markdown(f"""
                                <div class="side-card">
                                    <b>Rechnung #{r.get('rechnungsnummer')}</b><br>
                                    👤 {r.get('kunde_name', 'Kunde')}<br>
                                    📅 Datum: {r.get('rechnungs_datum', '-')}
                                </div>
                            """, unsafe_allow_html=True)

                # 2. Lager-Bestandswarnungen anzeigen
                if cfg["show_lager"]:
                    st.markdown("### 📦 Lager-Warnungen")
                    if not lager_warnungen:
                        st.success("✅ Alle Bestände im grünen Bereich!")
                    else:
                        for wm in lager_warnungen[:6]: # Maximal 6 anzeigen für Übersichtlichkeit auf dem TV
                            st.markdown(f"""
                                <div class="side-card side-card-warn">
                                    <b>{wm.get('bezeichnung')}</b><br>
                                    📍 Ort: <code>{wm.get('lagerort', '-')}</code><br>
                                    Ist: <b>{wm.get('ist_bestand')} {wm.get('einheit', 'Stk.')}</b> | Soll: {wm.get('soll_bestand')}
                                </div>
                            """, unsafe_allow_html=True)

    render_live_content()
