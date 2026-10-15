import streamlit as st
from datetime import datetime, date
from zoneinfo import ZoneInfo
import pandas as pd
from fpdf import FPDF
import calendar

class SteuerberaterPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - MONATLICHE LOHN- & ZEITERFASSUNG', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Monatsuebersicht fuer die Steuerberatung / Lohnbuchhaltung (DSGVO-konform)', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    replacements = {
        "🟢": "Erfolgreich / ",
        "⚠️": "Hinweis: ",
        "🔴": "Aktiv: "
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_steuerberater_pdf_multi(mitarbeiter_daten_liste, monat_str, jahr_str):
    """Erstellt ein einziges PDF-Dokument mit allen Mitarbeitern des Monats."""
    pdf = SteuerberaterPDF(orientation='P', unit='mm', format='A4')
    
    for idx, data in enumerate(mitarbeiter_daten_liste):
        if idx > 0:
            pdf.add_page() # Für jeden Mitarbeiter eine neue Seite
        else:
            pdf.add_page()

        ma_name = data["name"]
        ma_nr = data["nr"]
        tage_liste = data["tage"]
        gesamt_netto = data["netto"]
        gesamt_soll = data["soll"]

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 6, clean_text(f"Mitarbeiter: {ma_name} (Nr. {ma_nr})"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, clean_text(f"Abrechnungszeitraum: Monat {monat_str} / {jahr_str}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(22, 6, "Datum", border=1)
        pdf.cell(16, 6, "Tag", border=1)
        pdf.cell(24, 6, "Kommen", border=1)
        pdf.cell(24, 6, "Gehen", border=1)
        pdf.cell(16, 6, "Pause", border=1)
        pdf.cell(22, 6, "Netto Std.", border=1)
        pdf.cell(22, 6, "Soll Std.", border=1)
        pdf.cell(52, 6, "Status / Bemerkung", border=1, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font('Helvetica', '', 8)
        for row in tage_liste:
            pdf.cell(22, 5, clean_text(str(row["Datum"])), border=1)
            pdf.cell(16, 5, clean_text(str(row["Tag"])), border=1)
            pdf.cell(24, 5, clean_text(str(row["Kommen"])), border=1)
            pdf.cell(24, 5, clean_text(str(row["Gehen"])), border=1)
            pdf.cell(16, 5, clean_text(str(row["Pause"])), border=1)
            pdf.cell(22, 5, clean_text(str(row["Netto"])), border=1)
            pdf.cell(22, 5, clean_text(str(row["Soll"])), border=1)
            pdf.cell(52, 5, clean_text(str(row["Status"])), border=1, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, clean_text(f"Summe Netto-Arbeitsstunden im Monat: {gesamt_netto:.2f} Std."), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, clean_text(f"Summe Soll-Arbeitsstunden im Monat: {gesamt_soll:.2f} Std."), new_x="LMARGIN", new_y="NEXT")
        diff = gesamt_netto - gesamt_soll
        pdf.cell(0, 6, clean_text(f"Monatssaldo (Ueber-/Minusstunden): {diff:+.2f} Std."), new_x="LMARGIN", new_y="NEXT")

    return pdf.output()

def berechne_monatsdaten_fuer_ma(supabase, ma, monat_auswahl, jahr_auswahl):
    """Berechnet die Monatsdaten für einen einzelnen Mitarbeiter."""
    ma_id = ma["id"]
    anzahl_tage = calendar.monthrange(jahr_auswahl, monat_auswahl)[1]
    start_datum_monat = date(jahr_auswahl, monat_auswahl, 1)
    end_datum_monat = date(jahr_auswahl, monat_auswahl, anzahl_tage)

    try:
        zeit_res = supabase.table("zeiterfassung").select("*").eq("mitarbeiter_id", ma_id).gte("einstempeln", f"{start_datum_monat}T00:00:00").lte("einstempeln", f"{end_datum_monat}T23:59:59").execute()
        eintraege = zeit_res.data or []
    except Exception:
        eintraege = []

    try:
        antrag_res = supabase.table("antraege").select("*").eq("mitarbeiter_id", ma_id).eq("status", "genehmigt").execute()
        genehmigte_antraege = antrag_res.data or []
    except Exception:
        genehmigte_antraege = []

    def get_abwesenheit(d_check):
        for a in genehmigte_antraege:
            try:
                s = date.fromisoformat(a.get("start_datum"))
                e = date.fromisoformat(a.get("end_datum"))
                if s <= d_check <= e:
                    return a.get("art", "Abwesend")
            except Exception:
                pass
        return None

    tage_mapping = {
        0: float(ma.get("soll_mo", 8.0)),
        1: float(ma.get("soll_di", 8.0)),
        2: float(ma.get("soll_mi", 8.0)),
        3: float(ma.get("soll_do", 8.0)),
        4: float(ma.get("soll_fr", 6.0)),
        5: 0.0,
        6: 0.0
    }
    wochentage_kurz = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    tabelle_daten = []
    gesamt_netto = 0.0
    gesamt_soll = 0.0

    for tag_nr in range(1, anzahl_tage + 1):
        aktueller_tag = date(jahr_auswahl, monat_auswahl, tag_nr)
        wochentag_idx = aktueller_tag.weekday()
        tag_name = wochentage_kurz[wochentag_idx]
        tages_soll = tage_mapping.get(wochentag_idx, 0.0)
        gesamt_soll += tages_soll

        passender_eintrag = None
        for e in eintraege:
            try:
                ein_dt = datetime.fromisoformat(e["einstempeln"].replace('Z', '+00:00'))
                if ein_dt.date() == aktueller_tag:
                    passender_eintrag = e
                    break
            except Exception:
                pass

        abwesenheit = get_abwesenheit(aktueller_tag)

        kommen_str = "-"
        gehen_str = "-"
        pause_min = 0
        netto_std = 0.0
        status_bemerkung = "-"

        if passender_eintrag:
            ein_dt = datetime.fromisoformat(passender_eintrag["einstempeln"].replace('Z', '+00:00'))
            if ein_dt.tzinfo is not None:
                ein_dt = ein_dt.astimezone(ZoneInfo("Europe/Berlin"))
            kommen_str = ein_dt.strftime("%H:%M")

            aus_str = passender_eintrag.get("ausstempeln")
            if aus_str:
                aus_dt = datetime.fromisoformat(aus_str.replace('Z', '+00:00'))
                if aus_dt.tzinfo is not None:
                    aus_dt = aus_dt.astimezone(ZoneInfo("Europe/Berlin"))
                gehen_str = aus_dt.strftime("%H:%M")
                
                pause_min = passender_eintrag.get("pause_minuten", 0)
                dauer_sec = (aus_dt - ein_dt).total_seconds() - (pause_min * 60)
                netto_std = max(0.0, dauer_sec / 3600.0)
                gesamt_netto += netto_std
                status_bemerkung = passender_eintrag.get("notiz") or "Gearbeitet"
            else:
                status_bemerkung = "Laeuft noch aktiv"
        elif abwesenheit:
            status_bemerkung = f"{abwesenheit}"
        elif wochentag_idx >= 5:
            status_bemerkung = "Wochenende"
        else:
            status_bemerkung = "Kein Eintrag"

        tabelle_daten.append({
            "Datum": aktueller_tag.strftime("%d.%m.%Y"),
            "Tag": tag_name,
            "Kommen": kommen_str,
            "Gehen": gehen_str,
            "Pause": f"{pause_min}m" if passender_eintrag else "-",
            "Netto": round(netto_std, 2) if passender_eintrag else 0.0,
            "Soll": tages_soll,
            "Status": status_bemerkung
        })

    return {
        "name": f"{ma['vorname']} {ma['nachname']}",
        "nr": ma['mitarbeiternummer'],
        "tage": tabelle_daten,
        "netto": gesamt_netto,
        "soll": gesamt_soll
    }

def hat_recht(modul_id, aktion="sehen"):
    """Prüft anhand der in der DB hinterlegten rollen['erlaubte_menues'], ob die Aktion erlaubt ist."""
    user = st.session_state.get("user_data", {})
    
    # Rollen-Objekt aus der Datenbank prüfen
    rollen_obj = user.get("rollen") or {}
    erlaubte_menues = rollen_obj.get("erlaubte_menues", [])
    
    # Fallback für alte Rechte-Listen oder Admin-Rollen
    if not erlaubte_menues:
        alte_rechte = user.get("rechte", [])
        if f"{modul_id}_{aktion}" in alte_rechte or user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
            return True
        return False

    return f"{modul_id}_{aktion}" in erlaubte_menues

def render_steuerberater_export(supabase):
    st.title("📊 Monatsabrechnung & Steuerberater-Export")
    st.caption("Erstellen Sie monatliche Stempel- und Anwesenheitslisten – wahlweise für einzelne Mitarbeiter oder als **Gesamt-PDF für den gesamten Betrieb**.")

    if not hat_recht("10", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Steuerberater-Export-Modul aufzurufen.")
        return

    darf_exportieren = hat_recht("10", "exportieren")

    try:
        ma_res = supabase.table("mitarbeiter").select("id, vorname, nachname, mitarbeiternummer, soll_mo, soll_di, soll_mi, soll_do, soll_fr").eq("ist_aktiv", True).order("mitarbeiternummer").execute()
        mitarbeiter_liste = ma_res.data or []
    except Exception:
        mitarbeiter_liste = []

    if not mitarbeiter_liste:
        st.warning("Keine aktiven Mitarbeiter gefunden.")
        return

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        monat_auswahl = st.selectbox("Monat auswählen", list(range(1, 13)), index=datetime.now().month - 1, format_func=lambda x: calendar.month_name[x])
    with col_f2:
        jahr_auswahl = st.selectbox("Jahr auswählen", [2024, 2025, 2026, 2027], index=2)

    st.markdown("---")

    if not darf_exportieren:
        st.info("ℹ️ Ihr Account hat nur Leserechte für diesen Bereich. PDF-Exporte sind für Sie deaktiviert.")

    # --- HAUPTAKTION: GESAMTABRECHNUNG FÜR ALLE MITARBEITER ---
    st.subheader("🏢 Betriebs-Gesamtexport (Alle Mitarbeiter)")
    st.info(f"💡 Generiert eine einzige PDF-Datei mit den lückenlosen Monatszeiten aller **{len(mitarbeiter_liste)} aktiven Mitarbeiter** für {calendar.month_name[monat_auswahl]} {jahr_auswahl}.")

    if darf_exportieren:
        if st.button("🚀 Gesamt-PDF für alle Mitarbeiter generieren", type="primary", use_container_width=True):
            with st.spinner("Berechne Zeiten und erstelle Gesamt-PDF..."):
                alle_daten = []
                for ma in mitarbeiter_liste:
                    ma_daten = berechne_monatsdaten_fuer_ma(supabase, ma, monat_auswahl, jahr_auswahl)
                    alle_daten.append(ma_daten)

                pdf_bytes_gesamt = generate_steuerberater_pdf_multi(
                    mitarbeiter_daten_liste=alle_daten,
                    monat_str=calendar.month_name[monat_auswahl],
                    jahr_str=str(jahr_auswahl)
                )

                st.success("✅ Gesamt-PDF erfolgreich erstellt!")
                st.download_button(
                    label=f"📥 Gesamte Betriebs-Lohnliste ({calendar.month_name[monat_auswahl]} {jahr_auswahl}) herunterladen (PDF)",
                    data=bytes(pdf_bytes_gesamt),
                    file_name=f"Steuerberater_Gesamtliste_Betrieb_{monat_auswahl}_{jahr_auswahl}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

    st.markdown("---")
    st.subheader("🔍 Alternativ: Einzelansicht & Einzelauswahl")

    sel_ma_id = st.selectbox(
        "Mitarbeiter für Detailansicht wählen",
        options=[m["id"] for m in mitarbeiter_liste],
        format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in mitarbeiter_liste if m["id"] == x)
    )

    sel_ma = next(m for m in mitarbeiter_liste if m["id"] == sel_ma_id)
    einzel_daten = berechne_monatsdaten_fuer_ma(supabase, sel_ma, monat_auswahl, jahr_auswahl)

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Gesamt Netto-Stunden", f"{round(einzel_daten['netto'], 2)} Std.")
    col_m2.metric("Gesamt Soll-Stunden", f"{round(einzel_daten['soll'], 2)} Std.")
    col_m3.metric("Saldo (Über-/Minustunden)", f"{(einzel_daten['netto'] - einzel_daten['soll']):+.2f} Std.")

    st.dataframe(pd.DataFrame(einzel_daten["tage"]), use_container_width=True)

    if darf_exportieren:
        pdf_bytes_einzel = generate_steuerberater_pdf_multi(
            mitarbeiter_daten_liste=[einzel_daten],
            monat_str=calendar.month_name[monat_auswahl],
            jahr_str=str(jahr_auswahl)
        )

        st.download_button(
            label=f"📥 Einzel-PDF für {sel_ma['vorname']} {sel_ma['nachname']} herunterladen",
            data=bytes(pdf_bytes_einzel),
            file_name=f"Steuerberater_Zeiten_{sel_ma['mitarbeiternummer']}_{monat_auswahl}_{jahr_auswahl}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
