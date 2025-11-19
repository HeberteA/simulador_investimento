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
import json 

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR')
    except locale.Error:
        locale.setlocale(locale.LC_ALL, '')

def format_currency(value):
    if value is None: return "R$ 0,00"
    try:
        return locale.currency(float(value), grouping=True, symbol='R$')
    except:
        return f"R$ {float(value):,.2f}"

@st.cache_resource
def init_gsheet_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Segredos do GCP não encontrados.")
            return None
            
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict)
        
        if "spreadsheet_key" not in st.secrets:
            return None
            
        spreadsheet_key = st.secrets["spreadsheet_key"]
        spreadsheet = gc.open_by_key(spreadsheet_key)

        worksheets = {
            "simulations": spreadsheet.worksheet("simulations"),
            "aportes": spreadsheet.worksheet("aportes")
        }
        return worksheets

    except SpreadsheetNotFound:
        st.error("Planilha não encontrada.")
        return None
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return None
        
@st.cache_data(ttl=60)
def load_data_from_sheet(_worksheet):
    try:
        if _worksheet is None:
            return pd.DataFrame()

        all_values = _worksheet.get_all_values()
        if not all_values or len(all_values) < 1:
            return pd.DataFrame()

        header = all_values[0]
        data = all_values[1:]
        
        df = pd.DataFrame(data, columns=header)
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, [col for col in df.columns if col != '']]
        df.columns = df.columns.str.strip().str.lower()
        
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
                is_pt_br = series.str.contains(',', na=False)
                series.loc[is_pt_br] = series.loc[is_pt_br].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(series, errors='coerce').fillna(0)
                
        for date_col in ['created_at', 'data_aporte', 'start_date', 'project_end_date', 'data']:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        if 'created_at' in df.columns:
            df.dropna(subset=['created_at'], inplace=True)
            
        return df
    
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def calculate_financials(params):
    def safe_to_date(val):
        if val is None: return datetime.today().date()
        try:
            ts = pd.to_datetime(val)
            if pd.isna(ts): return datetime.today().date()
            return ts.date()
        except:
            return datetime.today().date()

    results = {}
    results.update(params)
    
    total_montante = 0
    total_contribution = 0
    aportes = params.get('aportes', [])
    
    start_date_dt = safe_to_date(params.get('start_date'))
    project_end_date_dt = safe_to_date(params.get('project_end_date'))

    if project_end_date_dt < start_date_dt:
        project_end_date_dt = start_date_dt + relativedelta(months=24)

    annual_rate_decimal = float(params.get('annual_interest_rate', 0)) / 100
    
    if 'monthly_interest_rate' in params and 'annual_interest_rate' not in params:
        monthly_rate_decimal = float(params.get('monthly_interest_rate', 0)) / 100
        annual_rate_decimal = (1 + monthly_rate_decimal) ** 12 - 1
        results['annual_interest_rate'] = annual_rate_decimal * 100

    daily_rate = (1 + annual_rate_decimal) ** (1/365) - 1
    
    total_days_for_roi = 1
    num_months_for_roi_display = 0

    if not aportes:
        contrib_manual = float(params.get('total_contribution', 0))
        if contrib_manual > 0:
            total_contribution = contrib_manual
            days = (project_end_date_dt - datetime.today().date()).days
            if days > 0:
                total_montante = contrib_manual * ((1 + daily_rate) ** days)
            else:
                total_montante = contrib_manual
            
        delta = relativedelta(project_end_date_dt, start_date_dt)
        num_months_for_roi_display = delta.years * 12 + delta.months
        total_days_for_roi = max(1, (project_end_date_dt - start_date_dt).days)
    else:
        valid_aportes = []
        for a in aportes:
            if isinstance(a, dict) and 'date' in a and 'value' in a:
                valid_aportes.append({
                    'date': safe_to_date(a['date']),
                    'value': float(a['value'])
                })
        
        sorted_aportes = sorted(valid_aportes, key=lambda x: x['date'])
        
        if sorted_aportes:
            first_contribution_date = sorted_aportes[0]['date']
            
            delta_total_dias = (project_end_date_dt - first_contribution_date).days
            total_days_for_roi = max(1, delta_total_dias)
            
            delta_total_meses = relativedelta(project_end_date_dt, first_contribution_date)
            num_months_for_roi_display = delta_total_meses.years * 12 + delta_total_meses.months
            if num_months_for_roi_display <= 0: num_months_for_roi_display = 1
                
            for aporte in sorted_aportes:
                contribution_date = aporte['date']
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
    
    # Cálculos do Projeto
    land_size = float(params.get('land_size', 0))
    value_m2 = float(params.get('value_m2', 0))
    const_cost_m2 = float(params.get('construction_cost_m2', 0))
    
    results['vgv'] = land_size * value_m2
    
    cost_obra_fisica = land_size * const_cost_m2
    area_exchange_value = results['vgv'] * (float(params.get('area_exchange_percentage', 0)) / 100)

    results['cost_obra_fisica'] = cost_obra_fisica
    results['area_exchange_value'] = area_exchange_value
    results['total_construction_cost'] = cost_obra_fisica + juros_investidor + area_exchange_value

    operational_result = results['vgv'] - results['total_construction_cost']
    results['final_operational_result'] = operational_result
    
    results['valor_participacao'] = results['final_operational_result'] * (float(params.get('spe_percentage', 0)) / 100)
    lucro_bruto_investidor = results['valor_corrigido'] + results['valor_participacao']
    
    results['resultado_final_investidor'] = lucro_bruto_investidor - total_contribution
    
    if total_contribution > 0:
        roi_raw = (results['resultado_final_investidor'] / total_contribution)
        
        if (1 + roi_raw) < 0:
            roi_anualizado_raw = -1.0
        else:
            if total_days_for_roi > 0:
                roi_anualizado_raw = ((1 + roi_raw) ** (365 / total_days_for_roi)) - 1
            else:
                roi_anualizado_raw = 0
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
        pdf.cell(0, 10, to_latin1("Dados do Cliente"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        client_info = f"Cliente: {data.get('client_name', '')}"
        if data.get('client_code'): client_info += f" (Cód: {data.get('client_code')})"
        
        pdf.cell(0, 5, to_latin1(client_info), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Aporte Total: {format_currency(data.get('total_contribution'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Prazo Estimado: {data.get('num_months')} meses"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"Taxa Anual: {data.get('annual_interest_rate', 0):.2f}%"), 0, 1)
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, to_latin1("Resultados"), 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, to_latin1(f"Lucro Líquido: {format_currency(data.get('resultado_final_investidor'))}"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"ROI do Período: {data.get('roi', 0):.2f}%"), 0, 1)
        pdf.cell(0, 5, to_latin1(f"ROI Anualizado: {data.get('roi_anualizado', 0):.2f}%"), 0, 1)
        pdf.ln(10)

        aportes = data.get('aportes', [])
        if aportes:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, to_latin1("Cronograma de Aportes"), 0, 1, "L")
            pdf.set_font("Arial", "B", 9)
            col_widths = [60, 80]
            pdf.cell(col_widths[0], 8, to_latin1("Data"), 1, 0, 'C')
            pdf.cell(col_widths[1], 8, to_latin1("Valor"), 1, 1, 'C')

            pdf.set_font("Arial", "", 9)
            for aporte in aportes:
                dt = aporte.get('date')
                if not isinstance(dt, str): dt = dt.strftime("%d/%m/%Y")
                pdf.cell(col_widths[0], 6, to_latin1(dt), 1, 0, 'C')
                pdf.cell(col_widths[1], 6, to_latin1(format_currency(aporte.get('value'))), 1, 1, 'R')

        return pdf.output(dest='S').encode('latin-1')

    except Exception as e:
        return b""
