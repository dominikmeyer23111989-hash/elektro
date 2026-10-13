import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
import qrcode
import cv2
import numpy as np

# Robuster Import für OpenCV QR-Code-Erkennung
try:
    qr_detector = cv2.QRCodeDetector()
    QR_AVAILABLE = True
except Exception:
    QR_AVAILABLE = False

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("Das intelligente Lager: QR-Code Kamera-Scan, Barcode-Scanner, Etikettendruck & Artikelpflege.")

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
        "📊 Bestandsübersicht", 
        "⚡ QR- / Barcode-Buchung", 
        "🖨️ Etiketten (QR & Barcode)",
        "➕ Artikel anlegen",
        "✏️ Artikel bearbeiten / löschen",
        "📋 Inventur",
        "📥 CSV-Import"
    ])

    # --- TAB 1: BESTANDSÜBERSICHT ---
    with tabs[0]:
        st.subheader("Aktueller Lagerbestand")

        if not material_liste:
            st.info("Noch keine Artikel im Lager vorhanden.")
        else:
            suchbegriff = st.text_input("🔍 Artikel suchen (Bezeichnung, Artikelnummer oder Kategorie)", "")

            gefilterte_liste = []
            for mat in material_liste:
                text_kombi = f"{mat.get('artikelnummer', '')} {mat.get('bezeichnung', '')} {mat.get('kategorie', '')}".lower()
                if suchbegriff.lower() in text_kombi:
                    gefilterte_liste.append(mat)

            anzeige_daten = []
            for m in gefilterte_liste:
                soll = m.get('soll_bestand', 0)
                ist = m.get('ist_bestand', 0)
                
                if ist <= 0:
                    status = "🔴 Leer / Kritisch"
                elif ist < soll:
                    status = "🟡 Unter Soll"
                else:
                    status = "🟢 Ausreichend"

                anzeige_daten.append({
                    "ID": m.get('id'),
                    "Status": status,
                    "Artikel-Nr. / Code": m.get('artikelnummer', '-'),
                    "Bezeichnung": m.get('bezeichnung'),
                    "Kategorie": m.get('kategorie', 'Allgemein'),
                    "Lagerort": m.get('lagerort', '-'),
                    "Ist-Bestand": f"{ist} {m.get('einheit', 'Stk.')}",
                    "Soll-Bestand": f"{soll} {m.get('einheit', 'Stk.')}"
                })

            df = pd.DataFrame(anzeige_daten)
            if not df.empty:
                st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
            else:
                st.warning("Keine Artikel gefunden.")

    # --- TAB 2: QR- / BARCODE-BUCHUNG (KAMERA ODER HANDSCANNER) ---
    with tabs[1]:
        st.subheader("⚡ QR- & Barcode Ein- / Ausbuchung")
        st.caption("Scannen Sie einen QR-Code per Handykamera oder nutzen Sie einen Handscanner.")

        if not material_liste:
            st.warning("Keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            scan_methode = st.radio("Erfassungsmethode", ["📷 QR-Code per Handykamera fotografieren", "⌨️ Handscanner / Manuelle Eingabe"], horizontal=True)

            erfasster_code = ""

            if "Kamera" in scan_methode:
                foto = st.camera_input("QR-Code vor die Kamera halten")
                if foto:
                    file_bytes = np.asarray(bytearray(foto.read()), dtype=np.uint8)
                    opencv_image = cv2.imdecode(file_bytes, 1)

                    if QR_AVAILABLE:
                        try:
                            retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(opencv_image)
                            if retval and decoded_info:
                                erfasster_code = decoded_info[0]
                                st.success(f"🎯 **QR-Code erkannt:** `{erfasster_code}`")
                            else:
                                st.warning("⚠️ Kein QR-Code auf dem Bild erkannt. Versuchen Sie es näher oder mit mehr Licht.")
                        except Exception as e:
                            st.error(f"Fehler bei der QR-Erkennung: {e}")
                    else:
                        st.error("OpenCV QR-Modul nicht verfügbar.")
            else:
                erfasster_code = st.text_input("🔍 Barcode scannen oder Nummer eintippen", placeholder="Code hier eingeben...")

            # Artikel anhand des Codes suchen
            selected_artikel = None
            if erfasster_code:
                selected_artikel = next((m for m in material_liste if str(m.get('artikelnummer')).strip().lower() == str(erfasster_code).strip().lower()), None)
                if selected_artikel:
                    st.info(f"Gefunden: **{selected_artikel['bezeichnung']}** (Aktueller Bestand: {selected_artikel['ist_bestand']} {selected_artikel.get('einheit', 'Stk.')})")
                else:
                    st.warning(f"⚠️ Kein Artikel mit dem Code '{erfasster_code}' im System gefunden.")

            # Fallback per Dropdown, falls man manuell wählen möchte
            if not selected_artikel:
                artikel_optionen = {f"{m['bezeichnung']} (Code: {m.get('artikelnummer', '-')}) [Bestand: {m['ist_bestand']}]": m for m in material_liste}
                auswahl_label = st.selectbox("Oder Artikel direkt aus Liste wählen", options=list(artikel_optionen.keys()))
                selected_artikel = artikel_optionen[auswahl_label]

            if selected_artikel:
                with st.form("buchungs_form"):
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
        st.subheader("🖨️ Etiketten (QR-Codes & Barcodes)")
        st.caption("Generieren Sie Etiketten für Ihre Regale und Kisten – sowohl als QR-Code (für Handys) als auch als Barcode (für Laserscanner).")

        if not material_liste:
            st.warning("Keine Artikel vorhanden.")
        else:
            eticket_optionen = {f"{m['bezeichnung']} (Code: {m.get('artikelnummer', 'Keiner')})": m for m in material_liste if m.get('artikelnummer')}
            
            if not eticket_optionen:
                st.info("💡 Hinterlegen Sie bei Ihren Artikeln eine Artikelnummer, um Etiketten zu drucken.")
            else:
                ausgewaehlte_labels = st.multiselect("Artikel für Etikettendruck wählen", options=list(eticket_optionen.keys()))

                if ausgewaehlte_labels and st.button("🖨️ Etiketten anzeigen", type="primary"):
                    for label in ausgewaehlte_labels:
                        mat = eticket_optionen[label]
                        code_val = str(mat.get('artikelnummer'))
                        
                        st.markdown(f"### 📦 {mat.get('bezeichnung')} (Lagerort: {mat.get('lagerort', 'Hauptlager')})")
                        col_q, col_b = st.columns(2)
                        
                        # QR-Code generieren
                        with col_q:
                            st.write("**QR-Code (für Handykamera):**")
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

                        # Barcode generieren
                        with col_b:
                            st.write("**Barcode (für Handscanner):**")
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
        st.caption("Scannen Sie optional einen Karton/Barcode per Kamera als Vorlage oder tragen Sie die Nummer ein.")

        if not darf_bearbeiten:
            st.error("⛔ Keine Berechtigung.")
        else:
            scan_anlegen = st.radio("QR-Code vom Karton scannen?", ["Nein (manuell eingeben)", "Ja (per Kamera scannen)"], horizontal=True)
            vorbelegter_code = ""

            if "Ja" in scan_anlegen:
                foto_anlegen = st.camera_input("QR-Code scannen für neuen Artikel")
                if foto_anlegen:
                    f_bytes = np.asarray(bytearray(foto_anlegen.read()), dtype=np.uint8)
                    cv_img = cv2.imdecode(f_bytes, 1)
                    if QR_AVAILABLE:
                        retval, decoded_info, _, _ = qr_detector.detectAndDecodeMulti(cv_img)
                        if retval and decoded_info:
                            vorbelegter_code = decoded_info[0]
                            st.success(f"🎯 Erkannt: `{vorbelegter_code}` (wird unten eingetragen)")

            with st.form("neuer_artikel_form"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    n_bezeichnung = st.text_input("Artikelbezeichnung *", placeholder="z.B. NYM-J 3x1.5")
                    n_artnr = st.text_input("Artikelnummer / Barcode *", value=vorbelegter_code, placeholder="z.B. EAN oder interner Code")
                    n_kategorie = st.selectbox("Kategorie", ["Kabel & Leitungen", "Schalter & Steckdosen", "Verteiler", "Kleinmaterial", "Leuchtmittel", "Werkzeug"])
                with col_a2:
                    n_einheit = st.selectbox("Einheit", ["Stk.", "Meter", "Rolle", "Paket", "Liter", "kg"])
                    n_lagerort = st.text_input("Lagerort / Regal", placeholder="z.B. Regal A1")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        n_soll = st.number_input("Mindestbestand", min_value=0, value=5)
                    with col_b2:
                        n_ist = st.number_input("Anfangsbestand", min_value=0, value=10)

                if st.form_submit_button("Artikel speichern & Codes generieren", type="primary", use_container_width=True):
                    if not n_bezeichnung or not n_artnr:
                        st.warning("Bitte Bezeichnung und Artikelnummer/Barcode angeben.")
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
                            st.toast(f"✅ Artikel '{n_bezeichnung}' erfolgreich angelegt!", icon="🎉")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    # --- TAB 5: ARTIKEL BEARBEITEN / LÖSCHEN ---
    with tabs[4]:
        st.subheader("✏️ Artikel bearbeiten oder löschen")
        st.caption("Wählen Sie einen Artikel aus, um Bestände, Bezeichnungen anzupassen oder den Artikel aus dem System zu löschen.")

        if not material_liste:
            st.warning("Keine Artikel vorhanden.")
        else:
            bearb_optionen = {f"{m['bezeichnung']} (Code: {m.get('artikelnummer', '-')})": m for m in material_liste}
            auswahl_bearb = st.selectbox("Artikel auswählen", options=list(bearb_optionen.keys()), key="select_bearb_artikel")
            aktiver_mat = bearb_optionen[auswahl_bearb]

            with st.form("artikel_bearbeiten_form"):
                e_bezeichnung = st.text_input("Bezeichnung", value=aktiver_mat.get('bezeichnung', ''))
                e_artnr = st.text_input("Artikelnummer / Barcode", value=aktiver_mat.get('artikelnummer', ''))
                e_kategorie = st.text_input("Kategorie", value=aktiver_mat.get('kategorie', 'Allgemein'))
                e_einheit = st.text_input("Einheit", value=aktiver_mat.get('einheit', 'Stk.'))
                e_lagerort = st.text_input("Lagerort", value=aktiver_mat.get('lagerort', ''))
                
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
                        st.error("Keine Berechtigung zum Bearbeiten.")

                if btn_loeschen:
                    if darf_loeschen:
                        try:
                            supabase.table("lager_material").delete().eq("id", aktiver_mat['id']).execute()
                            st.toast("🗑️ Artikel erfolgreich gelöscht!", icon="🗑️")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")
                    else:
                        st.error("Keine Berechtigung zum Löschen.")

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
                        st.write(f"**{m.get('bezeichnung')}** `({m.get('artikelnummer', 'Kein Code')})`")
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
