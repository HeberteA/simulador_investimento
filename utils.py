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

@@st.cache_resource
def init_gsheet_connection():
    try:
        creds = st.secrets["gcp_service_account"]
        sheet_name = st.secrets["g_sheet_name"]
        gc = gspread.service_account_from_dict(creds)
        spreadsheet = gc.open(sheet_name)
        worksheet_simulations = spreadsheet.worksheet("simulations")
        return worksheet_simulations
    except Exception as e:
        st.error(f"Erro fatal ao conectar com o Google Sheets: {e}")
        return None
        
@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet):
    if not _worksheet:
        return pd.DataFrame()
    
    all_values = _worksheet.get_all_values()
    if not all_values:
        return pd.DataFrame()

    header_row_index = -1
    for i, row in enumerate(all_values):
        if any(cell for cell in row):
            header_row_index = i
            break
    
    if header_row_index == -1:
        return pd.DataFrame()

    header = all_values[header_row_index]
    data = all_values[header_row_index + 1:]
    
    df = pd.DataFrame(data, columns=header)
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, [col for col in df.columns if col != '']]
    df.columns = df.columns.str.strip()
    if 'row_index' not in df.columns:
        df['row_index'] = range(header_row_index + 2, len(df) + header_row_index + 2)
    
    
    numeric_cols = [
        'total_contribution', 'num_months', 'monthly_interest_rate', 'spe_percentage', 
        'land_size', 'construction_cost_m2', 'value_m2', 'area_exchange_percentage', 
        'vgv', 'total_construction_cost', 'final_operational_result', 'valor_participacao', 
        'resultado_final_investidor', 'roi', 'roi_anualizado', 'valor_corrigido',
        'valor_aporte'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            series = df[col].astype(str).copy()
            is_pt_br_format = series.str.contains(',', na=False)
            series.loc[is_pt_br_format] = series.loc[is_pt_br_format].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(series, errors='coerce').fillna(0)
            
    for date_col in ['created_at', 'data_aporte', 'start_date', 'project_end_date']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    if 'created_at' in df.columns:
        df.dropna(subset=['created_at'], inplace=True)
        
    return df

def calculate_financials(params):
    results = {}
    results.update(params)
    
    total_montante = 0  
    total_contribution = 0
    aportes = params.get('aportes', [])
    project_end_date = params.get('project_end_date')
    monthly_rate_decimal = params.get('monthly_interest_rate', 0) / 100

    if not aportes:
        num_months_for_roi = 1
    else:
        aportes.sort(key=lambda x: x['date'])
        first_contribution_date = aportes[0]['date']
        
        delta_total = relativedelta(project_end_date, first_contribution_date)
        num_months_for_roi = delta_total.years * 12 + delta_total.months
        if num_months_for_roi <= 0:
            num_months_for_roi = 1
            
        for aporte in aportes:
            contribution_date = aporte['date']
            contribution_value = aporte['value']
            total_contribution += contribution_value

            delta = relativedelta(project_end_date, contribution_date)
            num_months_aporte = delta.years * 12 + delta.months
            
            if num_months_aporte > 0:
                montante_aporte = contribution_value * ((1 + monthly_rate_decimal) ** num_months_aporte)
                total_montante += montante_aporte
            else:
                total_montante += contribution_value

    results['valor_corrigido'] = total_montante
    results['total_contribution'] = total_contribution
    results['num_months'] = num_months_for_roi
    results['vgv'] = params.get('land_size', 0) * params.get('value_m2', 0)
    results['total_construction_cost'] = params.get('land_size', 0) * params.get('construction_cost_m2', 0)
    operational_result = results['vgv'] - results['total_construction_cost']
    area_exchange_value = results['vgv'] * (params.get('area_exchange_percentage', 0) / 100)
    results['final_operational_result'] = operational_result - area_exchange_value
    
    valor_investido = total_contribution
    
    results['valor_participacao'] = results['final_operational_result'] * (params.get('spe_percentage', 0) / 100)
    lucro_bruto_investidor = results['valor_corrigido'] + results['valor_participacao']
    results['resultado_final_investidor'] = lucro_bruto_investidor - valor_investido
    
    roi_raw = (results['resultado_final_investidor'] / valor_investido) * 100 if valor_investido > 0 else 0
    
    base_anualizacao = 1 + (roi_raw / 100)
    if base_anualizacao < 0:
        roi_anualizado_raw = -100.0
    else:
        roi_anualizado_raw = ((base_anualizacao ** (12 / num_months_for_roi)) - 1) * 100 if num_months_for_roi > 0 else 0

    results['roi'] = round(roi_raw, 2)
    results['roi_anualizado'] = round(roi_anualizado_raw, 2)
    
    return results
    
def generate_pdf(data):
    try:
        def to_latin1(text):
            """Converte uma string para o formato latin-1, substituindo caracteres incompatíveis."""
            if text is None:
                return ''
            return str(text).encode('latin-1', 'replace').decode('latin-1')

        pdf = FPDF()
        pdf.add_page()
        try:
            pdf.image("Lavie.png", x=10, y=8, w=40)
        except Exception:
            pdf.set_font("Arial", "I", 8)
            pdf.cell(0, 5, to_latin1("Logo 'Lavie.png' nao encontrado."), 0, 1, "L")
        
        pdf.set_font("Arial", "B", 16)
        pdf.set_x(60)
        pdf.cell(0, 10, to_latin1("Relatório de Simulação Financeira"), 0, 1, "C")
        pdf.ln(20)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Dados do Cliente e Investimento"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        client_info = f"Cliente: {data.get('client_name', '')} (Código: {data.get('client_code', '')})"
        pdf.cell(0, 5, to_latin1(client_info), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Valor do Aporte Total: {format_currency(data.get('total_contribution'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Duração: {data.get('num_months')} meses"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Taxa de Juros Mensal: {data.get('monthly_interest_rate', 0):.2f}%"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Participação na SPE: {data.get('spe_percentage', 0):.2f}%"), 0, 1)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Análise do Projeto Imobiliário"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"VGV (Valor Geral de Venda): {format_currency(data.get('vgv'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo Total da Obra: {format_currency(data.get('total_construction_cost'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Resultado Operacional Final: {format_currency(data.get('final_operational_result'))}"), 0, 1)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Resultados do Investidor"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"Montante Final (Aporte + Juros): {format_currency(data.get('valor_corrigido'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Resultado Final (Lucro): {format_currency(data.get('resultado_final_investidor'))}"), 0, 1)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, to_latin1(f"ROI: {data.get('roi', 0):.2f}%"), 0, 1)
        pdf.cell(0, 8, to_latin1(f"ROI Anualizado: {data.get('roi_anualizado', 0):.2f}%"), 0, 1)
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Plano de Parcelas Detalhado"), 0, 1, "L")
        pdf.set_font("Arial", "B", 9)
        
        col_widths = [20, 35, 40, 40, 40]
        header = [to_latin1("Parcela Nº"), "Vencimento", to_latin1("Valor Base"), "Juros Mensal", "Valor Total"]
        for i, item in enumerate(header):
            pdf.cell(col_widths[i], 8, item, 1, 0, 'C')
        pdf.ln()

        pdf.set_font("Arial", "", 9)
        num_months = int(data.get('num_months', 1))
        if num_months <= 0: num_months = 1
        
        start_date_val = data.get('start_date')
        if isinstance(start_date_val, str):
            try:
                start_date_val = pd.to_datetime(start_date_val).date()
            except (ValueError, TypeError):
                start_date_val = datetime.now().date()
        elif isinstance(start_date_val, (datetime, pd.Timestamp)):
            start_date_val = start_date_val.date()
        elif start_date_val is None:
            start_date_val = datetime.now().date()

        monthly_rate_dec = data.get('monthly_interest_rate', 0) / 100
        inst_val = data.get('total_contribution', 0) / num_months if num_months > 0 else 0
        int_val = inst_val * monthly_rate_dec
        inst_with_int = inst_val + int_val

        for i in range(1, num_months + 1):
            vencimento = (start_date_val + relativedelta(months=i-1)).strftime("%d/%m/%Y")
            pdf.cell(col_widths[0], 6, to_latin1(str(i)), 1, 0, 'C')
            pdf.cell(col_widths[1], 6, to_latin1(vencimento), 1, 0, 'C')
            pdf.cell(col_widths[2], 6, to_latin1(format_currency(inst_val)), 1, 0, 'R')
            pdf.cell(col_widths[3], 6, to_latin1(format_currency(int_val)), 1, 0, 'R')
            pdf.cell(col_widths[4], 6, to_latin1(format_currency(inst_with_int)), 1, 1, 'R')

        output = pdf.output(dest='S')

        if isinstance(output, str):
            return output.encode('latin-1')
        elif isinstance(output, bytes):
            return output
        else:
            return b""
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao gerar o PDF. Detalhes do erro:")
        st.error(e)
        return b""

  
