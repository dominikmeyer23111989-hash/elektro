import streamlit as st
from supabase import create_client, Client
from datetime import date, datetime
import pandas as pd
from fpdf import FPDF
from PIL import Image
from io import BytesIO

st.set_page_config(page_title="Elektro-Enterprise Portal", page_icon="⚡", layout="wide")

# -----------------------------------------------------------------------------
# Deutsches Datums- und Zeit-Format Hilfsfunktionen
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
# Bildkomprimierung (Pillow) für Supabase Storage
# -----------------------------------------------------------------------------
def compress_image(uploaded_file, max_width=1200, quality=75):
    """
    Komprimiert hochgeladene Bilder (JPEG/PNG) auf max. max_width Pixel Breite 
    und reduziert die Dateigröße um ca. 80-90%. PDFs werden unverändert zurückgegeben.
    """
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
    st.session_state.authenticated = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None

# -----------------------------------------------------------------------------
# 2. PDF-Generator für die Personalakte
# -----------------------------------------------------------------------------
class PersonalaktePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'ELEKTRO-ENTERPRISE - DIGITALE PERSONALAKTE', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 5, 'Vertrauliches Personaldokument (DSGVO-geschützt)', border=False, new_x="LMARGIN", new_y="NEXT", align='C')
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
    pdf.cell(0, 8, f"{mitarbeiter_data.get('vorname', '')} {mitarbeiter_data.get('nachname', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 11)
    
    fields = [
        ("Mitarbeiternummer:", str(mitarbeiter_data.get('mitarbeiternummer', '-'))),
        ("Rolle im Betrieb:", str(mitarbeiter_data.get('rollen', {}).get('bezeichnung', '-') if mitarbeiter_data.get('rollen') else '-')),
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
                    format_func=lambda x: next(f"{m['mitarbeiternummer']} - {m['vorname']} {m['nachname']}" for m in mitarbeiter_liste if m["id"] == x)
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
        except Exception as e
