import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import barcode
from barcode.writer import ImageWriter

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_lager_verwaltung(supabase):
    st.title("📦 5. Lager- & Materialverwaltung")
    st.caption("Blitzschnelles Lager: Optimiert für Barcode-Handscanner, Sofort-Buchung & Etikettendruck.")

    if not hat_recht("2", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Lager-Modul aufzurufen.")
        return

    darf_bearbeiten = hat_recht("2", "bearbeiten") or hat_recht("2", "erstellen")

    try:
        m_res = supabase.table("lager_material").select("*").order("bezeichnung").execute()
        material_liste = m_res.data or []
    except Exception:
        material_liste = []

    tabs = st.tabs([
        "📊 Bestandsübersicht", 
        "⚡ Blitz-Buchung (Scanner)", 
        "🖨️ Etiketten drucken",
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

    # --- TAB 2: BLITZ-BUCHUNG (FÜR HANDSCANNER) ---
    with tabs[1]:
        st.subheader("⚡ Blitz-Ein- / Ausbuchung")
        st.caption("Perfekt für Handscanner: Barcode einscannen, Menge anpassen, buchen. Fertig.")

        if not material_liste:
            st.warning("Keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung.")
        else:
            # Hier greift der Handscanner direkt ein
            scanned_code = st.text_input("🔍 Barcode scannen / Artikelnummer eingeben", placeholder="Scanner hierher richten...", key="blitz_scanner_input")

            selected_artikel = None
            if scanned_code:
                selected_artikel = next((m for m in material_liste if str(m.get('artikelnummer')) == str(scanned_code)), None)
                if selected_artikel:
                    st.success(f"Gefunden: **{selected_artikel['bezeichnung']}** (Lagerbestand: {selected_artikel['ist_bestand']} {selected_artikel.get('einheit', 'Stk.')})")
                else:
                    st.warning(f"⚠️ Unbekannter Code '{scanned_code}'. Legen Sie diesen Artikel zuerst unter 'Artikel anlegen' an.")

            if selected_artikel:
                with st.form("blitz_buchungs_form"):
                    buchungs_art = st.radio("Aktion", ["📤 Entnahme (Ausbuchung)", "📥 Zugang (Einbuchung)"], horizontal=True)
                    menge = st.number_input("Menge", min_value=1, value=1, step=1)
                    kommentar = st.text_input("Projekt / Baustelle", placeholder="z.B. BV Schulstraße")

                    if st.form_submit_button("Jetzt buchen", type="primary", use_container_width=True):
                        alter_bestand = selected_artikel.get('ist_bestand', 0)
                        neuer_bestand = alter_bestand + menge if "Zugang" in buchungs_art else max(0, alter_bestand - menge)

                        try:
                            supabase.table("lager_material").update({"ist_bestand": neuer_bestand}).eq("id", selected_artikel['id']).execute()
                            supabase.table("lager_bewegungen").insert({
                                "material_id": selected_artikel['id'],
                                "art": "Einbuchung" if "Zugang" in buchungs_art else "Ausbuchung",
                                "menge": menge,
                                "kommentar": kommentar or "Blitzbuchung"
                            }).execute()

                            st.toast(f"✅ Gebucht! Neuer Bestand: {neuer_bestand}", icon="🎉")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    # --- TAB 3: ETIKETTEN DRUCKEN ---
    with tabs[2]:
        st.subheader("🖨️ Barcode-Etiketten generieren")
        st.caption("Drucken Sie Strichcodes für Ihre Regale, damit der Handscanner sofort greift.")

        if not material_liste:
            st.warning("Keine Artikel vorhanden.")
        else:
            eticket_optionen = {f"{m['bezeichnung']} (Code: {m.get('artikelnummer', 'Keiner')})": m for m in material_liste if m.get('artikelnummer')}
            
            if not eticket_optionen:
                st.info("💡 Hinterlegen Sie bei Ihren Artikeln eine Artikelnummer, um hier Etiketten zu drucken.")
            else:
                ausgewaehlte_labels = st.multiselect("Artikel auswählen", options=list(eticket_optionen.keys()))

                if ausgewaehlte_labels and st.button("🖨️ Barcodes anzeigen", type="primary"):
                    for label in ausgewaehlte_labels:
                        mat = eticket_optionen[label]
                        code_val = str(mat.get('artikelnummer'))
                        
                        col_e1, col_e2 = st.columns([1, 2])
                        with col_e1:
                            try:
                                EAN = barcode.get_class('code128')
                                rv = BytesIO()
                                ean = EAN(code_val, writer=ImageWriter())
                                ean.write(rv)
                                st.image(rv.getvalue(), width=200)
                            except Exception as e:
                                st.error(f"Fehler: {e}")
                        with col_e2:
                            st.write(f"**Bezeichnung:** {mat.get('bezeichnung')}")
                            st.write(f"**Lagerort:** {mat.get('lagerort', 'Hauptlager')}")
                            st.write(f"**Code:** `{code_val}`")
                        st.divider()

    # --- TAB 4: CSV-MASSENIMPORT ---
    with tabs[3]:
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

    # --- TAB 5: INVENTUR ---
    with tabs[4]:
        st.subheader("📋 Systematische Inventur")
        if not material_liste:
            st.warning("Keine Artikel.")
        else:
            with st.form("inventur_form"):
                inventur_daten = {}
                for m in material_liste:
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1: st.write(f"**{m.get('bezeichnung')}** `({m.get('artikelnummer', '-')})`")
                    with c2: st.write(f"Soll: {m.get('ist_bestand', 0)}")
                    with c3:
                        gezahlt = st.number_input("Ist", min_value=0, value=int(m.get('ist_bestand', 0)), key=f"inv_{m['id']}", label_visibility="collapsed")
                        inventur_daten[m['id']] = gezahlt
                    st.divider()
                if st.form_submit_button("✅ Inventur finalisieren", type="primary", use_container_width=True):
                    for mat_id, neuer_ist in inventur_daten.items():
                        supabase.table("lager_material").update({"ist_bestand": neuer_ist}).eq("id", mat_id).execute()
                    st.toast("Inventur abgeschlossen!", icon="🎯")
                    st.rerun()

    # --- TAB 6: ARTIKEL ANLEGEN ---
    with tabs[5]:
        st.subheader("➕ Neuen Artikel anlegen")
        if not darf_bearbeiten:
            st.error("⛔ Keine Berechtigung.")
        else:
            with st.form("neuer_artikel_form"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    n_bezeichnung = st.text_input("Artikelbezeichnung *", placeholder="z.B. NYM-J 3x1.5")
                    n_artnr = st.text_input("Artikelnummer / Barcode", placeholder="Mit Handscanner einscannen oder tippen")
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
