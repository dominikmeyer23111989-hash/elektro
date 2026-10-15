import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from zoneinfo import ZoneInfo
from io import BytesIO
import base64
import tempfile
import os

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

def add_signature_to_pdf(pdf, sig_base64, label):
    if not sig_base64:
        return
    try:
        sig_str = str(sig_base64)
        if "," in sig_str:
            sig_str = sig_str.split(",")[1]
        img_data = base64.b64decode(sig_str)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(img_data)
            tmp_path = tmp.name
        
        pdf.ln(3)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, clean_text(label), new_x="LMARGIN", new_y="NEXT")
        pdf.image(tmp_path, w=45)
        os.unlink(tmp_path)
    except Exception:
        pass

def generate_rechnung_pdf(rechnung, positionen, auftrag_rec=None):
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

    # Auftragsdetails & Unterschriften im PDF einbetten, falls verknüpft
    if auftrag_rec:
        pdf.ln(8)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, clean_text(f"Auftragsreferenz: #{auftrag_rec.get('auftragsnummer', '-')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, clean_text(f"Arbeitsbericht: {auftrag_rec.get('arbeiten', '-')}"))
        
        kunde_sig = auftrag_rec.get('kunde_unterschrift')
        ma_sig = auftrag_rec.get('mitarbeiter_unterschrift')
        
        if kunde_sig or ma_sig:
            pdf.ln(4)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(0, 5, clean_text("Abnahmeprotokoll & Unterschriften:"), new_x="LMARGIN", new_y="NEXT")
            if kunde_sig:
                add_signature_to_pdf(pdf, kunde_sig, "Unterschrift Kunde (Abnahme):")
            if ma_sig:
                add_signature_to_pdf(pdf, ma_sig, "Unterschrift Monteur (Ausführung):")

    return pdf.output()

def render_rechnungen_verwaltung(supabase):
    st.title("💶 11. Rechnungs- & Abrechnungsmodul")
    st.caption("Verwalten Sie den zentralen Preiskatalog, rechnen Sie Aufträge transparent ab und exportieren Sie professionelle Rechnungs-PDFs.")

    # 1. Daten robust laden
    try:
        r_res = supabase.table("rechnungen").select("*").order("erstellt_am", desc=True).execute()
        rechnungen_liste = r_res.data or []
    except Exception:
        rechnungen_liste = []

    try:
        vorlagen_res = supabase.table("rechnung_vorlagen").select("*").order("bezeichnung").execute()
        vorlagen_liste = vorlagen_res.data or []
        vorlagen_lager_map = {str(v["material_id"]): v for v in vorlagen_liste if v.get("material_id")}
    except Exception:
        vorlagen_liste = []
        vorlagen_lager_map = {}

    try:
        k_res = supabase.table("kunden").select("id, vorname, nachname").execute()
        kunden_dict = {k["id"]: f"{k.get('vorname', '')} {k.get('nachname', '')}".strip() for k in (k_res.data or [])}
    except Exception:
        kunden_dict = {}

    try:
        mat_res = supabase.table("lager_material").select("id, bezeichnung, einheit, ist_bestand, artikelnummer").order("bezeichnung").execute()
        lager_material_liste = mat_res.data or []
        lager_dict = {m["id"]: m for m in lager_material_liste}
    except Exception:
        lager_material_liste = []
        lager_dict = {}

    try:
        a_res = supabase.table("auftraege").select("*").order("erstellt_am", desc=True).execute()
        alle_auftraege = a_res.data or []
    except Exception as e:
        alle_auftraege = []
        st.error(f"Fehler beim Laden der Aufträge: {e}")

    tabs = st.tabs([
        "📄 Rechnungsübersicht & Filter", 
        "🚀 Aufträge transparent abrechnen", 
        "⚙️ Zentraler Preiskatalog"
    ])

    # =========================================================================
    # TAB 1: RECHNUNGSÜBERSICHT & FILTER
    # =========================================================================
    with tabs[0]:
        st.subheader("Übersicht aller Rechnungen")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            such_text = st.text_input("🔍 Suche nach Rechnungsnummer oder Kunden", placeholder="z. B. RE-2026 oder Müller")
        with col_f2:
            status_filter = st.selectbox("Status-Filter", ["Alle", "Offen", "Bezahlt", "Storniert"])

        gefilterte_rechnungen = []
        for r in rechnungen_liste:
            if status_filter != "Alle" and r.get("status") != status_filter:
                continue
            if such_text:
                txt = such_text.lower()
                r_nr = str(r.get("rechnungsnummer", "")).lower()
                k_name = str(r.get("kunde_name", "")).lower()
                if txt not in r_nr and txt not in k_name:
                    continue
            gefilterte_rechnungen.append(r)

        if not gefilterte_rechnungen:
            st.info("Keine Rechnungen gefunden.")
        else:
            for r in gefilterte_rechnungen:
                try:
                    pos_res = supabase.table("rechnungspositionen").select("*").eq("rechnung_id", r["id"]).execute()
                    positionen = pos_res.data or []
                except Exception:
                    positionen = []

                # Zugehörigen Auftrag laden, falls vorhanden
                auftrag_rec = None
                if r.get("auftrag_id"):
                    try:
                        a_match = supabase.table("auftraege").select("*").eq("id", r["auftrag_id"]).execute()
                        if a_match.data:
                            auftrag_rec = a_match.data[0]
                    except Exception:
                        pass

                netto = sum(float(p.get("menge", 1)) * float(p.get("einzelpreis_netto", 0)) for p in positionen)
                mwst = netto * (float(r.get("mwst_satz", 19.0)) / 100.0)
                brutto = netto + mwst

                status = r.get('status', 'Offen')
                status_icon = "🟢 Bezahlt" if status == "Bezahlt" else ("🔴 Offen" if status == "Offen" else "⚪ Storniert")

                with st.expander(f"Rechnung #{r.get('rechnungsnummer')} | Kunde: {r.get('kunde_name')} | Brutto: {brutto:.2f} EUR | {status_icon}"):
                    col_det1, col_det2 = st.columns(2)
                    with col_det1:
                        st.write(f"**Rechnungsdatum:** {r.get('rechnungs_datum')}")
                        st.write(f"**MwSt.-Satz:** {r.get('mwst_satz')}%")
                    with col_det2:
                        neuer_status = st.selectbox("Status ändern", ["Offen", "Bezahlt", "Storniert"], index=["Offen", "Bezahlt", "Storniert"].index(status) if status in ["Offen", "Bezahlt", "Storniert"] else 0, key=f"status_sel_{r['id']}")
                        if neuer_status != status:
                            try:
                                supabase.table("rechnungen").update({"status": neuer_status}).eq("id", r["id"]).execute()
                                st.toast("Status aktualisiert!", icon="✅")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler: {e}")

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
                    pdf_bytes = generate_rechnung_pdf(r, positionen, auftrag_rec)
                    st.download_button(
                        label=f"📥 Rechnungs-PDF herunterladen ({r.get('rechnungsnummer')})",
                        data=bytes(pdf_bytes),
                        file_name=f"Rechnung_{r.get('rechnungsnummer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_rech_{r['id']}"
                    )

    # =========================================================================
    # TAB 2: TRANSPARENTE AUFTRAGSABRECHNUNG
    # =========================================================================
    with tabs[1]:
        st.subheader("Auftrag & Lager-Material transparent abrechnen")
        st.caption("Wählen Sie einen Auftrag aus. Die App zeigt Ihnen exakt an, welche Arbeitsleistungen, Materialien und Unterschriften vorliegen.")

        if "rechnung_positionen_temp" not in st.session_state:
            st.session_state["rechnung_positionen_temp"] = []

        if not alle_auftraege:
            st.warning("⚠️ Keine Aufträge in der Datenbank gefunden.")
        else:
            def get_auftrag_label(a):
                k_name = kunden_dict.get(a.get("kunde_id"), "") or a.get("freitext_kunde") or "Unbekannter Kunde"
                status = a.get("status", "Unbekannt")
                return f"[{status}] Auftrag {a.get('auftragsnummer')} | Kunde: {k_name}"

            ausgewaehlter_auftrag = st.selectbox(
                "Auftrag auswählen",
                options=[None] + alle_auftraege,
                format_func=lambda x: "--- Auftrag wählen ---" if x is None else get_auftrag_label(x)
            )

            if ausgewaehlter_auftrag:
                k_name_auto = kunden_dict.get(ausgewaehlter_auftrag.get("kunde_id"), "") or ausgewaehlter_auftrag.get("freitext_kunde", "Kunde")

                with st.container(border=True):
                    st.markdown(f"#### 🔍 Auftragsdetails: #{ausgewaehlter_auftrag.get('auftragsnummer')}")
                    c_inf1, c_inf2 = st.columns(2)
                    with c_inf1:
                        st.write(f"**Kunde:** {k_name_auto}")
                        st.write(f"**Status:** {ausgewaehlter_auftrag.get('status')}")
                    with c_inf2:
                        has_k_sig = bool(ausgewaehlter_auftrag.get('kunde_unterschrift'))
                        has_m_sig = bool(ausgewaehlter_auftrag.get('mitarbeiter_unterschrift'))
                        st.write(f"**Unterschrift Kunde:** {'✅ Vorhanden' if has_k_sig else '❌ Fehlt'}")
                        st.write(f"**Unterschrift Monteur:** {'✅ Vorhanden' if has_m_sig else '❌ Fehlt'}")

                    st.markdown(f"**📝 Arbeitsbericht:**\n> {ausgewaehlter_auftrag.get('arbeiten', '-')}")

                    try:
                        am_res = supabase.table("auftrag_material").select("*").eq("auftrag_id", ausgewaehlter_auftrag["id"]).execute()
                        auftrag_mat = am_res.data or []
                    except Exception:
                        auftrag_mat = []

                    if auftrag_mat:
                        st.markdown("**📦 Im Auftrag erfasste Materialpositionen:**")
                        mat_preview_list = []
                        for am in auftrag_mat:
                            if am.get("ist_fremdmaterial"):
                                bez = am.get("freitext_bezeichnung", "Fremdteil")
                                preis = 15.0
                            else:
                                mat_id = am.get("material_id")
                                mat_info = lager_dict.get(mat_id, {})
                                bez = mat_info.get("bezeichnung", "Lagerartikel")
                                kat_item = vorlagen_lager_map.get(str(mat_id)) if mat_id else None
                                preis = float(kat_item["einzelpreis_netto"]) if kat_item else 10.0
                            
                            menge = float(am.get("menge", 1))
                            mat_preview_list.append({
                                "Material": bez,
                                "Menge": menge,
                                "Katalog-Preis (Netto)": f"{preis:.2f} €",
                                "Gesamt (Netto)": f"{menge * preis:.2f} €"
                            })
                        st.dataframe(pd.DataFrame(mat_preview_list), use_container_width=True, hide_index=True)
                    else:
                        st.info("ℹ️ Keine Lager-Materialien direkt an diesen Auftrag gekoppelt.")

                if st.button("📥 Obige Auftragsdaten & Material in Rechnungspositionen übernehmen", type="primary"):
                    st.session_state["rechnung_positionen_temp"] = []
                    
                    # 1. Arbeitsbericht als Position
                    st.session_state["rechnung_positionen_temp"].append({
                        "beschreibung": f"Arbeitsleistung gem. Auftragsbericht ({ausgewaehlter_auftrag.get('auftragsnummer')}): {ausgewaehlter_auftrag.get('arbeiten', '')}",
                        "menge": 1.0,
                        "einzelpreis_netto": 120.0
                    })

                    # 2. Materialpositionen übernehmen
                    if auftrag_mat:
                        for am in auftrag_mat:
                            if am.get("ist_fremdmaterial"):
                                bez = am.get("freitext_bezeichnung", "Fremdteil")
                                preis = 15.0
                            else:
                                mat_id = am.get("material_id")
                                mat_info = lager_dict.get(mat_id, {})
                                bez = mat_info.get("bezeichnung", "Lagerartikel")
                                kat_item = vorlagen_lager_map.get(str(mat_id)) if mat_id else None
                                preis = float(kat_item["einzelpreis_netto"]) if kat_item else 10.0
                            
                            st.session_state["rechnung_positionen_temp"].append({
                                "beschreibung": f"Material: {bez}",
                                "menge": float(am.get("menge", 1)),
                                "einzelpreis_netto": preis
                            })
                    st.success("Auftrag erfolgreich in die Rechnungspositionen übernommen!")
                    st.rerun()

        st.markdown("---")
        st.markdown("##### 🛠️ Rechnung bearbeiten & finalisieren")

        st.markdown("##### Zusätzlichen Artikel aus Lager oder Vorlagen hinzufügen")
        katalog_optionen = [None] + [{"typ": "lager", "item": m} for m in lager_material_liste] + [{"typ": "vorlage", "item": v} for v in vorlagen_liste if not v.get("material_id")]
        sel_katalog_item = st.selectbox(
            "Artikel / Vorlage wählen",
            options=katalog_optionen,
            format_func=lambda x: "--- Artikel wählen ---" if x is None else (f"[Lager] {x['item']['bezeichnung']} (Bestand: {x['item']['ist_bestand']} {x['item'].get('einheit', 'Stk.')})" if x['typ'] == 'lager' else f"[Vorlage] {x['item']['bezeichnung']} ({float(x['item']['einzelpreis_netto']):.2f} EUR)")
        )

        auto_preis = 0.0
        if sel_katalog_item:
            item_data = sel_katalog_item["item"]
            if sel_katalog_item["typ"] == "lager":
                kat_match = vorlagen_lager_map.get(str(item_data.get("id")))
                auto_preis = float(kat_match["einzelpreis_netto"]) if kat_match else 0.0
            else:
                auto_preis = float(item_data["einzelpreis_netto"])
            
            st.info(f"💡 Hinterlegter Katalogpreis: **{auto_preis:.2f} € netto**")

        col_kat1, col_kat2 = st.columns([2, 1])
        with col_kat1:
            kat_menge = st.number_input("Menge", min_value=0.1, value=1.0, step=0.5, key="kat_menge_inp")
        with col_kat2:
            st.write("")
            st.write("")
            if st.button("➕ Artikel hinzufügen", use_container_width=True):
                if sel_katalog_item:
                    item_data = sel_katalog_item["item"]
                    bez = item_data["bezeichnung"]
                    st.session_state["rechnung_positionen_temp"].append({
                        "beschreibung": bez,
                        "menge": kat_menge,
                        "einzelpreis_netto": auto_preis
                    })
                    st.success(f"'{bez}' hinzugefügt!")
                    st.rerun()
                else:
                    st.warning("Bitte wählen Sie zuerst einen Artikel aus.")

        st.markdown("---")
        st.markdown("##### Freie Position hinzufügen (mit manuellem Preis)")
        col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
        with col_p1:
            p_beschr = st.text_input("Positionsbeschreibung", placeholder="z.B. Monteurstunde / Sonderarbeit", key="frei_beschr_inp")
        with col_p2:
            p_menge = st.number_input("Menge / Std.", min_value=0.1, value=1.0, step=0.5, key="frei_menge_inp")
        with col_p3:
            p_preis = st.number_input("Netto-Preis (€)", min_value=0.0, value=65.0, step=5.0, key="frei_preis_inp")

        if st.button("➕ Freie Position hinzufügen", use_container_width=True):
            if p_beschr.strip():
                st.session_state["rechnung_positionen_temp"].append({
                    "beschreibung": p_beschr.strip(),
                    "menge": p_menge,
                    "einzelpreis_netto": p_preis
                })
                st.success("Freie Position hinzugefügt!")
                st.rerun()
            else:
                st.warning("Bitte eine Positionsbeschreibung angeben.")

        st.markdown("---")

        if st.session_state["rechnung_positionen_temp"]:
            st.markdown("##### 📋 Aktuelle Rechnungspositionen:")
            
            idx_to_del = None
            for idx, p in enumerate(st.session_state["rechnung_positionen_temp"]):
                c_p1, c_p2, c_p3, c_p4 = st.columns([4, 2, 2, 1])
                c_p1.write(f"**{p['beschreibung']}**")
                c_p2.write(f"{p['menge']} Stk./Std.")
                c_p3.write(f"{p['einzelpreis_netto']:.2f} € netto")
                if c_p4.button("🗑️", key=f"del_pos_{idx}"):
                    idx_to_del = idx

            if idx_to_del is not None:
                st.session_state["rechnung_positionen_temp"].pop(idx_to_del)
                st.rerun()

            if st.button("🗑️ Alle Positionen löschen"):
                st.session_state["rechnung_positionen_temp"] = []
                st.rerun()
        else:
            st.info("Noch keine Positionen hinzugefügt.")

        st.markdown("---")

        with st.form("neue_rechnung_form"):
            st.markdown("##### 💾 Rechnung finalisieren & speichern")
            col1, col2 = st.columns(2)
            with col1:
                default_r_nr = f"RE-{datetime.now().strftime('%Y%m%d')}-01"
                r_nummer = st.text_input("Rechnungsnummer *", value=default_r_nr)
                r_kunde = st.text_input("Kundenname / Firma *", value=k_name_auto if 'k_name_auto' in locals() else "", placeholder="z. B. Hans Müller")
            with col2:
                r_mwst = st.number_input("Mehrwertsteuersatz (%)", min_value=0.0, value=19.0, step=0.5)

            submitted_rechnung = st.form_submit_button("💾 Rechnung speichern & ausstellen", type="primary", use_container_width=True)

            if submitted_rechnung:
                if not r_nummer.strip() or not r_kunde.strip():
                    st.warning("Bitte Rechnungsnummer und Kundenname angeben.")
                elif not st.session_state["rechnung_positionen_temp"]:
                    st.warning("Bitte fügen Sie mindestens eine Position hinzu.")
                else:
                    try:
                        r_payload = {
                            "rechnungsnummer": r_nummer.strip(),
                            "auftrag_id": ausgewaehlter_auftrag["id"] if 'ausgewaehlter_auftrag' in locals() and ausgewaehlter_auftrag else None,
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

    # =========================================================================
    # TAB 3: ZENTRALER PREISKATALOG
    # =========================================================================
    with tabs[2]:
        st.subheader("⚙️ Zentraler Preiskatalog & Stammdaten")
        st.caption("Legen Sie hier alle Verkaufspreise fest und pflegen Sie Ihre allgemeinen Vorlagen.")

        tab_kat_lager, tab_kat_allg = st.tabs(["📦 Lager-Artikel Preise", "📋 Allgemeine Vorlagen"])

        # --- SUB-TAB 1: LAGER-ARTIKEL PREISE ---
        with tab_kat_lager:
            st.markdown("##### Feste Verkaufspreise für Ihre Lagerartikel definieren")
            if not lager_material_liste:
                st.info("Keine Artikel im Lager vorhanden.")
            else:
                for mat in lager_material_liste:
                    m_id = mat["id"]
                    existierende_vorlage = vorlagen_lager_map.get(str(m_id))
                    aktiver_preis = float(existierende_vorlage["einzelpreis_netto"]) if existierende_vorlage else 0.0

                    with st.form(f"form_lager_preis_{m_id}"):
                        col_lp1, col_lp2, col_lp3, col_lp4 = st.columns([3, 1, 2, 1])
                        with col_lp1:
                            st.write(f"**{mat['bezeichnung']}**")
                            st.caption(f"Art-Nr: {mat.get('artikelnummer', '-')} | Bestand: {mat.get('ist_bestand', 0)} {mat.get('einheit', 'Stk.')}")
                        with col_lp2:
                            st.write(f"Einheit: {mat.get('einheit', 'Stk.')}")
                        with col_lp3:
                             neuer_kat_preis = st.number_input(
                                "Netto-Verkaufspreis (€)",
                                min_value=0.0,
                                value=aktiver_preis,
                                step=1.0,
                                key=f"input_p_{m_id}",
                                label_visibility="collapsed"
                            )
                        with col_lp4:
                            b_save_p = st.form_submit_button("💾 Speichern", use_container_width=True)

                        if b_save_p:
                            try:
                                if existierende_vorlage:
                                    supabase.table("rechnung_vorlagen").update({
                                        "einzelpreis_netto": neuer_kat_preis,
                                        "einheit": mat.get('einheit', 'Stk.')
                                    }).eq("id", existierende_vorlage["id"]).execute()
                                else:
                                    supabase.table("rechnung_vorlagen").insert({
                                        "bezeichnung": mat["bezeichnung"],
                                        "kategorie": "Material",
                                        "einheit": mat.get('einheit', 'Stk.'),
                                        "einzelpreis_netto": neuer_kat_preis,
                                        "material_id": m_id
                                    }).execute()
                                st.toast(f"Preis für '{mat['bezeichnung']}' gespeichert!", icon="🎯")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler: {e}")

        # --- SUB-TAB 2: ALLGEMEINE VORLAGEN (NEU MIT BEARBEITUNGS- & KATEGORIE-FUNKTION) ---
        with tab_kat_allg:
            st.markdown("##### ➕ Neue allgemeine Vorlage anlegen")
            with st.form("neue_vorlage_form"):
                v_bech_frei = st.text_input("Bezeichnung *", placeholder="z. B. Monteurstunde Standard oder Anfahrtspauschale")
                col_v1, col_v2, col_v3 = st.columns(3)
                with col_v1:
                    v_kat = st.selectbox("Kategorie", ["Arbeitszeit", "Pauschale", "Sonstiges"])
                with col_v2:
                    v_einh = st.text_input("Einheit", value="Std.")
                with col_v3:
                    v_preis = st.number_input("Nettopreis (EUR) *", min_value=0.0, value=65.0, step=5.0)

                btn_save_vorl = st.form_submit_button("➕ Allgemeine Vorlage speichern", type="primary", use_container_width=True)
                if btn_save_vorl:
                    if v_bech_frei.strip():
                        try:
                            supabase.table("rechnung_vorlagen").insert({
                                "bezeichnung": v_bech_frei.strip(),
                                "kategorie": v_kat,
                                "einheit": v_einh,
                                "einzelpreis_netto": v_preis,
                                "material_id": None
                            }).execute()
                            st.success(f"Vorlage '{v_bech_frei.strip()}' erfolgreich gespeichert!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")
                    else:
                        st.warning("Bitte eine Bezeichnung eingeben.")

            st.markdown("---")
            st.markdown("##### ✏️ Vorhandene allgemeine Vorlagen bearbeiten oder löschen")
            freie_vorlagen = [v for v in vorlagen_liste if not v.get("material_id")]
            if freie_vorlagen:
                edit_sel_id = st.selectbox(
                    "Vorlage zum Bearbeiten auswählen", 
                    options=[None] + [v["id"] for v in freie_vorlagen], 
                    format_func=lambda x: "--- Bitte wählen ---" if x is None else next((f"{v['bezeichnung']} ({v['kategorie']} - {float(v['einzelpreis_netto']):.2f} €)" for v in freie_vorlagen if v["id"] == x), "")
                )
                
                if edit_sel_id:
                    selected_v = next((v for v in freie_vorlagen if v["id"] == edit_sel_id), None)
                    if selected_v:
                        with st.form(f"form_edit_vorlage_{edit_sel_id}"):
                            st.write(f"**Bearbeite Vorlage:** {selected_v['bezeichnung']}")
                            ed_bez = st.text_input("Bezeichnung", value=selected_v.get("bezeichnung", ""))
                            
                            kats = ["Arbeitszeit", "Pauschale", "Sonstiges"]
                            current_kat = selected_v.get("kategorie", "Arbeitszeit")
                            kat_idx = kats.index(current_kat) if current_kat in kats else 0
                            ed_kat = st.selectbox("Kategorie", kats, index=kat_idx)
                            
                            ed_einh = st.text_input("Einheit", value=selected_v.get("einheit", "Std."))
                            ed_preis = st.number_input("Nettopreis (EUR)", min_value=0.0, value=float(selected_v.get("einzelpreis_netto", 0.0)), step=5.0)
                            
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                btn_update = st.form_submit_button("💾 Änderungen speichern", type="primary", use_container_width=True)
                            with col_e2:
                                btn_delete = st.form_submit_button("🗑️ Vorlage löschen", use_container_width=True)
                                
                            if btn_update:
                                try:
                                    supabase.table("rechnung_vorlagen").update({
                                        "bezeichnung": ed_bez.strip(),
                                        "kategorie": ed_kat,
                                        "einheit": ed_einh,
                                        "einzelpreis_netto": ed_preis
                                    }).eq("id", edit_sel_id).execute()
                                    st.success("Vorlage erfolgreich aktualisiert!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler: {e}")
                                    
                            if btn_delete:
                                try:
                                    supabase.table("rechnung_vorlagen").delete().eq("id", edit_sel_id).execute()
                                    st.success("Vorlage gelöscht!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler: {e}")
            else:
                st.info("Noch keine allgemeinen Vorlagen angelegt.")
