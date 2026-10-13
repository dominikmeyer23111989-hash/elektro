import streamlit as st
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from zoneinfo import ZoneInfo
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from io import BytesIO
import base64
import tempfile
import os

class AuftragPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'ELEKTRO-ENTERPRISE - MONTAGESCHEIN / ABNAHMEPROTOKOLL', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, 'Offizieller Arbeitsauftrag inklusive Objekt-, Team-, Fahrzeug- und Signaturdaten', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def clean_text(text):
    if not text:
        return "-"
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def format_de_datum(iso_string):
    if not iso_string:
        return "-"
    try:
        s = str(iso_string).split("T")[0]
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime('%d.%m.%Y')
    except Exception:
        return str(iso_string)

def format_de_zeit(iso_string):
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo("Europe/Berlin"))
        return dt.strftime('%d.%m.%Y um %H:%M Uhr')
    except Exception:
        return str(iso_string)[:16]

def draw_signature_on_pdf(pdf, base64_str, label):
    """Fügt eine Base64-Unterschrift sauber in das FPDF-Dokument ein."""
    if not base64_str or not base64_str.startswith('data:image'):
        return
    try:
        header, encoded = base64_str.split(",", 1)
        data = base64.b64decode(encoded)
        image = Image.open(BytesIO(data))
        
        # Auf weißem Hintergrund normalisieren
        rgb_img = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == 'RGBA':
            rgb_img.paste(image, mask=image.split()[3])
        else:
            rgb_img.paste(image)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            rgb_img.save(tmp.name, format="PNG")
            tmp_path = tmp.name
            
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 5, clean_text(label), new_x="LMARGIN", new_y="NEXT")
        pdf.image(tmp_path, w=45) # ca. 45 mm Breite für die Unterschrift
        os.unlink(tmp_path)
    except Exception as e:
        print(f"Fehler beim Rendern der Unterschrift: {e}")

