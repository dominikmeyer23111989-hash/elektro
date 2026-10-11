import streamlit as st
from supabase import create_client, Client
from datetime import date, datetime
import pandas as pd
from fpdf import FPDF
from PIL import Image
from io import BytesIO

st.set_page_config(
    page_title="Elektro-Enterprise Portal", 
    page_icon="⚡", 
    layout="wide"
)

# -----------------------------------------------------------------------------
# Deutsches Datums- und Zeit-Format
# -----------------------------------------------------------------------------
def format_datum(val):
    if not val or val == "-" or str(val).strip() == "":
        return "-"
    if isinstance(val, (date, datetime)):
        return val.strftime("%d.%m.%Y")
    try:
        dt = datetime.strptime(str(val)[:10], "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return str(val)

def format_zeit(val):
    if not val or val == "-":
        return "-"
    if isinstance(val, datetime):
        return val.strftime("%H:%M Uhr")
    try:
        dt = datetime.strptime(str(val), "%H:%M:%S")
        return dt.strftime("%H:%M Uhr")
    except Exception:
        return str(val)

# -----------------------------------------------------------------------------
# Bildkomprimierung (Pillow)
# -----------------------------------------------------------------------------
def compress_image(uploaded_file, max_width=1200, quality=75):
    if uploaded_file.type == "application/pdf":
        return uploaded_file.getvalue(), "application/pdf", uploaded_file.name

    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        
        base_name = uploaded_file.name.rsplit(".", 1)[0]
        new_filename = f"{base_name}_compressed.jpg"
        return output.getvalue(), "image/jpeg", new_filename
    except Exception:
        return uploaded_file.getvalue(), uploaded_file.type, uploaded_file.name

# -----------------------------------------------------------------------------
# 1. Supabase Initialisierung
# -----------------------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
    if "supabase" in st.secrets:
        url = st.secrets["supabase"]["SUPABASE_URL"]
        key = st.secrets["supabase"]["SUPABASE_KEY"]
    else:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = get_supabase()
except Exception as e:
    st.error(f"Fehler bei der Verbindung zu Supabase: {e}")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_data" not in st.session_state:
    st.session_state["user_data"] = None

# -----------------------------------------------------------------------------
# 2. PDF-Generator
# -----------------------------------------------------------------------------
class PersonalaktePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(
            0, 10, 
            'ELEKTRO-ENTERPRISE - DIGITALE PERSONALAKTE', 
            border=False, new_x="LMARGIN", new_y="NEXT", align='C'
        )
        self.set_font('Helvetica', 'I', 10)
        self.cell(
            0, 5, 
            'Vertrauliches Personaldokument (DSGVO-geschützt)', 
            border=False, new_x="LMARGIN", new_y="NEXT", align='C'
        )
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', align='C')

def generate_mitarbeiter_pdf(mitarbeiter_data, qualifikationen):
    pdf = PersonalaktePDF()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)
    
    pdf.set_font('Helvetica', 'B', 14)
    v_name = mitarbeiter_data.get('vorname', '')
    n_name = mitarbeiter_data.get('nachname', '')
    pdf.cell(0, 8, f"{v_name} {n_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 11)
    
    rolle_txt = "-"
    if mitarbeiter_data.get('rollen'):
        rolle_txt = str(mitarbeiter_data.get('rollen', {}).get('bezeichnung', '-'))

    fields = [
        ("Mitarbeiternummer:", str(mitarbeiter_data.get('mitarbeiternummer', '-'))),
        ("Rolle im Betrieb:", rolle_txt),
        ("Geburtsdatum:", format_datum(mitarbeiter_data.get('geburtsdatum'))),
        ("Tätig seit:", format_datum(mitarbeiter_data.get('taetig_seit'))),
        ("E-Mail:", str(mitarbeiter_data.get('email', '-'))),
        ("Telefon:", str(mitarbeiter_data.get('telefon', '-'))),
        ("Adresse:", str(mitarbeiter_data.get('adresse', '-'))),
        ("Status:", "Aktiv" if mitarbeiter_data.get('ist_aktiv') else "Inaktiv")
    ]
    
    pdf.ln(3)
    for label, val in fields:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(55, 6, label)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")
        
    pdf.ln(8)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, "Qualifikationen, Ausbildungen & Scheine", new_x="LMARGIN", new_y="NEXT")
    
    if qualifikationen:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(40, 6, "Kategorie", border=1)
        pdf.cell(60, 6, "Bezeichnung / Titel", border=1)
        pdf.cell(30, 6, "Erhalten am", border=1)
        pdf.cell(30, 6, "Gültig bis", border=1, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font('Helvetica', '', 9)
        for q in qualifikationen:
            pdf.cell(40, 6, str(q.get('kategorie', '')), border=1)
            pdf.cell(60, 6, str(q.get('titel', '')), border=1)
            pdf.cell(30, 6, format_datum(q.get('datum_erhalten')), border=1)
            pdf.cell(30, 6, format_datum(q.get('gueltig_bis')), border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 6, "Keine Qualifikationen / Scheine hinterlegt.", new_x="LMARGIN", new_y="NEXT")
        
    return pdf.output()

# -----------------------------------------------------------------------------
# 3. Modul 1: Mitarbeiterverwaltung
# -----------------------------------------------------------------------------
ALL_MODULES = {
    "1": "1. Mitarbeiterverwaltung",
    "2": "2. Lagerverwaltung",
    "3": "3. Zeiterfassung",
    "4": "4. Aufträge",
    "5": "5. Kunden",
    "6": "6. Fahrzeuge",
    "7": "7. Gebäude",
    "8": "8. Dokumente",
    "9": "9. Finanzen / Monitor"
}

def render_mitarbeiter_verwaltung():
    st.title("👨‍💼 1. Mitarbeiterverwaltung")
    
    tab_uebersicht, tab_neu, tab_rollen, tab_qualifikationen = st.tabs([
        "📋 Mitarbeiterübersicht", 
        "➕ Neuer Mitarbeiter", 
        "🔑 Rollen & Rechte", 
        "📜 Qualifikationen & Scheine"
    ])
    
    # --- TAB 1: Übersicht & PDF-Export ---
    with tab_uebersicht:
        st.subheader("Personalstamm")
        try:
            res = supabase.table("mitarbeiter").select("*, rollen(*)").execute()
            mitarbeiter_liste = res.data or []
            
            if mitarbeiter_liste:
                display_df = pd.DataFrame([{
                    "Nr": m.get("mitarbeiternummer"),
                    "Name": f"{m.get('vorname')} {m.get('nachname')}",
                    "Rolle": m.get("rollen", {}).get("bezeichnung", "-") if m.get("rollen") else "-",
                    "Tätig seit": format_datum(m.get("taetig_seit")),
                    "Geburtsdatum": format_datum(m.get("geburtsdatum")),
                    "Telefon": m.get("telefon", "-"),
                    "Status": "🟢 Aktiv" if m.get("ist_aktiv") else "🔴 Inaktiv"
                } for m in mitarbeiter_liste])
                
                st.dataframe(display_df, use_container_width=True)
                
                st.markdown("---")
                st.subheader("📄 Personalakte als PDF exportieren")
                
                selected_ma_id = st.selectbox(
                    "Mitarbeiter auswählen", 
                    options=[m["id"] for m in mitarbeiter_liste],
                    format_func=lambda x: next(
                        f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" 
                        for m in mitarbeiter_liste if m["id"] == x
                    )
                )
                
                selected_ma = next(m for m in mitarbeiter_liste if m["id"] == selected_ma_id)
                q_res = supabase.table("qualifikationen").select("*").eq("mitarbeiter_id", selected_ma_id).execute()
                qualis = q_res.data or []
                
                pdf_bytes = generate_mitarbeiter_pdf(selected_ma, qualis)
                
                st.download_button(
                    label=f"📥 Personalakte von {selected_ma['vorname']} {selected_ma['nachname']} herunterladen (PDF)",
                    data=bytes(pdf_bytes),
                    file_name=f"Personalakte_{selected_ma['mitarbeiternummer']}_{selected_ma['nachname']}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            else:
                st.info("Noch keine Mitarbeiter erfasst.")
        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")

    # --- TAB 2: Neuer Mitarbeiter ---
    with tab_neu:
        st.subheader("Neuen Mitarbeiter im System anlegen")
        try:
            rollen_res = supabase.table("rollen").select("*").execute()
            rollen_dict = {r["bezeichnung"]: r["id"] for r in rollen_res.data} if rollen_res.data else {}
        except Exception:
            rollen_dict = {}

        with st.form("neuer_mitarbeiter_form"):
            col1, col2 = st.columns(2)
            with col1:
                mitarbeiternr = st.text_input("Mitarbeiternummer *", placeholder="z. B. 1005")
                vorname = st.text_input("Vorname *")
                nachname = st.text_input("Nachname *")
                geburtsdatum = st.date_input("Geburtsdatum", value=date(1990, 1, 1), format="DD.MM.YYYY")
                taetig_seit = st.date_input("Im Unternehmen tätig seit", value=date.today(), format="DD.MM.YYYY")
            with col2:
                rolle_bezeichnung = st.selectbox("Rolle / Funktion *", list(rollen_dict.keys()) if rollen_dict else ["Admin"])
                passwort = st.text_input("Erst-Passwort / PIN *", type="password")
                notfall_pin = st.text_input("4-stellige Notfall-PIN (für Self-Service Reset)", type="password", max_chars=4, placeholder="z. B. 4321")
                email = st.text_input("E-Mail-Adresse (optional)")
                telefon = st.text_input("Telefonnummer (optional)")
                adresse = st.text_area("Anschrift (optional)")
                
            submitted = st.form_submit_button("Mitarbeiter anlegen", type="primary", use_container_width=True)
            if submitted:
                if not mitarbeiternr or not vorname or not nachname or not passwort:
                    st.warning("Bitte füllen Sie alle Pflichtfelder (*) aus.")
                else:
                    try:
                        rec_code = f"REC-{mitarbeiternr}-88"
                        data = {
                            "mitarbeiternummer": mitarbeiternr,
                            "vorname": vorname,
                            "nachname": nachname,
                            "geburtsdatum": str(geburtsdatum),
                            "taetig_seit": str(taetig_seit),
                            "rolle_id": rollen_dict.get(rolle_bezeichnung),
                            "pin_hash": passwort,
                            "notfall_pin": notfall_pin,
                            "recovery_code": rec_code,
                            "email": email,
                            "telefon": telefon,
                            "adresse": adresse,
                            "ist_aktiv": True
                        }
                        supabase.table("mitarbeiter").insert(data).execute()
                        st.success(f"Mitarbeiter {vorname} {nachname} erfolgreich angelegt!")
                        st.info(f"💡 Generierter Recovery-Code für Notfälle: `{rec_code}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Anlegen: {e}")

    # --- TAB 3: Rollen & Rechte ---
    with tab_rollen:
        st.subheader("Rollen- & Rechteverwaltung")
        try:
            rollen_data = supabase.table("rollen").select("*").execute().data or []
        except Exception:
            rollen_data = []

        if rollen_data:
            selected_rolle = st.selectbox("Rolle wählen", options=[r["bezeichnung"] for r in rollen_data])
            current_role_obj = next((r for r in rollen_data if r["bezeichnung"] == selected_rolle), None)
            
            if current_role_obj:
                current_allowed = current_role_obj.get("erlaubte_menues", [])
                new_allowed = []
                col_a, col_b = st.columns(2)
                for idx, (mod_key, mod_title) in enumerate(ALL_MODULES.items()):
                    target_col = col_a if idx < 5 else col_b
                    if target_col.checkbox(mod_title, value=(mod_key in current_allowed), key=f"perm_{selected_rolle}_{mod_key}"):
                        new_allowed.append(mod_key)
                        
                if st.button("💾 Rechte für diese Rolle speichern", type="primary"):
                    try:
                        supabase.table("rollen").update({"erlaubte_menues": new_allowed}).eq("id", current_role_obj["id"]).execute()
                        st.success(f"Rechte für '{selected_rolle}' aktualisiert!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern: {e}")

    # --- TAB 4: Qualifikationen & Scheine mit Komprimierung ---
    with tab_qualifikationen:
        st.subheader("Qualifikationen, Fortbildungen & Scheine")
        try:
            ma_list = supabase.table("mitarbeiter").select("id, vorname, nachname, mitarbeiternummer").execute().data or []
        except Exception:
            ma_list = []

        if ma_list:
            sel_ma_id = st.selectbox(
                "Mitarbeiter wählen", 
                options=[m["id"] for m in ma_list],
                format_func=lambda x: next(
                    f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" 
                    for m in ma_list if m["id"] == x
                )
            )
            with st.form("qualifikation_form"):
                kategorie = st.selectbox("Kategorie", ["Ausbildung", "Weiterbildung", "Zertifikat / Schein", "Sonstiges"])
                titel = st.text_input("Bezeichnung / Titel *", placeholder="z. B. Ersthelfer, DGUV V3 Prüfschein")
                col_d1, col_d2 = st.columns(2)
                datum_erhalten = col_d1.date_input("Erhalten am", value=date.today(), format="DD.MM.YYYY")
                gueltig_bis = col_d2.date_input("Gültig bis (optional)", value=None, format="DD.MM.YYYY")
                beschreibung = st.text_area("Freitext / Anmerkung")
                uploaded_file = st.file_uploader("Upload Nachweis-Foto oder PDF", type=["png", "jpg", "jpeg", "pdf"])
                
                if st.form_submit_button("Qualifikation speichern", type="primary"):
                    if not titel:
                        st.warning("Bitte Titel angeben.")
                    else:
                        file_url = None
                        if uploaded_file is not None:
                            try:
                                file_bytes, content_type, file_name = compress_image(uploaded_file)
                                file_path = f"{sel_ma_id}/{file_name}"
                                
                                supabase.storage.from_("mitarbeiter-dokumente").upload(
                                    file_path, 
                                    file_bytes, 
                                    {"content-type": content_type, "upsert": "true"}
                                )
                                file_url = supabase.storage.from_("mitarbeiter-dokumente").get_public_url(file_path)
                            except Exception as e_up:
                                st.warning(f"Upload-Hinweis: {e_up}")

                        q_data = {
                            "mitarbeiter_id": sel_ma_id,
                            "kategorie": kategorie,
                            "titel": titel,
                            "datum_erhalten": str(datum_erhalten) if datum_erhalten else None,
                            "gueltig_bis": str(gueltig_bis) if gueltig_bis else None,
                            "beschreibung": beschreibung,
                            "dokument_url": file_url
                        }
                        supabase.table("qualifikationen").insert(q_data).execute()
                        st.success("Qualifikation eingetragen!")
                        st.rerun()

            st.markdown("---")
            st.markdown("#### 📜 Hinterlegte Qualifikationen")
            try:
                existing_q = supabase.table("qualifikationen").select("*").eq("mitarbeiter_id", sel_ma_id).execute().data or []
            except Exception:
                existing_q = []

            if existing_q:
                for q in existing_q:
                    with st.expander(f"{q['kategorie']}: {q['titel']} (Erhalten am: {format_datum(q.get('datum_erhalten'))})"):
                        st.write(f"**Gültig bis:** {format_datum(q.get('gueltig_bis'))}")
                        st.write(f"**Beschreibung:** {q.get('beschreibung', '-')}")
                        if q.get("dokument_url"):
                            st.markdown(f"[📄 Nachweis-Dokument / Foto öffnen]({q['dokument_url']})")
            else:
                st.info("Für diesen Mitarbeiter wurden noch keine Qualifikationen erfasst.")

# -----------------------------------------------------------------------------
# 4. Login-System mit Self-Service Wiederherstellung
# -----------------------------------------------------------------------------
def render_login():
    st.title("⚡ Elektro-Enterprise System")
    st.caption("Willkommen! Bitte melden Sie sich an.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_reset = st.tabs(["🔑 Login", "🆘 Passwort vergessen"])

        # --- TAB 1: Login ---
        with tab_login:
            with st.form("login_form"):
                identifier = st.text_input("Mitarbeiternummer oder Vorname.Nachname", placeholder="z. B. 1000")
                password = st.text_input("Passwort / PIN", type="password")
                
                submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)

                if submitted:
                    if not identifier or not password:
                        st.warning("Bitte füllen Sie alle Felder aus.")
                    else:
                        try:
                            res = supabase.table("mitarbeiter").select("*, rollen(*)").eq("ist_aktiv", True).eq("mitarbeiternummer", identifier).execute()
                            
                            if not res.data and "." in identifier:
                                parts = identifier.split(".", 1)
                                res = supabase.table("mitarbeiter").select("*, rollen(*)").eq("ist_aktiv", True).ilike("vorname", parts[0]).ilike("nachname", parts[1]).execute()

                            if not res.data:
                                st.error("Mitarbeiter nicht gefunden oder Konto inaktiv.")
                                return
                            
                            user_rec = res.data[0]
                            if str(user_rec.get("pin_hash")) == str(password):
                                rolle_info = user_rec.get("rollen") or {}
                                f_rolle = rolle_info.get("bezeichnung", "Admin")
                                f_ebene = rolle_info.get("ebene", "buero")
                                f_rechte = rolle_info.get("erlaubte_menues") or ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

                                st.session_state["authenticated"] = True
                                st.session_state["user_data"] = {
                                    "id": user_rec["id"],
                                    "mitarbeiternummer": user_rec.get("mitarbeiternummer", "-"),
                                    "name": f"{user_rec.get('vorname', '')} {user_rec.get('nachname', '')}".strip(),
                                    "rolle": f_rolle,
                                    "ebene": f_ebene,
                                    "rechte": f_rechte
                                }
                                st.success("Erfolgreich angemeldet!")
                                st.rerun()
                            else:
                                st.error("Ungültiges Passwort.")
                        except Exception as e:
                            st.error(f"Login-Fehler: {e}")

        # --- TAB 2: Autonomes Passwort-Zurücksetzen ---
        with tab_reset:
            st.markdown("##### Self-Service Wiederherstellung")
            st.caption("Setzen Sie Ihr Passwort direkt über Ihre Notfall-PIN oder Ihren Recovery-Code zurück.")

            with st.form("reset_form"):
                reset_ma_nr = st.text_input("Mitarbeiternummer *", placeholder="z. B. 1000")
                method = st.radio("Verifizierungsmethode", ["Notfall-PIN & Geburtsdatum", "Master-Recovery-Code"])
                
                if method == "Notfall-PIN & Geburtsdatum":
                    geburtsdatum = st.date_input("Geburtsdatum zur Verifizierung", value=date(1990, 1, 1), format="DD.MM.YYYY")
                    notfall_pin = st.text_input("Ihre 4-stellige Notfall-PIN", type="password")
                    secret_check = str(notfall_pin)
                else:
                    recovery_code = st.text_input("Master-Recovery-Code", placeholder="z. B. REC-1000-88")
                    secret_check = str(recovery_code)

                st.markdown("---")
                new_pw = st.text_input("Neues Passwort vergeben *", type="password")
                new_pw_confirm = st.text_input("Neues Passwort wiederholen *", type="password")

                btn_reset = st.form_submit_button("Passwort jetzt zurücksetzen", type="primary", use_container_width=True)

                if btn_reset:
                    if not reset_ma_nr or not new_pw or not secret_check:
                        st.warning("Bitte füllen Sie alle erforderlichen Felder aus.")
                    elif new_pw != new_pw_confirm:
                        st.error("Die eingegebenen Passwörter stimmen nicht überein.")
                    elif len(new_pw) < 4:
                        st.error("Das neue Passwort muss mindestens 4 Zeichen lang sein.")
                    else:
                        try:
                            res = supabase.table("mitarbeiter").select("*").eq("mitarbeiternummer", reset_ma_nr).eq("ist_aktiv", True).execute()
                            if not res.data:
                                st.error("Mitarbeiternummer ungültig.")
                                return
                            
                            ma_rec = res.data[0]
                            verified = False

                            if method == "Notfall-PIN & Geburtsdatum":
                                ma_geb = str(ma_rec.get("geburtsdatum", ""))
                                ma_pin = str(ma_rec.get("notfall_pin", ""))
                                if ma_geb == str(geburtsdatum) and ma_pin == notfall_pin and notfall_pin != "":
                                    verified = True
                            else:
                                ma_code = str(ma_rec.get("recovery_code", ""))
                                if ma_code == recovery_code and recovery_code != "":
                                    verified = True

                            if verified:
                                supabase.table("mitarbeiter").update({"pin_hash": new_pw}).eq("id", ma_rec["id"]).execute()
                                st.success("Ihr Passwort wurde erfolgreich geändert! Sie können sich jetzt anmelden.")
                            else:
                                st.error("Verifizierung fehlgeschlagen: Sicherheitsdaten falsch.")

                        except Exception as e:
                            st.error(f"Fehler beim Zurücksetzen: {e}")

# -----------------------------------------------------------------------------
# 5. Hauptanwendung
# -----------------------------------------------------------------------------
def render_app():
    user = st.session_state.get("user_data")
    if not user:
        st.session_state["authenticated"] = False
        st.rerun()
        return
    
    st.sidebar.title("⚡ Elektro-Portal")
    st.sidebar.write(f"Angemeldet: **{user.get('name', 'Unbekannt')}**")
    st.sidebar.caption(f"Nr: {user.get('mitarbeiternummer', '-')} | Rolle: {user.get('rolle', '-')}")
    
    if st.sidebar.button("🚪 Abmelden", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user_data"] = None
        st.rerun()

    st.sidebar.markdown("---")

    menu_structure = {
        "1": {"title": "👨‍💼 1. Mitarbeiterverwaltung", "sub": ["Verwaltung"]},
        "2": {"title": "📦 2. Lagerverwaltung", "sub": ["Materialbestand"]},
        "3": {"title": "⏱️ 3. Zeiterfassung", "sub": ["Stundenzettel"]},
        "4": {"title": "📋 4. Aufträge", "sub": ["Auftragsübersicht"]},
        "5": {"title": "👥 5. Kunden", "sub": ["Kundenstamm"]},
        "6": {"title": "🚛 6. Fahrzeuge", "sub": ["Fuhrparkliste"]},
        "7": {"title": "🏢 7. Gebäude", "sub": ["Anlagenregister"]},
        "8": {"title": "📁 8. Dokumente", "sub": ["Schaltpläne"]},
        "9": {"title": "💶 9. Finanzen / Monitor", "sub": ["Rechnungen"]}
    }

    allowed_menu_keys = user.get("rechte", [])
    available_menus = {k: v for k, v in menu_structure.items() if k in allowed_menu_keys}

    if not available_menus:
        st.warning("Keine zugewiesenen Menürechte gefunden.")
        return

    selected_main = st.sidebar.selectbox(
        "Hauptmenü",
        options=list(available_menus.keys()),
        format_func=lambda x: available_menus[x]["title"]
    )

    if selected_main:
        if selected_main == "1":
            render_mitarbeiter_verwaltung()
        else:
            st.title(available_menus[selected_main]["title"])
            st.info("Dieses Modul wird als Nächstes ausgebaut.")

# Control Flow
if not st.session_state.get("authenticated", False):
    render_login()
else:
    render_app()
