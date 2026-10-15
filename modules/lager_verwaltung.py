import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
import qrcode
import cv2
import numpy as np

# ReportLab für PDF-Generierung prüfen
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    PDF_EXPORT_AVAILABLE = True
except ImportError:
    PDF_EXPORT_AVAILABLE = False

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
        
        data, _, _ = qr_detector.detectAndDecode(gray)
        if data:
            return str(data).strip()

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        data, _, _ = qr_detector.detectAndDecode(enhanced)
        if data:
            return str(data).strip()

        for scale in [0.5, 1.5, 2.0]:
            resized = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
            data, _, _ = qr_detector.detectAndDecode(resized)
            if data:
                return str(data).strip()
                
    except Exception:
        pass
    return ""

def generiere_pdf_bericht(titel, headers, daten):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=15,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=5
    )
    elements.append(Paragraph(titel, title_style))
    
    date_style = ParagraphStyle(
        'ReportDate',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=15
    )
    elements.append(Paragraph(f"Erstellt am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}", date_style))
    elements.append(Spacer(1, 5))
    
    table_data = [headers] + daten
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#007BFF")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f9fafb")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#d1d5db")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("High-Speed Lager: Turbo-Scan, Warenkorb, Sidebar-Warnungen, unterbrechbare Inventur & Logs.")

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

    # --- SIDEBAR: BESTANDSWARNUNGEN ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚨 Bestandswarnungen")
    warn_liste = [m for m in material_liste if m.get('ist_bestand', 0) <= m.get('soll_bestand', 0)]
    if warn_liste:
        st.sidebar.warning(f"⚠️ {len(warn_liste)} Artikel unter/auf Mindestbestand!")
        with st.sidebar.expander("🔍 Warnungen anzeigen"):
            for wm in warn_liste:
                st.sidebar.markdown(f"**{wm.get('bezeichnung')}**<br>Ort: `{wm.get('lagerort', '-')}`<br>Ist: **{wm.get('ist_bestand')}** | Soll: {wm.get('soll_bestand')}", unsafe_allow_html=True)
                st.sidebar.divider()
    else:
        st.sidebar.success("✅ Alle Bestände im grünen Bereich!")

    if "multibuchung_liste" not in st.session_state:
        st.session_state["multibuchung_liste"] = []

    if "last_foto_id" not in st.session_state:
        st.session_state["last_foto_id"] = None

    # Inventur-Zustand im Session State initialisieren
    if "inventur_werte" not in st.session_state:
        st.session_state["inventur_werte"] = {}
    if "inventur_gezahlt_ids" not in st.session_state:
        st.session_state["inventur_gezahlt_ids"] = set()

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

    # Standard-Kategorien für Dropdowns
    verfuegbare_kategorien = ["Kabel & Leitungen", "Schalter & Steckdosen", "Verteiler", "Kleinmaterial", "Leuchtmittel", "Werkzeug", "Material",  "Sonstiges", "Allgemein"]

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
            pdf_roh_daten = []
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

                pdf_roh_daten.append([
                    str(m.get('artikelnummer', '-')),
                    str(m.get('bezeichnung', '')),
                    str(m.get('kategorie', 'Allgemein')),
                    str(m.get('lagerort', '-')),
                    f"{ist} {m.get('einheit', 'Stk.')}",
                    str(soll),
                    status
                ])

            df = pd.DataFrame(anzeige_daten)
            if not df.empty:
                st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
                st.caption(f"Gefunden: {len(df)} Artikel")
                
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    if PDF_EXPORT_AVAILABLE:
                        pdf_bytes = generiere_pdf_bericht(
                            "Lagerbestand & Materialliste",
                            ["Code", "Bezeichnung", "Kategorie", "Lagerort", "Ist", "Soll", "Status"],
                            pdf_roh_daten
                        )
                        st.download_button(
                            label="📄 Materialliste als PDF herunterladen",
                            data=pdf_bytes,
                            file_name=f"Materialliste_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                            mime="application/pdf",
                            key="pdf_download_material"
                        )
                    else:
                        st.warning("⚠️ PDF-Export inaktiv (pip install reportlab)")
                with col_exp2:
                    csv_daten = df.drop(columns=["ID"]).to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Materialliste als CSV herunterladen",
                        data=csv_daten,
                        file_name=f"Materialliste_{datetime.now().strftime('%Y-%m-%d')}.csv",
                        mime="application/pdf",
                        key="csv_download_material"
                    )
            else:
                st.warning("Keine Artikel gefunden.")

    # --- TAB 2: TURBO-SCAN & MULTIBUCHUNG ---
    with tabs[1]:
        st.subheader("⚡ Turbo-Scan & Multibuchung")
        st.caption("QR-Code fotografieren – der Artikel wird automatisch erkannt und sofort in den Warenkorb gelegt!")

        if not material_liste:
            st.warning("Noch keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            col_m_mode, col_m_menge = st.columns(2)
            with col_m_mode:
                buchungs_art_multi = st.selectbox("Buchungs-Modus", ["📤 Entnahme (Ausbuchung)", "📥 Zugang (Einbuchung)"], key="buchungs_art_one_tap")
            with col_m_menge:
                standard_menge = st.number_input("Standard-Menge pro Scan", min_value=1, value=1, step=1, key="global_standard_menge")

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
                                gefundener_artikel = next((m for m in material_liste if str(m.get('artikelnummer')).strip().lower() == str(code_erfasst).strip().lower()), None)
                                
                                if gefundener_artikel:
                                    st.session_state["multibuchung_liste"].append({
                                        "id": gefundener_artikel['id'],
                                        "bezeichnung": gefundener_artikel['bezeichnung'],
                                        "code": gefundener_artikel.get('artikelnummer', '-'),
                                        "bestand_alt": gefundener_artikel.get('ist_bestand', 0),
                                        "einheit": gefundener_artikel.get('einheit', 'Stk.'),
                                        "menge": standard_menge,
                                        "art": buchungs_art_multi,
                                        "lagerort": gefundener_artikel.get('lagerort', '-')
                                    })
                                    st.success(f"🎯 **Erkannt & hinzugefügt:** {standard_menge}x {gefundener_artikel['bezeichnung']} (`{code_erfasst}`)")
                                else:
                                    st.error(f"⚠️ Code '{code_erfasst}' wurde im System nicht gefunden.")
                            else:
                                st.warning("⚠️ QR-Code auf dem Foto nicht eindeutig erkannt. Bitte versuchen Sie es erneut mit gutem Licht.")
                        except Exception as e:
                            st.error(f"Fehler bei der Bildverarbeitung: {e}")

            st.markdown("---")
            with st.expander("🔍 Manuelle Artikelsuche & Mengenauswahl (Alternativ zum Scan)"):
                such_filter_m = st.text_input("Artikel suchen (Name, Ort oder Code)", placeholder="z.B. NYM...", key="filter_multi_artikel")
                passende_m = [m for m in material_liste if such_filter_m.lower() in f"{m.get('bezeichnung')} {m.get('lagerort')} {m.get('artikelnummer')}".lower()] if such_filter_m else []
                
                if passende_m:
                    label_options = {f"{m['bezeichnung']} (Ort: {m.get('lagerort', '-')}) [Bestand: {m['ist_bestand']} {m.get('einheit', 'Stk.')}]": m for m in passende_m}
                    ausgewaehltes_label = st.selectbox("Treffer auswählen:", options=list(label_options.keys()), key="select_such_treffer")
                    manueller_treffer = label_options[ausgewaehltes_label]

                    manuelle_menge = st.number_input(f"Menge ({manueller_treffer.get('einheit', 'Stk.')}):", min_value=1, value=1, step=1, key="manuelle_menge_input")

                    if st.button("➕ Artikel manuell in Warenkorb", type="primary"):
                        st.session_state["multibuchung_liste"].append({
                            "id": manueller_treffer['id'],
                            "bezeichnung": manueller_treffer['bezeichnung'],
                            "code": manueller_treffer.get('artikelnummer', '-'),
                            "bestand_alt": manueller_treffer.get('ist_bestand', 0),
                            "einheit": manueller_treffer.get('einheit', 'Stk.'),
                            "menge": manuelle_menge,
                            "art": buchungs_art_multi,
                            "lagerort": manueller_treffer.get('lagerort', '-')
                        })
                        st.toast(f"✅ {manuelle_menge}x {manueller_treffer['bezeichnung']} hinzugefügt!", icon="🛒")
                        st.rerun()

            st.markdown("---")
            st.subheader("🛒 Aktuelle Scan-Liste (Warenkorb)")

            if not st.session_state["multibuchung_liste"]:
                st.info("Der Warenkorb ist leer. Scannen Sie QR-Codes mit der Kamera.")
            else:
                for idx, item in enumerate(st.session_state["multibuchung_liste"]):
                    c_row1, c_row2, c_row3, c_row4 = st.columns([3, 2, 2, 1])
                    with c_row1:
                        st.write(f"**{item['bezeichnung']}** `({item['code']})`")
                    with c_row2:
                        st.write(f"{item['menge']} {item['einheit']} ({item['art']})")
                    with c_row3:
                        st.write(f"📍 {item['lagerort']}")
                    with c_row4:
                        if st.button("❌", key=f"del_cart_{idx}", help="Diese Position entfernen"):
                            st.session_state["multibuchung_liste"].pop(idx)
                            st.rerun()

                st.markdown("---")
                kommentar_gesamt = st.text_input("Projekt / Baustelle (optional)", placeholder="z.B. BV Bahnhofstraße (leer lassen, wenn kein Auftrag)", key="kommentar_multibuchung")

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if st.button("🚀 Alle Positionen jetzt gesammelt buchen", type="primary", use_container_width=True):
                        try:
                            user_data = st.session_state.get("user_data", {})
                            current_user = user_data.get("name") or user_data.get("benutzername") or user_data.get("username") or "Mitarbeiter"
                            
                            projekt_text = kommentar_gesamt.strip() if kommentar_gesamt else "Kein Auftrag"
                            finaler_kommentar = f"Benutzer: {current_user} | Projekt: {projekt_text}"

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
                                    "kommentar": finaler_kommentar
                                }).execute()

                            st.session_state["multibuchung_liste"] = []
                            st.session_state["last_foto_id"] = None
                            st.toast("🎉 Alle Buchungen erfolgreich gespeichert & protokolliert!", icon="🎯")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Buchen: {e}")

                with col_c2:
                    if st.button("🗑️ Warenkorb komplett leeren", use_container_width=True):
                        st.session_state["multibuchung_liste"] = []
                        st.session_state["last_foto_id"] = None
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
                    n_kategorie = st.selectbox("Kategorie", verfuegbare_kategorien)
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
                
                # Kategorie als Selectbox statt Textfeld
                aktuelle_kat = aktiver_mat.get('kategorie', 'Allgemein')
                kats_bearb = list(verfuegbare_kategorien)
                if aktuelle_kat not in kats_bearb:
                    kats_bearb.append(aktuelle_kat)
                kat_idx = kats_bearb.index(aktuelle_kat) if aktuelle_kat in kats_bearb else 0
                e_kategorie = st.selectbox("Kategorie", kats_bearb, index=kat_idx)

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
        st.subheader("📋 Systematische Inventur (Live-Zwischengespeichert)")
        st.caption("Ihre Eingaben bleiben im Arbeitsspeicher erhalten. Artikel mit einem grünen Häkchen ✅ wurden bereits gezählt.")
        
        letzte_inventur_datum = "Noch nie durchgeführt"
        try:
            inv_check = supabase.table("lager_bewegungen").select("*").eq("art", "Inventur").order("id", desc=True).limit(1).execute()
            if inv_check.data and len(inv_check.data) > 0:
                v = inv_check.data[0].get("kommentar", "")
                if "am " in v:
                    teil = v.split("am ")[1]
                    letzte_inventur_datum = teil.split(" von")[0] if " von" in teil else teil[:10]
        except Exception:
            pass

        st.info(f"📅 **Letzte Inventur durchgeführt am:** `{letzte_inventur_datum}`")

        if not material_liste:
            st.warning("Noch keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Keine Berechtigung.")
        else:
            h1, h2, h3, h4 = st.columns([2, 1, 1, 2])
            with h1:
                st.markdown("**Artikel & Ort**")
            with h2:
                st.markdown("**System-Ist**")
            with h3:
                st.markdown("**Mindest-Soll**")
            with h4:
                st.markdown("**Gezählter Ist-Bestand**")
            st.divider()

            inventur_daten = {}
            for m in material_liste:
                m_id = m['id']
                system_ist = int(m.get('ist_bestand', 0))

                if m_id not in st.session_state["inventur_werte"]:
                    st.session_state["inventur_werte"][m_id] = system_ist

                col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
                with col1:
                    hat_gezahlt = m_id in st.session_state["inventur_gezahlt_ids"]
                    status_icon = " ✅" if hat_gezahlt else ""
                    st.markdown(f"**{m.get('bezeichnung')}**{status_icon}<br>📍 `{m.get('lagerort', 'Kein Ort')}`", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"**{system_ist}** {m.get('einheit', 'Stk.')}")
                with col3:
                    st.markdown(f"{m.get('soll_bestand', 0)} {m.get('einheit', 'Stk.')}")
                with col4:
                    alt_wert = st.session_state["inventur_werte"][m_id]
                    gezahlt = st.number_input(
                        "Ist", 
                        min_value=0, 
                        value=int(alt_wert), 
                        key=f"inv_input_{m_id}", 
                        label_visibility="collapsed"
                    )
                    
                    if gezahlt != alt_wert:
                        st.session_state["inventur_werte"][m_id] = gezahlt
                        st.session_state["inventur_gezahlt_ids"].add(m_id)

                    inventur_daten[m_id] = gezahlt
                st.divider()

            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                if st.button("✅ Inventur finalisieren & Bestände buchen", type="primary", use_container_width=True):
                    try:
                        user_data = st.session_state.get("user_data", {})
                        current_user = user_data.get("name") or user_data.get("benutzername") or user_data.get("username") or "Admin"
                        heute_datum = datetime.now().strftime('%d.%m.%Y')
                        inventur_kommentar = f"Benutzer: {current_user} | Inventur durchgeführt am {heute_datum}"

                        for mat_id, neuer_ist in inventur_daten.items():
                            supabase.table("lager_material").update({
                                "ist_bestand": neuer_ist
                            }).eq("id", mat_id).execute()
                            
                            supabase.table("lager_bewegungen").insert({
                                "material_id": mat_id,
                                "art": "Inventur",
                                "menge": neuer_ist,
                                "kommentar": inventur_kommentar
                            }).execute()

                        st.toast("Inventur erfolgreich abgeschlossen & Bestände aktualisiert!", icon="🎯")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")

            with col_fin2:
                if st.button("🗑️ Zwischenstand zurücksetzen", use_container_width=True):
                    st.session_state["inventur_werte"] = {}
                    st.session_state["inventur_gezahlt_ids"] = set()
                    st.toast("Alle Zähl-Zwischenstände und Häkchen zurückgesetzt.", icon="🔄")
                    st.rerun()

            st.markdown("---")
            inventur_pdf_daten = []
            for m in material_liste:
                m_id = m['id']
                gezahlt_wert = st.session_state["inventur_werte"].get(m_id, m.get('ist_bestand', 0))
                soll = m.get('soll_bestand', 0)
                if gezahlt_wert <= 0:
                    status = "🔴 Leer"
                elif gezahlt_wert < soll:
                    status = "🟡 Unter Soll"
                else:
                    status = "🟢 OK"
                
                inventur_pdf_daten.append([
                    str(m.get('artikelnummer', '-')),
                    str(m.get('bezeichnung', '')),
                    str(m.get('kategorie', 'Allgemein')),
                    str(m.get('lagerort', '-')),
                    f"{gezahlt_wert} {m.get('einheit', 'Stk.')}",
                    str(soll),
                    status
                ])

            if PDF_EXPORT_AVAILABLE and inventur_pdf_daten:
                inv_pdf_bytes = generiere_pdf_bericht(
                    "Inventur-Zählprotokoll",
                    ["Code", "Bezeichnung", "Kategorie", "Lagerort", "Gezählt", "Soll", "Status"],
                    inventur_pdf_daten
                )
                st.download_button(
                    label="📄 Inventur-Protokoll als PDF herunterladen",
                    data=inv_pdf_bytes,
                    file_name=f"Inventur_Protokoll_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf",
                    key="pdf_download_inventur"
                )
