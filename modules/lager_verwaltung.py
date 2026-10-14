import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
import qrcode
import cv2
import numpy as np

# Robustere QR-Erkennung mit OpenCV
try:
    qr_detector = cv2.QRCodeDetector()
    QR_SCAN_AVAILABLE = True
except Exception:
    QR_SCAN_AVAILABLE = False

def decodiere_qr_aus_bild(opencv_image):
    if not QR_SCAN_AVAILABLE or opencv_image is None:
        return ""
    try:
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
        
        # Direktversuch
        data, _, _ = qr_detector.detectAndDecode(gray)
        if data:
            return str(data).strip()

        # Kontrastverstärkung (gegen schlechtes Licht / Schatten)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        data, _, _ = qr_detector.detectAndDecode(enhanced)
        if data:
            return str(data).strip()

        # Skalierungstest
        for scale in [0.5, 1.5, 2.0]:
            resized = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
            data, _, _ = qr_detector.detectAndDecode(resized)
            if data:
                return str(data).strip()
                
    except Exception:
        pass
    return ""

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("High-Speed Lager: Turbo-Scan, präzise Mengenauswahl, Warenkorb & Logs.")

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

    # Session States initialisieren
    if "last_foto_id" not in st.session_state:
        st.session_state["last_foto_id"] = None
    if "current_scanned_code" not in st.session_state:
        st.session_state["current_scanned_code"] = ""

    tabs = st.tabs([
        "📊 Bestandsübersicht", 
        "⚡ Turbo-Scan & Multibuchung", 
        "🖨️ Etiketten",
        "➕ Artikel anlegen",
        "✏️ Bearbeiten / Löschen",
        "📋 Inventur",
        "📥 CSV-Import",
        "📜 Entnahme-Logs"
    ])

    # --- TAB 1: BESTANDSÜBERSICHT ---
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

    # --- TAB 2: TURBO-SCAN & MULTIBUCHUNG ---
    with tabs[1]:
        st.subheader("⚡ Turbo-Scan & Multibuchung")
        st.caption("QR-Code fotografieren oder Artikel suchen, gewünschte Menge einstellen und in den Warenkorb legen.")

        if not material_liste:
            st.warning("Noch keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            col_m_mode, col_m_menge = st.columns(2)
            with col_m_mode:
                buchungs_art_multi = st.selectbox("Buchungs-Modus", ["📤 Entnahme (Ausbuchung)", "📥 Zugang (Einbuchung)"], key="buchungs_art_one_tap")
            with col_m_menge:
                standard_menge = st.number_input("Standard-Menge", min_value=1, value=1, step=1, key="global_standard_menge")

            # Nativer Kamera-Input
            foto_input = st.camera_input("📷 QR-Code fotografieren", key="lager_camera_input")

            if foto_input:
                foto_id = getattr(foto_input, "file_id", None) or hash(foto_input.getvalue())
                if foto_id != st.session_state.get("last_foto_id"):
                    st.session_state["last_foto_id"] = foto_id
                    if QR_SCAN_AVAILABLE:
                        try:
                            file_bytes = np.asarray(bytearray(foto_input.read()), dtype=np.uint8)
                            opencv_image = cv2.imdecode(file_bytes, 1)
                            code_erfasst = decodiere_qr_aus_bild(opencv_image)
                            
                            if code_erfasst:
                                st.session_state["current_scanned_code"] = code_erfasst
                                st.success(f"🎯 **Erfolgreich erkannt! Code:** `{code_erfasst}`")
                            else:
                                st.warning("⚠️ QR-Code auf dem Foto nicht eindeutig erkannt. Bitte nutzen Sie die Suche unten.")
                        except Exception as e:
                            st.error(f"Fehler bei der Bildverarbeitung: {e}")

            # Artikel-Ermittlung über Scan oder Direktsuche
            current_code = st.session_state.get("current_scanned_code", "")
            
            st.markdown("---")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                eingabe_code = st.text_input("🔍 Artikelnummer / Code", value=current_code, placeholder="Wird automatisch gefüllt...", key="multiscan_input")
            with col_s2:
                such_filter_m = st.text_input("🔍 Oder Artikelsuche nach Name", placeholder="z.B. NYM...", key="filter_multi_artikel")

            aktueller_treffer = None
            if eingabe_code:
                match = next((m for m in material_liste if str(m.get('artikelnummer')).strip().lower() == str(eingabe_code).strip().lower()), None)
                if match:
                    aktueller_treffer = match
            
            if not aktueller_treffer and such_filter_m:
                passende_m = [m for m in material_liste if such_filter_m.lower() in f"{m.get('bezeichnung')} {m.get('lagerort')} {m.get('artikelnummer')}".lower()]
                if passende_m:
                    label_options = {f"{m['bezeichnung']} (Ort: {m.get('lagerort', '-')}) [Bestand: {m['ist_bestand']} {m.get('einheit', 'Stk.')}]": m for m in passende_m}
                    ausgewaehltes_label = st.selectbox("Wählen Sie den passenden Artikel aus:", options=list(label_options.keys()), key="select_such_treffer")
                    aktueller_treffer = label_options[ausgewaehltes_label]

            # Wenn Artikel ermittelt wurde, eindeutige Produktkarte mit Mengenauswahl anzeigen
            if aktueller_treffer:
                st.markdown("---")
                with st.container(border=True):
                    st.success(f"📦 **{aktueller_treffer['bezeichnung']}**")
                    st.write(f"📍 **Lagerort:** {aktueller_treffer.get('lagerort', '-')}")
                    st.write(f"🔢 **Code:** `{aktueller_treffer.get('artikelnummer', '-')}`")
                    st.write(f"📊 **Aktueller Bestand:** {aktueller_treffer.get('ist_bestand', 0)} {aktueller_treffer.get('einheit', 'Stk.')}")

                    # Explizite und komfortable Mengenauswahl
                    aktuelle_menge_artikel = st.number_input(
                        f"Gewünschte Menge ({aktueller_treffer.get('einheit', 'Stk.')}):", 
                        min_value=1, 
                        value=int(standard_menge), 
                        step=1, 
                        key=f"menge_artikel_{aktueller_treffer['id']}"
                    )

                    if st.button("➕ In den Warenkorb legen", type="primary", use_container_width=True):
                        st.session_state["multibuchung_liste"].append({
                            "id": aktueller_treffer['id'],
                            "bezeichnung": aktueller_treffer['bezeichnung'],
                            "code": aktueller_treffer.get('artikelnummer', '-'),
                            "bestand_alt": aktueller_treffer.get('ist_bestand', 0),
                            "einheit": aktueller_treffer.get('einheit', 'Stk.'),
                            "menge": aktuelle_menge_artikel,
                            "art": buchungs_art_multi,
                            "lagerort": aktueller_treffer.get('lagerort', '-')
                        })
                        st.toast(f"✅ {aktuelle_menge_artikel}x {aktueller_treffer['bezeichnung']} in den Warenkorb gelegt!", icon="🛒")
                        st.session_state["current_scanned_code"] = ""
                        st.session_state["last_foto_id"] = None
                        st.rerun()

            # Warenkorb & Gesamtabschluss
            st.markdown("---")
            st.subheader("🛒 Aktuelle Scan-Liste (Warenkorb)")

            if not st.session_state["multibuchung_liste"]:
                st.info("Der Warenkorb ist leer. Scannen Sie Artikel, um sie hier zu sammeln.")
            else:
                cart_df = pd.DataFrame(st.session_state["multibuchung_liste"])
                st.dataframe(cart_df[["bezeichnung", "code", "lagerort", "art", "menge", "einheit"]], use_container_width=True, hide_index=True)

                kommentar_gesamt = st.text_input("Projekt / Baustelle (optional)", placeholder="z.B. BV Bahnhofstraße (leer lassen, wenn kein Auftrag)", key="kommentar_multibuchung")

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if st.button("🚀 Alle Positionen jetzt gesammelt buchen", type="primary", use_container_width=True):
                        try:
                            user_data = st.session_state.get("user_data", {})
                            current_user = user_data.get("name") or user_data.get("benutzername") or user_data.get("username") or "Mitarbeiter"
                            
                            projekt_text = kommentar_gesamt.strip() if kommentar_gesamt else "-"

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
                                    "anzahl": menge_b,
                                    "benutzer": current_user,
                                    "kommentar": projekt_text
                                }).execute()

                            st.session_state["multibuchung_liste"] = []
                            st.session_state["current_scanned_code"] = ""
                            st.toast("🎉 Alle Buchungen erfolgreich gespeichert & protokolliert!", icon="🎯")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Buchen: {e}")

                with col_c2:
                    if st.button("🗑️ Warenkorb leeren", use_container_width=True):
                        st.session_state["multibuchung_liste"] = []
                        st.rerun()

    # --- TAB 3: ETIKETTEN DRUCKEN ---
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

    # --- TAB 8: ENTNAHME-LOGS (Rollenbasiert) ---
    with tabs[7]:
        st.subheader("📜 Historie & Entnahmeprotokoll (Logs)")
        st.caption("Wer hat wann, wie viel entnommen und für welches Projekt?")

        user_rolle = st.session_state.get("user_data", {}).get("rolle", "")
        if user_rolle not in ["Admin", "Inhaber", "Chef"] and not hat_recht("2", "bearbeiten"):
            st.error("⛔ Sie haben keine Berechtigung, das Entnahmeprotokoll einzusehen.")
        else:
            try:
                b_res = supabase.table("lager_bewegungen").select("*").order("id", desc=True).limit(200).execute()
                bewegungen = b_res.data or []

                if not bewegungen:
                    st.info("Noch keine Materialbewegungen aufgezeichnet.")
                else:
                    mat_map = {m["id"]: m for m in material_liste}

                    log_daten = []
                    for b in bewegungen:
                        mat_info = mat_map.get(b.get("material_id"), {})
                        m_val = b.get("menge") if b.get("menge") is not None else b.get("anzahl", 0)
                        
                        log_daten.append({
                            "Art": b.get("art", "-"),
                            "Artikel": mat_info.get("bezeichnung", "Unbekannt"),
                            "Code": mat_info.get("artikelnummer", "-"),
                            "Menge": m_val,
                            "Einheit": mat_info.get("einheit", "Stk."),
                            "Benutzer": b.get("benutzer", "Unbekannt"),
                            "Projekt / Baustelle": b.get("kommentar", "-")
                        })

                    log_df = pd.DataFrame(log_daten)
                    st.dataframe(log_df, use_container_width=True, hide_index=True)
                    st.caption(f"Letzte {len(log_df)} Buchungsvorgänge im System.")
            except Exception as e:
                st.error(f"Fehler beim Laden der Logs: {e}")
