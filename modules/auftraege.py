import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from zoneinfo import ZoneInfo

class AuftragPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - MONTAGESCHEIN / AUFTRAG', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Offizieller Arbeitsauftrag inklusive Objekt- und Materialdaten', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_auftrag_pdf(a, kunde, gebaeude, monteur):
    pdf = AuftragPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 6, clean_text(f"Auftragsnummer: {a.get('auftragsnummer')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    
    status_str = a.get('status', 'Offen')
    pdf.cell(0, 6, clean_text(f"Status: {status_str}"), new_x="LMARGIN", new_y="NEXT")
    
    t_um = str(a.get('termin_um', ''))[:16].replace('T', ' ')
    t_bis = str(a.get('termin_bis', ''))[:16].replace('T', ' ')
    pdf.cell(0, 6, clean_text(f"Einsatztermin: Von {t_um} bis {t_bis} Uhr"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Auftraggeber & Objektanschrift:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    
    k_name = f"{kunde.get('vorname', '')} {kunde.get('nachname', '')}" if kunde else "Kein Kunde zugeordnet"
    k_tel = kunde.get('telefon', '-') if kunde else '-'
    pdf.cell(0, 6, clean_text(f"Kunde: {k_name} (Tel: {k_tel})"), new_x="LMARGIN", new_y="NEXT")
    
    if gebaeude:
        g_adr = f"{gebaeude.get('strasse')} {gebaeude.get('hausnummer')}, {gebaeude.get('ort')}"
        g_code = f"[{gebaeude.get('gebaeude_code')}] " if gebaeude.get('gebaeude_code') else ""
        pdf.cell(0, 6, clean_text(f"Objektadresse: {g_code}{g_adr}"), new_x="LMARGIN", new_y="NEXT")
        if a.get('mieter_we'):
            pdf.cell(0, 6, clean_text(f"Betroffene WE / Mieter: {a.get('mieter_we')}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, clean_text("Objektadresse: -"), new_x="LMARGIN", new_y="NEXT")
    
    m_name = f"{monteur.get('vorname', '')} {monteur.get('nachname', '')}" if monteur else "Nicht zugewiesen"
    pdf.cell(0, 6, clean_text(f"Zuständiger Monteur: {m_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Auszuführende Arbeiten / Leistungsbeschreibung:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 5, clean_text(a.get('arbeiten', '-')))
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Verbrauchtes / Benötigtes Material:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 5, clean_text(a.get('benoetigtes_material', 'Noch kein Material eingetragen.')))
    
    return pdf.output()

def render_auftraege_verwaltung(supabase):
    st.title("📋 4. Auftrags- & Einsatzmanagement")
    st.caption("Planen Sie Aufträge, weisen Sie Monteure zu (mit automatischer Urlaubs-/Krank-Prüfung) und erfassen Sie Material.")

    user_data = st.session_state.get("user_data", {})
    user_id = user_data.get("id")
    user_rolle = user_data.get("rolle", "")
    is_admin = user_rolle in ["Admin", "Büro", "Inhaber"]

    try:
        a_res = supabase.table("auftraege").select("*, kunden(*), gebaeude(*), mitarbeiter(id, vorname, nachname)").order("erstellt_am", desc=True).execute()
        auftraege_liste = a_res.data or []
    except Exception:
        auftraege_liste = []

    try:
        k_res = supabase.table("kunden").select("id, vorname, nachname, firma").order("nachname").execute()
        kunden_liste = k_res.data or []
    except Exception:
        kunden_liste = []

    try:
        g_res = supabase.table("gebaeude").select("id, strasse, hausnummer, ort, gebaeude_code").order("ort").execute()
        gebaeude_liste = g_res.data or []
    except Exception:
        gebaeude_liste = []

    try:
        m_res = supabase.table("mitarbeiter").select("id, vorname, nachname").eq("ist_aktiv", True).execute()
        mitarbeiter_liste = m_res.data or []
    except Exception:
        mitarbeiter_liste = []

    verfuegbare_mitarbeiter = []
    heute_str = datetime.now().strftime("%Y-%m-%d")

    for ma in mitarbeiter_liste:
        try:
            abw_res = supabase.table("mitarbeiter_abwesenheit").select("*").eq("mitarbeiter_id", ma["id"]).lte("von_datum", heute_str).gte("bis_datum", heute_str).execute()
            if abw_res.data:
                continue
        except Exception:
            pass
        verfuegbare_mitarbeiter.append(ma)

    tabs_optionen = ["📋 Auftragsübersicht"]
    if is_admin:
        tabs_optionen.append("➕ Neuen Auftrag anlegen")

    tabs = st.tabs(tabs_optionen)

    with tabs[0]:
        st.subheader("Auftragsliste")

        sichtbare_auftraege = auftraege_liste
        if not is_admin:
            sichtbare_auftraege = [a for a in auftraege_liste if a.get("mitarbeiter_id") == user_id]

        if not sichtbare_auftraege:
            st.info("Keine Aufträge vorhanden oder Ihnen sind aktuell keine Aufträge zugeteilt.")
        else:
            for a in sichtbare_auftraege:
                kunde = a.get("kunden") or {}
                gebaeude = a.get("gebaeude") or {}
                monteur = a.get("mitarbeiter") or {}

                status_icon = "🟢" if a.get("status") == "Abgeschlossen" else ("🟡" if a.get("status") == "In Bearbeitung" else "🔴")
                k_name = f"{kunde.get('vorname', '')} {kunde.get('nachname', '')}".strip() or "Kein Kunde"
                g_adr = f"{gebaeude.get('strasse', '')} {gebaeude.get('hausnummer', '')}, {gebaeude.get('ort', '')}" if gebaeude else "Kein Objekt"
                m_name = f"{monteur.get('vorname', '')} {monteur.get('nachname', '')}".strip() or "Unzugewiesen"

                with st.expander(f"{status_icon} [{a.get('auftragsnummer')}] {k_name} | Objekt: {g_adr} (Monteur: {m_name})"):
                    st.write(f"**Auszuführende Arbeiten:** {a.get('arbeiten')}")
                    if a.get('mieter_we'):
                        st.write(f"**Mieter / WE:** {a.get('mieter_we')}")
                    
                    t_um = str(a.get('termin_um', ''))[:16].replace('T', ' ')
                    t_bis = str(a.get('termin_bis', ''))[:16].replace('T', ' ')
                    st.write(f"**Geplanter Einsatztermin:** Von {t_um} bis {t_bis} Uhr")
                    st.write(f"**Aktueller Status:** {a.get('status')}")
                    st.write(f"**Benötigtes Material:** {a.get('benoetigtes_material') or 'Noch nichts eingetragen'}")

                    st.markdown("---")
                    st.write("🛠️ **Monteur-Bearbeitung & Materialerfassung**")

                    with st.form(f"auftrag_edit_{a['id']}"):
                        neuer_status = st.selectbox("Status", ["Offen", "In Bearbeitung", "Abgeschlossen"], index=["Offen", "In Bearbeitung", "Abgeschlossen"].index(a.get("status", "Offen")))
                        verbrauchtes_material = st.text_area("Benötigtes / Verbrautes Material eintragen", value=a.get("benoetigtes_material") or "")
                        
                        neuer_monteur = None
                        if is_admin:
                            neuer_monteur = st.selectbox(
                                "Monteur zuweisen",
                                options=[m["id"] for m in verfuegbare_mitarbeiter],
                                format_func=lambda x: next(f"{m['vorname']} {m['nachname']}" for m in verfuegbare_mitarbeiter if m["id"] == x),
                                index=[m["id"] for m in verfuegbare_mitarbeiter].index(a.get("mitarbeiter_id")) if a.get("mitarbeiter_id") in [m["id"] for m in verfuegbare_mitarbeiter] else 0
                            )

                        b_save = st.form_submit_button("💾 Änderungen / Material speichern", type="primary", use_container_width=True)

                        if b_save:
                            try:
                                update_payload = {
                                    "status": neuer_status,
                                    "benoetigtes_material": verbrauchtes_material
                                }
                                if is_admin and neuer_monteur:
                                    update_payload["mitarbeiter_id"] = neuer_monteur

                                supabase.table("auftraege").update(update_payload).eq("id", a["id"]).execute()
                                st.success("Auftrag erfolgreich aktualisiert!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler: {e}")

                    pdf_bytes = generate_auftrag_pdf(a, kunde, gebaeude, monteur)
                    st.download_button(
                        label=f"📥 Auftrags-PDF herunterladen / Drucken ({a.get('auftragsnummer')})",
                        data=bytes(pdf_bytes),
                        file_name=f"Auftrag_{a.get('auftragsnummer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{a['id']}"
                    )

    if is_admin and len(tabs) > 1:
        with tabs[1]:
            st.subheader("Neuen Auftrag erstellen")

            if not kunden_liste:
                st.warning("Bitte legen Sie zuerst mindestens einen Kunden an.")
            elif not gebaeude_liste:
                st.warning("Bitte legen Sie zuerst mindestens ein Gebäude an.")
            else:
                with st.form("neuer_auftrag_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        n_auftragsnummer = st.text_input("Auftragsnummer *", value=f"A-{datetime.now().strftime('%Y%m%d')}-01")
                        n_kunde = st.selectbox(
                            "Auftraggeber (Kunde) *",
                            options=[k["id"] for k in kunden_liste],
                            format_func=lambda x: next(f"{k['nachname']}, {k['vorname']} ({k.get('firma', 'Privat')})" for k in kunden_liste if k["id"] == x)
                        )
                        n_gebaeude = st.selectbox(
                            "Auftragsort (Gebäude / Objekt) *",
                            options=[g["id"] for g in gebaeude_liste],
                            format_func=lambda x: next(f"[{g.get('gebaeude_code', 'Kein Code')}] {g['strasse']} {g['hausnummer']}, {g['ort']}" for g in gebaeude_liste if g["id"] == x)
                        )
                        n_mieter_we = st.text_input("Mieter / WE / Etage (optional)", placeholder="z.B. WE 4, 2. Obergeschoss links")

                    with col2:
                        n_monteur = st.selectbox(
                            "Zuständiger Mitarbeiter (Monteur) *",
                            options=[m["id"] for m in verfuegbare_mitarbeiter],
                            format_func=lambda x: next(f"{m['vorname']} {m['nachname']}" for m in verfuegbare_mitarbeiter if m["id"] == x)
                        )
                        
                        st.write("Einsatztermin (Datum & Uhrzeit)")
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            n_datum = st.date_input("Einsatzdatum", value=datetime.today())
                        with col_d2:
                            n_uhr_von = st.time_input("Uhrzeit Von", value=datetime.strptime("08:00", "%H:%M").time())
                            n_uhr_bis = st.time_input("Uhrzeit Bis", value=datetime.strptime("16:00", "%H:%M").time())

                    n_arbeiten = st.text_area("Auszuführende Arbeiten *", placeholder="z.B. Zählerschrank umbauen, Wallbox anschließen...")
                    n_material = st.text_area("Benötigtes Material (Vorbereitung)", placeholder="z.B. 1x FI-Schalter, 15m NYM-J 3x1.5...")

                    if st.form_submit_button("Auftrag anlegen & zuweisen", type="primary", use_container_width=True):
                        if not n_auftragsnummer or not n_arbeiten:
                            st.warning("Bitte Auftragsnummer und auszuführende Arbeiten angeben.")
                        else:
                            try:
                                dt_von = datetime.combine(n_datum, n_uhr_von).astimezone(ZoneInfo("Europe/Berlin")).isoformat()
                                dt_bis = datetime.combine(n_datum, n_uhr_bis).astimezone(ZoneInfo("Europe/Berlin")).isoformat()

                                auftrag_payload = {
                                    "auftragsnummer": n_auftragsnummer,
                                    "kunde_id": n_kunde,
                                    "gebaeude_id": n_gebaeude,
                                    "mitarbeiter_id": n_monteur,
                                    "arbeiten": n_arbeiten,
                                    "mieter_we": n_mieter_we,
                                    "termin_um": dt_von,
                                    "termin_bis": dt_bis,
                                    "benoetigtes_material": n_material,
                                    "status": "Offen"
                                }
                                supabase.table("auftraege").insert(auftrag_payload).execute()
                                st.success(f"Auftrag {n_auftragsnummer} erfolgreich angelegt und zugewiesen!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler beim Anlegen: {e}")
