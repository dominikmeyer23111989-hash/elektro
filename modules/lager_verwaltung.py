import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
import qrcode

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("High-Speed Lager: Live-Suche, Lagerort-Anzeige & Barcode-/QR-Workflow.")

    if not hat_recht("2", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Lager-Modul aufzurufen.")
        return

    darf_bearbeiten = hat_recht("2", "bearbeiten") or hat_recht("2", "erstellen")
    darf_loeschen = hat_recht("2", "loeschen") or hat_recht("2", "bearbeiten") or hat_recht("2", "erstellen")

    try:
        m_res = supabase.table("lager_material").select("*").order("bezeichnung").execute()
        material_liste = m_res.data or []
    except Exception:
        material_liste = []

    tabs = st.tabs([
        "📊 Bestandsübersicht & Turbo-Suche", 
        "⚡ Schnell-Buchung (Entnahme / Zugang)", 
        "🖨️ Etiketten (QR & Barcode)",
        "➕ Artikel anlegen",
        "✏️ Artikel bearbeiten / löschen",
        "📋 Inventur",
        "📥 CSV-Import"
    ])

    # --- TAB 1: BESTANDSÜBERSICHT & TURBO-SUCHE ---
    with tabs[0]:
        st.subheader("Aktueller Lagerbestand & Standort-Finder")

        if not material_liste:
            st.info("Noch keine Artikel im Lager vorhanden.")
        else:
            # Sofort-Suchfeld mit Live-Filter
            suchbegriff = st.text_input("🔍 Turbo-Suche (Nach Bezeichnung, Artikelnummer, Kategorie oder Lagerort suchen)...", "", key="turbo_suche_input")

            gefilterte_liste = []
            for mat in material_liste:
                text_kombi = f"{mat.get('artikelnummer', '')} {mat.get('bezeichnung', '')} {mat.get('kategorie', '')} {mat.get('lagerort', '')}".lower()
                if suchbegriff.lower() in text_kombi:
                    gefilterte_liste.append(mat)

            anzeige_daten = []
            for m in gefilterte_liste:
                soll = m.get('soll_bestand', 0)
                ist = m.get('ist_bestand', 0)
                
                if ist <= 0:
                    status = "🔴 Leer"
                elif ist < soll:
                    status = "🟡 Unter Soll"
                else:
                    status = "🟢 OK"

                anzeige_daten.append({
                    "ID": m.get('id'),
                    "Status": status,
                    "Code": m.get('artikelnummer', '-'),
                    "Bezeichnung": m.get('bezeichnung'),
                    "Kategorie": m.get('kategorie', 'Allgemein'),
                    "📍 Lagerort": m.get('lagerort', '⚠️ Kein Ort angegeben'),
                    "Ist-Bestand": f"{ist} {m.get('einheit', 'Stk.')}",
                    "Soll": f"{soll}"
                })

            df = pd.DataFrame(anzeige_daten)
            if not df.empty:
                st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
                st.caption(f"Gefunden: {len(df)} Artikel")
            else:
                st.warning("Keine Artikel gefunden.")

    # --- TAB 2: SCHNELL-BUCHUNG MIT TURBO-AUSWAHL & LAGERORT ---
    with tabs[1]:
        st.subheader("⚡ Material Ein- oder Ausbuchen")
        st.caption("Geben Sie den Code ein oder tippen Sie den Namen ein – der Lagerort wird sofort angezeigt.")

        if not material_liste:
            st.warning("Noch keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            # Schnelle Eingabe per Scanner / Tastatur
            eingabe_code = st.text_input("🔍 Barcode / Artikelnummer eingeben oder scannen", placeholder="Code eintippen oder scannen...", key="schnell_buchung_code_input")

            selected_artikel = None
            if eingabe_code:
                # Exakte Suche nach Code oder Teilsuche
                selected_artikel = next((m for m in material_liste if str(m.get('artikelnummer')).strip().lower() == str(eingabe_code).strip().lower()), None)
                
            # Wenn kein exakter Code getroffen wurde oder man direkt wählen will:
            if not selected_artikel:
                st.markdown("---")
                st.write("💡 **Oder direkt nach Artikel / Lagerort filtern:**")
                
                # Filterbares Auswahlfeld (ersetzt das starre Dropdown für große Datenmengen)
                such_filter = st.text_input("Suchfilter für Auswahlliste", placeholder="z.B. NYM oder Regal B...", key="filter_auswahl_buchung")
                
                passende_optionen = []
                for m in material_liste:
                    zeile = f"{m.get('bezeichnung')} | Ort: {m.get('lagerort', 'Kein Ort')} | Code: {m.get('artikelnummer', '-')} | Bestand: {m.get('ist_bestand', 0)} {m.get('einheit', 'Stk.')}"
                    if such_filter.lower() in zeile.lower():
                        passende_optionen.append((zeile, m))

                if passende_optionen:
                    auswahl_labels = [opt[0] for opt in passende_optionen]
                    gewähltes_label = st.selectbox("Treffer in der Auswahlliste", options=auswahl_labels, key="selectbox_gefundener_artikel")
                    selected_artikel = next((opt[1] for opt in passende_optionen if opt[0] == gewähltes_label), None)
                else:
                    st.warning("Kein Artikel entspricht dem Filter.")

            # Wenn ein Artikel aktiv ist, Buchungsmaske anzeigen
            if selected_artikel:
                st.success(f"📦 **{selected_artikel['bezeichnung']}**")
                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.metric("Aktueller Bestand", f"{selected_artikel.get('ist_bestand', 0)} {selected_artikel.get('einheit', 'Stk.')}")
                with col_info2:
                    st.metric("📍 Lagerort", f"{selected_artikel.get('lagerort', 'Nicht zugewiesen')}")
                with col_info3:
                    st.metric("Artikel-Code", f"{selected_artikel.get('artikelnummer', '-')}")

                with st.form("buchungs_maske_form"):
                    buchungs_art = st.radio("Aktion", ["📤 Entnahme (Ausbuchung)", "📥 Zugang (Einbuchung)"], horizontal=True)
                    menge = st.number_input("Menge", min_value=1, value=1, step=1)
                    kommentar = st.text_input("Projekt / Baustelle / Grund", placeholder="z.B. BV Hauptstraße")

                    if st.form_submit_button("Bestand jetzt buchen", type="primary", use_container_width=True):
                        alter_bestand = selected_artikel.get('ist_bestand', 0)
                        neuer_bestand = alter_bestand + menge if "Zugang" in buchungs_art else max(0, alter_bestand - menge)

                        try:
                            supabase.table("lager_material").update({"ist_bestand": neuer_bestand}).eq("id", selected_artikel['id']).execute()
                            supabase.table("lager_bewegungen").insert({
                                "material_id": selected_artikel['id'],
                                "art": "Einbuchung" if "Zugang" in buchungs_art else "Ausbuchung",
                                "menge": menge,
                                "kommentar": kommentar or "Buchung"
                            }).execute()

                            st.toast(f"✅ Gebucht! Neuer Bestand: {neuer_bestand}", icon="🎉")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    # --- TAB 3: ETIKETTEN DRUCKEN (QR & BARCODE) ---
    with tabs[2]:
        st.subheader("🖨️ Etiketten für Regale & Kartons drucken")
        st.caption("Drucken Sie QR-Codes (für Handys) und Barcodes (für Scanner) aus und kleben Sie diese direkt an den Lagerort/Regalplatz.")

        if not material_liste:
            st.warning("Keine Artikel vorhanden.")
        else:
            eticket_optionen = {f"{m['bezeichnung']} [Ort: {m.get('lagerort', 'Kein Ort')}] (Code: {m.get('artikelnummer', 'Keiner')})": m for m in material_liste if m.get('artikelnummer')}
            
            if not eticket_optionen:
                st.info("💡 Hinterlegen Sie Artikelnummern, um Etiketten zu drucken.")
            else:
                ausgewaehlte_labels = st.multiselect("Artikel für Etikettendruck wählen", options=list(eticket_optionen.keys()))

                if ausgewaehlte_labels and st.button("🖨️ Etiketten anzeigen", type="primary"):
                    for label in ausgewaehlte_labels:
                        mat = eticket_optionen[label]
                        code_val = str(mat.get('artikelnummer'))
                        
                        st.markdown(f"### 📦 {mat.get('bezeichnung')} | 📍 Lagerort: **{mat.get('lagerort', 'Hauptlager')}**")
                        col_q, col_b = st.columns(2)
                        
                        with col_q:
                            st.write("**QR-Code (Regal / Handy):**")
                            try:
                                qr = qrcode.QRCode(version=1, box_size=5, border=2)
                                qr.add_data(code_val)
                                qr.make(fit=True)
                                img_qr = qr.make_image(fill_color="black", back_color="white")
                                buf_qr = BytesIO()
                                img_qr.save(buf_qr)
                                st.image(buf_qr.getvalue(), width=150)
                            except Exception as e:
                                st.error(f"QR-Fehler: {e}")

                        with col_b:
                            st.write("**Barcode (Handscanner):**")
                            try:
                                EAN = barcode.get_class('code128')
                                rv = BytesIO()
                                ean = EAN(code_val, writer=ImageWriter())
                                ean.write(rv)
                                st.image(rv.getvalue(), width=200)
                            except Exception as e:
                                st.error(f"Barcode-Fehler: {e}")

                        st.markdown(f"**Code-Wert:** `{code_val}`")
                        st.divider()

    # --- TAB 4: ARTIKEL ANLEGEN ---
    with tabs[3]:
        st.subheader("➕ Neuen Artikel anlegen")
        if not darf_bearbeiten:
            st.error("⛔ Keine Berechtigung.")
        else:
            with st.form("neuer_artikel_form"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    n_bezeichnung = st.text_input("Artikelbezeichnung *", placeholder="z.B. NYM-J 3x1.5")
                    n_artnr = st.text_input("Artikelnummer / Barcode *", placeholder="z.B. EAN oder interner Code")
                    n_kategorie = st.selectbox("Kategorie", ["Kabel & Leitungen", "Schalter & Steckdosen", "Verteiler", "Kleinmaterial", "Leuchtmittel", "Werkzeug"])
                with col_a2:
                    n_einheit = st.selectbox("Einheit", ["Stk.", "Meter", "Rolle", "Paket", "Liter", "kg"])
                    n_lagerort = st.text_input("📍 Lagerort / Regal (wichtig für Suche)", placeholder="z.B. Regal A1, Fach 3")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        n_soll = st.number_input("Mindestbestand", min_value=0, value=5)
                    with col_b2:
                        n_ist = st.number_input("Anfangsbestand", min_value=0, value=10)

                if st.form_submit_button("Artikel speichern", type="primary", use_container_width=True):
                    if not n_bezeichnung or not n_artnr:
                        st.warning("Bitte Bezeichnung und Artikelnummer angeben.")
                    else:
                        try:
                            supabase.table("lager_material").insert({
                                "bezeichnung": n_bezeichnung,
                                "artikelnummer": n_artnr,
                                "kategorie": n_kategorie,
                                "einheit": n_einheit,
                                "lagerort": n_lagerort,
                                "soll_bestand": n_soll,
                                "ist_bestand": n_ist
                            }).execute()
                            st.toast(f"✅ Artikel '{n_bezeichnung}' angelegt!", icon="🎉")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    # --- TAB 5: ARTIKEL BEARBEITEN / LÖSCHEN ---
    with tabs[4]:
        st.subheader("✏️ Artikel bearbeiten oder löschen")
        if not material_liste:
            st.warning("Keine Artikel vorhanden.")
        else:
            bearb_optionen = {f"{m['bezeichnung']} (Ort: {m.get('lagerort', '-')}) [Code: {m.get('artikelnummer', '-')}]": m for m in material_liste}
            auswahl_bearb = st.selectbox("Artikel für Bearbeitung wählen", options=list(bearb_optionen.keys()), key="select_bearb_artikel")
            aktiver_mat = bearb_optionen[auswahl_bearb]

            with st.form("artikel_bearbeiten_form"):
                e_bezeichnung = st.text_input("Bezeichnung", value=aktiver_mat.get('bezeichnung', ''))
                e_artnr = st.text_input("Artikelnummer / Barcode", value=aktiver_mat.get('artikelnummer', ''))
                e_kategorie = st.text_input("Kategorie", value=aktiver_mat.get('kategorie', 'Allgemein'))
                e_einheit = st.text_input("Einheit", value=aktiver_mat.get('einheit', 'Stk.'))
                e_lagerort = st.text_input("📍 Lagerort / Regal", value=aktiver_mat.get('lagerort', ''))
                
                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    e_soll = st.number_input("Mindestbestand", min_value=0, value=int(aktiver_mat.get('soll_bestand', 5)))
                with c_b2:
                    e_ist = st.number_input("Ist-Bestand", min_value=0, value=int(aktiver_mat.get('ist_bestand', 0)))

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    btn_speichern = st.form_submit_button("💾 Änderungen speichern", type="primary", use_container_width=True)
                with col_btn2:
                    btn_loeschen = st.form_submit_button("🗑️ Artikel löschen", use_container_width=True)

                if btn_speichern:
                    if darf_bearbeiten:
                        try:
                            supabase.table("lager_material").update({
                                "bezeichnung": e_bezeichnung,
                                "artikelnummer": e_artnr,
                                "kategorie": e_kategorie,
                                "einheit": e_einheit,
                                "lagerort": e_lagerort,
                                "soll_bestand": e_soll,
                                "ist_bestand": e_ist
                            }).eq("id", aktiver_mat['id']).execute()
                            st.toast("✅ Änderungen gespeichert!", icon="🎯")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")
                    else:
                        st.error("Keine Berechtigung.")

                if btn_loeschen:
                    if darf_loeschen:
                        try:
                            supabase.table("lager_material").delete().eq("id", aktiver_mat['id']).execute()
                            st.toast("🗑️ Artikel gelöscht!", icon="🗑️")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")
                    else:
                        st.error("Keine Berechtigung.")

    # --- TAB 6: INVENTUR ---
    with tabs[5]:
        st.subheader("📋 Systematische Inventur")
        if not material_liste:
            st.warning("Keine Artikel vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Keine Berechtigung.")
        else:
            with st.form("inventur_form"):
                inventur_daten = {}
                for m in material_liste:
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.write(f"**{m.get('bezeichnung')}** | 📍 `{m.get('lagerort', 'Kein Ort')}`")
                    with col2:
                        st.write(f"Soll: **{m.get('ist_bestand', 0)}**")
                    with col3:
                        gezahlt = st.number_input("Ist", min_value=0, value=int(m.get('ist_bestand', 0)), key=f"inv_{m['id']}", label_visibility="collapsed")
                        inventur_daten[m['id']] = gezahlt
                    st.divider()

                if st.form_submit_button("✅ Inventur finalisieren", type="primary", use_container_width=True):
                    try:
                        for mat_id, neuer_ist in inventur_daten.items():
                            supabase.table("lager_material").update({"ist_bestand": neuer_ist}).eq("id", mat_id).execute()
                        st.toast("Inventur erfolgreich abgeschlossen!", icon="🎯")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")

    # --- TAB 7: CSV-MASSENIMPORT ---
    with tabs[6]:
        st.subheader("📥 Massen-Import (CSV)")
        uploaded_file = st.file_uploader("CSV-Datei auswählen", type=["csv"])
        if uploaded_file is not None:
            try:
                df_import = pd.read_csv(uploaded_file)
                st.write("Vorschau:", df_import.head())
                if st.button("🚀 Importieren", type="primary"):
                    for _, row in df_import.iterrows():
                        supabase.table("lager_material").insert({
                            "artikelnummer": str(row.get('artikelnummer', '')),
                            "bezeichnung": str(row.get('bezeichnung', 'Unbekannt')),
                            "kategorie": str(row.get('kategorie', 'Allgemein')),
                            "einheit": str(row.get('einheit', 'Stk.')),
                            "soll_bestand": int(row.get('soll_bestand', 5)),
                            "ist_bestand": int(row.get('ist_bestand', 0)),
                            "lagerort": str(row.get('lagerort', 'Hauptlager'))
                        }).execute()
                    st.toast("Erfolgreich importiert!", icon="🎉")
                    st.rerun()
            except Exception as e:
                st.error(f"Fehler: {e}")
