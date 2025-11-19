import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import locale
import io
import streamlit as st
from fpdf import FPDF
import gspread
from gspread.exceptions import SpreadsheetNotFound

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '')

def format_currency(value):
    if value is None: return "N/A"
    try:
        return locale.currency(float(value), grouping=True, symbol='R$')
    except:
        return f"R$ {value}"

def _ensure_date(val):
    """Converte qualquer coisa (String, Timestamp, Datetime) para datetime.date (Python Puro)."""
    if val is None or pd.isna(val) or str(val).strip() == '':
        return date.today()
    
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    
    try:
        dt = pd.to_datetime(val)
        if pd.isna(dt): return date.today()
        return dt.date() 
    except:
        return date.today()

@st.cache_resource
def init_gsheet_connection():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict)
        if "spreadsheet_key" not in st.secrets: return None
        sh = gc.open_by_key(st.secrets["spreadsheet_key"])
        return {"simulations": sh.worksheet("simulations"), "aportes": sh.worksheet("aportes")}
    except Exception as e:
        st.error(f"Erro GSheets: {e}")
        return None

@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet, tab_name="default"):
    try:
        if _worksheet is None: return pd.DataFrame()
        vals = _worksheet.get_all_values()
        if not vals: return pd.DataFrame()
        
        df = pd.DataFrame(vals[1:], columns=vals[0])
        
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, [c for c in df.columns if c != '']]
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        rename_map = {'date': 'data_aporte', 'value': 'valor_aporte', 'data': 'data_aporte', 'valor': 'valor_aporte'}
        df.rename(columns=rename_map, inplace=True)
        
        if 'row_index' not in df.columns:
            df['row_index'] = [i + 2 for i in range(len(df))]

        cols_num = ['total_contribution', 'num_months', 'annual_interest_rate', 'spe_percentage',
                    'land_size', 'construction_cost_m2', 'value_m2', 'area_exchange_percentage',
                    'vgv', 'total_construction_cost', 'final_operational_result', 'valor_participacao',
                    'resultado_final_investidor', 'roi', 'roi_anualizado', 'valor_corrigido',
                    'valor_aporte', 'cost_obra_fisica', 'juros_investidor']
        
        for c in cols_num:
            if c in df.columns:
                s = df[c].astype(str).str.replace('R$', '', regex=False).str.strip()
                is_br = s.str.contains(',', na=False)
                s.loc[is_br] = s.loc[is_br].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[c] = pd.to_numeric(s, errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Erro load ({tab_name}): {e}")
        return pd.DataFrame()

def calculate_financials(params):
    results = {}
    results.update(params)
    
    dt_start = _ensure_date(params.get('start_date'))
    dt_end = _ensure_date(params.get('project_end_date'))
    
    aportes = params.get('aportes', [])
    total_contribution = 0
    total_montante = 0
    
    annual_rate = params.get('annual_interest_rate', 0) / 100
    daily_rate = (1 + annual_rate) ** (1/365) - 1
    
    if not aportes:
        days_roi = 1
        months_roi = 1
    else:
        sorted_aps = sorted(aportes, key=lambda x: _ensure_date(x.get('date', x.get('data'))))
        dt_first_ap = _ensure_date(sorted_aps[0].get('date', sorted_aps[0].get('data')))
        
        days_roi = max(1, (dt_end - dt_first_ap).days)
        
        rd = relativedelta(dt_end, dt_first_ap)
        months_roi = max(1, rd.years * 12 + rd.months)
        
        for ap in sorted_aps:
            dt_ap = _ensure_date(ap.get('date', ap.get('data')))
            val = float(ap.get('value', ap.get('valor', 0)))
            total_contribution += val
            
            days_active = (dt_end - dt_ap).days
            if days_active > 0:
                total_montante += val * ((1 + daily_rate) ** days_active)
            else:
                total_montante += val

    juros = max(0, total_montante - total_contribution)
    
    results['valor_corrigido'] = total_montante
    results['total_contribution'] = total_contribution
    results['num_months'] = months_roi
    results['total_days_for_roi'] = days_roi
    results['start_date'] = dt_start
    results['project_end_date'] = dt_end
    results['juros_investidor'] = juros
    
    vgv = params.get('land_size', 0) * params.get('value_m2', 0)
    custo_obra = params.get('land_size', 0) * params.get('construction_cost_m2', 0)
    permuta = vgv * (params.get('area_exchange_percentage', 0) / 100)
    custo_total = custo_obra + juros + permuta
    res_operacional = vgv - custo_total
    
    part_spe = res_operacional * (params.get('spe_percentage', 0) / 100)
    lucro_investidor = (total_montante + part_spe) - total_contribution
    
    if total_contribution > 0:
        roi_abs = lucro_investidor / total_contribution
        if (1 + roi_abs) > 0:
            roi_aa = ((1 + roi_abs) ** (365 / days_roi)) - 1
        else:
            roi_aa = -1
    else:
        roi_abs, roi_aa = 0, 0

    results.update({
        'vgv': vgv, 'cost_obra_fisica': custo_obra, 'area_exchange_value': permuta,
        'total_construction_cost': custo_total, 'final_operational_result': res_operacional,
        'valor_participacao': part_spe, 'resultado_final_investidor': lucro_investidor,
        'roi': round(roi_abs * 100, 2), 'roi_anualizado': round(roi_aa * 100, 2)
    })
    
    return results

def generate_pdf(data):
    try:
        def clean_txt(t): return str(t).encode('latin-1', 'replace').decode('latin-1') if t else ''
        
        pdf = FPDF()
        pdf.add_page()
        
        try: pdf.image("Lavie.png", x=10, y=8, w=40)
        except: pass
        
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 20, clean_txt("Relatório de Simulação"), 0, 1, "C")
        pdf.ln(10)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, clean_txt("Resumo do Cliente"), 0, 1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, clean_txt(f"Cliente: {data.get('client_name','')}"), 0, 1)
        pdf.cell(0, 6, clean_txt(f"Aporte Total: {format_currency(data.get('total_contribution'))}"), 0, 1)
        
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, clean_txt("Resultados"), 0, 1)
        pdf.set_font("Arial", "", 10)
        items = [
            f"VGV: {format_currency(data.get('vgv'))}",
            f"Lucro Líquido: {format_currency(data.get('resultado_final_investidor'))}",
            f"ROI Anualizado: {data.get('roi_anualizado')}%"
        ]
        for i in items: pdf.cell(0, 6, clean_txt(i), 0, 1)
        
        aps = data.get('aportes', [])
        if aps:
            pdf.ln(5)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 10, clean_txt("Aportes"), 0, 1)
            for a in aps:
                dt = _ensure_date(a.get('date', a.get('data'))).strftime("%d/%m/%Y")
                val = format_currency(float(a.get('value', a.get('valor', 0))))
                pdf.set_font("Arial", "", 9)
                pdf.cell(50, 6, clean_txt(dt), 1, 0, 'C')
                pdf.cell(50, 6, clean_txt(val), 1, 1, 'R')
                
        return bytes(pdf.output(dest='S'))
    except Exception as e:
        print(f"Erro PDF: {e}")
        return b""
