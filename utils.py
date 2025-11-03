import pandas as pd
import numpy as np
from datetime import datetime, date
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
        
        worksheets = {
            "simulations": spreadsheet.worksheet("simulations"),
            "aportes": spreadsheet.worksheet("aportes")
        }
        return worksheets
    except Exception as e:
        st.error(f"Erro fatal ao conectar com o Google Sheets: {e}")
        return None
        
@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet):
    if not _worksheet:
        return pd.DataFrame()
    
    all_values = _worksheet.get_all_values()
    if not all_values or len(all_values) < 1:
        return pd.DataFrame()

    header = all_values[0]
    if _worksheet.title == "aportes":
        st.warning(f"DEBUG (Aba 'aportes') - Cabeçalhos encontrados na Linha 1: {header}")
    # --- FIM DO CÓDIGO DE DEBUG ---
        
    data = all_values[1:]
    
    df = pd.DataFrame(data, columns=header)
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, [col for col in df.columns if col != '']]
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.lower()
    
    if 'row_index' not in df.columns:
        df['row_index'] = range(2, len(df) + 2)
    
    numeric_cols = [
        'total_contribution', 'num_months', 'annual_interest_rate', 'monthly_interest_rate', 
        'spe_percentage', 'land_size', 'construction_cost_m2', 'value_m2', 'area_exchange_percentage', 
        'vgv', 'total_construction_cost', 'final_operational_result', 'valor_participacao', 
        'resultado_final_investidor', 'roi', 'roi_anualizado', 'valor_corrigido',
        'valor_aporte'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            series = df[col].astype(str).copy()
            is_pt_br_format = series.str.contains(',', na=False)
            series = df[col].astype(str).copy()
            
            series_cleaned = series.str.replace('R$', '', regex=False) \
                                   .str.replace('$', '', regex=False) \
                                   .str.strip()
            is_pt_br_format = series_cleaned.str.contains(',', na=False)
            series_cleaned.loc[is_pt_br_format] = series_cleaned.loc[is_pt_br_format] \
                                                    .str.replace('.', '', regex=False) \
                                                    .str.replace(',', '.', regex=False)
            
            series_cleaned.loc[~is_pt_br_format] = series_cleaned.loc[~is_pt_br_format] \
                                                    .str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(series_cleaned, errors='coerce').fillna(0)
            
    for date_col in ['created_at', 'data_aporte', 'start_date', 'project_end_date']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    if 'created_at' in df.columns:
        df.dropna(subset=['created_at'], inplace=True)
        
    return df

def safe_date_to_string(date_val, fmt='%Y-%m-%d'):
    if pd.isna(date_val):
        return ""  
    try:
        return pd.to_datetime(date_val).strftime(fmt)
    except (ValueError, TypeError):
        return "" 

def calculate_financials(params):
    results = {}
    results.update(params)
    
    total_montante = 0  
    total_contribution = 0
    aportes = params.get('aportes', [])
    
    project_end_date = params.get('project_end_date')
    if isinstance(project_end_date, str):
        project_end_date = pd.to_datetime(project_end_date).date()
    elif isinstance(project_end_date, pd.Timestamp):
        project_end_date = project_end_date.date()

    if 'annual_interest_rate' in params and params.get('annual_interest_rate', 0) > 0:
        annual_rate_decimal = params.get('annual_interest_rate', 0) / 100
    else:
        monthly_rate_decimal = params.get('monthly_interest_rate', 0) / 100
        annual_rate_decimal = ((1 + monthly_rate_decimal) ** 12) - 1
        results['annual_interest_rate'] = annual_rate_decimal * 100 
        
    if annual_rate_decimal <= -1:
        daily_rate = -1.0
    else:
        daily_rate = (1 + annual_rate_decimal) ** (1/365) - 1

    total_days_for_roi = 1
    
    if not aportes:
        num_months_for_roi_display = 1
    else:
        for aporte in aportes:
            if isinstance(aporte['date'], str):
                aporte['date'] = pd.to_datetime(aporte['date']).date()
            elif isinstance(aporte['date'], pd.Timestamp):
                aporte['date'] = aporte['date'].date()
                
        aportes.sort(key=lambda x: x['date'])
        first_contribution_date = aportes[0]['date']
        
        total_days_for_roi = (project_end_date - first_contribution_date).days
        
        if total_days_for_roi <= 0:
            total_days_for_roi = 1
            
        num_months_for_roi_display = max(1, round(total_days_for_roi / 30.4375)) 
            
        for aporte in aportes:
            contribution_date = aporte['date']
            contribution_value = aporte['value']
            total_contribution += contribution_value

            num_days_aporte = (project_end_date - contribution_date).days
            
            if num_days_aporte > 0:
                montante_aporte = contribution_value * ((1 + daily_rate) ** num_days_aporte)
                total_montante += montante_aporte
            else:
                total_montante += contribution_value

    juros_investidor = max(0, total_montante - total_contribution)
    results['juros_investidor'] = juros_investidor

    results['valor_corrigido'] = total_montante
    results['total_contribution'] = total_contribution
    results['num_months'] = num_months_for_roi_display 
    
    results['vgv'] = params.get('land_size', 0) * params.get('value_m2', 0)
    
    cost_obra_fisica = params.get('land_size', 0) * params.get('construction_cost_m2', 0)
    results['cost_obra_fisica'] = cost_obra_fisica
    results['total_construction_cost'] = cost_obra_fisica + juros_investidor

    operational_result = results['vgv'] - results['total_construction_cost']
    area_exchange_value = results['vgv'] * (params.get('area_exchange_percentage', 0) / 100)
    results['final_operational_result'] = operational_result - area_exchange_value
    
    valor_investido = total_contribution
    
    results['valor_participacao'] = results['final_operational_result'] * (params.get('spe_percentage', 0) / 100)
    lucro_bruto_investidor = results['valor_corrigido'] + results['valor_participacao']
    results['resultado_final_investidor'] = lucro_bruto_investidor - valor_investido
    
    if valor_investido > 0:
        roi_raw = (results['resultado_final_investidor'] / valor_investido) * 100
        base_anualizacao = 1 + (roi_raw / 100)
        
        if base_anualizacao < 0:
            roi_anualizado_raw = -100.0
        else:
            roi_anualizado_raw = ((base_anualizacao ** (365 / total_days_for_roi)) - 1) * 100
    else:
        roi_raw = 0
        roi_anualizado_raw = 0

    results['roi'] = round(roi_raw, 2)
    results['roi_anualizado'] = round(roi_anualizado_raw, 2)
    
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
        pdf.cell(0, 5, to_latin1(f"Duração (meses aprox.): {data.get('num_months')} meses"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Taxa de Juros Anual: {data.get('annual_interest_rate', 0):.2f}%"), 0, 1)
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
        pdf.cell(0, 8, to_latin1(f"ROI (Período): {data.get('roi', 0):.2f}%"), 0, 1)
        pdf.cell(0, 8, to_latin1(f"ROI Anualizado: {data.get('roi_anualizado', 0):.2f}%"), 0, 1)
        pdf.ln(10)

        aportes = data.get('aportes', [])
        if aportes:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, to_latin1("Cronograma de Vencimentos"), 0, 1, "L")
            pdf.set_font("Arial", "B", 9)
            
            col_widths = [60, 80]
            header = [to_latin1("Data de Vencimento"), to_latin1("Valor do Aporte")]
            for i, item in enumerate(header):
                pdf.cell(col_widths[i], 8, item, 1, 0, 'C') 
            pdf.ln()

            pdf.set_font("Arial", "", 9)
            for aporte in aportes:
                aporte_date = aporte.get('date')
                
                if isinstance(aporte_date, (datetime, pd.Timestamp, date)):
                    date_str = aporte_date.strftime("%d/%m/%Y")
                else:
                    try:
                        date_str = pd.to_datetime(aporte_date).strftime("%d/%m/%Y")
                    except:
                        date_str = str(aporte_date)
                
                pdf.cell(col_widths[0], 6, to_latin1(date_str), 1, 0, 'C')
                pdf.cell(col_widths[1], 6, to_latin1(format_currency(aporte.get('value'))), 1, 1, 'R')

        output = pdf.output(dest='S')

        if isinstance(output, str):
            return output.encode('latin-1')
        return output if isinstance(output, bytes) else b""

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao gerar o PDF. Detalhes do erro: {e}")
        return b""



