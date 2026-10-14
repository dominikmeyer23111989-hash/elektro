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

def render_rechnungen_verwaltung(supabase):
    st.title("💶 11. Rechnungs- & Abrechnungsmodul")
    st.caption("Verwalten Sie den Preiskatalog, rechnen Sie Aufträge ab und exportieren Sie Rechnungen als PDF.")

    # 1. Daten robust laden
    try:
        r_res = supabase.table("rechnungen").select("*").order("erstellt_am", desc=True).execute()
        rechnungen_liste = r_res.data or []
    except Exception:
        rechnungen_liste = []

    try:
        vorlagen_res = supabase.table("rechnung_vorlagen").select("*").order("bezeichnung").execute()
        vorlagen_liste = vorlagen_res.data or []
        vorlagen_lager_map = {v["material_id"]: float(v["einzelpreis_netto"]) for v in vorlagen_liste if v.get("material_id")}
    except Exception:
        vorlagen_liste = []
        vorlagen_lager_map = {}

    try:
        k_res = supabase.table("kunden").select("id, vorname, nachname").execute()
        kunden_dict = {k["id"]: f"{k.get('vorname', '')} {k.get('nachname', '')}".strip() for k in (k_res.data or [])}
    except Exception:
        kunden_dict = {}

    try:
        mat_res = supabase.table("lager_material").select("id, bezeichnung, einheit, ist_bestand").order("bezeichnung").execute()
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
        "🚀 Aufträge & Lager abrechnen", 
        "⚙️ Standard-Preiskatalog & Lager-Preise"
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
                    pdf_bytes = generate_rechnung_pdf(r, positionen)
                    st.download_button(
                        label=f"📥 Rechnungs-PDF herunterladen ({r.get('rechnungsnummer')})",
                        data=bytes(pdf_bytes),
                        file_name=f"Rechnung_{r.get('rechnungsnummer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_rech_{r['id']}"
                    )

    # =========================================================================
    # TAB 2: AUFTRÄGE & LAGER ABRECHNEN
    # =========================================================================
    with tabs[1]:
        st.subheader("Auftrag & Lager-Material in Rechnung übernehmen")
        st.caption("Wählen Sie einen Auftrag aus. Die App übernimmt den Arbeitsbericht und zieht automatisch die hinterlegten Verkaufspreise für verbrauchte Lagerartikel.")

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

                st.success(f"Auftrag {ausgewaehlter_auftrag.get('auftragsnummer')} (Status: {ausgewaehlter_auftrag.get('status')}) für Kunde **{k_name_auto}** ausgewählt.")
                st.write(f"📝 **Arbeitsbericht:** {ausgewaehlter_auftrag.get('arbeiten', '-')}")

                # Lager-Material des Auftrags laden
                try:
                    am_res = supabase.table("auftrag_material").select("*").eq("auftrag_id", ausgewaehlter_auftrag["id"]).execute()
                    auftrag_mat = am_res.data or []
                except Exception as e:
                    auftrag_mat = []
                    st.warning(f"Konnte Lager-Material nicht laden: {e}")

                if st.button("📥 Arbeitsbericht & verknüpftes Lager-Material laden", type="primary"):
                    st.session_state["rechnung_positionen_temp"] = []
                    
                    # 1. Arbeitsbericht als Position
                    st.session_state["rechnung_positionen_temp"].append({
                        "beschreibung": f"Arbeitsleistung gem. Auftragsbericht ({ausgewaehlter_auftrag.get('auftragsnummer')}): {ausgewaehlter_auftrag.get('arbeiten', '')}",
                        "menge": 1.0,
                        "einzelpreis_netto": 120.0
                    })

                    # 2. Lager- & Fremdmaterialien einfügen
                    if auftrag_mat:
                        for am in auftrag_mat:
                            if am.get("ist_fremdmaterial"):
                                bez = am.get("freitext_bezeichnung", "Fremdteil")
                                preis = 15.0
                            else:
                                mat_id = am.get("material_id")
                                mat_info = lager_dict.get(mat_id, {})
                                bez = mat_info.get("bezeichnung", "Lagerartikel")
                                preis = vorlagen_lager_map.get(mat_id, 10.0)
                            
                            st.session_state["rechnung_positionen_temp"].append({
                                "beschreibung": f"Material: {bez}",
                                "menge": float(am.get("menge", 1)),
                                "einzelpreis_netto": preis
                            })
                        st.success(f"{len(auftrag_mat)} Material-Position(en) aus dem Lager mit Preisen übernommen!")
                    else:
                        st.info("Dieser Auftrag hat keine verknüpften Lager-Materialien in 'auftrag_material'.")
                    
                    st.rerun()

        st.markdown("---")
        st.markdown("##### 🛠️ Rechnung bearbeiten, Preise anpassen & finalisieren")

        with st.form("neue_rechnung_form"):
            col1, col2 = st.columns(2)
            with col1:
                default_r_nr = f"RE-{datetime.now().strftime('%Y%m%d')}-01"
                r_nummer = st.text_input("Rechnungsnummer *", value=default_r_nr)
                r_kunde = st.text_input("Kundenname / Firma *", value=k_name_auto if 'k_name_auto' in locals() else "", placeholder="z. B. Hans Müller")
            with col2:
                r_mwst = st.number_input("Mehrwertsteuersatz (%)", min_value=0.0, value=19.0, step=0.5)

            st.markdown("##### Artikel aus Lager oder Vorlagen hinzufügen (Preise frei anpassbar)")
            
            katalog_optionen = [None] + [{"typ": "lager", "item": m} for m in lager_material_liste] + [{"typ": "vorlage", "item": v} for v in vorlagen_liste]
            sel_katalog_item = st.selectbox(
                "Artikel / Vorlage wählen",
                options=katalog_optionen,
                format_func=lambda x: "--- Artikel wählen ---" if x is None else (f"[Lager] {x['item']['bezeichnung']} (Bestand: {x['item']['ist_bestand']} {x['item'].get('einheit', 'Stk.')})" if x['typ'] == 'lager' else f"[Vorlage] {x['item']['bezeichnung']} ({x['item']['einzelpreis_netto']:.2f} EUR)")
            )

            # Automatischen Standardpreis als Vorschlag für das Inputfeld ermitteln
            default_preset_preis = 10.0
            if sel_katalog_item:
                item_data = sel_katalog_item["item"]
                if sel_katalog_item["typ"] == "lager":
                    default_preset_preis = vorlagen_lager_map.get(item_data["id"], 10.0)
                else:
                    default_preset_preis = float(item_data["einzelpreis_netto"])

            col_kat1, col_kat2, col_kat3 = st.columns(3)
            with col_kat1:
                kat_menge = st.number_input("Menge", min_value=0.1, value=1.0, step=0.5)
            with col_kat2:
                kat_preis_netto = st.number_input("Einzelpreis netto (EUR)", min_value=0.0, value=float(default_preset_preis), step=5.0)
            with col_kat3:
                st.write("")
                st.write("")
                btn_kat_add = st.form_submit_button("➕ Position hinzufügen", use_container_width=True)

            if btn_kat_add and sel_katalog_item:
                item_data = sel_katalog_item["item"]
                bez = item_data["bezeichnung"]

                st.session_state["rechnung_positionen_temp"].append({
                    "beschreibung": bez,
                    "menge": kat_menge,
                    "einzelpreis_netto": kat_preis_netto
                })
                st.rerun()

            st.markdown("---")
            st.markdown("##### Freie Position hinzufügen")
            p_beschr = st.text_input("Positionsbeschreibung", placeholder="z.B. Monteurstunde / Sonderarbeit")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                p_menge = st.number_input("Menge / Stunden", min_value=0.1, value=1.0, step=0.5, key="p_menge_neu")
            with col_p2:
                p_preis = st.number_input("Einzelpreis netto (EUR)", min_value=0.0, value=65.0, step=5.0, key="p_preis_neu")

            btn_add_pos = st.form_submit_button("➕ Freie Position hinzufügen", use_container_width=True)
            if btn_add_pos:
                if p_beschr.strip():
                    st.session_state["rechnung_positionen_temp"].append({
                        "beschreibung": p_beschr.strip(),
                        "menge": p_menge,
                        "einzelpreis_netto": p_preis
                    })
                    st.rerun()

            submitted_rechnung = st.form_submit_button("💾 Rechnung speichern & ausstellen", type="primary", use_container_width=True)

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
    # TAB 3: STANDARD-PREISKATALOG & LAGER-PREISE
    # =========================================================================
    with tabs[2]:
        st.subheader("⚙️ Standard-Preiskatalog & Lager-Preise verknüpfen")
        st.caption("Hier definieren Sie feste Verkaufspreise. Sie können entweder einen echten **Lager-Artikel** auswählen und mit einem Preis versehen oder freie Vorlagen anlegen.")

        with st.form("neue_vorlage_form"):
            st.markdown("##### Option A: Fester Verkaufspreis für einen Lager-Artikel")
            sel_lager_artikel = st.selectbox(
                "Lager-Artikel auswählen (optional)",
                options=[None] + lager_material_liste,
                format_func=lambda x: "--- Kein Lagerartikel (Freie Vorlage unten) ---" if x is None else f"{x['bezeichnung']} (Bestand: {x['ist_bestand']} {x.get('einheit', 'Stk.')})"
            )

            st.markdown("---")
            st.markdown("##### Option B: Allgemeine Vorlage (z.B. Arbeitszeit, Pauschale)")
            v_bech_frei = st.text_input("Bezeichnung / Name", placeholder="z. B. Monteurstunde Standard oder NYM-Leitung 3x1.5")
            
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                v_kat = st.selectbox("Kategorie", ["Arbeitszeit", "Material", "Pauschale"])
            with col_v2:
                v_einh = st.text_input("Einheit", value="Stk.")
            with col_v3:
                v_preis = st.number_input("Nettopreis (EUR) *", min_value=0.0, value=65.0, step=5.0)

            btn_save_vorl = st.form_submit_button("➕ Preisvorlage speichern", type="primary", use_container_width=True)
            if btn_save_vorl:
                if sel_lager_artikel:
                    final_bez = sel_lager_artikel["bezeichnung"]
                    final_einh = sel_lager_artikel.get("einheit", "Stk.")
                    final_mat_id = sel_lager_artikel["id"]
                    final_kat = "Material"
                else:
                    final_bez = v_bech_frei.strip()
                    final_einh = v_einh
                    final_mat_id = None
                    final_kat = v_kat

                if final_bez:
                    try:
                        supabase.table("rechnung_vorlagen").insert({
                            "bezeichnung": final_bez,
                            "kategorie": final_kat,
                            "einheit": final_einh,
                            "einzelpreis_netto": v_preis,
                            "material_id": final_mat_id
                        }).execute()
                        st.success(f"Preis für '{final_bez}' ({v_preis:.2f} EUR) erfolgreich gespeichert!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")
                else:
                    st.warning("Bitte wählen Sie einen Lagerartikel aus oder geben Sie eine freie Bezeichnung ein.")

        st.markdown("---")
        st.markdown("##### 📋 Aktive Preisvorlagen & verknüpfte Lagerpreise")
        if vorlagen_liste:
            df_vorlagen = pd.DataFrame([{
                "ID": v["id"],
                "Bezeichnung": v["bezeichnung"],
                "Kategorie": v["kategorie"],
                "Einheit": v["einheit"],
                "Lager-Verknüpfung": "Ja 🔗" if v.get("material_id") else "Nein (Frei)",
                "Preis (Netto)": f"{float(v['einzelpreis_netto']):.2f} EUR"
            } for v in vorlagen_liste])
            st.dataframe(df_vorlagen, use_container_width=True, hide_index=True)
            
            del_id = st.selectbox("Vorlage zum Löschen auswählen", options=[None] + [v["id"] for v in vorlagen_liste], format_func=lambda x: "--- Bitte wählen ---" if x is None else next((v["bezeichnung"] for v in vorlagen_liste if v["id"] == x), ""))
            if st.button("🗑️ Ausgewählte Vorlage löschen"):
                if del_id:
                    try:
                        supabase.table("rechnung_vorlagen").delete().eq("id", del_id).execute()
                        st.success("Vorlagen-Eintrag gelöscht!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")
        else:
            st.info("Noch keine Preisvorlagen angelegt.")
