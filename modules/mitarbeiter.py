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
    "4": "4. Anträge & Urlaub",
    "5": "5. Kunden",
    "6": "6. Fahrzeuge",
    "7": "7. Gebäude",
    "8": "8. Dokumente",
    "9": "9. Finanzen / Monitor"
}

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
        ("Urlaubstage / Jahr:", str(mitarbeiter_data.get('urlaubstage_gesamt', 30))),
        ("Wochenstunden:", f"{mitarbeiter_data.get('wochenstunden', 40.0)} Std."),
        ("Geburtsdatum:", str(mitarbeiter_data.get('geburtsdatum', '-'))),
        ("Tätig seit:", str(mitarbeiter_data.get('taetig_seit', '-'))),
        ("E-Mail:", str(mitarbeiter_data.get('email', '-'))),
        ("Telefon:", str(mitarbeiter_data.get('telefon', '-'))),
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

def render_mitarbeiter_verwaltung(supabase):
    st.title("👨‍💼 1. Mitarbeiterverwaltung")
    
    tab_uebersicht, tab_neu, tab_rollen, tab_qualifikationen = st.tabs([
        "📋 Personalstamm & Status", 
        "➕ Neuer Mitarbeiter", 
        "🔑 Rollen & Rechte", 
        "📜 Qualifikationen"
    ])
    
    # --- TAB 1: Übersicht & Bearbeiten ---
    with tab_uebersicht:
        st.subheader("Personalstamm, Arbeitszeiten & Urlaubsanspruch")
        try:
            res = supabase.table("mitarbeiter").select("*, rollen(*)").execute()
            mitarbeiter_liste = res.data or []
            
            if mitarbeiter_liste:
                display_df = pd.DataFrame([{
                    "Nr": m.get("mitarbeiternummer"),
                    "Name": f"{m.get('vorname')} {m.get('nachname')}",
                    "Rolle": m.get("rollen", {}).get("bezeichnung", "-") if m.get("rollen") else "-",
                    "Urlaub/Jahr": m.get("urlaubstage_gesamt", 30),
                    "Std/Woche": m.get("wochenstunden", 40.0),
                    "Status": "🟢 Aktiv" if m.get("ist_aktiv") else "🔴 Inaktiv"
                } for m in mitarbeiter_liste])
                
                st.dataframe(display_df, use_container_width=True)
                
                st.markdown("---")
                st.subheader("⚙️ Mitarbeiter-Details, Kontingente & Status bearbeiten")
                
                selected_ma_id = st.selectbox(
                    "Mitarbeiter auswählen", 
                    options=[m["id"] for m in mitarbeiter_liste],
                    format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in mitarbeiter_liste if m["id"] == x)
                )
                
                selected_ma = next(m for m in mitarbeiter_liste if m["id"] == selected_ma_id)

                with st.form("ma_edit_form"):
                    st.write(f"Bearbeite: **{selected_ma['vorname']} {selected_ma['nachname']}**")
                    
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        neuer_urlaub = st.number_input("Urlaubstage pro Jahr", min_value=0, max_value=60, value=int(selected_ma.get("urlaubstage_gesamt") or 30))
                        neue_wochenstunden = st.number_input("Wochenstunden (für Zeiterfassung)", min_value=0.0, max_value=60.0, value=float(selected_ma.get("wochenstunden") or 40.0), step=0.5)
                    with col_e2:
                        neuer_status = st.checkbox("Account ist aktiv (Login erlaubt)", value=selected_ma.get("ist_aktiv", True))
                    
                    if st.form_submit_button("Stammdaten aktualisieren", type="primary", use_container_width=True):
                        try:
                            supabase.table("mitarbeiter").update({
                                "urlaubstage_gesamt": neuer_urlaub,
                                "wochenstunden": neue_wochenstunden,
                                "ist_aktiv": neuer_status
                            }).eq("id", selected_ma_id).execute()
                            st.success("Stammdaten erfolgreich aktualisiert!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

                st.markdown("---")
                q_res = supabase.table("qualifikationen").select("*").eq("mitarbeiter_id", selected_ma_id).execute()
                pdf_bytes = generate_mitarbeiter_pdf(selected_ma, q_res.data or [])
                st.download_button(
                    label=f"📥 Personalakte von {selected_ma['vorname']} {selected_ma['nachname']} herunterladen (PDF)",
                    data=bytes(pdf_bytes),
                    file_name=f"Personalakte_{selected_ma['mitarbeiternummer']}_{selected_ma['nachname']}.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"Fehler: {e}")

    # --- TAB 2: Neuer Mitarbeiter ---
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
                urlaubstage = st.number_input("Urlaubstage pro Jahr", value=30, min_value=0, max_value=60)
                wochenstunden = st.number_input("Wochenstunden", value=40.0, min_value=0.0, max_value=60.0, step=0.5)
            with col2:
                rolle_bezeichnung = st.selectbox("Rolle / Funktion *", list(rollen_dict.keys()) if rollen_dict else ["Keine Rolle"])
                passwort = st.text_input("Erst-Passwort / PIN *", type="password")
                notfall_pin = st.text_input("4-stellige Notfall-PIN", type="password", max_chars=4)
                ist_aktiv_neu = st.checkbox("Account sofort aktivieren", value=True)
                email = st.text_input("E-Mail (optional)")
                telefon = st.text_input("Telefon (optional)")
                adresse = st.text_area("Anschrift (optional)")
                
            if st.form_submit_button("Mitarbeiter anlegen", type="primary", use_container_width=True):
                if not mitarbeiternr or not vorname or not nachname or not passwort:
                    st.warning("Bitte Pflichtfelder ausfüllen.")
                else:
                    try:
                        rec_code = f"REC-{mitarbeiternr}-88"
                        data = {
                            "mitarbeiternummer": mitarbeiternr,
                            "vorname": vorname,
                            "nachname": nachname,
                            "geburtsdatum": str(geburtsdatum),
                            "taetig_seit": str(taetig_seit),
                            "urlaubstage_gesamt": urlaubstage,
                            "wochenstunden": wochenstunden,
                            "rolle_id": rollen_dict.get(rolle_bezeichnung),
                            "pin_hash": passwort,
                            "notfall_pin": notfall_pin,
                            "recovery_code": rec_code,
                            "email": email,
                            "telefon": telefon,
                            "adresse": adresse,
                            "ist_aktiv": ist_aktiv_neu
                        }
                        supabase.table("mitarbeiter").insert(data).execute()
                        st.success(f"Mitarbeiter {vorname} {nachname} angelegt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")

    # --- TAB 3: Rollen ---
    with tab_rollen:
        st.subheader("🔑 Rollen & Rechteverwaltung")
        try:
            rollen_data = supabase.table("rollen").select("*").execute().data or []
        except Exception:
            rollen_data = []

        with st.expander("➕ Neue Rolle erstellen"):
            with st.form("neue_rolle"):
                r_bez = st.text_input("Rollenbezeichnung")
                r_sel = []
                col_r1, col_r2 = st.columns(2)
                for idx, (m_k, m_t) in enumerate(ALL_MODULES.items()):
                    if (col_r1 if idx < 5 else col_r2).checkbox(m_t, key=f"r_m_{m_k}"):
                        r_sel.append(m_k)
                if st.form_submit_button("Rolle speichern"):
                    if r_bez:
                        supabase.table("rollen").insert({"bezeichnung": r_bez, "erlaubte_menues": r_sel}).execute()
                        st.success("Rolle gespeichert!")
                        st.rerun()

        if rollen_data:
            sel_r = st.selectbox("Rolle bearbeiten", [r["bezeichnung"] for r in rollen_data])
            r_obj = next((r for r in rollen_data if r["bezeichnung"] == sel_r), None)
            if r_obj:
                cur_m = r_obj.get("erlaubte_menues", [])
                new_m = []
                col_a, col_b = st.columns(2)
                for idx, (m_k, m_t) in enumerate(ALL_MODULES.items()):
                    if (col_a if idx < 5 else col_b).checkbox(m_t, value=(m_k in cur_m), key=f"edit_r_{r_obj['id']}_{m_k}"):
                        new_m.append(m_k)
                if st.button("Rechte aktualisieren", type="primary"):
                    supabase.table("rollen").update({"erlaubte_menues": new_m}).eq("id", r_obj["id"]).execute()
                    st.success("Aktualisiert!")
                    st.rerun()

    # --- TAB 4: Qualifikationen ---
    with tab_qualifikationen:
        st.subheader("Qualifikationen & Scheine")
        try:
            ma_list = supabase.table("mitarbeiter").select("id, vorname, nachname, mitarbeiternummer").execute().data or []
        except Exception:
            ma_list = []

        if ma_list:
            sel_ma = st.selectbox("Mitarbeiter wählen", [m["id"] for m in ma_list], format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in ma_list if m["id"] == x))
            with st.form("quali_form"):
                kat = st.selectbox("Kategorie", ["Ausbildung", "Weiterbildung", "Zertifikat", "Sonstiges"])
                titel = st.text_input("Titel *")
                d_erh = st.date_input("Erhalten am", value=date.today())
                d_bis = st.date_input("Gültig bis", value=None)
                desc = st.text_area("Anmerkung")
                up_file = st.file_uploader("Nachweis (Bild/PDF)", type=["png", "jpg", "jpeg", "pdf"])
                
                if st.form_submit_button("Speichern", type="primary"):
                    if titel:
                        f_url = None
                        if up_file:
                            fb, ct, fn = compress_image(up_file)
                            fp = f"{sel_ma}/{fn}"
                            supabase.storage.from_("mitarbeiter-dokumente").upload(fp, fb, {"content-type": ct, "upsert": "true"})
                            f_url = supabase.storage.from_("mitarbeiter-dokumente").get_public_url(fp)
                        
                        supabase.table("qualifikationen").insert({
                            "mitarbeiter_id": sel_ma, "kategorie": kat, "titel": titel,
                            "datum_erhalten": str(d_erh), "gueltig_bis": str(d_bis) if d_bis else None,
                            "beschreibung": desc, "dokument_url": f_url
                        }).execute()
                        st.success("Gespeichert!")
                        st.rerun()