def generate_auftrag_pdf(a, kunde, gebaeude, fahrzeug, team_liste):
    pdf = AuftragPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 6, clean_text(f"Auftragsnummer: {a.get('auftragsnummer')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    
    status_str = a.get('status', 'In Planung')
    pdf.cell(0, 6, clean_text(f"Status: {status_str}"), new_x="LMARGIN", new_y="NEXT")
    
    a_datum_de = format_de_datum(a.get('termin_um'))
    t_von_de = format_de_zeit(a.get('termin_um'))
    t_bis_de = format_de_zeit(a.get('termin_bis'))
    
    pdf.cell(0, 6, clean_text(f"Auftragsdatum: {a_datum_de}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, clean_text(f"Einsatztermin: Von {t_von_de} bis {t_bis_de}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Auftraggeber & Objektanschrift:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    
    if kunde:
        k_name = f"{kunde.get('vorname', '')} {kunde.get('nachname', '')}"
        k_tel = kunde.get('telefon', '-')
        pdf.cell(0, 6, clean_text(f"Kunde: {k_name} (Tel: {k_tel})"), new_x="LMARGIN", new_y="NEXT")
    elif a.get('freitext_kunde'):
        pdf.cell(0, 6, clean_text(f"Kunde (Manuell): {a.get('freitext_kunde')}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, clean_text("Kunde: Kein Kunde angegeben"), new_x="LMARGIN", new_y="NEXT")
    
    if gebaeude:
        g_adr = f"{gebaeude.get('strasse')} {gebaeude.get('hausnummer')}, {gebaeude.get('ort')}"
        g_code = f"[{gebaeude.get('gebaeude_code')}] " if gebaeude.get('gebaeude_code') else ""
        pdf.cell(0, 6, clean_text(f"Objektadresse: {g_code}{g_adr}"), new_x="LMARGIN", new_y="NEXT")
        if a.get('mieter_we'):
            pdf.cell(0, 6, clean_text(f"Betroffene WE / Mieter: {a.get('mieter_we')}"), new_x="LMARGIN", new_y="NEXT")
    elif a.get('freitext_ort'):
        pdf.cell(0, 6, clean_text(f"Auftragsort (Manuell): {a.get('freitext_ort')}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, clean_text("Objektadresse: Keine Adresse angegeben"), new_x="LMARGIN", new_y="NEXT")
    
    team_names = ", ".join([f"{m.get('vorname', '')} {m.get('nachname', '')}" for m in team_liste]) if team_liste else "Kein Team zugewiesen"
    pdf.cell(0, 6, clean_text(f"Einsatz-Team (Monteure / Azubis): {team_names}"), new_x="LMARGIN", new_y="NEXT")

    if fahrzeug:
        f_info = f"{fahrzeug.get('marke', '')} {fahrzeug.get('modell', '')} ({fahrzeug.get('kennzeichen', '')})"
        pdf.cell(0, 6, clean_text(f"Zugewiesenes Fahrzeug: {f_info}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, clean_text("Zugewiesenes Fahrzeug: Kein Fahrzeug zugeordnet"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Auszuführende Arbeiten / Leistungsbeschreibung:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 5, clean_text(a.get('arbeiten', '-')))
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Verbrauchtes / Benötigtes Material:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 5, clean_text(a.get('benoetigtes_material', 'Noch kein Material eingetragen.')))
    pdf.ln(6)

    # Unterschriften auf dem PDF ausgeben
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Digitale Abnahme & Unterschriften:", new_x="LMARGIN", new_y="NEXT")
    
    draw_signature_on_pdf(pdf, a.get('kunde_unterschrift'), "Unterschrift Kunde / Auftraggeber:")
    draw_signature_on_pdf(pdf, a.get('mitarbeiter_unterschrift'), "Unterschrift Monteur / Einsatz-Team:")

    return pdf.output()

def hat_recht(modul_id, aktion="sehen"):
    """Prüft über die app.py-Logik, ob das Recht vorliegt."""
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_auftraege_verwaltung(supabase):
    st.title("📋 4. Auftrags- & Einsatzmanagement")
    st.caption("Planen Sie Aufträge, steuern Sie den Status, weisen Sie Teams & Fahrzeuge zu und erfassen Sie Material inkl. digitaler Unterschriftenabnahme.")

    if not hat_recht("4", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Auftragsmodul aufzurufen.")
        return

    user_data = st.session_state.get("user_data", {})
    user_id = user_data.get("id")
    user_rolle = user_data.get("rolle", "")
    
    is_admin = hat_recht("4", "erstellen") or hat_recht("4", "bearbeiten") or (user_rolle in ["Admin", "Büro", "Inhaber"])

    # Daten laden
    try:
        a_res = supabase.table("auftraege").select("*, kunden(*), gebaeude(*), fahrzeuge(*)").order("erstellt_am", desc=True).execute()
        auftraege_liste = a_res.data or []
    except Exception:
        auftraege_liste = []

    try:
        k_res = supabase.table("kunden").select("id, vorname, nachname, firma").order("nachname").execute()
        kunden_liste = k_res.data or []
    except Exception:
        kunden_liste = []

    try:
        g_res = supabase.table("gebaeude").select("id, strasse, hausnummer, ort, gebaeude_code").order("ort").execute()
        gebaeude_liste = g_res.data or []
    except Exception:
        gebaeude_liste = []

    try:
        f_res = supabase.table("fahrzeuge").select("*").execute()
        fahrzeuge_liste = f_res.data or []
    except Exception:
        fahrzeuge_liste = []

    try:
        m_res = supabase.table("mitarbeiter").select("id, vorname, nachname").eq("ist_aktiv", True).execute()
        mitarbeiter_liste = m_res.data or []
    except Exception:
        mitarbeiter_liste = []

    verfuegbare_mitarbeiter = []
    heute_str = datetime.now().strftime("%Y-%m-%d")

    for ma in mitarbeiter_liste:
        try:
            abw_res = supabase.table("mitarbeiter_abwesenheit").select("*").eq("mitarbeiter_id", ma["id"]).lte("von_datum", heute_str).gte("bis_datum", heute_str).execute()
            if abw_res.data:
                continue
        except Exception:
            pass
        verfuegbare_mitarbeiter.append(ma)

    tabs_optionen = ["📋 Auftragsübersicht"]
    darf_erstellen = hat_recht("4", "erstellen")
    if darf_erstellen:
        tabs_optionen.append("➕ Neuen Auftrag anlegen")

    tabs = st.tabs(tabs_optionen)

    # --- TAB 1: ÜBERSICHT ---
    with tabs[0]:
        st.subheader("Auftragsliste & Digitale Unterschriftenabnahme")

        sichtbare_auftraege = []
        for a in auftraege_liste:
            try:
                team_res = supabase.table("auftrag_mitarbeiter").select("mitarbeiter_id, mitarbeiter(id, vorname, nachname)").eq("auftrag_id", a["id"]).execute()
                team_mitglieder = [t["mitarbeiter"] for t in (team_res.data or []) if t.get("mitarbeiter")]
            except Exception:
                team_mitglieder = []
            
            a["team"] = team_mitglieder
            status = a.get("status", "In Planung")

            if not is_admin:
                if status == "In Planung":
                    continue
                user_in_team = any(m["id"] == user_id for m in team_mitglieder)
                if not user_in_team:
                    continue

            sichtbare_auftraege.append(a)

        if not sichtbare_auftraege:
            st.info("Keine Aufträge vorhanden oder aktuell keine Freigabe für Ihr Konto (Aufträge 'In Planung' sind für Monteure unsichtbar).")
        else:
            darf_bearbeiten = hat_recht("4", "bearbeiten")

            for a in sichtbare_auftraege:
                kunde = a.get("kunden") or {}
                gebaeude = a.get("gebaeude") or {}
                fahrzeug = a.get("fahrzeuge") or {}
                team = a.get("team", [])

                status = a.get("status", "In Planung")
                status_icons = {
                    "In Planung": "⏳",
                    "Offener Auftrag": "🔴",
                    "In Bearbeitung": "🟡",
                    "Erledigt": "🟢"
                }
                status_icon = status_icons.get(status, "⚪")

                k_name = f"{kunde.get('vorname', '')} {kunde.get('nachname', '')}".strip() or a.get("freitext_kunde") or "Spontanauftrag"
                g_adr = f"{gebaeude.get('strasse', '')} {gebaeude.get('hausnummer', '')}, {gebaeude.get('ort', '')}" if gebaeude else a.get("freitext_ort") or "Kein Objekt"
                team_names = ", ".join([f"{m['vorname']} {m['nachname']}" for m in team]) or "Kein Team zugewiesen"
                
                f_marke = fahrzeug.get('marke') or fahrzeug.get('titel') or 'Fahrzeug'
                f_kennz = fahrzeug.get('kennzeichen') or ''
                f_info = f"{f_marke} ({f_kennz})" if f_kennz else f_marke

                with st.expander(f"{status_icon} [{a.get('auftragsnummer')}] Status: {status} | Kunde: {k_name} | Team: {team_names}"):
                    a_datum_de = format_de_datum(a.get('termin_um'))
                    st.write(f"**Auftragsdatum:** {a_datum_de}")
                    st.write(f"**Objektadresse:** {g_adr}")
                    st.write(f"**Auszuführende Arbeiten:** {a.get('arbeiten')}")
                    if a.get('mieter_we'):
                        st.write(f"**Mieter / WE:** {a.get('mieter_we')}")
                
                    t_von_de = format_de_zeit(a.get('termin_um'))
                    t_bis_de = format_de_zeit(a.get('termin_bis'))
                    st.write(f"**Einsatztermin:** Von {t_von_de} bis {t_bis_de}")
                    st.write(f"**Zugewiesenes Fahrzeug:** {f_info}")
                    st.write(f"**Benötigtes Material:** {a.get('benoetigtes_material') or 'Noch nichts eingetragen'}")

                    st.markdown("---")
                    st.write("🛠️ **Bearbeitung, Status & Materialerfassung**")

                    if not darf_bearbeiten:
                        st.info("ℹ️ Ihr Account hat nur Leserechte für Aufträge. Sie können keine Änderungen speichern.")
                    
                    with st.form(f"auftrag_edit_{a['id']}"):
                        neuer_status = st.selectbox(
                            "Status ändern", 
                            ["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"], 
                            index=["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"].index(status) if status in ["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"] else 0,
                            disabled=not darf_bearbeiten
                        )
                        verbrauchtes_material = st.text_area("Benötigtes / Verbrautes Material eintragen", value=a.get("benoetigtes_material") or "", disabled=not darf_bearbeiten)
                        
                        neues_team = []
                        neues_fahrzeug = a.get("fahrzeug_id")

                        if is_admin:
                            st.markdown("---")
                            st.write("👑 **Admin-Bereich: Team & Fahrzeug neu zuweisen**")
                            
                            aktuelle_team_ids = [m["id"] for m in team]
                            neues_team = st.multiselect(
                                "Einsatz-Team (Monteure & Azubis wählen)",
                                options=[m["id"] for m in verfuegbare_mitarbeiter],
                                format_func=lambda x: next(f"{m['vorname']} {m['nachname']}" for m in verfuegbare_mitarbeiter if m["id"] == x),
                                default=[mid for mid in aktuelle_team_ids if mid in [m["id"] for m in verfuegbare_mitarbeiter]],
                                disabled=not darf_bearbeiten
                            )

                            fahrzeug_optionen = [None] + [f["id"] for f in fahrzeuge_liste]
                            neues_fahrzeug = st.selectbox(
                                "Fahrzeug zuweisen (optional)",
                                options=fahrzeug_optionen,
                                format_func=lambda x: "--- Kein Fahrzeug ---" if x is None else next((f"{f.get('marke', f.get('titel', 'Fahrzeug'))} ({f.get('kennzeichen', '')})" for f in fahrzeuge_liste if f["id"] == x), ""),
                                index=fahrzeug_optionen.index(a.get("fahrzeug_id")) if a.get("fahrzeug_id") in fahrzeug_optionen else 0,
                                disabled=not darf_bearbeiten
                            )

                        if darf_bearbeiten:
                            b_save = st.form_submit_button("💾 Änderungen & Material speichern", type="primary", use_container_width=True)
                            if b_save:
                                try:
                                    update_payload = {
                                        "status": neuer_status,
                                        "benoetigtes_material": verbrauchtes_material
                                    }
                                    if is_admin:
                                        update_payload["fahrzeug_id"] = neues_fahrzeug

                                    supabase.table("auftraege").update(update_payload).eq("id", a["id"]).execute()

                                    if is_admin:
                                        supabase.table("auftrag_mitarbeiter").delete().eq("auftrag_id", a["id"]).execute()
                                        if neues_team:
                                            team_inserts = [{"auftrag_id": a["id"], "mitarbeiter_id": m_id} for m_id in neues_team]
                                            supabase.table("auftrag_mitarbeiter").insert(team_inserts).execute()

                                    st.success("Auftrag erfolgreich aktualisiert!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler: {e}")

                    # --- DIGITALE UNTERSCHRIFTEN ---
                    st.markdown("---")
                    st.write("✍️ **Digitale Unterschriften (Abnahmeprotokoll)**")
                    
                    col_sig1, col_sig2 = st.columns(2)
                    
                    with col_sig1:
                        st.markdown("Unterschrift Kunde / Auftraggeber")
                        canvas_kunde = st_canvas(
                            fill_color="rgba(255, 165, 0, 0.3)",
                            stroke_width=2,
                            stroke_color="#000000",
                            background_color="#FFFFFF",
                            height=100,
                            width=300,
                            drawing_mode="freedraw",
                            key=f"canvas_kunde_{a['id']}"
                        )
                        if st.button("💾 Kunde Unterschrift speichern", key=f"btn_save_kunde_{a['id']}"):
                            if canvas_kunde.json_data is not None and len(canvas_kunde.json_data.get("objects", [])) > 0:
                                try:
                                    img = Image.fromarray(canvas_kunde.image_data.astype('uint8'), 'RGBA')
                                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                                    rgb_img.paste(img, mask=img.split()[3])
                                    buffered = BytesIO()
                                    rgb_img.save(buffered, format="PNG")
                                    sig_base64 = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
                                    
                                    supabase.table("auftraege").update({"kunde_unterschrift": sig_base64}).eq("id", a["id"]).execute()
                                    st.success("Kundenunterschrift erfolgreich gespeichert!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler beim Speichern: {e}")
                            else:
                                st.warning("⚠️ Bitte zuerst im Feld unterschreiben, bevor Sie speichern!")

                    with col_sig2:
                        st.markdown("Unterschrift Monteur / Team")
                        canvas_ma = st_canvas(
                            fill_color="rgba(255, 165, 0, 0.3)",
                            stroke_width=2,
                            stroke_color="#000000",
                            background_color="#FFFFFF",
                            height=100,
                            width=300,
                            drawing_mode="freedraw",
                            key=f"canvas_ma_{a['id']}"
                        )
                        if st.button("💾 Monteur Unterschrift speichern", key=f"btn_save_ma_{a['id']}"):
                            if canvas_ma.json_data is not None and len(canvas_ma.json_data.get("objects", [])) > 0:
                                try:
                                    img = Image.fromarray(canvas_ma.image_data.astype('uint8'), 'RGBA')
                                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                                    rgb_img.paste(img, mask=img.split()[3])
                                    buffered = BytesIO()
                                    rgb_img.save(buffered, format="PNG")
                                    sig_base64 = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
                                    
                                    supabase.table("auftraege").update({"mitarbeiter_unterschrift": sig_base64}).eq("id", a["id"]).execute()
                                    st.success("Monteurunterschrift erfolgreich gespeichert!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler beim Speichern: {e}")
                            else:
                                st.warning("⚠️ Bitte zuerst im Feld unterschreiben, bevor Sie speichern!")

                    st.markdown("---")
                    # Frische Daten für das PDF abrufen (inkl. gespeicherter Signaturen)
                    try:
                        fresh_res = supabase.table("auftraege").select("*").eq("id", a["id"]).execute()
                        current_a = fresh_res.data[0] if fresh_res.data else a
                    except Exception:
                        current_a = a

                    pdf_bytes = generate_auftrag_pdf(current_a, kunde, gebaeude, fahrzeug, team)
                    st.download_button(
                        label=f"📥 Abnahmeprotokoll-PDF mit Unterschriften herunterladen ({a.get('auftragsnummer')})",
                        data=bytes(pdf_bytes),
                        file_name=f"Abnahmeprotokoll_{a.get('auftragsnummer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{a['id']}"
                    )

    # --- TAB 2: NEUEN AUFTRAG ANLEGEN ---
    if darf_erstellen and len(tabs) > 1:
        with tabs[1]:
            st.subheader("Neuen Auftrag erstellen")

            with st.form("neuer_auftrag_form"):
                col1, col2 = st.columns(2)
                with col1:
                    n_auftragsnummer = st.text_input("Auftragsnummer *", value=f"A-{datetime.now().strftime('%Y%m%d')}-01")
                    
                    kunden_optionen = [None] + [k["id"] for k in kunden_liste]
                    n_kunde = st.selectbox(
                        "Auftraggeber (Kunde aus Modul wählen)",
                        options=kunden_optionen,
                        format_func=lambda x: "--- Anderer / Spontankunde (Freitext unten) ---" if x is None else next((f"{k['nachname']}, {k['vorname']} ({k.get('firma', 'Privat')})" for k in kunden_liste if k["id"] == x), "")
                    )
                    n_freitext_kunde = st.text_input("Oder Spontankunde / Name & Telefon (Freitext)", placeholder="z.B. Herr Müller, Tel: 0171-1234567")

                    gebaeude_optionen = [None] + [g["id"] for g in gebaeude_liste]
                    n_gebaeude = st.selectbox(
                        "Auftragsort (Gebäude / Objekt wählen)",
                        options=gebaeude_optionen,
                        format_func=lambda x: "--- Alternative Anschrift (Freitext unten) ---" if x is None else next((f"[{g.get('gebaeude_code', 'Kein Code')}] {g['strasse']} {g['hausnummer']}, {g['ort']}" for g in gebaeude_liste if g["id"] == x), "")
                    )
                    n_freitext_ort = st.text_input("Oder alternativer Auftragsort (Freitext)", placeholder="z.B. Bahnhofstraße 10, 44787 Bochum")

                    n_mieter_we = st.text_input("Mieter / WE / Etage (optional)", placeholder="z.B. WE 4, 2. Obergeschoss links")
                    
                    n_status = st.selectbox("Initialer Status", ["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"], index=0)
                    st.caption("ℹ️ Hinweis: Aufträge im Status 'In Planung' sind für Monteure unsichtbar.")

                with col2:
                    if verfuegbare_mitarbeiter:
                        n_team = st.multiselect(
                            "Einsatz-Team (Monteure & Azubis wählen) *",
                            options=[m["id"] for m in verfuegbare_mitarbeiter],
                            format_func=lambda x: next(f"{m['vorname']} {m['nachname']}" for m in verfuegbare_mitarbeiter if m["id"] == x)
                        )
                    else:
                        n_team = []
                        st.warning("Keine verfügbaren Mitarbeiter gefunden.")

                    fahrzeug_optionen = [None] + [f["id"] for f in fahrzeuge_liste]
                    n_fahrzeug = st.selectbox(
                        "Fahrzeug zuweisen (optional)",
                        options=fahrzeug_optionen,
                        format_func=lambda x: "--- Kein Fahrzeug ---" if x is None else next((f"{f.get('marke', f.get('titel', 'Fahrzeug'))} ({f.get('kennzeichen', '')})" for f in fahrzeuge_liste if f["id"] == x), "")
                    )
                    
                    st.write("Termindaten & Auftragsdatum")
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        n_datum = st.date_input("Auftragsdatum (TT.MM.JJJJ)", value=datetime.today(), format="DD.MM.YYYY")
                    with col_d2:
                        n_uhr_von = st.time_input("Uhrzeit Von", value=datetime.strptime("08:00", "%H:%M").time())
                        n_uhr_bis = st.time_input("Uhrzeit Bis", value=datetime.strptime("16:00", "%H:%M").time())

                n_arbeiten = st.text_area("Auszuführende Arbeiten *", placeholder="z.B. Zählerschrank umbauen, Notdienst Störung Beseitigung...")
                n_material = st.text_area("Benötigtes Material (Vorbereitung)", placeholder="z.B. 1x FI-Schalter, 15m NYM-J 3x1.5...")

                if st.form_submit_button("Auftrag anlegen & zuweisen", type="primary", use_container_width=True):
                    if not n_auftragsnummer or not n_arbeiten:
                        st.warning("Bitte Auftragsnummer und auszuführende Arbeiten angeben.")
                    elif not n_team:
                        st.warning("Bitte wählen Sie mindestens einen Mitarbeiter für das Team aus.")
                    else:
                        try:
                            dt_von = datetime.combine(n_datum, n_uhr_von).astimezone(ZoneInfo("Europe/Berlin")).isoformat()
                            dt_bis = datetime.combine(n_datum, n_uhr_bis).astimezone(ZoneInfo("Europe/Berlin")).isoformat()

                            auftrag_payload = {
                                "auftragsnummer": n_auftragsnummer,
                                "kunde_id": n_kunde,
                                "freitext_kunde": n_freitext_kunde if not n_kunde else None,
                                "gebaeude_id": n_gebaeude,
                                "freitext_ort": n_freitext_ort if not n_gebaeude else None,
                                "fahrzeug_id": n_fahrzeug,
                                "arbeiten": n_arbeiten,
                                "mieter_we": n_mieter_we,
                                "termin_um": dt_von,
                                "termin_bis": dt_bis,
                                "benoetigtes_material": n_material,
                                "status": n_status
                            }
                            res = supabase.table("auftraege").insert(auftrag_payload).execute()
                            
                            if res.data:
                                neu_id = res.data[0]["id"]
                                team_inserts = [{"auftrag_id": neu_id, "mitarbeiter_id": m_id} for m_id in n_team]
                                supabase.table("auftrag_mitarbeiter").insert(team_inserts).execute()

                            st.success(f"Auftrag {n_auftragsnummer} erfolgreich angelegt!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler beim Anlegen: {e}")
