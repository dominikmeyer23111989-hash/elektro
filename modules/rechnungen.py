import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from zoneinfo import ZoneInfo
from io import BytesIO

class RechnungsPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - RECHNUNG', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Rechnungsstellung für Montage, Service und Material', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_rechnung_pdf(rechnung, positionen):
    pdf = RechnungsPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 6, clean_text(f"Rechnungsnummer: {rechnung.get('rechnungsnummer')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    
    r_datum = rechnung.get('rechnungs_datum', datetime.now().strftime('%Y-%m-%d'))
    pdf.cell(0, 6, clean_text(f"Rechnungsdatum: {r_datum}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, clean_text(f"Kunde: {rechnung.get('kunde_name', '-')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Tabellenkopf
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(90, 6, "Beschreibung", border=1)
    pdf.cell(25, 6, "Menge", border=1, align='C')
    pdf.cell(35, 6, "Einzelpreis (Netto)", border=1, align='R')
    pdf.cell(40, 6, "Gesamt (Netto)", border=1, align='R', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 10)
    netto_summe = 0.0

    for p in positionen:
        menge = float(p.get('menge', 1))
        epreis = float(p.get('einzelpreis_netto', 0.0))
        gpreis = menge * epreis
        netto_summe += gpreis

        pdf.cell(90, 6, clean_text(p.get('beschreibung', '')), border=1)
        pdf.cell(25, 6, clean_text(str(menge)), border=1, align='C')
        pdf.cell(35, 6, clean_text(f"{epreis:.2f} EUR"), border=1, align='R')
        pdf.cell(40, 6, clean_text(f"{gpreis:.2f} EUR"), border=1, align='R', new_x="LMARGIN", new_y="NEXT")

    mwst_satz = float(rechnung.get('mwst_satz', 19.0))
    mwst_betrag = netto_summe * (mwst_satz / 100.0)
    brutto_summe = netto_summe + mwst_betrag

    pdf.ln(5)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(150, 6, "Summe Netto:", align='R')
    pdf.cell(40, 6, f"{netto_summe:.2f} EUR", align='R', new_x="LMARGIN", new_y="NEXT")

    pdf.cell(150, 6, f"Mehrwertsteuer ({mwst_satz}%):", align='R')
    pdf.cell(40, 6, f"{mwst_betrag:.2f} EUR", align='R', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(150, 8, "Gesamtauftragssumme (Brutto):", align='R')
    pdf.cell(40, 8, f"{brutto_summe:.2f} EUR", align='R', new_x="LMARGIN", new_y="NEXT")

    return pdf.output()

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_rechnungen_verwaltung(supabase):
    st.title("💶 6. Rechnungs- & Abrechnungsmodul")
    st.caption("Rechnen Sie Aufträge ab, legen Sie flexible Preise fest und exportieren Sie Rechnungen als PDF.")

    # Berechtigungsprüfung (Modul-ID 6 oder Admin)
    user_data = st.session_state.get("user_data", {})
    user_rolle = user_data.get("rolle", "")
    is_admin = user_rolle in ["Admin", "Inhaber", "Chef", "Büro"]

    try:
        r_res = supabase.table("rechnungen").select("*").order("erstellt_am", desc=True).execute()
        rechnungen_liste = r_res.data or []
    except Exception:
        rechnungen_liste = []

    try:
        a_res = supabase.table("auftraege").select("id, auftragsnummer, freitext_kunde, kunden(vorname, nachname, firma), status").execute()
        auftraege_liste = a_res.data or []
    except Exception:
        auftraege_liste = []

    tabs = st.tabs(["📄 Rechnungsübersicht", "➕ Neue Rechnung erstellen"])

    # --- TAB 1: RECHNUNGSÜBERSICHT ---
    with tabs[0]:
        st.subheader("Erstellte Rechnungen")
        if not rechnungen_liste:
            st.info("Noch keine Rechnungen erstellt.")
        else:
            for r in rechnungen_liste:
                try:
                    pos_res = supabase.table("rechnungspositionen").select("*").eq("rechnung_id", r["id"]).execute()
                    positionen = pos_res.data or []
                except Exception:
                    positionen = []

                netto = sum(float(p.get("menge", 1)) * float(p.get("einzelpreis_netto", 0)) for p in positionen)
                mwst = netto * (float(r.get("mwst_satz", 19.0)) / 100.0)
                brutto = netto + mwst

                with st.expander(f"Rechnung #{r.get('rechnungsnummer')} | Kunde: {r.get('kunde_name')} | Brutto: {brutto:.2f} EUR | Status: {r.get('status')}"):
                    st.write(f"**Datum:** {r.get('rechnungs_datum')}")
                    st.write(f"**Mehrwertsteuersatz:** {r.get('mwst_satz')}%")
                    
                    if positionen:
                        st.markdown("**Positionen:**")
                        df_p = pd.DataFrame([{
                            "Beschreibung": p["beschreibung"],
                            "Menge": p["menge"],
                            "Einzelpreis (Netto)": f"{float(p['einzelpreis_netto']):.2f} EUR",
                            "Gesamt (Netto)": f"{float(p['menge']) * float(p['einzelpreis_netto']):.2f} EUR"
                        } for p in positionen])
                        st.dataframe(df_p, use_container_width=True, hide_index=True)
                    
                    st.markdown(f"**Summe Netto:** {netto:.2f} EUR | **MwSt.:** {mwst:.2f} EUR | **Gesamt Brutto:** **{brutto:.2f} EUR**")
                    
                    st.markdown("---")
                    pdf_bytes = generate_rechnung_pdf(r, positionen)
                    st.download_button(
                        label=f"📥 Rechnungs-PDF herunterladen ({r.get('rechnungsnummer')})",
                        data=bytes(pdf_bytes),
                        file_name=f"Rechnung_{r.get('rechnungsnummer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_rech_{r['id']}"
                    )

    # --- TAB 2: NEUE RECHNUNG ERSTELLEN ---
    with tabs[1]:
        st.subheader("Neue Rechnung aus Auftrag oder Direktabrechnung erstellen")

        if "rechnung_positionen_temp" not in st.session_state:
            st.session_state["rechnung_positionen_temp"] = []

        with st.form("neue_rechnung_form"):
            col1, col2 = st.columns(2)
            with col1:
                default_r_nr = f"RE-{datetime.now().strftime('%Y%m%d')}-01"
                r_nummer = st.text_input("Rechnungsnummer *", value=default_r_nr)
                
                auftrag_optionen = [None] + auftraege_liste
                sel_auftrag = st.selectbox(
                    "Bezug zu Auftrag (optional)",
                    options=auftrag_optionen,
                    format_func=lambda x: "--- Keine Auftragsverknüpfung ---" if x is None else f"Auftrag {x.get('auftragsnummer')} ({x.get('status', '-')})"
                )
            with col2:
                r_kunde = st.text_input("Kundenname / Firma *", placeholder="z.B. Hans Müller GmbH")
                r_mwst = st.number_input("Mehrwertsteuersatz (%)", min_value=0.0, value=19.0, step=0.5)

            st.markdown("---")
            st.markdown("##### 🛠️ Positionen hinzufügen (Stunden, Material, Pauschalen)")
            
            p_beschr = st.text_input("Positionsbeschreibung", placeholder="z.B. Arbeitsstunden Monteur / NYM-Leitung 3x1.5")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                p_menge = st.number_input("Menge / Stunden", min_value=0.1, value=1.0, step=0.5)
            with col_p2:
                p_preis = st.number_input("Einzelpreis netto (EUR)", min_value=0.0, value=65.0, step=5.0)

            btn_add_pos = st.form_submit_button("➕ Position zur Rechnung hinzufügen")
            if btn_add_pos:
                if p_beschr.strip():
                    st.session_state["rechnung_positionen_temp"].append({
                        "beschreibung": p_beschr.strip(),
                        "menge": p_menge,
                        "einzelpreis_netto": p_preis
                    })
                    st.toast("Position hinzugefügt!", icon="✅")
                    st.rerun()
                else:
                    st.warning("Bitte eine Positionsbeschreibung angeben.")

        # Anzeige der aktuellen Positionen
        if st.session_state["rechnung_positionen_temp"]:
            st.markdown("##### 📋 Aktuelle Rechnungspositionen:")
            df_temp = pd.DataFrame([{
                "Beschreibung": p["beschreibung"],
                "Menge": p["menge"],
                "Einzelpreis (Netto)": f"{p['einzelpreis_netto']:.2f} EUR",
                "Gesamt (Netto)": f"{p['menge'] * p['einzelpreis_netto']:.2f} EUR"
            } for p in st.session_state["rechnung_positionen_temp"]])
            st.dataframe(df_temp, use_container_width=True, hide_index=True)

            if st.button("🗑️ Alle Positionen zurücksetzen"):
                st.session_state["rechnung_positionen_temp"] = []
                st.rerun()

            st.markdown("---")
            if st.button("💾 Rechnung final speichern & erstellen", type="primary", use_container_width=True):
                if not r_nummer.strip() or not r_kunde.strip():
                    st.warning("Bitte Rechnungsnummer und Kundenname angeben.")
                else:
                    try:
                        # Rechnung in Supabase speichern
                        r_payload = {
                            "rechnungsnummer": r_nummer.strip(),
                            "auftrag_id": sel_auftrag["id"] if sel_auftrag else None,
                            "kunde_name": r_kunde.strip(),
                            "mwst_satz": r_mwst,
                            "status": "Offen"
                        }
                        res = supabase.table("rechnungen").insert(r_payload).execute()

                        if res.data:
                            rech_id = res.data[0]["id"]
                            pos_inserts = [{
                                "rechnung_id": rech_id,
                                "beschreibung": p["beschreibung"],
                                "menge": p["menge"],
                                "einzelpreis_netto": p["einzelpreis_netto"]
                            } for p in st.session_state["rechnung_positionen_temp"]]

                            supabase.table("rechnungspositionen").insert(pos_inserts).execute()

                        st.session_state["rechnung_positionen_temp"] = []
                        st.success(f"Rechnung {r_nummer} erfolgreich erstellt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern der Rechnung: {e}")
        else:
            st.info("Fügen Sie mindestens eine Position hinzu, um die Rechnung speichern zu können.")
