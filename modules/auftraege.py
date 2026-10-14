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
        self.cell(0, 5, 'Offizieller Arbeitsauftrag inklusive Objekt-, Team-, Fahrzeug- und Materialdaten', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
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
    if not base64_str or not base64_str.startswith('data:image'):
        return
    try:
        header, encoded = base64_str.split(",", 1)
        data = base64.b64decode(encoded)
        image = Image.open(BytesIO(data))
        
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
        pdf.image(tmp_path, w=45)
        os.unlink(tmp_path)
    except Exception as e:
        print(f"Fehler beim Rendern der Unterschrift: {e}")

def generate_auftrag_pdf(a, kunde, gebaeude, fahrzeug, team_liste, material_positionen):
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
    pdf.cell(0, 6, "Verbrauchtes Material & Bauteile (Lager & Vor Ort):", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    
    if material_positionen:
        for mp in material_positionen:
            menge = mp.get('menge', 1)
            if mp.get('ist_fremdmaterial'):
                bez = mp.get('freitext_bezeichnung', 'Fremdteil')
                einheit_str = "Stk."
            else:
                mat_info = mp.get('lager_material') or {}
                bez = mat_info.get('bezeichnung', 'Lagerartikel')
                einheit_str = mat_info.get('einheit', 'Stk.')
            pdf.cell(0, 5, clean_text(f"- {menge} {einheit_str} {bez}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 5, clean_text("Noch kein Material direkt zugeordnet."), new_x="LMARGIN", new_y="NEXT")
    
    if a.get('benoetigtes_material'):
        pdf.ln(2)
        pdf.multi_cell(0, 5, clean_text(f"Zusatznotizen Material: {a.get('benoetigtes_material')}"))

    pdf.ln(6)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, "Digitale Abnahme & Unterschriften:", new_x="LMARGIN", new_y="NEXT")
    
    draw_signature_on_pdf(pdf, a.get('kunde_unterschrift'), "Unterschrift Kunde / Auftraggeber:")
    draw_signature_on_pdf(pdf, a.get('mitarbeiter_unterschrift'), "Unterschrift Monteur / Einsatz-Team:")

    return pdf.output()

def hat_recht(modul_id, aktion="sehen"):
    user = st.session_state.get("user_data", {})
    if user.get("rolle") in ["Admin", "Inhaber", "Chef"]:
        return True
    rechte = user.get("rechte", [])
    return f"{modul_id}_{aktion}" in rechte

def render_auftraege_verwaltung(supabase):
    st.title("📋 4. Auftrags- & Einsatzmanagement")
    st.caption("Planen Sie Aufträge, weisen Sie Teams & Fahrzeuge zu und buchen Sie Material direkt aus dem Lager auf den Auftrag.")

    if not hat_recht("4", "sehen"):
        st.error("⛔ Sie haben keine Berechtigung, das Auftragsmodul aufzurufen.")
        return

    user_data = st.session_state.get("user_data", {})
    user_id = user_data.get("id")
    user_rolle = user_data.get("rolle", "")
    current_user_name = user_data.get("name") or user_data.get("benutzername") or "Mitarbeiter"
    
    is_admin = hat_recht("4", "erstellen") or hat_recht("4", "bearbeiten") or (user_rolle in ["Admin", "Büro", "Inhaber"])

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

    try:
        mat_res = supabase.table("lager_material").select("id, bezeichnung, artikelnummer, einheit, ist_bestand, lagerort").order("bezeichnung").execute()
        lager_material_liste = mat_res.data or []
    except Exception:
        lager_material_liste = []

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

    with tabs[0]:
        st.subheader("Auftragsliste, Lager-Zuordnung & Abnahmeprotokoll")

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
            st.info("Keine Aufträge vorhanden oder aktuell keine Freigabe für Ihr Konto.")
        else:
            darf_bearbeiten = True # Monteure dürfen am Auftrag arbeiten & Material buchen

            for a in sichtbare_auftraege:
                kunde = a.get("kunden") or {}
                gebaeude = a.get("gebaeude") or {}
                fahrzeug = a.get("fahrzeuge") or {}
                team = a.get("team", [])

                # Verknüpftes Material zu diesem Auftrag laden
                try:
                    am_res = supabase.table("auftrag_material").select("*, lager_material(bezeichnung, einheit, artikelnummer)").eq("auftrag_id", a["id"]).execute()
                    auftrag_materialien = am_res.data or []
                except Exception:
                    auftrag_materialien = []

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

                with st.expander(f"{status_icon} [{a.get('auftragsnummer')}] Status: {status} | Kunde: {k_name} | Team: {team_names}"):
                    a_datum_de = format_de_datum(a.get('termin_um'))
                    st.write(f"**Auftragsdatum:** {a_datum_de}")
                    st.write(f"**Objektadresse:** {g_adr}")
                    st.write(f"**Auszuführende Arbeiten:** {a.get('arbeiten')}")

                    # Aktuelle Material-Liste als Tabelle anzeigen
                    st.markdown("---")
                    st.write("📦 **Dem Auftrag zugeordnetes Material:**")
                    if auftrag_materialien:
                        mat_anzeige = []
                        for am in auftrag_materialien:
                            if am.get('ist_fremdmaterial'):
                                bez = f"{am.get('freitext_bezeichnung')} (Fremdteil)"
                                einh = "Stk."
                            else:
                                minfo = am.get('lager_material') or {}
                                bez = minfo.get('bezeichnung', 'Unbekannter Artikel')
                                einh = minfo.get('einheit', 'Stk.')
                            mat_anzeige.append({"Position / Artikel": bez, "Menge": f"{am.get('menge')} {einh}"})
                        st.dataframe(pd.DataFrame(mat_anzeige), use_container_width=True, hide_index=True)
                    else:
                        st.info("Noch kein Material für diesen Auftrag erfasst.")

                    st.markdown("---")
                    st.write("🛠️ **Material hinzufügen & Status bearbeiten**")

                    with st.form(f"auftrag_edit_{a['id']}"):
                        neuer_status = st.selectbox(
                            "Status ändern", 
                            ["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"], 
                            index=["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"].index(status) if status in ["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"] else 0
                        )

                        st.markdown("##### ➕ Material-Position hinzufügen")
                        ausgewaehlter_lager_artikel = st.selectbox(
                            "Artikel aus Lager wählen",
                            options=[None] + lager_material_liste,
                            format_func=lambda x: "--- Kein Lagerartikel wählen ---" if x is None else f"{x['bezeichnung']} (Bestand: {x['ist_bestand']} {x.get('einheit', 'Stk.')} | Ort: {x.get('lagerort', '-')})",
                            key=f"select_mat_{a['id']}"
                        )
                        menge_lager = st.number_input("Menge (Lagerartikel)", min_value=1, value=1, step=1, key=f"menge_lager_{a['id']}")

                        st.markdown("Oder **Fremd- / Ad-hoc-Material** (z.B. Ersatzteil vom Baumarkt):")
                        freitext_mat = st.text_input("Bezeichnung des Fremdteils", placeholder="z.B. Spezial-Relais Fabrikat X", key=f"free_mat_{a['id']}")
                        menge_fremd = st.number_input("Menge (Fremdteil)", min_value=1, value=1, step=1, key=f"menge_fremd_{a['id']}")

                        neues_team = []
                        neues_fahrzeug = a.get("fahrzeug_id")

                        if is_admin:
                            st.markdown("---")
                            st.write("👑 **Admin-Bereich: Team & Fahrzeug**")
                            aktuelle_team_ids = [m["id"] for m in team]
                            neues_team = st.multiselect(
                                "Team zuweisen",
                                options=[m["id"] for m in verfuegbare_mitarbeiter],
                                format_func=lambda x: next(f"{m['vorname']} {m['nachname']}" for m in verfuegbare_mitarbeiter if m["id"] == x),
                                default=[mid for mid in aktuelle_team_ids if mid in [m["id"] for m in verfuegbare_mitarbeiter]],
                                key=f"team_sel_{a['id']}"
                            )

                            fahrzeug_optionen = [None] + [f["id"] for f in fahrzeuge_liste]
                            neues_fahrzeug = st.selectbox(
                                "Fahrzeug",
                                options=fahrzeug_optionen,
                                format_func=lambda x: "--- Kein Fahrzeug ---" if x is None else next((f"{f.get('marke', 'Fahrzeug')} ({f.get('kennzeichen', '')})" for f in fahrzeuge_liste if f["id"] == x), ""),
                                index=fahrzeug_optionen.index(a.get("fahrzeug_id")) if a.get("fahrzeug_id") in fahrzeug_optionen else 0,
                                key=f"fzg_sel_{a['id']}"
                            )

                        b_save = st.form_submit_button("💾 Änderungen & Material buchen", type="primary", use_container_width=True)
                        if b_save:
                            try:
                                # 1. Status aktualisieren
                                update_payload = {"status": neuer_status}
                                if is_admin:
                                    update_payload["fahrzeug_id"] = neues_fahrzeug
                                supabase.table("auftraege").update(update_payload).eq("id", a["id"]).execute()

                                # 2. Lagerartikel hinzufügen & Bestand im Lager abziehen
                                if ausgewaehlter_lager_artikel:
                                    mat_id = ausgewaehlter_lager_artikel['id']
                                    alter_b = int(ausgewaehlter_lager_artikel.get('ist_bestand', 0))
                                    neuer_b = max(0, alter_b - menge_lager)

                                    # Lagerbestand updaten
                                    supabase.table("lager_material").update({"ist_bestand": neuer_b}).eq("id", mat_id).execute()
                                    
                                    # Bewegungs-Log schreiben
                                    supabase.table("lager_bewegungen").insert({
                                        "material_id": mat_id,
                                        "art": "Ausbuchung",
                                        "menge": menge_lager,
                                        "kommentar": f"Auftrag {a.get('auftragsnummer')} | Monteur: {current_user_name}"
                                    }).execute()

                                    # In auftrag_material eintragen
                                    supabase.table("auftrag_material").insert({
                                        "auftrag_id": a["id"],
                                        "material_id": mat_id,
                                        "menge": menge_lager,
                                        "ist_fremdmaterial": False
                                    }).execute()

                                # 3. Fremdmaterial eintragen (berührt das Lager nicht)
                                if freitext_mat.strip():
                                    supabase.table("auftrag_material").insert({
                                        "auftrag_id": a["id"],
                                        "menge": menge_fremd,
                                        "ist_fremdmaterial": True,
                                        "freitext_bezeichnung": freitext_mat.strip()
                                    }).execute()

                                if is_admin and neues_team:
                                    supabase.table("auftrag_mitarbeiter").delete().eq("auftrag_id", a["id"]).execute()
                                    team_inserts = [{"auftrag_id": a["id"], "mitarbeiter_id": m_id} for m_id in neues_team]
                                    supabase.table("auftrag_mitarbeiter").insert(team_inserts).execute()

                                st.toast("Erfolgreich gespeichert und Lagerbestand angepasst!", icon="🎯")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler beim Speichern: {e}")

                    # --- UNTERSCHRIFTEN & PDF ---
                    st.markdown("---")
                    st.write("✍️ **Digitale Unterschriften (Abnahmeprotokoll)**")
                    col_sig1, col_sig2 = st.columns(2)
                    
                    with col_sig1:
                        st.markdown("Unterschrift Kunde")
                        db_kunde_sig = a.get("kunde_unterschrift")
                        if db_kunde_sig and db_kunde_sig.startswith("data:image"):
                            st.success("✅ Unterschrieben!")
                            st.image(db_kunde_sig, width=250)
                            if st.button("🔄 Neu machen", key=f"reset_k_{a['id']}"):
                                supabase.table("auftraege").update({"kunde_unterschrift": None}).eq("id", a["id"]).execute()
                                st.rerun()
                        else:
                            canvas_kunde = st_canvas(fill_color="rgba(255,165,0,0.3)", stroke_width=2, stroke_color="#000", background_color="#FFF", height=100, width=300, drawing_mode="freedraw", return_image_data=True, key=f"can_k_{a['id']}")
                            if st.button("💾 Kunde speichern", key=f"save_k_{a['id']}"):
                                if canvas_kunde.json_data is not None and len(canvas_kunde.json_data.get("objects", [])) > 0:
                                    img = Image.fromarray(canvas_kunde.image_data.astype('uint8'), 'RGBA')
                                    rgb = Image.new("RGB", img.size, (255, 255, 255))
                                    rgb.paste(img, mask=img.split()[3])
                                    buf = BytesIO()
                                    rgb.save(buf, format="PNG")
                                    sig_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
                                    supabase.table("auftraege").update({"kunde_unterschrift": sig_b64}).eq("id", a["id"]).execute()
                                    st.rerun()

                    with col_sig2:
                        st.markdown("Unterschrift Monteur")
                        db_ma_sig = a.get("mitarbeiter_unterschrift")
                        if db_ma_sig and db_ma_sig.startswith("data:image"):
                            st.success("✅ Unterschrieben!")
                            st.image(db_ma_sig, width=250)
                            if st.button("🔄 Neu machen", key=f"reset_m_{a['id']}"):
                                supabase.table("auftraege").update({"mitarbeiter_unterschrift": None}).eq("id", a["id"]).execute()
                                st.rerun()
                        else:
                            canvas_ma = st_canvas(fill_color="rgba(255,165,0,0.3)", stroke_width=2, stroke_color="#000", background_color="#FFF", height=100, width=300, drawing_mode="freedraw", return_image_data=True, key=f"can_m_{a['id']}")
                            if st.button("💾 Monteur speichern", key=f"save_m_{a['id']}"):
                                if canvas_ma.json_data is not None and len(canvas_ma.json_data.get("objects", [])) > 0:
                                    img = Image.fromarray(canvas_ma.image_data.astype('uint8'), 'RGBA')
                                    rgb = Image.new("RGB", img.size, (255, 255, 255))
                                    rgb.paste(img, mask=img.split()[3])
                                    buf = BytesIO()
                                    rgb.save(buf, format="PNG")
                                    sig_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
                                    supabase.table("auftraege").update({"mitarbeiter_unterschrift": sig_b64}).eq("id", a["id"]).execute()
                                    st.rerun()

                    st.markdown("---")
                    pdf_bytes = generate_auftrag_pdf(a, kunde, gebaeude, fahrzeug, team, auftrag_materialien)
                    st.download_button(
                        label=f"📥 Abnahmeprotokoll-PDF mit Materialliste herunterladen ({a.get('auftragsnummer')})",
                        data=bytes(pdf_bytes),
                        file_name=f"Abnahmeprotokoll_{a.get('auftragsnummer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{a['id']}"
                    )

    if darf_erstellen and len(tabs) > 1:
        with tabs[1]:
            st.subheader("Neuen Auftrag erstellen")

            with st.form("neuer_auftrag_form"):
                col1, col2 = st.columns(2)
                with col1:
                    n_auftragsnummer = st.text_input("Auftragsnummer *", value=f"A-{datetime.now().strftime('%Y%m%d')}-01")
                    
                    kunden_optionen = [None] + [k["id"] for k in kunden_liste]
                    n_kunde = st.selectbox(
                        "Auftraggeber (Kunde)",
                        options=kunden_optionen,
                        format_func=lambda x: "--- Spontankunde (Freitext unten) ---" if x is None else next((f"{k['nachname']}, {k['vorname']} ({k.get('firma', 'Privat')})" for k in kunden_liste if k["id"] == x), "")
                    )
                    n_freitext_kunde = st.text_input("Oder Spontankunde / Name & Telefon", placeholder="z.B. Herr Müller, Tel: 0171-1234567")

                    gebaeude_optionen = [None] + [g["id"] for g in gebaeude_liste]
                    n_gebaeude = st.selectbox(
                        "Auftragsort (Gebäude)",
                        options=gebaeude_optionen,
                        format_func=lambda x: "--- Alternative Anschrift (Freitext unten) ---" if x is None else next((f"[{g.get('gebaeude_code', 'Code')}] {g['strasse']} {g['hausnummer']}, {g['ort']}" for g in gebaeude_liste if g["id"] == x), "")
                    )
                    n_freitext_ort = st.text_input("Oder alternativer Auftragsort", placeholder="z.B. Bahnhofstraße 10, Bochum")

                    n_mieter_we = st.text_input("Mieter / WE / Etage (optional)", placeholder="z.B. WE 4, 2. Obergeschoss")
                    n_status = st.selectbox("Initialer Status", ["In Planung", "Offener Auftrag", "In Bearbeitung", "Erledigt"], index=0)

                with col2:
                    if verfuegbare_mitarbeiter:
                        n_team = st.multiselect(
                            "Einsatz-Team *",
                            options=[m["id"] for m in verfuegbare_mitarbeiter],
                            format_func=lambda x: next(f"{m['vorname']} {m['nachname']}" for m in verfuegbare_mitarbeiter if m["id"] == x)
                        )
                    else:
                        n_team = []
                        st.warning("Keine verfügbaren Mitarbeiter gefunden.")

                    fahrzeug_optionen = [None] + [f["id"] for f in fahrzeuge_liste]
                    n_fahrzeug = st.selectbox(
                        "Fahrzeug zuweisen",
                        options=fahrzeug_optionen,
                        format_func=lambda x: "--- Kein Fahrzeug ---" if x is None else next((f"{f.get('marke', 'Fahrzeug')} ({f.get('kennzeichen', '')})" for f in fahrzeuge_liste if f["id"] == x), "")
                    )
                    
                    st.write("Termindaten")
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        n_datum = st.date_input("Auftragsdatum", value=datetime.today(), format="DD.MM.YYYY")
                    with col_d2:
                        n_uhr_von = st.time_input("Uhrzeit Von", value=datetime.strptime("08:00", "%H:%M").time())
                        n_uhr_bis = st.time_input("Uhrzeit Bis", value=datetime.strptime("16:00", "%H:%M").time())

                n_arbeiten = st.text_area("Auszuführende Arbeiten *", placeholder="z.B. Zählerschrank umbauen, Störung beseitigen...")
                n_material = st.text_area("Zusatznotizen zum Material (optional)", placeholder="z.B. Besonderheiten bei Bauteilen...")

                if st.form_submit_button("Auftrag anlegen & zuweisen", type="primary", use_container_width=True):
                    if not n_auftragsnummer or not n_arbeiten:
                        st.warning("Bitte Auftragsnummer und Arbeiten angeben.")
                    elif not n_team:
                        st.warning("Bitte wählen Sie mindestens einen Mitarbeiter aus.")
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
