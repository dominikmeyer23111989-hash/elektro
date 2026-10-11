import streamlit as st
from datetime import date
import pandas as pd
from fpdf import FPDF
from io import BytesIO
from PIL import Image

ALL_MODULES = {
    "1": "1. Mitarbeiterverwaltung",
    "2": "2. Lagerverwaltung",
    "3": "3. Zeiterfassung",
    "4": "4. Aufträge",
    "5": "5. Kunden",
    "6": "6. Fahrzeuge",
    "7": "7. Gebäude",
    "8": "8. Dokumente",
    "9": "9. Finanzen / Monitor"
}

# -----------------------------------------------------------------------------
# Bildkomprimierung für Dokumente & Fotos
# -----------------------------------------------------------------------------
def compress_image(uploaded_file, max_width=1200, quality=75):
    if uploaded_file.type == "application/pdf":
        return uploaded_file.getvalue(), "application/pdf", uploaded_file.name

    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        
        base_name = uploaded_file.name.rsplit(".", 1)[0]
        new_filename = f"{base_name}_compressed.jpg"
        return output.getvalue(), "image/jpeg", new_filename
    except Exception:
        return uploaded_file.getvalue(), uploaded_file.type, uploaded_file.name

# -----------------------------------------------------------------------------
# PDF-Generator für die digitale Personalakte
# -----------------------------------------------------------------------------
class PersonalaktePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'ELEKTRO-ENTERPRISE - DIGITALE PERSONALAKTE', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 5, 'Vertrauliches Personaldokument (DSGVO-geschützt)', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def generate_mitarbeiter_pdf(mitarbeiter_data, qualifikationen):
    pdf = PersonalaktePDF()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)
    
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, f"{mitarbeiter_data.get('vorname')} {mitarbeiter_data.get('nachname')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 11)
    
    rolle_txt = "-"
    if mitarbeiter_data.get('rollen'):
        rolle_txt = str(mitarbeiter_data.get('rollen', {}).get('bezeichnung', '-'))

    fields = [
        ("Mitarbeiternummer:", str(mitarbeiter_data.get('mitarbeiternummer', '-'))),
        ("Rolle im Betrieb:", rolle_txt),
        ("Geburtsdatum:", str(mitarbeiter_data.get('geburtsdatum', '-'))),
        ("Tätig seit:", str(mitarbeiter_data.get('taetig_seit', '-'))),
        ("E-Mail:", str(mitarbeiter_data.get('email', '-'))),
        ("Telefon:", str(mitarbeiter_data.get('telefon', '-'))),
        ("Adresse:", str(mitarbeiter_data.get('adresse', '-'))),
        ("Status:", "Aktiv" if mitarbeiter_data.get('ist_aktiv') else "Inaktiv")
    ]
    
    pdf.ln(3)
    for label, val in fields:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(55, 6, label)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")
        
    pdf.ln(8)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, "Qualifikationen, Ausbildungen & Scheine", new_x="LMARGIN", new_y="NEXT")
    
    if qualifikationen:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(40, 6, "Kategorie", border=1)
        pdf.cell(60, 6, "Bezeichnung / Titel", border=1)
        pdf.cell(30, 6, "Erhalten am", border=1)
        pdf.cell(30, 6, "Gültig bis", border=1, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font('Helvetica', '', 9)
        for q in qualifikationen:
            pdf.cell(40, 6, str(q.get('kategorie', '')), border=1)
            pdf.cell(60, 6, str(q.get('titel', '')), border=1)
            pdf.cell(30, 6, str(q.get('datum_erhalten', '-')), border=1)
            pdf.cell(30, 6, str(q.get('gueltig_bis', '-')), border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 6, "Keine Qualifikationen / Scheine hinterlegt.", new_x="LMARGIN", new_y="NEXT")
        
    return pdf.output()

# -----------------------------------------------------------------------------
# Haupt-Rendering-Funktion für Modul 1
# -----------------------------------------------------------------------------
def render_mitarbeiter_verwaltung(supabase):
    st.title("👨‍💼 1. Mitarbeiterverwaltung")
    
    tab_uebersicht, tab_neu, tab_rollen, tab_qualifikationen = st.tabs([
        "📋 Mitarbeiterübersicht", 
        "➕ Neuer Mitarbeiter", 
        "🔑 Rollen & Rechte", 
        "📜 Qualifikationen & Scheine"
    ])
    
    # -------------------------------------------------------------------------
    # TAB 1: Mitarbeiterübersicht & PDF-Export
    # -------------------------------------------------------------------------
    with tab_uebersicht:
        st.subheader("Personalstamm")
        try:
            res = supabase.table("mitarbeiter").select("*, rollen(*)").execute()
            mitarbeiter_liste = res.data or []
            
            if mitarbeiter_liste:
                display_df = pd.DataFrame([{
                    "Nr": m.get("mitarbeiternummer"),
                    "Name": f"{m.get('vorname')} {m.get('nachname')}",
                    "Rolle": m.get("rollen", {}).get("bezeichnung", "-") if m.get("rollen") else "-",
                    "Tätig seit": m.get("taetig_seit", "-"),
                    "Geburtsdatum": m.get("geburtsdatum", "-"),
                    "Telefon": m.get("telefon", "-"),
                    "Status": "🟢 Aktiv" if m.get("ist_aktiv") else "🔴 Inaktiv"
                } for m in mitarbeiter_liste])
                
                st.dataframe(display_df, width="stretch")
                
                st.markdown("---")
                st.subheader("📄 Personalakte als PDF exportieren")
                
                selected_ma_id = st.selectbox(
                    "Mitarbeiter auswählen", 
                    options=[m["id"] for m in mitarbeiter_liste],
                    format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in mitarbeiter_liste if m["id"] == x)
                )
                
                selected_ma = next(m for m in mitarbeiter_liste if m["id"] == selected_ma_id)
                q_res = supabase.table("qualifikationen").select("*").eq("mitarbeiter_id", selected_ma_id).execute()
                qualis = q_res.data or []
                
                pdf_bytes = generate_mitarbeiter_pdf(selected_ma, qualis)
                
                st.download_button(
                    label=f"📥 Personalakte von {selected_ma['vorname']} {selected_ma['nachname']} herunterladen (PDF)",
                    data=bytes(pdf_bytes),
                    file_name=f"Personalakte_{selected_ma['mitarbeiternummer']}_{selected_ma['nachname']}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            else:
                st.info("Noch keine Mitarbeiter erfasst.")
        except Exception as e:
            st.error(f"Fehler beim Laden der Mitarbeiter: {e}")

    # -------------------------------------------------------------------------
    # TAB 2: Neuer Mitarbeiter anlegen
    # -------------------------------------------------------------------------
    with tab_neu:
        st.subheader("Neuen Mitarbeiter im System anlegen")
        
        try:
            rollen_res = supabase.table("rollen").select("*").execute()
            rollen_dict = {r["bezeichnung"]: r["id"] for r in rollen_res.data} if rollen_res.data else {}
        except Exception:
            rollen_dict = {}
        
        with st.form("neuer_mitarbeiter_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                mitarbeiternr = st.text_input("Mitarbeiternummer *", placeholder="z. B. 1005")
                vorname = st.text_input("Vorname *")
                nachname = st.text_input("Nachname *")
                geburtsdatum = st.date_input("Geburtsdatum", value=date(1990, 1, 1), format="DD.MM.YYYY")
                taetig_seit = st.date_input("Im Unternehmen tätig seit", value=date.today(), format="DD.MM.YYYY")
                
            with col2:
                rolle_bezeichnung = st.selectbox(
                    "Rolle / Funktion im Unternehmen *", 
                    list(rollen_dict.keys()) if rollen_dict else ["Keine Rolle vorhanden"]
                )
                passwort = st.text_input("Erst-Passwort / PIN *", type="password", help="Wird dem Mitarbeiter mitgeteilt.")
                notfall_pin = st.text_input("4-stellige Notfall-PIN", type="password", max_chars=4, placeholder="z. B. 4321")
                email = st.text_input("E-Mail-Adresse (optional)")
                telefon = st.text_input("Telefonnummer (optional)")
                adresse = st.text_area("Anschrift (optional)")
                
            submitted = st.form_submit_button("Mitarbeiter anlegen", type="primary", width="stretch")
            
            if submitted:
                if not mitarbeiternr or not vorname or not nachname or not passwort or not rollen_dict:
                    st.warning("Bitte füllen Sie alle Pflichtfelder (*) aus und legen Sie vorher mindestens eine Rolle an.")
                else:
                    try:
                        rec_code = f"REC-{mitarbeiternr}-88"
                        data = {
                            "mitarbeiternummer": mitarbeiternr,
                            "vorname": vorname,
                            "nachname": nachname,
                            "geburtsdatum": str(geburtsdatum),
                            "taetig_seit": str(taetig_seit),
                            "rolle_id": rollen_dict.get(rolle_bezeichnung),
                            "pin_hash": passwort,
                            "notfall_pin": notfall_pin,
                            "recovery_code": rec_code,
                            "email": email,
                            "telefon": telefon,
                            "adresse": adresse,
                            "ist_aktiv": True
                        }
                        supabase.table("mitarbeiter").insert(data).execute()
                        st.success(f"Mitarbeiter {vorname} {nachname} ({mitarbeiternr}) erfolgreich angelegt!")
                        st.info(f"💡 Generierter Recovery-Code für Notfälle: `{rec_code}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Anlegen: {e}")

    # -------------------------------------------------------------------------
    # TAB 3: Vollständig freie Rollen- & Rechteverwaltung
    # -------------------------------------------------------------------------
    with tab_rollen:
        st.subheader("🔑 Dynamische Rollen- & Rechteverwaltung")
        st.caption("Erstellen Sie neue Betriebrollen (z. B. Bauleiter, Azubi, Monteur) komplett frei und bestimmen Sie per Checkbox, welche Module diese sehen dürfen.")

        # 1. Neue Rolle anlegen
        with st.expander("➕ Neue Rolle im System erstellen", expanded=False):
            with st.form("neue_rolle_form"):
                n_bezeichnung = st.text_input("Rollenbezeichnung *", placeholder="z. B. Kundendienst-Techniker")
                n_ebene = st.text_input("Bereich / Ebene (optional)", placeholder="z. B. baustelle oder buero")
                
                st.markdown("**Ersterlaubte Module für diese Rolle auswählen:**")
                col_r1, col_r2 = st.columns(2)
                initial_selected = []
                for idx, (m_k, m_t) in enumerate(ALL_MODULES.items()):
                    target_col = col_r1 if idx < 5 else col_r2
                    if target_col.checkbox(m_t, value=(m_k in ["3", "8"]), key=f"new_role_mod_{m_k}"):
                        initial_selected.append(m_k)

                if st.form_submit_button("Neue Rolle speichern", type="primary"):
                    if not n_bezeichnung:
                        st.warning("Bitte geben Sie eine Rollenbezeichnung ein.")
                    else:
                        try:
                            payload = {
                                "bezeichnung": n_bezeichnung,
                                "erlaubte_menues": initial_selected
                            }
                            if n_ebene.strip():
                                payload["ebene"] = n_ebene.strip()
                            
                            supabase.table("rollen").insert(payload).execute()
                            st.success(f"Rolle '{n_bezeichnung}' erfolgreich erstellt!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Speichern der Rolle: {e}")

        st.markdown("---")

        # 2. Bestehende Rollen bearbeiten oder löschen
        try:
            rollen_data = supabase.table("rollen").select("*").execute().data or []
        except Exception:
            rollen_data = []

        if not rollen_data:
            st.info("Noch keine eigenen Rollen im System vorhanden. Erstellen Sie oben Ihre erste Rolle.")
        else:
            selected_rolle_name = st.selectbox(
                "Rolle auswählen zum Bearbeiten oder Löschen", 
                options=[r["bezeichnung"] for r in rollen_data]
            )
            
            current_role_obj = next((r for r in rollen_data if r["bezeichnung"] == selected_rolle_name), None)
            
            if current_role_obj:
                st.markdown(f"#### Rechte bearbeiten für: **{current_role_obj['bezeichnung']}**")
                
                current_allowed = current_role_obj.get("erlaubte_menues", [])
                new_allowed = []
                
                col_a, col_b = st.columns(2)
                for idx, (mod_key, mod_title) in enumerate(ALL_MODULES.items()):
                    target_col = col_a if idx < 5 else col_b
                    is_checked = target_col.checkbox(
                        mod_title, 
                        value=(mod_key in current_allowed), 
                        key=f"perm_edit_{current_role_obj['id']}_{mod_key}"
                    )
                    if is_checked:
                        new_allowed.append(mod_key)
                        
                c_save, c_del = st.columns([3, 1])
                with c_save:
                    if st.button("💾 Berechtigungen aktualisieren", type="primary", width="stretch"):
                        try:
                            supabase.table("rollen").update({"erlaubte_menues": new_allowed}).eq("id", current_role_obj["id"]).execute()
                            st.success(f"Rechte für Rolle '{selected_rolle_name}' aktualisiert!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")
                
                with c_del:
                    if st.button("🗑️ Rolle löschen", width="stretch"):
                        try:
                            supabase.table("rollen").delete().eq("id", current_role_obj["id"]).execute()
                            st.success(f"Rolle '{selected_rolle_name}' gelöscht.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Löschen (wird evt. noch von Mitarbeitern verwendet): {e}")

    # -------------------------------------------------------------------------
    # TAB 4: Qualifikationen & Scheine eintragen
    # -------------------------------------------------------------------------
    with tab_qualifikationen:
        st.subheader("Qualifikationen, Fortbildungen & Scheine")
        
        try:
            ma_res = supabase.table("mitarbeiter").select("id, vorname, nachname, mitarbeiternummer").execute()
            ma_list = ma_res.data or []
        except Exception:
            ma_list = []
        
        if ma_list:
            sel_ma_id = st.selectbox(
                "Mitarbeiter wählen", 
                options=[m["id"] for m in ma_list],
                format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in ma_list if m["id"] == x),
                key="qual_ma_select"
            )
            
            st.markdown("---")
            st.markdown("#### ➕ Neue Qualifikation / Schein erfassen")
            
            with st.form("qualifikation_form"):
                kategorie = st.selectbox("Kategorie", ["Ausbildung", "Weiterbildung", "Zertifikat / Schein", "Sonstiges"])
                titel = st.text_input("Bezeichnung / Titel *", placeholder="z. B. Ersthelfer, DGUV V3 Prüfschein")
                
                col_d1, col_d2 = st.columns(2)
                datum_erhalten = col_d1.date_input("Erhalten am", value=date.today(), format="DD.MM.YYYY")
                gueltig_bis = col_d2.date_input("Gültig bis (optional)", value=None, format="DD.MM.YYYY")
                
                beschreibung = st.text_area("Freitext / Anmerkung (optional)")
                uploaded_file = st.file_uploader("Upload Nachweis-Foto oder PDF (optional)", type=["png", "jpg", "jpeg", "pdf"])
                
                submit_q = st.form_submit_button("Qualifikation speichern", type="primary", width="stretch")
                
                if submit_q:
                    if not titel:
                        st.warning("Bitte geben Sie einen Titel an.")
                    else:
                        file_url = None
                        if uploaded_file is not None:
                            try:
                                file_bytes, content_type, file_name = compress_image(uploaded_file)
                                file_path = f"{sel_ma_id}/{file_name}"
                                supabase.storage.from_("mitarbeiter-dokumente").upload(
                                    file_path, 
                                    file_bytes, 
                                    {"content-type": content_type, "upsert": "true"}
                                )
                                file_url = supabase.storage.from_("mitarbeiter-dokumente").get_public_url(file_path)
                            except Exception as e_up:
                                st.warning(f"Upload konnte nicht durchgeführt werden: {e_up}")

                        q_data = {
                            "mitarbeiter_id": sel_ma_id,
                            "kategorie": kategorie,
                            "titel": titel,
                            "datum_erhalten": str(datum_erhalten) if datum_erhalten else None,
                            "gueltig_bis": str(gueltig_bis) if gueltig_bis else None,
                            "beschreibung": beschreibung,
                            "dokument_url": file_url
                        }
                        supabase.table("qualifikationen").insert(q_data).execute()
                        st.success("Qualifikation erfolgreich eingetragen!")
                        st.rerun()

            st.markdown("---")
            st.markdown("#### 📜 Hinterlegte Qualifikationen")
            try:
                existing_q = supabase.table("qualifikationen").select("*").eq("mitarbeiter_id", sel_ma_id).execute().data or []
            except Exception:
                existing_q = []

            if existing_q:
                for q in existing_q:
                    with st.expander(f"{q['kategorie']}: {q['titel']} (Erhalten: {q.get('datum_erhalten', '-')})"):
                        st.write(f"**Gültig bis:** {q.get('gueltig_bis', 'Unbefristet')}")
                        st.write(f"**Beschreibung:** {q.get('beschreibung', '-')}")
                        if q.get("dokument_url"):
                            st.markdown(f"[📄 Nachweis-Dokument / Foto öffnen]({q['dokument_url']})")
            else:
                st.info("Für diesen Mitarbeiter wurden noch keine Qualifikationen erfasst.")
