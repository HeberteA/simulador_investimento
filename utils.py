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
    return locale.currency(value, grouping=True, symbol='R$')

def _ensure_date(val):
    """Converte qualquer input de data (str, datetime, timestamp) para datetime.date"""
    if val is None or pd.isna(val):
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
        
        if "spreadsheet_key" not in st.secrets:
            st.error("Erro: 'spreadsheet_key' não encontrada nos segredos.")
            return None
            
        spreadsheet_key = st.secrets["spreadsheet_key"]
        spreadsheet = gc.open_by_key(spreadsheet_key)

        worksheets = {
            "simulations": spreadsheet.worksheet("simulations"),
            "aportes": spreadsheet.worksheet("aportes")
        }
        return worksheets

    except SpreadsheetNotFound:
        st.error("Erro: Planilha não encontrada.")
        return None
    except KeyError as e:
        st.error(f"Erro Credenciais: {e}")
        return None
    except Exception as e:
        st.error(f"Erro GSheets: {e}")
        return None
        
@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet, tab_name="default"):
    try:
        if _worksheet is None: return pd.DataFrame()

        all_values = _worksheet.get_all_values()
        if not all_values or len(all_values) < 1: return pd.DataFrame()

        header = all_values[0]
        data = all_values[1:]
        
        df = pd.DataFrame(data, columns=header)
        
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, [col for col in df.columns if col != '']]
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        rename_map = {'date': 'data_aporte', 'value': 'valor_aporte', 'data': 'data_aporte', 'valor': 'valor_aporte'}
        df.rename(columns=rename_map, inplace=True)
        
        if 'row_index' not in df.columns:
            df['row_index'] = [i + 2 for i in range(len(df))]
        
        numeric_cols = [
            'total_contribution', 'num_months', 'monthly_interest_rate', 'annual_interest_rate', 'spe_percentage',
            'land_size', 'construction_cost_m2', 'value_m2', 'area_exchange_percentage',
            'vgv', 'total_construction_cost', 'final_operational_result', 'valor_participacao',
            'resultado_final_investidor', 'roi', 'roi_anualizado', 'valor_corrigido',
            'valor_aporte', 'cost_obra_fisica', 'juros_investidor'
        ]
        
        for col in numeric_cols:
            if col in df.columns:
                series = df[col].astype(str).copy()
                series = series.str.replace('R$', '', regex=False).str.strip()
                is_pt_br = series.str.contains(',', na=False)
                series.loc[is_pt_br] = series.loc[is_pt_br].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(series, errors='coerce').fillna(0)

        date_cols = ['created_at', 'data_aporte', 'start_date', 'project_end_date']
        for date_col in date_cols:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        if 'created_at' in df.columns:
            df.dropna(subset=['created_at'], inplace=True)
            
        return df
    
    except Exception as e:
        st.error(f"Erro ao carregar aba '{tab_name}': {e}")
        return pd.DataFrame()

def calculate_financials(params):
    results = {}
    results.update(params)
    
    total_montante = 0
    total_contribution = 0
    aportes = params.get('aportes', [])
    
    start_date_dt = _ensure_date(params.get('start_date'))
    project_end_date_dt = _ensure_date(params.get('project_end_date'))
    annual_rate_decimal = params.get('annual_interest_rate', 0) / 100
    if 'monthly_interest_rate' in params and 'annual_interest_rate' not in params:
        monthly_rate_decimal = params.get('monthly_interest_rate', 0) / 100
        annual_rate_decimal = (1 + monthly_rate_decimal) ** 12 - 1
        results['annual_interest_rate'] = annual_rate_decimal * 100

    daily_rate = (1 + annual_rate_decimal) ** (1/365) - 1
    
    total_days_for_roi = 1
    num_months_for_roi_display = 0

    if not aportes:
        num_days_for_roi = 1
        num_months_for_roi_display = 1
    else:
        sorted_aportes = sorted(aportes, key=lambda x: x['date'])
        
        first_contribution_date = _ensure_date(sorted_aportes[0]['date'])
        
        delta_total_dias = (project_end_date_dt - first_contribution_date).days
        total_days_for_roi = max(1, delta_total_dias)
        
        delta_total_meses = relativedelta(project_end_date_dt, first_contribution_date)
        num_months_for_roi_display = delta_total_meses.years * 12 + delta_total_meses.months
        if num_months_for_roi_display <= 0: num_months_for_roi_display = 1
            
        for aporte in sorted_aportes:
            contribution_date = _ensure_date(aporte['date'])
            contribution_value = aporte['value']
            total_contribution += contribution_value

            num_days_aporte = (project_end_date_dt - contribution_date).days
            
            if num_days_aporte > 0:
                montante_aporte = contribution_value * ((1 + daily_rate) ** num_days_aporte)
                total_montante += montante_aporte
            else:
                total_montante += contribution_value

    juros_investidor = max(0, total_montante - total_contribution)

    results['valor_corrigido'] = total_montante
    results['total_contribution'] = total_contribution
    results['total_days_for_roi'] = total_days_for_roi
    results['num_months'] = num_months_for_roi_display
    results['start_date'] = start_date_dt
    results['project_end_date'] = project_end_date_dt
    results['juros_investidor'] = juros_investidor
    
    results['vgv'] = params.get('land_size', 0) * params.get('value_m2', 0)
    
    cost_obra_fisica = params.get('land_size', 0) * params.get('construction_cost_m2', 0)
    area_exchange_value = results['vgv'] * (params.get('area_exchange_percentage', 0) / 100)

    results['cost_obra_fisica'] = cost_obra_fisica
    results['area_exchange_value'] = area_exchange_value
    results['total_construction_cost'] = cost_obra_fisica + juros_investidor + area_exchange_value

    operational_result = results['vgv'] - results['total_construction_cost']
    results['final_operational_result'] = operational_result
    
    valor_investido = total_contribution
    
    results['valor_participacao'] = results['final_operational_result'] * (params.get('spe_percentage', 0) / 100)
    lucro_bruto_investidor = results['valor_corrigido'] + results['valor_participacao']
    
    results['resultado_final_investidor'] = lucro_bruto_investidor - valor_investido
    
    if valor_investido > 0:
        roi_raw = (results['resultado_final_investidor'] / valor_investido)
        if (1 + roi_raw) < 0: roi_anualizado_raw = -1.0
        else: roi_anualizado_raw = ((1 + roi_raw) ** (365 / total_days_for_roi)) - 1
    else:
        roi_raw = 0
        roi_anualizado_raw = 0

    results['roi'] = round(roi_raw * 100, 2)
    results['roi_anualizado'] = round(roi_anualizado_raw * 100, 2)
    
    return results
    
