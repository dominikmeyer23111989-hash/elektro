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
    st.caption("Verwalten Sie Artikel, Soll- und Ist-Bestände, buchen Sie Material ein/aus und führen Sie strukturierte Inventuren durch.")

    if not hat_recht("2", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Lager-Modul aufzurufen.")
        return

    darf_bearbeiten = hat_recht("2", "bearbeiten") or hat_recht("2", "erstellen")

    try:
        m_res = supabase.table("lager_material").select("*").order("bezeichnung").execute()
        material_liste = m_res.data or []
    except Exception:
        material_liste = []

    tabs = st.tabs(["📊 Bestandsübersicht & Buchung", "⚡ Schnelle Ein-/Ausbuchung", "📋 Inventur-Modus", "➕ Neuen Artikel anlegen"])

    # --- TAB 1: BESTANDSÜBERSICHT ---
    with tabs[0]:
        st.subheader("Aktueller Lagerbestand")

        if not material_liste:
            st.info("Noch keine Artikel im Lager vorhanden. Legen Sie im Reiter 'Neuen Artikel anlegen' den ersten Artikel an.")
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
                    "Artikel-Nr.": m.get('artikelnummer', '-'),
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
                st.warning("Keine Artikel gefunden, die dem Suchbegriff entsprechen.")

    # --- TAB 2: SCHNELLE EIN- / AUSBUCHUNG ---
    with tabs[1]:
        st.subheader("Material ein- oder ausbuchen")
        st.caption("Buchen Sie Artikel direkt zu oder ab (z.B. nach Einkauf oder Entnahme für das Fahrzeug).")

        if not material_liste:
            st.warning("Keine Artikel im Lager vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung, Bestände zu verändern.")
        else:
            with st.form("schnell_buchung_form"):
                artikel_optionen = {f"{m['bezeichnung']} (Aktuell: {m['ist_bestand']} {m.get('einheit', 'Stk.')}) [Art-Nr: {m.get('artikelnummer', '-')}]": m['id'] for m in material_liste}
                
                selected_label = st.selectbox("Artikel auswählen *", options=list(artikel_optionen.keys()))
                selected_id = artikel_optionen[selected_label]

                aktiver_artikel = next((m for m in material_liste if m['id'] == selected_id), None)

                buchungs_art = st.radio("Buchungsart *", ["📥 Einbuchung (Zugang / Lieferung)", "📤 Ausbuchung (Entnahme / Verbrauch)"], horizontal=True)
                menge = st.number_input("Menge *", min_value=1, value=1, step=1)
                kommentar = st.text_input("Grund / Projekt / Bemerkung (optional)", placeholder="z.B. Nachbestellung Großhändler oder Entnahme Baustelle")

                if st.form_submit_button("Bestand jetzt buchen", type="primary", use_container_width=True):
                    if aktiver_artikel:
                        alter_bestand = aktiver_artikel.get('ist_bestand', 0)
                        if "Einbuchung" in buchungs_art:
                            neuer_bestand = alter_bestand + menge
                        else:
                            neuer_bestand = max(0, alter_bestand - menge)

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
                            st.error(f"Fehler beim Speichern der Buchung: {e}")

    # --- TAB 3: INVENTUR-MODUS ---
    with tabs[2]:
        st.subheader("📋 Systematische Inventur")
        st.caption("Tragen Sie hier die tatsächlichen Zählbestände ein. Das System gleicht das Soll mit dem Ist ab.")

        if not material_liste:
            st.warning("Keine Artikel für eine Inventur vorhanden.")
        elif not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung, eine Inventur durchzuführen.")
        else:
            st.info("💡 Tipp: Geben Sie für jeden Artikel den physisch gezählten Ist-Bestand ein und klicken Sie unten auf Inventur abschließen.")

            with st.form("inventur_form"):
                inventur_daten = {}
                for m in material_liste:
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.write(f"**{m.get('bezeichnung')}** `({m.get('artikelnummer', 'Keine Art-Nr')})`")
                        st.caption(f"Lagerort: {m.get('lagerort', 'Standard')} | Einheit: {m.get('einheit', 'Stk.')}")
                    with col2:
                        st.write(f"Soll: **{m.get('ist_bestand', 0)}**")
                    with col3:
                        gezahlt = st.number_input(
                            "Gezählter Bestand", 
                            min_value=0, 
                            value=int(m.get('ist_bestand', 0)), 
                            step=1, 
                            key=f"inv_{m['id']}",
                            label_visibility="collapsed"
                        )
                        inventur_daten[m['id']] = gezahlt
                    st.divider()

                if st.form_submit_button("✅ Inventur finalisieren & Bestände aktualisieren", type="primary", use_container_width=True):
                    try:
                        for mat_id, neuer_ist in inventur_daten.items():
                            supabase.table("lager_material").update({"ist_bestand": neuer_ist}).eq("id", mat_id).execute()
                            
                            try:
                                supabase.table("lager_bewegungen").insert({
                                    "material_id": mat_id,
                                    "art": "Inventurkorrektur",
                                    "menge": neuer_ist,
                                    "kommentar": "Perioden-Inventur"
                                }).execute()
                            except Exception:
                                pass

                        st.toast("Inventur erfolgreich abgeschlossen!", icon="🎯")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler bei der Inventur-Speicherung: {e}")

    # --- TAB 4: NEUEN ARTIKEL ANLEGEN ---
    with tabs[3]:
        st.subheader("Neuen Artikel zum Lager hinzufügen")

        if not darf_bearbeiten:
            st.error("⛔ Ihr Account hat keine Berechtigung, neue Artikel anzulegen.")
        else:
            with st.form("neuer_artikel_form"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    n_bezeichnung = st.text_input("Artikelbezeichnung *", placeholder="z.B. NYM-J 3x1.5 mm² Mantelleitung")
                    n_artnr = st.text_input("Artikelnummer / Barcode", placeholder="z.B. CAB-3X15")
                    n_kategorie = st.selectbox("Kategorie", ["Kabel & Leitungen", "Schalter & Steckdosen", "Verteiler & Sicherungen", "Kleinmaterial", "Leuchtmittel", "Werkzeug", "Sonstiges"])
                with col_a2:
                    n_einheit = st.selectbox("Einheit", ["Stk.", "Meter", "Rolle", "Paket", "Liter", "kg"])
                    n_lagerort = st.text_input("Lagerort / Regal", placeholder="z.B. Regal A1, Fach 3")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        n_soll = st.number_input("Mindestbestand (Soll)", min_value=0, value=5, step=1)
                    with col_b2:
                        n_ist = st.number_input("Aktueller Anfangsbestand", min_value=0, value=10, step=1)

                n_preis = st.number_input("Einkaufspreis netto (€, optional)", min_value=0.0, value=0.0, step=0.10)

                if st.form_submit_button("Artikel im Lager anlegen", type="primary", use_container_width=True):
                    if not n_bezeichnung:
                        st.warning("Bitte geben Sie mindestens eine Artikelbezeichnung an.")
                    else:
                        try:
                            artikel_payload = {
                                "bezeichnung": n_bezeichnung,
                                "artikelnummer": n_artnr if n_artnr else None,
                                "kategorie": n_kategorie,
                                "einheit": n_einheit,
                                "lagerort": n_lagerort,
                                "soll_bestand": n_soll,
                                "ist_bestand": n_ist,
                                "einkaufspreis": n_preis
                            }
                            supabase.table("lager_material").insert(artikel_payload).execute()
                            st.toast(f"Artikel '{n_bezeichnung}' erfolgreich angelegt!", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Anlegen des Artikels: {e}")
