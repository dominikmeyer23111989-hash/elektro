import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF

class GebaeudePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - GEBÄUDE-STAMMBLATT', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Liefer- und Objektadresse inklusive technischer Anlagendetails', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_gebaeude_pdf(g):
    pdf = GebaeudePDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    pdf.set_font('Helvetica', 'B', 12)
    code_str = f"[{g.get('gebaeude_code')}] " if g.get('gebaeude_code') else ""
    pdf.cell(0, 6, clean_text(f"Objekt: {code_str}{g.get('strasse')} {g.get('hausnummer')}, {g.get('ort')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    fields = [
        ("Gebäude-Code:", str(g.get('gebaeude_code', '-'))),
        ("Anschrift:", f"{g.get('strasse')} {g.get('hausnummer')}, {g.get('ort')}"),
        ("Wohneinheiten:", str(g.get('wohneinheiten', '-'))),
        ("Baujahr:", str(g.get('baujahr', '-'))),
        ("Bauart:", str(g.get('bauart', '-'))),
        ("Energieart / Heizung:", str(g.get('energieart', '-'))),
        ("PV-Anlage vorhanden:", "Ja" if g.get('pv_anlage') else "Nein")
    ]

    for label, val in fields:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(45, 6, clean_text(label))
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, clean_text(val), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, "Besonderheiten / Technische Hinweise:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 9)
    pdf.multi_cell(0, 5, clean_text(g.get('besonderheiten', 'Keine besonderen Hinweise hinterlegt.')))

    return pdf.output()

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

def render_gebaeude_verwaltung(supabase):
    st.title("🏠 7. Gebäude- & Liegenschaftsverwaltung")
    st.caption("Verwalten Sie hier Gebäude, Liegenschaftsadressen, Anlagendetails (PV, Heizung) und Baustellenhinweise.")

    if not hat_recht("7", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Gebäude-Modul aufzurufen.")
        return

    darf_erstellen = hat_recht("7", "erstellen")
    darf_bearbeiten = hat_recht("7", "bearbeiten")

    # Tabs dynamisch aufbauen
    tabs_optionen = ["📋 Gebäudeübersicht & Details"]
    if darf_erstellen:
        tabs_optionen.append("➕ Neues Gebäude anlegen")

    tabs = st.tabs(tabs_optionen)

    # --- TAB 1: Übersicht & Details ---
    with tabs[0]:
        st.subheader("Alle gespeicherten Gebäude & Objekte")

        try:
            res = supabase.table("gebaeude").select("*").order("ort").execute()
            gebaeude_liste = res.data or []
        except Exception as e:
            st.error(f"Fehler beim Laden der Gebäude: {e}")
            gebaeude_liste = []

        if gebaeude_liste:
            suchbegriff = st.text_input("🔍 Gebäude suchen (Straße, Ort, Code oder Bauart)", placeholder="z.B. Hauptstraße, Essen, G-01")
            
            gefilterte_gebaeude = gebaeude_liste
            if suchbegriff:
                s = suchbegriff.lower()
                gefilterte_gebaeude = [
                    g for g in gebaeude_liste if 
                    s in str(g.get("strasse", "")).lower() or
                    s in str(g.get("ort", "")).lower() or
                    s in str(g.get("gebaeude_code", "")).lower() or
                    s in str(g.get("bauart", "")).lower() or
                    s in str(g.get("energieart", "")).lower()
                ]

            display_df = pd.DataFrame([{
                "Code": g.get("gebaeude_code") or "-",
                "Anschrift": f"{g.get('strasse')} {g.get('hausnummer')}",
                "Ort": g.get("ort"),
                "WE": g.get("wohneinheiten") or 1,
                "Baujahr": g.get("baujahr") or "-",
                "Energieart": g.get("energieart") or "-",
                "PV-Anlage": "⚡ Ja" if g.get("pv_anlage") else "Nein"
            } for g in gefilterte_gebaeude])

            st.dataframe(display_df, use_container_width=True)

            st.markdown("---")
            st.subheader("⚙️ Gebäudedetails, Bearbeiten & Stammblatt")

            sel_geb_id = st.selectbox(
                "Gebäude für Details / Bearbeitung auswählen",
                options=[g["id"] for g in gefilterte_gebaeude],
                format_func=lambda x: next(f"[{g.get('gebaeude_code', 'Kein Code')}] {g.get('strasse')} {g.get('hausnummer')}, {g.get('ort')}" for g in gefilterte_gebaeude if g["id"] == x)
            )

            sel_gebaeude = next(g for g in gefilterte_gebaeude if g["id"] == sel_geb_id)

            if not darf_bearbeiten:
                st.info("ℹ️ Ihr Account hat nur Leserechte für Gebäude. Sie können keine Änderungen speichern.")

            with st.form("gebaeude_edit_form"):
                st.write(f"Bearbeite Objekt: **{sel_gebaeude.get('strasse')} {sel_gebaeude.get('hausnummer')}, {sel_gebaeude.get('ort')}**")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    e_strasse = st.text_input("Straße *", value=sel_gebaeude.get("strasse") or "", disabled=not darf_bearbeiten)
                    e_hausnummer = st.text_input("Hausnummer *", value=sel_gebaeude.get("hausnummer") or "", disabled=not darf_bearbeiten)
                    e_ort = st.text_input("Ort *", value=sel_gebaeude.get("ort") or "", disabled=not darf_bearbeiten)
                    e_code = st.text_input("Gebäude-Code (optional)", value=sel_gebaeude.get("gebaeude_code") or "", disabled=not darf_bearbeiten)
                with col_e2:
                    e_we = st.number_input("Wohneinheiten", min_value=1, value=int(sel_gebaeude.get("wohneinheiten") or 1), disabled=not darf_bearbeiten)
                    e_baujahr = st.number_input("Baujahr", min_value=1800, max_value=2030, value=int(sel_gebaeude.get("baujahr") or 1995), disabled=not darf_bearbeiten)
                    e_bauart = st.selectbox("Bauart", ["Massivbau", "Fertighaus", "Altbau / Fachwerk", "Holzrahmenbau", "Sonstige"], index=["Massivbau", "Fertighaus", "Altbau / Fachwerk", "Holzrahmenbau", "Sonstige"].index(sel_gebaeude.get("bauart", "Massivbau")) if sel_gebaeude.get("bauart") in ["Massivbau", "Fertighaus", "Altbau / Fachwerk", "Holzrahmenbau", "Sonstige"] else 0, disabled=not darf_bearbeiten)
                    e_energie = st.selectbox("Energieart / Heizung", ["Wärmepumpe", "Gas", "Öl", "Fernwärme", "Elektro / Nachtspeicher", "Pellets / Biomasse"], index=0, disabled=not darf_bearbeiten)

                e_pv = st.checkbox("PV-Anlage vorhanden", value=bool(sel_gebaeude.get("pv_anlage")), disabled=not darf_bearbeiten)
                e_besonderheiten = st.text_area("Besonderheiten / Technische Infos", value=sel_gebaeude.get("besonderheiten") or "", disabled=not darf_bearbeiten)

                if darf_bearbeiten:
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        btn_save = st.form_submit_button("💾 Änderungen speichern", type="primary", use_container_width=True)
                    with col_b2:
                        btn_delete = st.form_submit_button("🗑️ Gebäude löschen", use_container_width=True)

                    if btn_save:
                        try:
                            supabase.table("gebaeude").update({
                                "strasse": e_strasse,
                                "hausnummer": e_hausnummer,
                                "ort": e_ort,
                                "gebaeude_code": e_code,
                                "wohneinheiten": e_we,
                                "baujahr": e_baujahr,
                                "bauart": e_bauart,
                                "energieart": e_energie,
                                "pv_anlage": e_pv,
                                "besonderheiten": e_besonderheiten
                            }).eq("id", sel_geb_id).execute()
                            st.success("Gebäudedaten erfolgreich aktualisiert!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")

                    if btn_delete:
                        try:
                            supabase.table("gebaeude").delete().eq("id", sel_geb_id).execute()
                            st.success("Gebäude wurde gelöscht!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Löschen: {e}")

            st.markdown("---")
            pdf_bytes = generate_gebaeude_pdf(sel_gebaeude)
            st.download_button(
                label=f"📥 Gebäude-Stammblatt für {sel_gebaeude.get('strasse')} als PDF herunterladen",
                data=bytes(pdf_bytes),
                file_name=f"Gebaeudestammblatt_{sel_gebaeude.get('ort')}_{sel_gebaeude.get('strasse')}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("Noch keine Gebäude im System hinterlegt. Legen Sie im zweiten Reiter Ihr erstes Gebäude an.")

    # --- TAB 2: Neues Gebäude ---
    if darf_erstellen and len(tabs) > 1:
        with tabs[1]:
            st.subheader("Neues Gebäude / Objekt anlegen")

            with st.form("neues_gebaeude_form"):
                col1, col2 = st.columns(2)
                with col1:
                    n_strasse = st.text_input("Straße *", placeholder="z.B. Hauptstraße")
                    n_hausnummer = st.text_input("Hausnummer *", placeholder="z.B. 12a")
                    n_ort = st.text_input("Ort *", placeholder="z.B. Bochum")
                    n_code = st.text_input("Gebäude-Code (optional)", placeholder="z.B. OBJEKT-104")
                with col2:
                    n_we = st.number_input("Wohneinheiten", min_value=1, value=1)
                    n_baujahr = st.number_input("Baujahr", min_value=1800, max_value=2030, value=2020)
                    n_bauart = st.selectbox("Bauart", ["Massivbau", "Fertighaus", "Altbau / Fachwerk", "Holzrahmenbau", "Sonstige"])
                    n_energie = st.selectbox("Energieart / Heizung", ["Wärmepumpe", "Gas", "Öl", "Fernwärme", "Elektro / Nachtspeicher", "Pellets / Biomasse"])

                n_pv = st.checkbox("PV-Anlage auf dem Dach vorhanden?")
                n_besonderheiten = st.text_area("Besonderheiten / Technische Infos (optional)", placeholder="z.B. Zählerschrank im Keller, PV-Wechselrichter in der Garage, Klingelanlage defekt...")

                if st.form_submit_button("Gebäude jetzt anlegen", type="primary", use_container_width=True):
                    if not n_strasse or not n_hausnummer or not n_ort:
                        st.warning("Bitte mindestens Straße, Hausnummer und Ort ausfüllen.")
                    else:
                        try:
                            data = {
                                "strasse": n_strasse,
                                "hausnummer": n_hausnummer,
                                "ort": n_ort,
                                "gebaeude_code": n_code,
                                "wohneinheiten": n_we,
                                "baujahr": n_baujahr,
                                "bauart": n_bauart,
                                "energieart": n_energie,
                                "pv_anlage": n_pv,
                                "besonderheiten": n_besonderheiten
                            }
                            supabase.table("gebaeude").insert(data).execute()
                            st.success(f"Gebäude {n_strasse} {n_hausnummer}, {n_ort} erfolgreich angelegt!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Anlegen: {e}")
