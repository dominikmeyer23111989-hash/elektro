import streamlit as st
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

@st.fragment(run_every=30)
def render_tv_dashboard(supabase):
    # CSS für ein großes, kontrastreiches TV-Layout (Dark Mode optimiert für Bildschirme)
    st.markdown("""
        <style>
            .tv-header { font-size: 2.8rem; font-weight: bold; color: #FF4B4B; text-align: center; margin-bottom: 5px; }
            .tv-sub { font-size: 1.2rem; text-align: center; color: #A0A0A0; margin-bottom: 25px; }
            .order-card { background-color: #161A22; padding: 22px; border-radius: 12px; margin-bottom: 20px; border-left: 8px solid #FF4B4B; color: #FFFFFF; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            .order-in-prog { border-left-color: #FFA500 !important; }
            .order-title { font-size: 1.6rem; font-weight: bold; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
            .order-detail { font-size: 1.2rem; margin-bottom: 8px; }
            .badge-offen { background-color: #FF4B4B; color: white; padding: 4px 10px; border-radius: 6px; font-size: 1rem; }
            .badge-prog { background-color: #FFA500; color: white; padding: 4px 10px; border-radius: 6px; font-size: 1rem; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="tv-header">⚡ ELEKTRO-ENTERPRISE — Live-Leitsystem</div>', unsafe_allow_html=True)
    
    current_time = datetime.now(ZoneInfo("Europe/Berlin")).strftime('%d.%m.%Y, %H:%M:%S Uhr')
    st.markdown(f'<div class="tv-sub">Status-Übersicht für aktive Einsätze | Letzte Aktualisierung: {current_time} (Auto-Refresh alle 30 Sek.)</div>', unsafe_allow_html=True)
    st.markdown("---")

    try:
        res = supabase.table("auftraege").select("*, kunden(*), gebaeude(*), fahrzeuge(*)").in_("status", ["Offener Auftrag", "In Bearbeitung"]).order("termin_um").execute()
        auftraege = res.data or []
    except Exception as e:
        st.error(f"Fehler beim Laden der Live-Daten: {e}")
        auftraege = []

    if not auftraege:
        st.markdown("<h2 style='text-align: center; color: #808080; margin-top: 50px;'>🎉 Aktuell sind keine offenen Einsätze im System.</h2>", unsafe_allow_html=True)
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
        else:
            card_class = "order-card"
            badge = '<span class="badge-offen">🔴 Offener Auftrag</span>'

        with target_col:
            st.markdown(f"""
                <div class="{card_class}">
                    <div class="order-title">
                        <span>#{a.get('auftragsnummer')}</span>
                        <span>{badge}</span>
                    </div>
                    <div class="order-detail"><b>👤 Kunde:</b> {k_name}</div>
                    <div class="order-detail"><b>📍 Objekt:</b> {g_adr}</div>
                    <div class="order-detail"><b>⚡ Arbeiten:</b> {a.get('arbeiten')}</div>
                    <div class="order-detail"><b>🕒 Termin:</b> {format_de_zeit(a.get('termin_um'))}</div>
                    <div class="order-detail"><b>👷 Team:</b> {team_names}</div>
                    <div class="order-detail"><b>🚐 Fahrzeug:</b> {f_info}</div>
                </div>
            """, unsafe_allow_html=True)
