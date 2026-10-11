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
            pdf.