def generate_pdf(data):
    try:
        def to_latin1(text):
            if text is None: return ''
            return str(text).encode('latin-1', 'replace').decode('latin-1')

        pdf = FPDF()
        pdf.add_page()
        try:
            pdf.image("Lavie.png", x=10, y=8, w=40)
        except Exception:
            pdf.set_font("Arial", "I", 8)
            pdf.cell(0, 5, to_latin1("Lavie"), 0, 1, "L")

        pdf.set_font("Arial", "B", 16)
        pdf.set_x(60)
        pdf.cell(0, 10, to_latin1("Relatório de Simulação Financeira"), 0, 1, "C")
        pdf.ln(20)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Dados do Cliente e Investimento"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        c_name = data.get('client_name', '') or 'Cliente'
        c_code = data.get('client_code', '')
        pdf.cell(0, 5, to_latin1(f"Cliente: {c_name} {f'({c_code})' if c_code else ''}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Valor do Aporte Total: {format_currency(data.get('total_contribution'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Duração (aprox.): {data.get('num_months')} meses"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Taxa de Juros Anual: {data.get('annual_interest_rate', 0):.2f}%"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Participação na SPE: {data.get('spe_percentage', 0):.2f}%"), 0, 1)
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Análise do Projeto Imobiliário"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"VGV (Valor Geral de Venda): {format_currency(data.get('vgv'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo Físico da Obra: {format_currency(data.get('cost_obra_fisica'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo Financeiro (Juros): {format_currency(data.get('juros_investidor'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Permuta/Troca de Área: {format_currency(data.get('area_exchange_value'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo Total: {format_currency(data.get('total_construction_cost'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Resultado Operacional: {format_currency(data.get('final_operational_result'))}"), 0, 1)
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Resultados do Investidor"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"Montante Final (Capital + Juros): {format_currency(data.get('valor_corrigido'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"(+) Participação na SPE: {format_currency(data.get('valor_participacao'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"(-) Capital Investido: {format_currency(data.get('total_contribution'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Resultado Líquido: {format_currency(data.get('resultado_final_investidor'))}"), 0, 1)
        
        pdf.ln(2)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, to_latin1(f"ROI: {data.get('roi', 0):.2f}%"), 0, 1)
        pdf.cell(0, 8, to_latin1(f"ROI Anualizado: {data.get('roi_anualizado', 0):.2f}%"), 0, 1)
        pdf.ln(10)

        aportes = data.get('aportes', [])
        if aportes:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, to_latin1("Cronograma de Aportes"), 0, 1, "L")
            pdf.set_font("Arial", "B", 9)
            
            w_dt, w_val = 50, 50
            pdf.cell(w_dt, 8, to_latin1("Data"), 1, 0, 'C')
            pdf.cell(w_val, 8, to_latin1("Valor"), 1, 1, 'C')
            
            pdf.set_font("Arial", "", 9)
            for aporte in aportes:
                d_obj = _ensure_date(aporte.get('date'))
                d_str = d_obj.strftime("%d/%m/%Y")
                
                pdf.cell(w_dt, 6, to_latin1(d_str), 1, 0, 'C')
                pdf.cell(w_val, 6, to_latin1(format_currency(aporte.get('value'))), 1, 1, 'R')

        return bytes(pdf.output(dest='S'))

    except Exception as e:
        print(f"Erro PDF: {e}")
        return b""
