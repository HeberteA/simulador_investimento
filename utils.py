import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import locale
import io
import streamlit as st
from fpdf import FPDF
import gspread
from gspread.exceptions import WorksheetNotFound

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '')

def format_currency(value):
    if value is None: return "N/A"
    return locale.currency(value, grouping=True, symbol='R$')

@st.cache_resource
def init_gsheet_connection():
    try:
        creds = st.secrets["gcp_service_account"]
        sheet_name = st.secrets["g_sheet_name"]
        gc = gspread.service_account_from_dict(creds)
        spreadsheet = gc.open(sheet_name)
        try:
            worksheet = spreadsheet.worksheet("simulations")
        except WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="simulations", rows="100", cols="22")
            header = [
                "created_at", "client_name", "client_code", "total_contribution",
                "num_months", "monthly_interest_rate", "spe_percentage", "land_size",
                "construction_cost_m2", "value_m2", "area_exchange_percentage",
                "vgv", "total_construction_cost", "final_operational_result", "valor_participacao",
                "resultado_final_investidor", "roi", "roi_anualizado", "valor_corrigido"
            ]
            worksheet.append_row(header)
        return worksheet
    except Exception as e:
        st.error(f"Erro fatal ao conectar com o Google Sheets: {e}")
        return None

@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet):
    if not _worksheet:
        return pd.DataFrame()
    
    values = _worksheet.get_all_values()
    if len(values) < 2:
        return pd.DataFrame()

    header = values[0]
    data = values[1:]
    df = pd.DataFrame(data, columns=header)
    
    df['row_index'] = range(2, len(df) + 2)
    
    numeric_cols = [
        'total_contribution', 'num_months', 'monthly_interest_rate', 
        'spe_percentage', 'land_size', 'construction_cost_m2', 'value_m2', 
        'area_exchange_percentage', 'vgv', 'total_construction_cost', 
        'final_operational_result', 'valor_participacao', 'resultado_final_investidor', 
        'roi', 'roi_anualizado', 'valor_corrigido'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            series = df[col].astype(str).copy()
            is_pt_br_format = series.str.contains(',', na=False)
            series.loc[is_pt_br_format] = series.loc[is_pt_br_format].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(series, errors='coerce').fillna(0)
            
    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
    df.dropna(subset=['created_at'], inplace=True)
    return df

def calculate_financials(params):
    results = {}
    results.update(params)
    results['vgv'] = params.get('land_size', 0) * params.get('value_m2', 0)
    results['total_construction_cost'] = params.get('land_size', 0) * params.get('construction_cost_m2', 0)
    operational_result = results['vgv'] - results['total_construction_cost']
    area_exchange_value = results['vgv'] * (params.get('area_exchange_percentage', 0) / 100)
    results['final_operational_result'] = operational_result - area_exchange_value
    valor_investido = params.get('total_contribution', 0)
    num_months = params.get('num_months', 1)
    if num_months <= 0: num_months = 1
    monthly_rate_decimal = params.get('monthly_interest_rate', 0) / 100
    total_juros = valor_investido * monthly_rate_decimal * num_months
    results['valor_corrigido'] = valor_investido + total_juros
    results['valor_participacao'] = results['final_operational_result'] * (params.get('spe_percentage', 0) / 100)
    lucro_bruto_investidor = results['valor_corrigido'] + results['valor_participacao']
    results['resultado_final_investidor'] = lucro_bruto_investidor - valor_investido
    
    roi_raw = (results['resultado_final_investidor'] / valor_investido) * 100 if valor_investido > 0 else 0
    
    base_anualizacao = 1 + (roi_raw / 100)
    if base_anualizacao < 0:
        roi_anualizado_raw = -100.0
    else:
        roi_anualizado_raw = ((base_anualizacao ** (12 / num_months)) - 1) * 100 if num_months > 0 else 0

    results['roi'] = round(roi_raw, 2)
    results['roi_anualizado'] = round(roi_anualizado_raw, 2)
    
    return results

def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.image("Lavie.png", x=10, y=8, w=40)
    except FileNotFoundError:
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 5, "Logo 'Lavie.png' nao encontrado.", 0, 1, "L")
    pdf.set_font("Arial", "B", 16)
    pdf.set_x(60)
    pdf.cell(0, 10, "Relatório de Simulação Financeira", 0, 1, "C")
    pdf.ln(20)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Dados do Cliente e Investimento", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"Cliente: {data.get('client_name')} (Código: {data.get('client_code')})", 0, 1)
    pdf.cell(0, 5, f"Valor do Aporte Total: {format_currency(data.get('total_contribution'))}", 0, 1)
    pdf.cell(0, 5, f"Duração: {data.get('num_months')} meses", 0, 1)
    pdf.cell(0, 5, f"Taxa de Juros Mensal: {data.get('monthly_interest_rate', 0):.2f}%", 0, 1)
    pdf.cell(0, 5, f"Participação na SPE: {data.get('spe_percentage', 0):.2f}%", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Análise do Projeto Imobiliário", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"VGV (Valor Geral de Venda): {format_currency(data.get('vgv'))}", 0, 1)
    pdf.cell(0, 5, f"Custo Total da Obra: {format_currency(data.get('total_construction_cost'))}", 0, 1)
    pdf.cell(0, 5, f"Resultado Operacional Final: {format_currency(data.get('final_operational_result'))}", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resultados do Investidor", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"Montante Final (Aporte + Juros): {format_currency(data.get('valor_corrigido'))}", 0, 1)
    pdf.cell(0, 5, f"Resultado Final (Lucro): {format_currency(data.get('resultado_final_investidor'))}", 0, 1)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"ROI: {data.get('roi', 0):.2f}%", 0, 1)
    pdf.cell(0, 8, f"ROI Anualizado: {data.get('roi_anualizado', 0):.2f}%", 0, 1)
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Plano de Parcelas Detalhado", 0, 1, "L")
    pdf.set_font("Arial", "B", 9)
    col_widths = [20, 35, 40, 40, 40]
    header = ["Parcela No", "Vencimento", "Valor Base", "Juros Mensal", "Valor Total"]
    for i, item in enumerate(header):
        pdf.cell(col_widths[i], 8, item, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    num_months = int(data.get('num_months', 1))
    if num_months <= 0: num_months = 1
    start_date_val = data.get('start_date')
    if isinstance(start_date_val, str):
        try: start_date_val = pd.to_datetime(start_date_val).date()
        except (ValueError, TypeError): start_date_val = datetime.now().date()
    elif isinstance(start_date_val, datetime): start_date_val = start_date_val.date()
    elif isinstance(start_date_val, pd.Timestamp): start_date_val = start_date_val.date()
    elif start_date_val is None: start_date_val = datetime.now().date()
    monthly_rate_dec = data.get('monthly_interest_rate', 0) / 100
    inst_val = data.get('total_contribution', 0) / num_months if num_months > 0 else 0
    int_val = inst_val * monthly_rate_dec
    inst_with_int = inst_val + int_val
    for i in range(1, num_months + 1):
        vencimento = (start_date_val + relativedelta(months=i-1)).strftime("%d/%m/%Y")
        pdf.cell(col_widths[0], 6, str(i), 1, 0, 'C')
        pdf.cell(col_widths[1], 6, vencimento, 1, 0, 'C')
        pdf.cell(col_widths[2], 6, format_currency(inst_val), 1, 0, 'R')
        pdf.cell(col_widths[3], 6, format_currency(int_val), 1, 0, 'R')
        pdf.cell(col_widths[4], 6, format_currency(inst_with_int), 1, 1, 'R')
    
    if output_string:
        return output_string.encode('latin-1')
    else:
        return b""
  
