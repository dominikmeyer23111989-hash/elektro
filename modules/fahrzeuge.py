import streamlit as st
from datetime import date, datetime
import pandas as pd
from fpdf import FPDF

class FahrzeugPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - FAHRZEUG- & MAENGELREPORT', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Flottenuebersicht und aktuelle Schadenshistorie (DSGVO-konform)', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_fahrzeug_bericht_pdf(f, maengel_liste):
    pdf = FahrzeugPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 6, clean_text(f"Fahrzeug: {f.get('kennzeichen')} - {f.get('fahrzeug_typ')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, clean_text(f"Aktueller Status: {f.get('status')} | Kilometerstand: {f.get('kilometerstand', 0):,} km".replace(',', '.')), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, clean_text(f"TÜV fällig: {f.get('tuev_monat')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Historie der Maengelmeldungen:", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(30, 6, "Datum", border=1)
    pdf.cell(45, 6, "Titel / Problem", border=1)
    pdf.cell(30, 6, "Prioritaet", border=1)
    pdf.cell(30, 6, "Status", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 9)
    for m in maengel_liste:
        raw_dt = str(m.get('erstellt_am', ''))[:10]
        try:
            datum_str = datetime.strptime(raw_dt, "%Y-%m-%d").strftime("%d.%m.%Y")
        except Exception:
            datum_str = raw_dt

        pdf.cell(30, 5, clean_text(datum_str), border=1)
        pdf.cell(45, 5, clean_text(m.get('mangel_titel')), border=1)
        pdf.cell(30, 5, clean_text(m.get('prioritaet')), border=1)
        pdf.cell(30, 5, clean_text(m.get('status')), border=1, new_x="LMARGIN", new_y="NEXT")

    return pdf.output()

def render_fahrzeug_warnungen_sidebar(supabase):
    """Prüft in der Sidebar, ob TÜV in 4 Wochen ansteht oder offene Mängel existieren."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🚨 Flotten-Warnungen")

    try:
        m_res = supabase.table("fahrzeug_maengel").select("id, prioritaet", count="exact").eq("status", "Offen").execute()
        offene_maengel_count = m_res.count if m_res.count is not None else len(m_res.data or [])
        
        f_res = supabase.table("fahrzeuge").select("kennzeichen, tuev_monat").execute()
        fahrzeuge = f_res.data or []
        
        heute = date.today()
        tuev_warnungen = []

        for f in fahrzeuge:
            t_str = f.get("tuev_monat")
            if t_str:
                try:
                    t_clean = t_str.replace("/", ".")
                    teile = t_clean.split(".")
                    if len(teile) == 2:
                        monat = int(teile[0])
                        jahr = int(teile[1])
                        if monat == 12:
                            tuev_datum = date(jahr + 1, 1, 1)
                        else:
                            tuev_datum = date(jahr, monat + 1, 1)
                        
                        tage_bis_tuev = (tuev_datum - heute).days
                        if tage_bis_tuev <= 30:
                            tuev_warnungen.append(f"{f.get('kennzeichen')} ({t_str})")
                except Exception:
                    pass

        if offene_maengel_count > 0:
            st.sidebar.error(f"⚠️ **{offene_maengel_count} offene Mängelmeldung(en)!**")
        
        if tuev_warnungen:
            st.sidebar.warning(f"⚠️ **TÜV fällig:**\n" + "\n".join([f"- {k}" for k in tuev_warnungen]))

        if offene_maengel_count == 0 and not tuev_warnungen:
            st.sidebar.success("🟢 Flotten-Status: Alles optimal")

    except Exception:
        st.sidebar.info("Flotten-Check aktiv")

def hat_recht(modul_id, aktion="sehen"):
    """Prüft über die app.py-Logik, ob das Recht vorliegt."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_fahrzeug_verwaltung(supabase):
    st.title("🚗 6. Fahrzeugflotte & Mängelmeldungen")
    st.caption("Verwalten Sie Ihre Firmenwagen, überwachen Sie den Status und melden Sie Defekte direkt in Echtzeit.")

    if not hat_recht("6", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Flottenmodul aufzurufen.")
        return

    darf_erstellen = hat_recht("6", "erstellen")
    darf_bearbeiten = hat_recht("6", "bearbeiten")

    # Radio-Optionen dynamisch aufbauen
    menu_optionen = ["🚙 Flottenübersicht & Stammdaten", "🚨 Mängelmeldungen & Schäden"]
    if darf_erstellen:
        menu_optionen.append("➕ Neues Fahrzeug anlegen")

    sub_menu = st.radio(
        "Bereich auswählen",
        options=menu_optionen,
        horizontal=True
    )

    st.markdown("---")

    try:
        f_res = supabase.table("fahrzeuge").select("*").order("kennzeichen").execute()
        fahrzeuge_liste = f_res.data or []
    except Exception:
        fahrzeuge_liste = []

    try:
        m_res = supabase.table("fahrzeug_maengel").select("*, fahrzeuge(kennzeichen, fahrzeug_typ), mitarbeiter(vorname, nachname)").order("erstellt_am", desc=True).execute()
        maengel_liste = m_res.data or []
    except Exception:
        maengel_liste = []

    # --- BEREICH 1: FLOTTENÜBERSICHT & DETAILS ---
    if sub_menu == "🚙 Flottenübersicht & Stammdaten":
        st.subheader("Fahrzeugpark & technischer Status")

        if not fahrzeuge_liste:
            st.info("Noch keine Fahrzeuge im System hinterlegt.")
            return

        display_data = []
        for f in fahrzeuge_liste:
            status_icon = "🟢" if f.get("status") == "Einsatzbereit" else ("🟡" if f.get("status") == "In Werkstatt" else "🔴")
            display_data.append({
                "Kennzeichen": f.get("kennzeichen"),
                "Typ / Modell": f.get("fahrzeug_typ"),
                "Status": f"{status_icon} {f.get('status')}",
                "KM-Stand": f"{f.get('kilometerstand', 0):,} km".replace(",", "."),
                "TÜV fällig": f.get("tuev_monat") or "-",
                "Notizen": f.get("notizen") or "-"
            })

        st.dataframe(pd.DataFrame(display_data), use_container_width=True)

        st.markdown("---")
        st.subheader("⚙️ Fahrzeug bearbeiten & PDF-Report")

        sel_f_id = st.selectbox(
            "Fahrzeug auswählen",
            options=[f["id"] for f in fahrzeuge_liste],
            format_func=lambda x: next(f"{f['kennzeichen']} - {f['fahrzeug_typ']} ({f['status']})" for f in fahrzeuge_liste if f["id"] == x)
        )

        sel_fahrzeug = next(f for f in fahrzeuge_liste if f["id"] == sel_f_id)
        zugehoerige_maengel = [m for m in maengel_liste if m.get("fahrzeug_id") == sel_f_id]

        akt_tuev = sel_fahrzeug.get("tuev_monat") or "12.2026"
        try:
            p_monat, p_jahr = akt_tuev.replace("/", ".").split(".")
            def_m_idx = int(p_monat) - 1
            def_j_idx = [2024, 2025, 2026, 2027, 2028, 2029].index(int(p_jahr)) if int(p_jahr) in [2024, 2025, 2026, 2027, 2028, 2029] else 2
        except Exception:
            def_m_idx = 0
            def_j_idx = 2

        if not darf_bearbeiten:
            st.info("ℹ️ Ihr Account hat Leserechte für die Flotte. Sie können keine Änderungen an Fahrzeugen speichern.")

        with st.form("fahrzeug_edit_form"):
            col1, col2 = st.columns(2)
            with col1:
                e_kennzeichen = st.text_input("Kennzeichen *", value=sel_fahrzeug.get("kennzeichen"), disabled=not darf_bearbeiten)
                e_typ = st.text_input("Fahrzeug-Typ / Modell *", value=sel_fahrzeug.get("fahrzeug_typ"), disabled=not darf_bearbeiten)
                e_baujahr = st.number_input("Baujahr", min_value=1990, max_value=2030, value=int(sel_fahrzeug.get("baujahr") or 2022), disabled=not darf_bearbeiten)
            with col2:
                st.write("TÜV fällig (Monat / Jahr)")
                c_m1, c_m2 = st.columns(2)
                with c_m1:
                    e_tuev_monat = st.selectbox("Monat", [f"{i:02d}" for i in range(1, 13)], index=def_m_idx, disabled=not darf_bearbeiten)
                with c_m2:
                    e_tuev_jahr = st.selectbox("Jahr", [2024, 2025, 2026, 2027, 2028, 2029], index=def_j_idx, disabled=not darf_bearbeiten)

                e_km = st.number_input("Kilometerstand", min_value=0, value=int(sel_fahrzeug.get("kilometerstand") or 0), step=1000, disabled=not darf_bearbeiten)
                e_status = st.selectbox("Status", ["Einsatzbereit", "In Werkstatt", "Gesperrt / Defekt"], index=["Einsatzbereit", "In Werkstatt", "Gesperrt / Defekt"].index(sel_fahrzeug.get("status", "Einsatzbereit")), disabled=not darf_bearbeiten)

            e_notizen = st.text_area("Ausstattung / Tankkarte / Hinweise", value=sel_fahrzeug.get("notizen") or "", disabled=not darf_bearbeiten)

            if darf_bearbeiten:
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    btn_update = st.form_submit_button("💾 Fahrzeug aktualisieren", type="primary", use_container_width=True)
                with col_b2:
                    btn_del = st.form_submit_button("🗑️ Fahrzeug löschen", use_container_width=True)

                if btn_update:
                    tuev_kombiniert = f"{e_tuev_monat}.{e_tuev_jahr}"
                    try:
                        supabase.table("fahrzeuge").update({
                            "kennzeichen": e_kennzeichen,
                            "fahrzeug_typ": e_typ,
                            "baujahr": e_baujahr,
                            "tuev_monat": tuev_kombiniert,
                            "kilometerstand": e_km,
                            "status": e_status,
                            "notizen": e_notizen
                        }).eq("id", sel_f_id).execute()
                        st.success("Fahrzeugdaten erfolgreich aktualisiert!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")

                if btn_del:
                    try:
                        supabase.table("fahrzeuge").delete().eq("id", sel_f_id).execute()
                        st.success("Fahrzeug gelöscht!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Löschen: {e}")

        st.markdown("---")
        pdf_bytes = generate_fahrzeug_bericht_pdf(sel_fahrzeug, zugehoerige_maengel)
        st.download_button(
            label=f"📥 Fahrzeug- & Mängelreport für {sel_fahrzeug.get('kennzeichen')} herunterladen (PDF)",
            data=bytes(pdf_bytes),
            file_name=f"Fahrzeugbericht_{sel_fahrzeug.get('kennzeichen')}.pdf",
            mime="application/pdf"
        )

    # --- BEREICH 2: MÄNGELMELDUNGEN ---
    elif sub_menu == "🚨 Mängelmeldungen & Schäden":
        st.subheader("🚨 Mängelmeldungen & Werkstatt-Tickets")

        if not maengel_liste:
            st.info("Aktuell sind keine Mängel oder Schäden gemeldet. Alles im grünen Bereich!")
        else:
            for m in maengel_liste:
                f_info = m.get("fahrzeuge") or {}
                ma_info = m.get("mitarbeiter") or {}
                
                status_color = "🔴" if m.get("status") == "Offen" else ("🟡" if m.get("status") == "In Bearbeitung" else "🟢")
                prio_str = f"⚠️ Prio: {m.get('prioritaet')}" if m.get("prioritaet") in ["Hoch", "Sofort-Stopp"] else f"Prio: {m.get('prioritaet')}"

                raw_dt = str(m.get('erstellt_am', ''))[:10]
                try:
                    erstellt_dt_de = datetime.strptime(raw_dt, "%Y-%m-%d").strftime("%d.%m.%Y")
                except Exception:
                    erstellt_dt_de = raw_dt

                with st.expander(f"{status_color} [{f_info.get('kennzeichen', 'Unbekannt')}] {m.get('mangel_titel')} ({prio_str})"):
                    st.write(f"**Fahrzeug:** {f_info.get('fahrzeug_typ')} ({f_info.get('kennzeichen')})")
                    st.write(f"**Gemeldet von:** {ma_info.get('vorname', 'Unbekannt')} {ma_info.get('nachname', '')} am {erstellt_dt_de}")
                    st.write(f"**Beschreibung:** {m.get('beschreibung')}")
                    st.write(f"**Aktueller Status:** {m.get('status')}")

                    if darf_bearbeiten:
                        new_status = st.selectbox("Status bearbeiten", ["Offen", "In Bearbeitung", "Erledigt"], index=["Offen", "In Bearbeitung", "Erledigt"].index(m.get("status", "Offen")), key=f"status_{m['id']}")
                        
                        if st.button("Status speichern", key=f"btn_status_{m['id']}"):
                            try:
                                supabase.table("fahrzeug_maengel").update({"status": new_status}).eq("id", m["id"]).execute()
                                st.success("Status aktualisiert!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler: {e}")

        st.markdown("---")
        st.subheader("➕ Neuen Mangel / Schaden melden")

        if not fahrzeuge_liste:
            st.warning("Bitte legen Sie zuerst mindestens ein Fahrzeug an.")
        else:
            with st.form("mangel_melden_form"):
                m_fahrzeug = st.selectbox(
                    "Betroffenes Fahrzeug *",
                    options=[f["id"] for f in fahrzeuge_liste],
                    format_func=lambda x: next(f"{f['kennzeichen']} - {f['fahrzeug_typ']}" for f in fahrzeuge_liste if f["id"] == x)
                )
                m_titel = st.text_input("Kurztitel des Mangels *", placeholder="z.B. Scheinwerfer vorne links defekt / Reifen abgefahren")
                m_prio = st.selectbox("Priorität", ["Niedrig", "Normal", "Hoch", "Sofort-Stopp (Fahrverbot)"])
                m_beschreibung = st.text_area("Genaue Schadensbeschreibung / Ort des Defekts", placeholder="Bitte Details angeben...")

                if st.form_submit_button("Mängelmeldung absenden", type="primary", use_container_width=True):
                    if not m_titel:
                        st.warning("Bitte einen Titel für den Mangel angeben.")
                    else:
                        try:
                            user_data = st.session_state.get("user_data", {})
                            supabase.table("fahrzeug_maengel").insert({
                                "fahrzeug_id": m_fahrzeug,
                                "gemeldet_durch": user_data.get("id"),
                                "mangel_titel": m_titel,
                                "beschreibung": m_beschreibung,
                                "prioritaet": m_prio,
                                "status": "Offen"
                            }).execute()
                            st.success("Mängelmeldung erfolgreich eingereicht! Die Werkstatt wurde informiert.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")

    # --- BEREICH 3: NEUES FAHRZEUG ANLEGEN ---
    elif sub_menu == "➕ Neues Fahrzeug anlegen" and darf_erstellen:
        st.subheader("Neues Fahrzeug zur Flotte hinzufügen")

        with st.form("neues_fahrzeug_form"):
            col1, col2 = st.columns(2)
            with col1:
                n_kennzeichen = st.text_input("Kennzeichen *", placeholder="z.B. BO-EL 2026")
                n_typ = st.text_input("Fahrzeug-Typ / Modell *", placeholder="z.B. VW Crafter Kastenwagen")
                n_baujahr = st.number_input("Baujahr", min_value=1990, max_value=2030, value=2024)
            with col2:
                st.write("TÜV fällig (Monat / Jahr)")
                nc_1, nc_2 = st.columns(2)
                with nc_1:
                    n_tuev_monat = st.selectbox("Monat", [f"{i:02d}" for i in range(1, 13)], index=11)
                with nc_2:
                    n_tuev_jahr = st.selectbox("Jahr", [2024, 2025, 2026, 2027, 2028, 2029], index=2)

                n_km = st.number_input("Aktueller Kilometerstand", min_value=0, value=15000, step=1000)
                n_status = st.selectbox("Start-Status", ["Einsatzbereit", "In Werkstatt", "Gesperrt / Defekt"])

            n_notizen = st.text_area("Ausstattung / Tankkarte / Besonderheiten", placeholder="z.B. Mit Regaleinbau, Dachträger...")

            if st.form_submit_button("Fahrzeug speichern", type="primary", use_container_width=True):
                if not n_kennzeichen or not n_typ:
                    st.warning("Bitte Kennzeichen und Fahrzeug-Typ angeben.")
                else:
                    tuev_kombiniert = f"{n_tuev_monat}.{n_tuev_jahr}"
                    try:
                        supabase.table("fahrzeuge").insert({
                            "kennzeichen": n_kennzeichen,
                            "fahrzeug_typ": n_typ,
                            "baujahr": n_baujahr,
                            "tuev_monat": tuev_kombiniert,
                            "kilometerstand": n_km,
                            "status": n_status,
                            "notizen": n_notizen
                        }).execute()
                        st.success(f"Fahrzeug {n_kennzeichen} erfolgreich zur Flotte hinzugefügt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Anlegen: {e}")
