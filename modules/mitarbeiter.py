import streamlit as st
from datetime import date
import pandas as pd
from fpdf import FPDF
from io import BytesIO
from PIL import Image

# Alle Module und ihre feinen Aktionen (Sehen, Erstellen, Bearbeiten, Löschen)
ALL_MODULES = {
    "1": ("1. Mitarbeiterverwaltung", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "2": ("2. Lagerverwaltung", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "3": ("3. Zeiterfassung", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "4": ("4. Aufträge & Einsätze", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "5": ("5. Kundenverwaltung", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "6": ("6. Fahrzeugflotte", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "7": ("7. Gebäude", ["sehen", "erstellen", "bearbeiten", "loeschen"]),
    "8": ("8. Dokumente", ["sehen", "erstellen", "loeschen"]),
    "9": ("9. TV-Leitsystem", ["sehen", "bearbeiten"]),
    "10": ("10. Steuerberater-Export", ["sehen", "exportieren"])
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
        ("Standard-Pause:", f"{mitarbeiter_data.get('standard_pause_minuten', 30)} Min."),
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
    st.title("👨‍💼 1. Mitarbeiterverwaltung & Personalakten")
    
    user = st.session_state.get("user_data", {})
    user_id = user.get("id")

    try:
        user_db_res = supabase.table("mitarbeiter").select("rollen(darf_antraege_pruefen)").eq("id", user_id).execute()
        r_info = user_db_res.data[0].get("rollen") if user_db_res.data else {}
        is_antrag_admin = bool(r_info.get("darf_antraege_pruefen", False)) if r_info else False
    except Exception:
        is_antrag_admin = user.get("rolle") in ["Admin", "Bauleiter", "Büro / Verwaltung"]

    tab_uebersicht, tab_neu, tab_rollen, tab_urlaub, tab_qualifikationen = st.tabs([
        "📋 Personalstamm & Status", 
        "➕ Neuer Mitarbeiter", 
        "🔑 Rollen & feine Rechte", 
        "🏖️ Urlaub & Anträge",
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
                    "Pause (Min)": m.get("standard_pause_minuten", 30),
                    "Status": "🟢 Aktiv" if m.get("ist_aktiv") else "🔴 Inaktiv"
                } for m in mitarbeiter_liste])
                
                st.dataframe(display_df, use_container_width=True)
                
                st.markdown("---")
                st.subheader("⚙️ Mitarbeiter-Details, Kontingente & Arbeitszeitmodell bearbeiten")
                
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
                        neue_pause = st.number_input("Standard-Pause (Minuten)", min_value=0, max_value=120, value=int(selected_ma.get("standard_pause_minuten") or 30), step=5)
                    with col_e2:
                        neuer_status = st.checkbox("Account ist aktiv (Login erlaubt)", value=selected_ma.get("ist_aktiv", True))

                    st.markdown("##### 📅 Tägliche Soll-Stunden (Wochenmodell)")
                    col_w1, col_w2, col_w3, col_w4, col_w5 = st.columns(5)
                    soll_mo = col_w1.number_input("Mo", 0.0, 12.0, float(selected_ma.get("soll_mo", 8.0)), 0.5)
                    soll_di = col_w2.number_input("Di", 0.0, 12.0, float(selected_ma.get("soll_di", 8.0)), 0.5)
                    soll_mi = col_w3.number_input("Mi", 0.0, 12.0, float(selected_ma.get("soll_mi", 8.0)), 0.5)
                    soll_do = col_w4.number_input("Do", 0.0, 12.0, float(selected_ma.get("soll_do", 8.0)), 0.5)
                    soll_fr = col_w5.number_input("Fr", 0.0, 12.0, float(selected_ma.get("soll_fr", 6.0)), 0.5)

                    berechnete_wochenstunden = soll_mo + soll_di + soll_mi + soll_do + soll_fr
                    st.info(f"Ergeben automatisch **{berechnete_wochenstunden} Wochenstunden**")
                    
                    if st.form_submit_button("Stammdaten & Arbeitszeiten aktualisieren", type="primary", use_container_width=True):
                        try:
                            supabase.table("mitarbeiter").update({
                                "urlaubstage_gesamt": neuer_urlaub,
                                "wochenstunden": berechnete_wochenstunden,
                                "standard_pause_minuten": neue_pause,
                                "ist_aktiv": neuer_status,
                                "soll_mo": soll_mo,
                                "soll_di": soll_di,
                                "soll_mi": soll_mi,
                                "soll_do": soll_do,
                                "soll_fr": soll_fr
                            }).eq("id", selected_ma_id).execute()
                            st.success("Stammdaten & Arbeitszeitmodell erfolgreich aktualisiert!")
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
                standard_pause = st.number_input("Standard-Pause pro Schicht (Minuten)", value=30, min_value=0, max_value=120, step=5)
            with col2:
                rolle_bezeichnung = st.selectbox("Rolle / Funktion *", list(rollen_dict.keys()) if rollen_dict else ["Keine Rolle"])
                passwort = st.text_input("Erst-Passwort / PIN *", type="password")
                notfall_pin = st.text_input("4-stellige Notfall-PIN", type="password", max_chars=4)
                ist_aktiv_neu = st.checkbox("Account sofort aktivieren", value=True)
                email = st.text_input("E-Mail (optional)")
                telefon = st.text_input("Telefon (optional)")
                adresse = st.text_area("Anschrift (optional)")

            st.markdown("##### 📅 Voreinstellung Wochenmodell (Mo - Fr)")
            col_n1, col_n2, col_n3, col_n4, col_n5 = st.columns(5)
            n_mo = col_n1.number_input("Mo Std", 0.0, 12.0, 8.0, 0.5, key="n_mo")
            n_di = col_n2.number_input("Di Std", 0.0, 12.0, 8.0, 0.5, key="n_di")
            n_mi = col_n3.number_input("Mi Std", 0.0, 12.0, 8.0, 0.5, key="n_mi")
            n_do = col_n4.number_input("Do Std", 0.0, 12.0, 8.0, 0.5, key="n_do")
            n_fr = col_n5.number_input("Fr Std", 0.0, 12.0, 6.0, 0.5, key="n_fr")
            
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
                            "wochenstunden": n_mo + n_di + n_mi + n_do + n_fr,
                            "standard_pause_minuten": standard_pause,
                            "soll_mo": n_mo,
                            "soll_di": n_di,
                            "soll_mi": n_mi,
                            "soll_do": n_do,
                            "soll_fr": n_fr,
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

    # --- TAB 3: Rollen & Feine Rechte (CRUD) ---
    with tab_rollen:
        st.subheader("🔑 Feingranulares Rollen- & Rechtssystem")
        st.caption("Legen Sie fest, welche Rolle welche Module sehen, erstellen, bearbeiten oder löschen darf.")

        try:
            rollen_data = supabase.table("rollen").select("*").execute().data or []
        except Exception:
            rollen_data = []

        with st.expander("➕ Neue Rolle mit feinen Rechten erstellen"):
            with st.form("neue_rolle_crud"):
                r_bez = st.text_input("Rollenbezeichnung *", placeholder="z. B. Monteur (eingeschränkt)")
                r_darf_antraege = st.checkbox("Darf Urlaubs- und Abwesenheitsanträge prüfen & genehmigen")
                
                st.markdown("---")
                st.markdown("**Feine Berechtigungen (Sehen, Erstellen, Bearbeiten, Löschen):**")
                
                new_rechte_liste = []
                for mod_id, (mod_titel, aktionen) in ALL_MODULES.items():
                    st.markdown(f"**{mod_titel}**")
                    cols = st.columns(len(aktionen))
                    for idx, akt in enumerate(aktionen):
                        recht_key = f"{mod_id}_{akt}"
                        if cols[idx].checkbox(f"{akt.capitalize()}", key=f"new_r_{mod_id}_{akt}"):
                            new_rechte_liste.append(recht_key)
                    st.markdown("")

                if st.form_submit_button("Rolle anlegen", type="primary", use_container_width=True):
                    if r_bez:
                        try:
                            supabase.table("rollen").insert({
                                "bezeichnung": r_bez, 
                                "erlaubte_menues": new_rechte_liste, # Speichert Keys wie "4_sehen", "4_bearbeiten"
                                "darf_antraege_pruefen": r_darf_antraege
                            }).execute()
                            st.success(f"Rolle '{r_bez}' erfolgreich erstellt!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")

        if rollen_data:
            st.markdown("---")
            sel_r = st.selectbox("Rolle auswählen zum Anpassen der feinen Rechte", [r["bezeichnung"] for r in rollen_data])
            r_obj = next((r for r in rollen_data if r["bezeichnung"] == sel_r), None)
            
            if r_obj:
                with st.form(f"edit_rolle_crud_{r_obj['id']}"):
                    st.markdown(f"#### Rechte feinjustieren für: **{r_obj['bezeichnung']}**")
                    
                    cur_darf = bool(r_obj.get("darf_antraege_pruefen", False))
                    new_darf = st.checkbox("Darf Urlaubs- und Abwesenheitsanträge prüfen & genehmigen", value=cur_darf)
                    
                    st.markdown("---")
                    st.markdown("**Modul-Aktionen (CRUD):**")
                    cur_m = r_obj.get("erlaubte_menues", [])
                    updated_rechte_liste = []

                    for mod_id, (mod_titel, aktionen) in ALL_MODULES.items():
                        st.markdown(f"**{mod_titel}**")
                        cols = st.columns(len(aktionen))
                        for idx, akt in enumerate(aktionen):
                            recht_key = f"{mod_id}_{akt}"
                            is_checked = recht_key in cur_m
                            if cols[idx].checkbox(f"{akt.capitalize()}", value=is_checked, key=f"edit_rc_{r_obj['id']}_{mod_id}_{akt}"):
                                updated_rechte_liste.append(recht_key)
                        st.markdown("")
                        
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        btn_update = st.form_submit_button("💾 Feine Rechte aktualisieren", type="primary", use_container_width=True)
                    with col_b2:
                        btn_delete = st.form_submit_button("🗑️ Rolle löschen", use_container_width=True)

                    if btn_update:
                        try:
                            supabase.table("rollen").update({
                                "erlaubte_menues": updated_rechte_liste,
                                "darf_antraege_pruefen": new_darf
                            }).eq("id", r_obj["id"]).execute()
                            st.success("Rechte erfolgreich aktualisiert!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

                    if btn_delete:
                        try:
                            check_ma = supabase.table("mitarbeiter").select("id").eq("rolle_id", r_obj["id"]).execute()
                            if check_ma.data and len(check_ma.data) > 0:
                                st.error(f"Rolle kann nicht gelöscht werden, da noch {len(check_ma.data)} Mitarbeiter dieser Rolle zugeordnet sind!")
                            else:
                                supabase.table("rollen").delete().eq("id", r_obj["id"]).execute()
                                st.success(f"Rolle '{r_obj['bezeichnung']}' wurde erfolgreich gelöscht!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Löschen: {e}")

    # --- TAB 4: Urlaub & Anträge ---
    with tab_urlaub:
        st.subheader("🏖️ Urlaubs- & Abwesenheitsanträge")
        # (Bleibt wie in Ihrer Version erhalten)
        try:
            all_antraege_res = supabase.table("antraege").select("*, mitarbeiter(vorname, nachname, mitarbeiternummer)").execute()
            all_antraege = all_antraege_res.data or []
        except Exception:
            all_antraege = []

        offene_antraege = [a for a in all_antraege if a.get("status") == "in_bearbeitung"]
        anzahl_offen = len(offene_antraege)

        if is_antrag_admin and anzahl_offen > 0:
            st.warning(f"🔔 **Benachrichtigung:** Es gibt **{anzahl_offen} neue/offene Anträge**, die auf Ihre Prüfung warten!")

        try:
            ma_res = supabase.table("mitarbeiter").select("urlaubstage_gesamt").eq("id", user_id).execute()
            gesamt_urlaub = ma_res.data[0].get("urlaubstage_gesamt", 30) if ma_res.data else 30
        except Exception:
            gesamt_urlaub = 30

        current_year = date.today().year
        try:
            user_antraege = [a for a in all_antraege if a.get("mitarbeiter_id") == user_id]
        except Exception:
            user_antraege = []

        berechnete_tage = 0
        for a in user_antraege:
            if a.get("art") == "Urlaub" and a.get("status") in ["genehmigt", "in_bearbeitung"]:
                try:
                    start = date.fromisoformat(a.get("start_datum"))
                    ende = date.fromisoformat(a.get("end_datum"))
                    if start.year == current_year:
                        berechnete_tage += (ende - start).days + 1
                except Exception:
                    pass

        rest_urlaub = max(0, gesamt_urlaub - berechnete_tage)

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Urlaubsanspruch gesamt", f"{gesamt_urlaub} Tage")
        col_m2.metric("Bereits beantragt / genommen", f"{berechnete_tage} Tage")
        col_m3.metric("Verbleibende Urlaubstage", f"{rest_urlaub} Tage", delta=f"{rest_urlaub} übrig")

        st.markdown("---")

        sub_tab_neu, sub_tab_meine, sub_tab_admin = st.tabs([
            "➕ Neuen Antrag stellen", 
            "📄 Meine Anträge", 
            f"⚙️ Anträge prüfen ({anzahl_offen} offen)" if is_antrag_admin else "🔒 Admin-Ansicht (Gesperrt)"
        ])

        with sub_tab_neu:
            with st.form("neuer_antrag_form"):
                art = st.selectbox("Art des Antrags", ["Urlaub", "Sonderurlaub", "Krankheitstag (Nachmeldung)", "Fortbildung", "Sonstiges"])
                col_d1, col_d2 = st.columns(2)
                start_datum = col_d1.date_input("Von Datum", value=date.today(), format="DD.MM.YYYY")
                end_datum = col_d2.date_input("Bis Datum", value=date.today(), format="DD.MM.YYYY")
                grund = st.text_area("Grund / Bemerkung (optional)")
                
                if st.form_submit_button("Antrag abschicken", type="primary", use_container_width=True):
                    if start_datum > end_datum:
                        st.error("Das Startdatum kann nicht nach dem Enddatum liegen.")
                    else:
                        try:
                            supabase.table("antraege").insert({
                                "mitarbeiter_id": user_id,
                                "art": art,
                                "start_datum": str(start_datum),
                                "end_datum": str(end_datum),
                                "details": grund,
                                "status": "in_bearbeitung"
                            }).execute()
                            st.success("Antrag erfolgreich eingereicht! Zuständige Vorgesetzte wurden benachrichtigt (Status: 🟡 In Bearbeitung).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

        with sub_tab_meine:
            if user_antraege:
                for a in user_antraege:
                    status = a.get("status")
                    badge = "🟢 Genehmigt" if status == "genehmigt" else ("🔴 Abgelehnt" if status == "abgelehnt" else "🟡 In Bearbeitung")
                    with st.expander(f"{badge} | {a.get('art')} vom {a.get('start_datum')} bis {a.get('end_datum')}"):
                        st.write(f"**Details:** {a.get('details', '-')}")
                        if status == "abgelehnt" and a.get("ablehnungsgrund"):
                            st.error(f"**Ablehnungsgrund:** {a.get('ablehnungsgrund')}")
            else:
                st.info("Keine Anträge vorhanden.")

        with sub_tab_admin:
            if is_antrag_admin:
                if all_antraege:
                    for a in all_antraege:
                        ma = a.get("mitarbeiter") or {}
                        ma_name = f"{ma.get('vorname', '')} {ma.get('nachname', '')} (Nr: {ma.get('mitarbeiternummer', '-')})"
                        status = a.get("status")
                        badge = "🟢 Genehmigt" if status == "genehmigt" else ("🔴 Abgelehnt" if status == "abgelehnt" else "🟡 In Bearbeitung")

                        with st.expander(f"{badge} | {ma_name} - {a.get('art')} ({a.get('start_datum')} bis {a.get('end_datum')})"):
                            st.write(f"**Grund:** {a.get('details', '-')}")
                            with st.form(f"admin_antrag_{a['id']}"):
                                neu_status = st.selectbox("Status", ["in_bearbeitung", "genehmigt", "abgelehnt"], index=["in_bearbeitung", "genehmigt", "abgelehnt"].index(status))
                                ablehnung_grund = st.text_input("Ablehnungsgrund (bei Rot erforderlich)", value=a.get("ablehnungsgrund", ""))
                                if st.form_submit_button("Status speichern", type="primary"):
                                    supabase.table("antraege").update({
                                        "status": neu_status,
                                        "ablehnungsgrund": ablehnung_grund if neu_status == "abgelehnt" else ""
                                    }).eq("id", a["id"]).execute()
                                    st.success("Antrag aktualisiert!")
                                    st.rerun()
                else:
                    st.info("Keine Anträge im System.")

    # --- TAB 5: Qualifikationen ---
    with tab_qualifikationen:
        st.subheader("Qualifikationen & Scheine")
        try:
            ma_list = supabase.table("mitarbeiter").select("id, vorname, nachname, mitarbeiternummer").execute().data or []
        except Exception:
            ma_list = []

        if ma_list:
            sel_ma = st.selectbox("Mitarbeiter wählen", [m["id"] for m in ma_list], format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in ma_list if m["id"] == x), key="q_ma_sel")
            with st.form("quali_form"):
                kat = st.selectbox("Kategorie", ["Ausbildung", "Weiterbildung", "Zertifikat", "Sonstiges"])
                titel = st.text_input("Titel *")
                d_erh = st.date_input("Erhalten am", value=date.today())
                d_bis = st.date_input("Gültig bis", value=None)
                desc = st.text_area("Anmerkung")
                up_file = st.file_uploader("Nachweis (Bild/PDF)", type=["png", "jpg", "jpeg", "pdf"])
                
                if st.form_submit_button("Speichern", type="primary", use_container_width=True):
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
