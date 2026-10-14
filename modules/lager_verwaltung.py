import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
import qrcode
import cv2
import numpy as np

# OpenCV QR-Detector initialisieren
try:
    qr_detector = cv2.QRCodeDetector()
    QR_SCAN_AVAILABLE = True
except Exception:
    QR_SCAN_AVAILABLE = False

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("High-Speed Lager: One-Tap Kamera-Scan, Multibuchungs-Warenkorb & Direkte QR-Anzeige.")

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

    if "multibuchung_liste" not in st.session_state:
        st.session_state["multibuchung_liste"] = []

    tabs = st.tabs([
        "📊 Bestandsübersicht & Turbo-Suche", 
        "⚡ Multibuchung & Schnell-Scan", 
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
            suchbegriff = st.text_input("🔍 Turbo-Suche (Bezeichnung, Artikelnummer, Kategorie oder Lagerort)...", "", key="turbo_suche_input")

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

    # --- TAB 2: MULTIBUCHUNG & SCHNELL-SCAN (ONE-TAP KAMERA) ---
    with tabs[1]:
        st.subheader("⚡ Multibuchung (One-Tap Kamera-Scan für Mitarbeiter)")
        st.caption("Einfach auf 'Foto aufnehmen' tippen, QR-Code am Regal fotografieren – der Artikel wird sofort automatisch erkannt!")

        if not material_liste:
            st.warning("Noch keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            buchungs_art_multi = st.selectbox("Buchungs-Modus", ["📤 Entnahme (Ausbuchung)", "📥 Zugang (Einbuchung)"], key="buchungs_art_one_tap")

            erfasster_code = ""

            # Nativer Streamlit Kamera-Input (funktioniert auf Smartphones absolut reibungslos)
            foto_input = st.camera_input("📷 QR-Code fotografieren", key="lager_camera_input")

            if foto_input and QR_SCAN_AVAILABLE:
                try:
                    file_bytes = np.asarray(bytearray(foto_input.read()), dtype=np.uint8)
                    opencv_image = cv2.imdecode(file_bytes, 1)

                    # QR-Code Erkennung über OpenCV
                    retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(opencv_image)
                    if retval and decoded_info and decoded_info[0]:
                        erfasster_code = str(decoded_info[0]).strip()
                        st.success(f"🎯 **Erkannt! Artikel-Code:** `{erfasster_code}`")
                    else:
                        # Fallback Einzel-Erkennung
                        data, bbox, _ = qr_detector.detectAndDecode(opencv_image)
                        if data:
                            erfasster_code = str(data).strip()
                            st.success(f"🎯 **Erkannt! Artikel-Code:** `{erfasster_code}`")
                        else:
                            st.warning("⚠️ Kein QR-Code auf dem Foto erkannt. Bitte halten Sie die Kamera etwas näher an den Code und sorgen Sie für gutes Licht.")
                except Exception as e:
                    st.error(f"Fehler bei der Bildverarbeitung: {e}")

            # Manuelle Eingabe als Alternative / Fallback
            eingabe_manuell = st.text_input("Oder Artikelnummer direkt eintippen", placeholder="Code eingeben...", key="manuell_code_input")
            if eingabe_manuell:
                erfasster_code = eingabe_manuell.strip()

            # Artikel in der Liste suchen
            aktueller_treffer = None
            if erfasster_code:
                aktueller_treffer = next((m for m in material_liste if str(m.get('artikelnummer', '')).strip().lower() == erfasster_code.lower()), None)
                if not aktueller_treffer:
                    st.error(f"⚠️ Der Code '{erfasster_code}' wurde im System nicht gefunden.")

            if aktueller_treffer:
                st.markdown("---")
                col_i1, col_i2, col_i3 = st.columns([2, 2, 1])
                
                with col_i1:
                    st.success(f"📦 **{aktueller_treffer['bezeichnung']}**")
                    st.write(f"📍 **Lagerort:** {aktueller_treffer.get('lagerort', '-')}")
                    st.write(f"🔢 **Code:** `{aktueller_treffer.get('artikelnummer', '-')}`")
                    st.write(f"📊 **Bestand:** {aktueller_treffer.get('ist_bestand', 0)} {aktueller_treffer.get('einheit', 'Stk.')}")
                
                with col_i2:
                    code_val = str(aktueller_treffer.get('artikelnummer', ''))
                    if code_val:
                        st.write("**Produkt-QR-Code:**")
                        try:
                            qr = qrcode.QRCode(version=1, box_size=4, border=1)
                            qr.add_data(code_val)
                            qr.make(fit=True)
                            img_q = qr.make_image(fill_color="black", back_color="white")
                            buf_q = BytesIO()
                            img_q.save(buf_q)
                            st.image(buf_q.getvalue(), width=110)
                        except Exception:
                            pass

                with col_i3:
                    menge_hinzu = st.number_input("Menge", min_value=1, value=1, step=1, key="menge_one_tap_add")
                    if st.button("➕ In Warenkorb", type="primary", use_container_width=True):
                        st.session_state["multibuchung_liste"].append({
                            "id": aktueller_treffer['id'],
                            "bezeichnung": aktueller_treffer['bezeichnung'],
                            "code": aktueller_treffer.get('artikelnummer', '-'),
                            "bestand_alt": aktueller_treffer.get('ist_bestand', 0),
                            "einheit": aktueller_treffer.get('einheit', 'Stk.'),
                            "menge": menge_hinzu,
                            "art": buchungs_art_multi,
                            "lagerort": aktueller_treffer.get('lagerort', '-')
                        })
                        st.toast(f"✅ {aktueller_treffer['bezeichnung']} in den Warenkorb gelegt!", icon="🛒")
                        st.rerun()

            # Warenkorb & Gesamtabschluss
            st.markdown("---")
            st.subheader("🛒 Aktuelle Scan-Liste (Warenkorb)")

            if not st.session_state["multibuchung_liste"]:
                st.info("Der Warenkorb ist leer. Machen Sie ein Foto vom QR-Code, um Artikel hinzuzufügen.")
            else:
                cart_df = pd.DataFrame(st.session_state["multibuchung_liste"])
                st.dataframe(cart_df[["bezeichnung", "code", "lagerort", "art", "menge", "einheit"]], use_container_width=True, hide_index=True)

                kommentar_gesamt = st.text_input("Projekt / Baustelle für alle Artikel im Warenkorb", placeholder="z.B. BV Bahnhofstraße", key="kommentar_multibuchung_one_tap")

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if st.button("🚀 Alle Positionen jetzt gesammelt buchen", type="primary", use_container_width=True):
                        try:
                            for item in st.session_state["multibuchung_liste"]:
                                alter_b = item["bestand_alt"]
                                menge_b = item["menge"]
                                ist_zugang = "Zugang" in item["art"]
                                neuer_b = alter_b + menge_b if ist_zugang else max(0, alter_b - menge_b)

                                supabase.table("lager_material").update({"ist_bestand": neuer_b}).eq("id", item["id"]).execute()
                                
                                supabase.table("lager_bewegungen").insert({
                                    "material_id": item["id"],
                                    "art": "Einbuchung" if ist_zugang else "Ausbuchung",
                                    "menge": menge_b,
                                    "kommentar": kommentar_gesamt or "Multibuchung"
                                }).execute()

                            st.session_state["multibuchung_liste"] = []
                            st.toast("🎉 Alle Buchungen erfolgreich gespeichert!", icon="🎯")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Buchen: {e}")

                with col_c2:
                    if st.button("🗑️ Warenkorb leeren", use_container_width=True):
                        st.session_state["multibuchung_liste"] = []
                        st.rerun()

    # --- TAB 3: ETIKETTEN DRUCKEN (QR & BARCODE) ---
    with tabs[2]:
        st.subheader("🖨️ Etiketten für Regale & Kartons drucken")
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
                    n_lagerort = st.text_input("📍 Lagerort / Regal", placeholder="z.B. Regal A1, Fach 3")
                    
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

    # --- TAB 7: CSV-IMPORT ---
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
