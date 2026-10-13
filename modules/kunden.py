import streamlit as st
from datetime import date
import pandas as pd
from fpdf import FPDF
from io import BytesIO

class KundenPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - KUNDENSTAMMBLATT', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Kunden- und Projektdetails (DSGVO-konform)', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_kunden_pdf(k):
    pdf = KundenPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    pdf.set_font('Helvetica', 'B', 12)
    name_zeile = f"{k.get('firmenname') + ' - ' if k.get('firmenname') else ''}{k.get('vorname', '')} {k.get('nachname', '')}"
    pdf.cell(0, 6, clean_text(f"Kunde: {name_zeile}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, clean_text(f"Kundennummer: {k.get('kundennummer', '-') }"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    fields = [
        ("Firma:", str(k.get('firmenname', '-'))),
        ("Ansprechpartner:", f"{k.get('vorname', '')} {k.get('nachname', '')}".strip()),
        ("Anschrift:", f"{k.get('strasse', '-')}, {k.get('plz', '-')} {k.get('ort', '-')}" ),
        ("Telefon:", str(k.get('telefon', '-'))),
        ("E-Mail:", str(k.get('email', '-'))),
        ("Kunden seit:", str(k.get('erstellt_am', '-')[:10] if k.get('erstellt_am') else '-'))
    ]

    for label, val in fields:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, clean_text(label))
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, clean_text(val), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, "Interne Notizen / Besonderheiten:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 9)
    pdf.multi_cell(0, 5, clean_text(k.get('notizen', 'Keine Notizen hinterlegt.')))

    return pdf.output()

