"""Downloadable calculation records, with no installation schedule on failed cases."""
import json
import math
import unicodedata
from datetime import datetime, timezone
from fpdf import FPDF
from . import __version__
from .schema import FIELD_DEFINITIONS

RESULT_LABELS = {
    'installed_plies':'Installed plies', 'installed_thickness_mm':'Installed thickness [mm]',
    'required_thickness_mm':'Required thickness before rounding [mm]',
    'total_repair_length_mm':'Total repair length [mm]', 'overlap_mm':'Required overlap [mm]',
    'count_500':'500 mm fabric bands total', 'count_300':'300 mm fabric bands total',
    'fabric_area_m2':'Fabric area total [m2]', 'laminate_epoxy_kg':'Laminate epoxy total [kg]',
    'putty_kg':'Putty total [kg]', 'total_epoxy_kg':'Total epoxy [kg]',
    'quantity':'Number of repairs', 'repair_type':'Defect design type',
    'putty_per_repair_kg':'Putty per defect [kg]',
}

def _clean(value):
    if isinstance(value, dict): return {str(k):_clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [_clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    if value is None or isinstance(value,(str,int,float,bool)): return value
    if hasattr(value,'item'): return _clean(value.item())
    return str(value)

def report_json(result):
    return json.dumps(_clean(result),ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')

def _text(value):
    s=str(value)
    replacements={'ı':'i','İ':'I','ş':'s','Ş':'S','ğ':'g','Ğ':'G','≤':'<=','≥':'>=','−':'-','–':'-','—':'-','γ':'gamma','ε':'epsilon','ν':'nu','×':'x','′':"'",'³':'3','²':'2','→':'->','•':'-'}
    for a,b in replacements.items(): s=s.replace(a,b)
    s=s.encode('latin-1','replace').decode('latin-1')
    return ''.join(c for c in s if c in '\n\t' or ord(c)>=32)

def _value(value):
    if isinstance(value,float): return f'{value:.7g}' if math.isfinite(value) else 'Not finite'
    if isinstance(value,(list,dict)): return json.dumps(_clean(value),ensure_ascii=False)
    return str(value)

class _Report(FPDF):
    def header(self):
        self.set_font('Arial','B',11); self.set_text_color(25,53,78)
        self.cell(0,7,'PROWRAP  |  ISO 24817:2026',0,1)
        self.set_text_color(0,0,0); self.ln(2)
    def footer(self):
        self.set_y(-13); self.set_font('Arial','',8)
        self.cell(0,5,f'Calculation record  |  v{__version__}  |  Page {self.page_no()}',0,0,'R')

def report_pdf(result):
    pdf=_Report(); pdf.set_margins(17,16,17); pdf.set_auto_page_break(True,18); pdf.add_page()
    def para(text,bold=False,size=10):
        pdf.set_font('Arial','B' if bold else '',size)
        pdf.multi_cell(0,5,_text(text)); pdf.ln(1)
    def section(title):
        pdf.ln(3); para(title,True,12)
    para('Repair calculation report',True,17)
    para(f"Repair ID: {result.get('repair_id','')}  |  Status: {result.get('status','')}",True)
    para('Generated: '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),size=8)
    para('Calculated checks and dimensions for engineering review. The project work pack supplies the approved application and inspection procedures.',size=9)
    if result.get('details',{}).get('pressure_basis'):
        pressure=result['details']['pressure_basis']
        para(f"Calculation pressure [bar]: {_value(pressure['calculation_pressure_bar'])} | Basis: {pressure['basis']}",True)
    if result.get('issues'):
        section('Calculation messages')
        for item in result['issues']: para('- '+str(item))
    success=result.get('status') in ('CALCULATED','ESTIMATE')
    if success:
        section('Calculated repair and quantities')
        if result.get('status')=='ESTIMATE': para('ESTIMATE - quantities use the stated estimating geometry.',True)
        for key,value in result.get('results',{}).items():
            if value is not None: para(f'{RESULT_LABELS.get(key,key.replace("_"," ").capitalize())}: {_value(value)}')
    section('Design input record')
    for key,value in result.get('inputs',{}).items():
        if value is None or value=='': continue
        label=FIELD_DEFINITIONS.get(key,{}).get('label',key.replace('_',' '))
        para(f'{label}: {_value(value)}',size=9)
    if result.get('checks'):
        section('Calculated checks')
        for check in result['checks']:
            state='PASS' if check.get('passed') else 'FAIL'
            para(f"{state} - {check.get('name','Check')} | value: {_value(check.get('value',''))} | limit: {_value(check.get('limit',''))} | ISO {check.get('clause','')}",size=9)
    if result.get('details'):
        section('Calculation trace')
        # Keep diagnostic information on failures, while excluding any accidental installable fields.
        for key,value in result['details'].items():
            if not success and key in RESULT_LABELS: continue
            text=f'{key.replace("_"," ")}: {_value(value)}'
            # Narrow long unbroken tokens to avoid core-font overflow.
            words=[]
            for word in text.split(' '):
                words.extend(word[n:n+85] for n in range(0,len(word),85))
            para(' '.join(words),size=8)
    value=pdf.output(dest='S')
    return value.encode('latin-1') if isinstance(value,str) else bytes(value)
