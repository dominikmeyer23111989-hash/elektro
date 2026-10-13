import streamlit as st
import pandas as pd
from datetime import datetime

def hat_recht(modul_id, aktion="sehen"):
    """Prüft über die app.py-Logik, ob das Recht vorliegt."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("Multifunktionales Lager: Barcode-Scanner, Kamera-Erfassung, CSV-Massenimport & manuelle Verwaltung.")

    if not hat_recht("2", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Lager-Modul aufzurufen.")
        return

    darf_bearbeiten = hat_recht("2", "bearbeiten") or hat_recht("2", "erstellen")

    # Daten aus Supabase laden
    try:
        m_res = supabase.table("lager_material").select("*").order("bezeichnung").execute()
        material_liste = m_res.data or []
    except Exception:
        material_liste = []

    tabs = st.tabs([
        "📊 Bestandsübersicht", 
        "⚡ Schnell-Buchung & Barcode", 
        "📷 Kamera & Foto-Erfassung", 
        "📥 CSV-Massenimport", 
        "📋 Inventur", 
        "➕ Artikel anlegen"
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
                    "Artikel-Nr. / Barcode": m.get('artikelnummer', '-'),
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

    # --- TAB 2: SCHNELL-BUCHUNG & BARCODE ---
    with tabs[1]:
        st.subheader("⚡ Schnelle Ein- / Ausbuchung per Barcode oder Auswahl")
        st.caption("Nutzen Sie einen Handscanner oder tippen Sie die Artikelnummer ein.")

        if not material_liste:
            st.warning("Keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            scanned_code = st.text_input("🔍 Artikelnummer / Barcode scannen", placeholder="Scanner hierher richten oder Code eingeben...")

            selected_artikel = None
            if scanned_code:
                selected_artikel = next((m for m in material_liste if str(m.get('artikelnummer')) == str(scanned_code)), None)
                if selected_artikel:
                    st.success(f"Gefunden: **{selected_artikel['bezeichnung']}** (Aktueller Bestand: {selected_artikel['ist_bestand']} {selected_artikel.get('einheit', 'Stk.')})")
                else:
                    st.warning(f"Kein Artikel mit Code '{scanned_code}' im System gefunden.")

            with st.form("schnell_buchung_form"):
                if not selected_artikel:
                    artikel_optionen = {f"{m['bezeichnung']} (Aktuell: {m['ist_bestand']} {m.get('einheit', 'Stk.')}) [Code: {m.get('artikelnummer', '-')}]": m['id'] for m in material_liste}
                    selected_label = st.selectbox("Oder Artikel manuell wählen", options=list(artikel_optionen.keys()))
                    selected_id = artikel_optionen[selected_label]
                    aktiver_artikel = next((m for m in material_liste if m['id'] == selected_id), None)
                else:
                    aktiver_artikel = selected_artikel
                    selected_id = selected_artikel['id']

                buchungs_art = st.radio("Buchungsart *", ["📥 Einbuchung (Zugang)", "📤 Ausbuchung (Entnahme)"], horizontal=True)
                menge = st.number_input("Menge *", min_value=1, value=1, step=1)
                kommentar = st.text_input("Grund / Projekt / Bemerkung", placeholder="z.B. Baustelle Bahnhofstraße")

                if st.form_submit_button("Bestand jetzt buchen", type="primary", use_container_width=True):
                    if aktiver_artikel:
                        alter_bestand = aktiver_artikel.get('ist_bestand', 0)
                        neuer_bestand = alter_bestand + menge if "Einbuchung" in buchungs_art else max(0, alter_bestand - menge)

                        try:
                            supabase.table("lager_material").update({"ist_bestand": neuer_bestand}).eq("id", selected_id).execute()
                            try:
                                supabase.table("lager_bewegungen").insert({
                                    "material_id": selected_id,
                                    "art": "Einbuchung" if "Einbuchung" in buchungs_art else "Ausbuchung",
                                    "menge": menge,
                                    "kommentar": kommentar or "Schnellbuchung"
                                }).execute()
                            except Exception:
                                pass

                            st.toast(f"✅ Buchung erfolgreich! Neuer Bestand: {neuer_bestand}", icon="🎉")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    # --- TAB 3: KAMERA & FOTO-ERFASSUNG ---
    with tabs[2]:
        st.subheader("📷 Mobile Kamera & Foto-Dokumentation")
        st.caption("Machen Sie mit Ihrem Smartphone direkt ein Foto vom Material oder Typenschild, um es im Lager zu dokumentieren.")

        foto = st.camera_input("Foto aufnehmen")
        if foto:
            st.image(foto, caption="Aufgenommenes Materialfoto", width=350)
            st.success("✅ Foto erfolgreich aufgenommen und im Arbeitsspeicher hinterlegt.")

    # --- TAB 4: CSV-MASSENIMPORT ---
    with tabs[3]:
        st.subheader("📥 Massen-Import (CSV)")
        st.caption("Laden Sie eine CSV-Liste hoch, um hunderte Artikel auf einmal in das Lager einzupflegen.")

        st.markdown("""
        **Format-Anleitung für Ihre CSV-Datei:**
        Die CSV-Datei muss folgende Spaltennamen in der ersten Zeile besitzen:
        `artikelnummer`, `bezeichnung`, `kategorie`, `einheit`, `soll_bestand`, `ist_bestand`, `lagerort`
        """)

        uploaded_file = st.file_uploader("CSV-Datei auswählen", type=["csv"])
        if uploaded_file is not None:
            try:
                df_import = pd.read_csv(uploaded_file)
                st.write("Vorschau der importierten Daten:", df_import.head())

                if st.button("🚀 Alle Artikel aus CSV importieren", type="primary"):
                    erfolgreich = 0
                    for _, row in df_import.iterrows():
                        payload = {
                            "artikelnummer": str(row.get('artikelnummer', '')),
                            "bezeichnung": str(row.get('bezeichnung', 'Unbekannt')),
                            "kategorie": str(row.get('kategorie', 'Allgemein')),
                            "einheit": str(row.get('einheit', 'Stk.')),
                            "soll_bestand": int(row.get('soll_bestand', 5)),
                            "ist_bestand": int(row.get('ist_bestand', 0)),
                            "lagerort": str(row.get('lagerort', 'Hauptlager'))
                        }
                        supabase.table("lager_material").insert(payload).execute()
                        erfolgreich += 1

                    st.toast(f"✅ {erfolgreich} Artikel erfolgreich importiert!", icon="🎉")
                    st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Verarbeiten der CSV-Datei: {e}")

    # --- TAB 5: INVENTUR ---
    with tabs[4]:
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

    # --- TAB 6: ARTIKEL ANLEGEN ---
    with tabs[5]:
        st.subheader("➕ Neuen Artikel händisch anlegen")
        if not darf_bearbeiten:
            st.error("⛔ Keine Berechtigung.")
        else:
            with st.form("neuer_artikel_form"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    n_bezeichnung = st.text_input("Artikelbezeichnung *", placeholder="z.B. NYM-J 3x1.5")
                    n_artnr = st.text_input("Artikelnummer / Barcode", placeholder="z.B. EAN-Code")
                    n_kategorie = st.selectbox("Kategorie", ["Kabel & Leitungen", "Schalter & Steckdosen", "Verteiler", "Kleinmaterial", "Leuchtmittel", "Werkzeug"])
                with col_a2:
                    n_einheit = st.selectbox("Einheit", ["Stk.", "Meter", "Rolle", "Paket", "Liter", "kg"])
                    n_lagerort = st.text_input("Lagerort / Regal", placeholder="z.B. Regal A1")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        n_soll = st.number_input("Mindestbestand", min_value=0, value=5)
                    with col_b2:
                        n_ist = st.number_input("Anfangsbestand", min_value=0, value=10)

                if st.form_submit_button("Artikel speichern", type="primary", use_container_width=True):
                    if not n_bezeichnung:
                        st.warning("Bitte Bezeichnung angeben.")
                    else:
                        try:
                            supabase.table("lager_material").insert({
                                "bezeichnung": n_bezeichnung,
                                "artikelnummer": n_artnr if n_artnr else None,
                                "kategorie": n_kategorie,
                                "einheit": n_einheit,
                                "lagerort": n_lagerort,
                                "soll_bestand": n_soll,
                                "ist_bestand": n_ist
                            }).execute()
                            st.toast(f"Artikel '{n_bezeichnung}' angelegt!", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")
