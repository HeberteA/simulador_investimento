import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import utils
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
from utils import format_currency, generate_pdf, calculate_financials

THEME_PRIMARY_COLOR = "#E37026"

def display_full_results(results, show_save_button=False, show_download_button=False, save_callback=None):
    unique_id = results.get('simulation_id', str(datetime.now().timestamp()))

    st.header("Resultados da Simulação")

    tab_vencimentos, tab_resumo, tab_sensibilidade = st.tabs(["**Cronograma de Vencimentos**", "**Resumo Financeiro**", "**Análise de Cenários**"])

    with tab_vencimentos:
        st.subheader("📅 Cronograma de Vencimentos Detalhado")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Nome do Cliente", results.get('client_name', "N/A"))
        with c2:
            st.metric("Montante Final (Aporte + Juros)", utils.format_currency(results.get('valor_corrigido', 0)))
        with c3:
            st.metric("Total Aportado", utils.format_currency(results.get('total_contribution', 0)))
        st.divider()

        aportes_list = results.get('aportes', [])
        
        if aportes_list:
            aportes_list_sorted = sorted(aportes_list, key=lambda x: x['date'])
            df_aportes_display = pd.DataFrame([{'Vencimento': a['date'], 'Valor': a['value']} for a in aportes_list_sorted])
            df_aportes_display['Vencimento'] = pd.to_datetime(df_aportes_display['Vencimento']).dt.strftime('%d/%m/%Y')
            df_aportes_display['Valor'] = df_aportes_display['Valor'].apply(utils.format_currency)
            st.dataframe(df_aportes_display, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum aporte foi encontrado para esta simulação.")

    with tab_resumo:
        st.subheader("📈 Resumo Financeiro")
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("##### Demonstrativo de Retorno do Investidor")
            st.metric("1. Montante Corrigido (Aporte + Juros)", format_currency(results.get('valor_corrigido', 0)))
            spe_percentage_label = f"2. Participação de ({results.get('spe_percentage', 0):.2f}%) da SPE no Projeto"
            st.metric(spe_percentage_label, format_currency(results.get('valor_participacao', 0)))
            total_bruto = results.get('valor_corrigido', 0) + results.get('valor_participacao', 0)
            st.metric("(=) Total Bruto Recebido", format_currency(total_bruto))
            st.metric("(-) Aporte Inicial", f"- {format_currency(results.get('total_contribution', 0))}")
            st.markdown("---")
            st.metric("**(=) Resultado Final (Lucro Líquido)**", f"{format_currency(results.get('resultado_final_investidor', 0))}")
        
        with col2:
            st.markdown("##### Resumo do Projeto Imobiliário")
            st.metric("VGV (Valor Geral de Venda)", format_currency(results.get('vgv', 0)))
            st.metric("Custo Total da Obra", format_currency(results.get('total_construction_cost', 0)))
            st.metric("Resultado Operacional do Projeto", format_currency(results.get('final_operational_result', 0)))
            st.divider()
            st.markdown("##### Rentabilidade do Investimento")
            
            roi_anualizado = results.get('roi_anualizado', 0)
            gauge_max_range_anual = max(30, (np.ceil(roi_anualizado / 10) * 10) * 1.5) if roi_anualizado > 0 else 30
            fig_gauge_anual = go.Figure(go.Indicator(
                mode="gauge+number", value=roi_anualizado,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "ROI Anualizado", 'font': {'size': 20}},
                number={'suffix': "%", 'font': {'size': 24}},
                gauge={'axis': {'range': [0, gauge_max_range_anual]}, 'bar': {'color': THEME_PRIMARY_COLOR}}
            ))
            fig_gauge_anual.update_layout(height=180, margin=dict(l=20, r=20, t=50, b=10))
            st.plotly_chart(fig_gauge_anual, use_container_width=True, key=f"gauge_anual_{unique_id}")

            roi_periodo = results.get('roi', 0)
            duracao_meses = results.get('num_months', 0) 
            gauge_max_range_periodo = max(30, (np.ceil(roi_periodo / 10) * 10) * 1.5) if roi_periodo > 0 else 30
            fig_gauge_periodo = go.Figure(go.Indicator(
                mode="gauge+number", value=roi_periodo,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"ROI no Período ({duracao_meses} meses aprox.)", 'font': {'size': 20}},
                number={'suffix': "%", 'font': {'size': 24}},
                gauge={'axis': {'range': [0, gauge_max_range_periodo]}, 'bar': {'color': '#E37026'}} 
            ))
            fig_gauge_periodo.update_layout(height=180, margin=dict(l=20, r=20, t=50, b=10))
            st.plotly_chart(fig_gauge_periodo, use_container_width=True, key=f"gauge_periodo_{unique_id}")


    with tab_sensibilidade:
        st.subheader("🔬 Matriz de Cenários")
        st.markdown("Análise do impacto no **ROI Anualizado do Investidor** com base nas principais variáveis do projeto.")
        scenarios = {}
        base_params = results.copy()
        scenarios['Realista'] = calculate_financials(base_params)
        
        pessimistic_params = base_params.copy()
        pessimistic_params['value_m2'] *= 0.85
        pessimistic_params['construction_cost_m2'] *= 1.15
        scenarios['Pessimista'] = calculate_financials(pessimistic_params)
        
        optimistic_params = base_params.copy()
        optimistic_params['value_m2'] *= 1.15
        optimistic_params['construction_cost_m2'] *= 0.85
        scenarios['Otimista'] = calculate_financials(optimistic_params)

        c1, c2, c3 = st.columns(3)
        with c1:
            with st.container(border=True):
                st.markdown("<h5 style='text-align: center; color: #D32F2F;'>🔴 Pessimista</h5>", unsafe_allow_html=True)
                st.metric("ROI Anualizado", f"{scenarios['Pessimista']['roi_anualizado']:.2f}%")
                st.metric("Lucro do Investidor", format_currency(scenarios['Pessimista']['resultado_final_investidor']))
                st.caption(f"Venda m²: {format_currency(pessimistic_params['value_m2'])} | Custo m²: {format_currency(pessimistic_params['construction_cost_m2'])}")
        with c2:
            with st.container(border=True):
                st.markdown("<h5 style='text-align: center; color: #1976D2;'>🔵 Realista (Base)</h5>", unsafe_allow_html=True)
                st.metric("ROI Anualizado", f"{scenarios['Realista']['roi_anualizado']:.2f}%")
                st.metric("Lucro do Investidor", format_currency(scenarios['Realista']['resultado_final_investidor']))
                st.caption(f"Venda m²: {format_currency(base_params['value_m2'])} | Custo m²: {format_currency(base_params['construction_cost_m2'])}")
        with c3:
            with st.container(border=True):
                st.markdown("<h5 style='text-align: center; color: #388E3C;'>🟢 Otimista</h5>", unsafe_allow_html=True)
                st.metric("ROI Anualizado", f"{scenarios['Otimista']['roi_anualizado']:.2f}%")
                st.metric("Lucro do Investidor", format_currency(scenarios['Otimista']['resultado_final_investidor']))
                st.caption(f"Venda m²: {format_currency(optimistic_params['value_m2'])} | Custo m²: {format_currency(optimistic_params['construction_cost_m2'])}")
        
        st.divider()

        with st.expander("**Análise Interativa (What-If)**", expanded=False):
            st.markdown("Ajuste as variáveis abaixo para simular seu próprio cenário.")
            
            original_value_m2 = results.get('value_m2', 0)
            original_cost_m2 = results.get('construction_cost_m2', 0)

            c1, c2 = st.columns(2)
            with c1:
                new_value_m2 = st.slider(
                    "Novo Valor de Venda do m²", 
                    min_value=float(original_value_m2 * 0.7), max_value=float(original_value_m2 * 1.3), 
                    value=float(original_value_m2), step=50.0, key=f"slider_val_{unique_id}"
                )
            with c2:
                new_cost_m2 = st.slider(
                    "Novo Custo da Obra por m²", 
                    min_value=float(original_cost_m2 * 0.7), max_value=float(original_cost_m2 * 1.3), 
                    value=float(original_cost_m2), step=50.0, key=f"slider_cost_{unique_id}"
                )
            
            if new_value_m2 > 0:
                temp_params = results.copy()
                temp_params['value_m2'] = new_value_m2
                temp_params['construction_cost_m2'] = new_cost_m2
                sensitive_results = calculate_financials(temp_params)
                
                st.subheader("Resultados para sua Simulação Personalizada:")
                scol1, scol2, scol3 = st.columns(3)
                
                delta_lucro = sensitive_results.get('resultado_final_investidor', 0) - results.get('resultado_final_investidor', 0)
                scol1.metric("Novo Resultado (Lucro)", format_currency(sensitive_results.get('resultado_final_investidor', 0)), delta=format_currency(delta_lucro))
                
                delta_roi_anualizado = sensitive_results.get('roi_anualizado', 0) - results.get('roi_anualizado', 0)
                scol2.metric("Novo ROI Anualizado", f"{sensitive_results.get('roi_anualizado', 0):.2f}%", delta=f"{delta_roi_anualizado:.2f}%")

                delta_roi = sensitive_results.get('roi', 0) - results.get('roi', 0)
                scol3.metric("Novo ROI (Período)", f"{sensitive_results.get('roi', 0):.2f}%", delta=f"{delta_roi:.2f}%")

        st.divider()
        st.subheader("Mapa de Calor: Análise de Sensibilidade do ROI")
        
        original_value_m2 = results.get('value_m2', 6000)
        original_cost_m2 = results.get('construction_cost_m2', 2500)

        m2_venda_range = np.linspace(original_value_m2 * 0.8, original_value_m2 * 1.2, 5)
        m2_custo_range = np.linspace(original_cost_m2 * 0.8, original_cost_m2 * 1.2, 5)

        heatmap_data = []
        temp_params = results.copy()
        
        for custo in m2_custo_range:
            row = []
            for venda in m2_venda_range:
                temp_params['value_m2'] = venda
                temp_params['construction_cost_m2'] = custo
                res = calculate_financials(temp_params)
                row.append(res['roi_anualizado'])
            heatmap_data.append(row)

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=[f"{v/1000:.1f}k" for v in m2_venda_range],
            y=[f"{c/1000:.1f}k" for c in m2_custo_range],
            hoverongaps=False,
            colorscale='RdYlGn',
            zmin=np.min(heatmap_data),
            zmax=np.max(heatmap_data),
            text=[[f"{val:.2f}%" for val in row] for row in heatmap_data],
            texttemplate="%{text}",
            textfont={"size":10}
        ))
        fig_heatmap.update_layout(
            title="Mapa de Calor: ROI Anualizado (Venda vs. Custo)",
            xaxis_title="Valor de Venda m² (Simulado)",
            yaxis_title="Custo da Obra m² (Simulado)",
            margin=dict(l=40, r=40, t=40, b=40)
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)
              
    buttons_to_show = []
    if show_download_button: buttons_to_show.append("download")
    if show_save_button: buttons_to_show.append("save")

    if buttons_to_show:
        st.divider()
        st.subheader("Ações")
        
        cols = st.columns(len(buttons_to_show) or 1)
        col_index = 0
        
        if "download" in buttons_to_show:
            with cols[col_index]:
                pdf_data = results.copy()
                pdf_data['aportes'] = results.get('aportes', []) 
                pdf_bytes = utils.generate_pdf(pdf_data)
                
                client_name_safe = "".join(c for c in results.get('client_name', 'simulacao') if c.isalnum() or c in (' ', '_')).rstrip()
                client_name_safe = client_name_safe.replace(' ', '_').lower()
                timestamp = datetime.now().strftime('%Y%m%d')
                file_name = f"relatorio_{client_name_safe}_{timestamp}.pdf"

                st.download_button(
                    label="📄 Baixar Relatório em PDF",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"pdf_dl_{unique_id}"
                )
            col_index += 1

        if "save" in buttons_to_show:
            with cols[col_index]:
                if st.button(
                    "💾 Salvar Simulação na Planilha", 
                    use_container_width=True, 
                    type="primary", 
                    key=f"save_btn_{unique_id}" 
                ):
                    if save_callback:
                        save_callback()
            col_index += 1

