import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import locale
import io
import streamlit as st
from fpdf import FPDF
import gspread
import json 

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
        creds_input = st.secrets["gcp_service_account"]
        
        if isinstance(creds_input, str):
            creds_dict = json.loads(creds_input)
        else:
            creds_dict = dict(creds_input) 

        if "private_key" in creds_dict:
            key_str_corrigida = creds_dict["private_key"].replace('\\n', '\n')
            creds_dict["private_key"] = key_str_corrigida.encode('utf-8')


        gc = gspread.service_account_from_dict(creds_dict)
        
        sheet_name = st.secrets["g_sheet_name"]
        if not sheet_name:
            st.error("Erro Crítico: A variável 'g_sheet_name' está faltando nos seus Segredos (Secrets).")
            return None
            
        spreadsheet = gc.open(sheet_name)
        
        worksheets = {
            "simulations": spreadsheet.worksheet("simulations"),
            "aportes": spreadsheet.worksheet("aportes")
        }
        return worksheets
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro Crítico: Planilha não encontrada. Verifique se o nome '{st.secrets.get('g_sheet_name', 'N/A')}' está correto em 'g_sheet_name' nos seus Segredos.", icon="🚨")
        st.info("Lembre-se também de 'compartilhar' sua Planilha Google com o email de serviço: "
                f"`{creds_dict.get('client_email', 'Email não encontrado nas credenciais.')}`")
        return None
    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Erro Crítico: Uma aba da planilha não foi encontrada. O app procurou por 'simulations' e 'aportes'.", icon="🚨")
        st.exception(e)
        return None
    except Exception as e:
        st.error(f"Erro fatal e inesperado ao conectar com o Google Sheets:", icon="🚨")
        st.exception(e) 
        return None
        
@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet):
    if not _worksheet:
        return pd.DataFrame()
    
    all_values = _worksheet.get_all_values()
    if not all_values or len(all_values) < 1:
        return pd.DataFrame()

    header = all_values[0]
    data = all_values[1:]
    
    df = pd.DataFrame(data, columns=header)
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, [col for col in df.columns if col != '']]
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.lower()
    
    if 'row_index' not in df.columns:
        df['row_index'] = range(2, len(df) + 2)
    
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
            is_pt_br_format = series.str.contains(',', na=False)
            series.loc[is_pt_br_format] = series.loc[is_pt_br_format].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(series, errors='coerce').fillna(0)
            
    for date_col in ['created_at', 'data_aporte', 'start_date', 'project_end_date', 'data']:
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
    
    start_date_dt = pd.to_datetime(params.get('start_date', datetime.today()))
    project_end_date_dt = pd.to_datetime(params.get('project_end_date', datetime.today()))

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
        aportes.sort(key=lambda x: x['date'])
        first_contribution_date = pd.to_datetime(aportes[0]['date'])
        
        delta_total_dias = (project_end_date_dt - first_contribution_date).days
        total_days_for_roi = max(1, delta_total_dias)
        
        delta_total_meses = relativedelta(project_end_date_dt, first_contribution_date)
        num_months_for_roi_display = delta_total_meses.years * 12 + delta_total_meses.months
        if num_months_for_roi_display <= 0: num_months_for_roi_display = 1
            
        for aporte in aportes:
            contribution_date = pd.to_datetime(aporte['date'])
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
    results['start_date'] = start_date_dt.date()
    results['project_end_date'] = project_end_date_dt.date()
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
        
        if (1 + roi_raw) < 0:
            roi_anualizado_raw = -1.0
        else:
            roi_anualizado_raw = ((1 + roi_raw) ** (365 / total_days_for_roi)) - 1
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
        pdf.cell(0, 5, to_latin1(f"Duração (aprox.): {data.get('num_months')} meses"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Taxa de Juros Anual: {data.get('annual_interest_rate', 0):.2f}%"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Participação na SPE: {data.get('spe_percentage', 0):.2f}%"), 0, 1)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Análise do Projeto Imobiliário"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"VGV (Valor Geral de Venda): {format_currency(data.get('vgv'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo Físico da Obra: {format_currency(data.get('cost_obra_fisica'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo do Capital (Juros): {format_currency(data.get('juros_investidor'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo da Troca de Área: {format_currency(data.get('area_exchange_value'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Custo Total da Obra: {format_currency(data.get('total_construction_cost'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Resultado Operacional: {format_currency(data.get('final_operational_result'))}"), 0, 1)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Resultados do Investidor"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"Montante Final (Aporte + Juros): {format_currency(data.get('valor_corrigido'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"(+) Participação na SPE: {format_currency(data.get('valor_participacao'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"(-) Aporte Total: {format_currency(data.get('total_contribution'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Resultado Final (Lucro): {format_currency(data.get('resultado_final_investidor'))}"), 0, 1)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, to_latin1(f"ROI: {data.get('roi', 0):.2f}%"), 0, 1)
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