def hat_recht(modul_id, aktion="sehen"):
    """Prüft über die app.py-Logik, ob das Recht vorliegt."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_kunden_verwaltung(supabase):
    st.title("🏢 5. Kundenverwaltung")
    st.caption("Verwalten Sie hier Ihre Kunden, Kontaktdaten, Adressen und Projekthinweise.")

    if not hat_recht("5", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Kunden-Modul aufzurufen.")
        return

    darf_erstellen = hat_recht("5", "erstellen")
    darf_bearbeiten = hat_recht("5", "bearbeiten")

    # Tabs dynamisch aufbauen
    tabs_optionen = ["📋 Kundenübersicht & Details"]
    if darf_erstellen:
        tabs_optionen.append("➕ Neuen Kunden anlegen")

    tabs = st.tabs(tabs_optionen)

    # --- TAB 1: Übersicht & Details ---
    with tabs[0]:
        st.subheader("Alle gespeicherten Kunden")

        try:
            res = supabase.table("kunden").select("*").order("kundennummer").execute()
            kunden_liste = res.data or []
        except Exception as e:
            st.error(f"Fehler beim Laden der Kunden: {e}")
            kunden_liste = []

        if kunden_liste:
            suchbegriff = st.text_input("🔍 Kunden suchen (Name, Firma, Ort oder Nummer)", placeholder="z.B. Müller, Essen, K-1001")
            
            gefilterte_kunden = kunden_liste
            if suchbegriff:
                s = suchbegriff.lower()
                gefilterte_kunden = [
                    k for k in kunden_liste if 
                    s in str(k.get("kundennummer", "")).lower() or
                    s in str(k.get("firmenname", "")).lower() or
                    s in str(k.get("nachname", "")).lower() or
                    s in str(k.get("vorname", "")).lower() or
                    s in str(k.get("ort", "")).lower()
                ]

            display_df = pd.DataFrame([{
                "Nr.": k.get("kundennummer"),
                "Firma": k.get("firmenname") or "-",
                "Name": f"{k.get('vorname', '')} {k.get('nachname', '')}".strip(),
                "Ort": k.get("ort") or "-",
                "Telefon": k.get("telefon") or "-",
                "E-Mail": k.get("email") or "-"
            } for k in gefilterte_kunden])

            st.dataframe(display_df, use_container_width=True)

            st.markdown("---")
            st.subheader("⚙️ Kundendetails, Bearbeiten & Stammblatt")

            sel_kunden_id = st.selectbox(
                "Kunden für Details / Bearbeitung auswählen",
                options=[k["id"] for k in gefilterte_kunden],
                format_func=lambda x: next(f"{k['kundennummer']} - {k.get('firmenname') + ' (' if k.get('firmenname') else ''}{k['vorname']} {k['nachname']}{')' if k.get('firmenname') else ''}" for k in gefilterte_kunden if k["id"] == x)
            )

            sel_kunde = next(k for k in gefilterte_kunden if k["id"] == sel_kunden_id)

            if not darf_bearbeiten:
                st.info("ℹ️ Ihr Account hat nur Leserechte für Kunden. Sie können keine Änderungen speichern.")

            with st.form("kunde_edit_form"):
                st.write(f"Bearbeite Kunde: **{sel_kunde.get('kundennummer')} - {sel_kunde.get('nachname')}**")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    e_firma = st.text_input("Firmenname (optional)", value=sel_kunde.get("firmenname") or "", disabled=not darf_bearbeiten)
                    e_vorname = st.text_input("Vorname", value=sel_kunde.get("vorname") or "", disabled=not darf_bearbeiten)
                    e_nachname = st.text_input("Nachname *", value=sel_kunde.get("nachname") or "", disabled=not darf_bearbeiten)
                    e_strasse = st.text_input("Strasse & Hausnummer", value=sel_kunde.get("strasse") or "", disabled=not darf_bearbeiten)
                with col_e2:
                    e_plz = st.text_input("PLZ", value=sel_kunde.get("plz") or "", disabled=not darf_bearbeiten)
                    e_ort = st.text_input("Ort", value=sel_kunde.get("ort") or "", disabled=not darf_bearbeiten)
                    e_telefon = st.text_input("Telefon", value=sel_kunde.get("telefon") or "", disabled=not darf_bearbeiten)
                    e_email = st.text_input("E-Mail", value=sel_kunde.get("email") or "", disabled=not darf_bearbeiten)

                e_notizen = st.text_area("Interne Notizen / Baustellenhinweise", value=sel_kunde.get("notizen") or "", disabled=not darf_bearbeiten)

                if darf_bearbeiten:
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        btn_save = st.form_submit_button("💾 Änderungen speichern", type="primary", use_container_width=True)
                    with col_b2:
                        btn_delete = st.form_submit_button("🗑️ Kunde löschen", use_container_width=True)

                    if btn_save:
                        try:
                            supabase.table("kunden").update({
                                "firmenname": e_firma,
                                "vorname": e_vorname,
                                "nachname": e_nachname,
                                "strasse": e_strasse,
                                "plz": e_plz,
                                "ort": e_ort,
                                "telefon": e_telefon,
                                "email": e_email,
                                "notizen": e_notizen
                            }).eq("id", sel_kunden_id).execute()
                            st.success("Kundendaten erfolgreich aktualisiert!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")

                    if btn_delete:
                        try:
                            supabase.table("kunden").delete().eq("id", sel_kunden_id).execute()
                            st.success("Kunde wurde gelöscht!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Löschen: {e}")

            st.markdown("---")
            pdf_bytes = generate_kunden_pdf(sel_kunde)
            st.download_button(
                label=f"📥 Kundenstammblatt von {sel_kunde.get('nachname')} als PDF herunterladen",
                data=bytes(pdf_bytes),
                file_name=f"Kundenstammblatt_{sel_kunde.get('kundennummer')}_{sel_kunde.get('nachname')}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("Noch keine Kunden im System hinterlegt. Legen Sie im zweiten Reiter Ihren ersten Kunden an.")

    # --- TAB 2: Neuer Kunde ---
    if darf_erstellen and len(tabs) > 1:
        with tabs[1]:
            st.subheader("Neuen Kunden anlegen")

            with st.form("neuer_kunde_form"):
                col1, col2 = st.columns(2)
                with col1:
                    k_nr = st.text_input("Kundennummer *", placeholder="z.B. K-1001")
                    k_firma = st.text_input("Firmenname (optional)", placeholder="z.B. Elektro Müller GmbH")
                    k_vorname = st.text_input("Vorname", placeholder="Max")
                    k_nachname = st.text_input("Nachname *", placeholder="Mustermann")
                    k_strasse = st.text_input("Strasse & Hausnummer", placeholder="Musterstraße 12")
                with col2:
                    k_plz = st.text_input("PLZ", placeholder="44787")
                    k_ort = st.text_input("Ort", placeholder="Bochum")
                    k_telefon = st.text_input("Telefon", placeholder="0234 / 123456")
                    k_email = st.text_input("E-Mail", placeholder="kontakt@kunde.de")
                
                k_notizen = st.text_area("Interne Notizen / Baustellenhinweise (optional)", placeholder="z.B. Hinterhof, Klingel defekt, Schließfach-Code...")

                if st.form_submit_button("Kunden jetzt anlegen", type="primary", use_container_width=True):
                    if not k_nr or not k_nachname:
                        st.warning("Bitte mindestens Kundennummer und Nachname (oder Firmenname) ausfüllen.")
                    else:
                        try:
                            data = {
                                "kundennummer": k_nr,
                                "firmenname": k_firma,
                                "vorname": k_vorname,
                                "nachname": k_nachname,
                                "strasse": k_strasse,
                                "plz": k_plz,
                                "ort": k_ort,
                                "telefon": k_telefon,
                                "email": k_email,
                                "notizen": k_notizen
                            }
                            supabase.table("kunden").insert(data).execute()
                            st.success(f"Kunde {k_nr} - {k_nachname} erfolgreich angelegt!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Anlegen: {e}")
