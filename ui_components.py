import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import utils
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
import plotly.figure_factory as ff
import plotly.express as px
from utils import format_currency, calculate_financials

THEME_PRIMARY_COLOR = "#E37026"

def display_full_results(results, show_save_button=False, show_download_button=False, save_callback=None, is_simulation_saved=False):
    unique_id = results.get('simulation_id', str(datetime.now().timestamp()))


    tab_vencimentos, tab_resumo, tab_sensibilidade = st.tabs(["**Cronograma de Vencimentos**", "**Resumo Financeiro**", "**Análise de Cenários**"])

    with tab_vencimentos:
        st.subheader("Cronograma de Vencimentos Detalhado")
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
            df_aportes_display = pd.DataFrame([{'Vencimento': a['date'], 'Valor': a['value']} for a in aportes_list])
            df_aportes_display['Vencimento'] = pd.to_datetime(df_aportes_display['Vencimento']).dt.strftime('%d/%m/%Y')
            df_aportes_display['Valor'] = df_aportes_display['Valor'].apply(utils.format_currency)
            st.dataframe(df_aportes_display, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum aporte foi encontrado para esta simulação.")

    with tab_resumo:
        st.subheader("Resumo Financeiro")
        col2, col1= st.columns([1.25, 1])
        with col1:
            st.markdown("##### Demonstrativo de Retorno do Investidor")
            st.metric("Resultado Operacional do Projeto (VGV - Custo Total)", f"={format_currency(results.get('final_operational_result', 0))}")
            col8, col9 = st.columns([3, 1])
            with col8:
                spe_percentage_label = f"2. Participação da SPE no Projeto"
                c_spe, c_mon = st.columns(2)
                c_spe.metric(spe_percentage_label, format_currency(results.get('valor_participacao', 0)), delta=f"{results.get('spe_percentage', 0):.2f}%")
                c_mon.metric("1. Montante Corrigido (Aporte + Juros)", f"+ {format_currency(results.get('valor_corrigido', 0))}")
            total_bruto = results.get('valor_corrigido', 0) + results.get('valor_participacao', 0)
            st.metric("Total Bruto Recebido", f"= {format_currency(total_bruto)}")
            st.metric("Aporte Inicial", f"- {format_currency(results.get('total_contribution', 0))}")
        
        with col2:
            st.markdown("##### Resumo do Projeto Imobiliário")
            st.metric("VGV (Valor Geral de Venda)", format_currency(results.get('vgv', 0)))
            col5, col6 = st.columns([3, 1])
            with col5:
                with st.container(height=300):
                    st.metric("Custo Físico da Obra", format_currency(results.get('cost_obra_fisica', 0)))
                    c_troca, c_juros = st.columns([2, 1])
                    c_juros.metric("Custo do Capital (Juros)", f"+ {format_currency(results.get('juros_investidor', 0))}")
                    c_troca.metric("Custo Troca de Área", f"+ {format_currency(results.get('area_exchange_value', 0))}")
                    st.metric("Custo Total da Obra", f"= -{format_currency(results.get('total_construction_cost', 0))}")
                    
        colu1, colu2 = st.columns([1, 1])
        with colu1:
            st.markdown("")
            st.markdown("##### Retorno sobre o Investimento")
            
            roi_anualizado = results.get('roi_anualizado', 0)
            gauge_max_range_anual = max(30, roi_anualizado * 1.5)
            fig_gauge_anual = go.Figure(go.Indicator(
                mode="gauge+number", value=roi_anualizado,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "ROI Anualizado", 'font': {'size': 20}},
                number={'suffix': "%", 'font': {'size': 30, 'color': '#E37026'}},
                gauge={'axis': {'range': [0, gauge_max_range_anual]}, 'bar': {'color': THEME_PRIMARY_COLOR}}
            ))
            fig_gauge_anual.update_layout(height=225, paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=50, r=50, t=50, b=10))
            st.plotly_chart(fig_gauge_anual, use_container_width=True, key=f"gauge_anual_{unique_id}")

            roi_periodo = results.get('roi', 0)
            duracao_meses = results.get('num_months', 0)
            gauge_max_range_periodo = max(30, roi_periodo * 1.5)
            fig_gauge_periodo = go.Figure(go.Indicator(
                mode="gauge+number", value=roi_periodo,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"ROI no Período ({duracao_meses} meses aprox.)", 'font': {'size': 20}},
                number={'suffix': "%", 'font': {'size': 30, 'color': '#E37026'}},
                gauge={'axis': {'range': [0, gauge_max_range_periodo]}, 'bar': {'color': '#E37026'}} 
            ))
            fig_gauge_periodo.update_layout(paper_bgcolor='rgba(0,0,0,0)', height=225, margin=dict(l=50, r=50, t=50, b=10))
            st.plotly_chart(fig_gauge_periodo, use_container_width=True, key=f"gauge_periodo_{unique_id}")

        with colu2: 
            
            co1, co2, co3 = st.columns([1, 3, 1])
            with co2:
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                st.markdown("")
                resultado_final_str = format_currency(results.get('resultado_final_investidor', 0))
                st.markdown(f"""
                <div style="
                    background-color: rgba(0,0,0,0);
                    border-radius: 5px; 
                    padding: 20px; 
                    border: 1px solid {THEME_PRIMARY_COLOR};
                ">
                    <p style="
                        font-size: 27px; 
                        color: #FFFFFF; 
                        margin: 0; 
                        font-weight: bold;
                    ">
                        Resultado Final (Lucro Líquido)
                    </p>
                    <p style="
                        font-size: 2.3rem; 
                        color: {THEME_PRIMARY_COLOR}; 
                        font-weight: 600; 
                        margin: 0;
                        line-height: 1;
                    ">
                        ={resultado_final_str}
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
        st.divider()
                

        st.markdown("##### Fluxo de Caixa do Investidor")
        
        try:
            aportes_df = pd.DataFrame(results.get('aportes', []))
            if not aportes_df.empty:
                aportes_df.rename(columns={'date': 'Data', 'value': 'Valor'}, inplace=True)
                aportes_df['Valor'] = -aportes_df['Valor']
                aportes_df['Tipo'] = 'Aporte'
                
                retorno_capital = results.get('valor_corrigido', 0)
                lucro_spe = results.get('valor_participacao', 0)
                data_final = pd.to_datetime(results.get('project_end_date'))

                df_retornos = pd.DataFrame([
                    {'Data': data_final, 'Valor': retorno_capital, 'Tipo': 'Retorno (Capital + Juros)'},
                    {'Data': data_final, 'Valor': lucro_spe, 'Tipo': 'Lucro (Participação SPE)'}
                ])
                
                df_fluxo = pd.concat([aportes_df, df_retornos], ignore_index=True)
                df_fluxo['Data'] = pd.to_datetime(df_fluxo['Data'])
                df_fluxo_agregado = df_fluxo.groupby(['Data', 'Tipo'])['Valor'].sum().reset_index()

                fig_fluxo = px.bar(
                    df_fluxo_agregado, 
                    x='Data', 
                    y='Valor', 
                    color='Tipo',
                    title="Fluxo de Caixa (Aportes vs. Retornos)",
                    labels={'Valor': 'Valor (R$)', 'Data': 'Data'},
                    color_discrete_map={
                        'Aporte': '#D32F2F',
                        'Retorno (Capital + Juros)': '#1976D2',
                        'Lucro (Participação SPE)': '#388E3C'
                    }
                )
                fig_fluxo.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', barmode='relative')
                st.plotly_chart(fig_fluxo, use_container_width=True)
            else:
                st.warning("Não há aportes para exibir o fluxo de caixa.")
        except Exception as e:
            st.error(f"Erro ao gerar gráfico de fluxo de caixa: {e}")


    with tab_sensibilidade:
        st.subheader("Matriz de Cenários")
        st.markdown("Análise do impacto no **ROI Anualizado do Investidor** com base nas principais variáveis do projeto.")
        scenarios = {}
        base_params = results.copy()
        
        try:
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
        
        except Exception as e:
            st.error(f"Erro ao calcular cenários: {e}")

        st.divider()
        st.subheader("Simulação Interativa (What-If)")
        
        c1, c2 = st.columns(2)
        with c1:
            variacao_vgv = st.slider("Variação do Valor de Venda (VGV %)", -25.0, 25.0, 0.0, 0.5)
            variacao_custo = st.slider("Variação do Custo da Obra (%)", -25.0, 25.0, 0.0, 0.5)
        
        with c2:
            sim_params = results.copy()
            sim_params['value_m2'] *= (1 + variacao_vgv / 100)
            sim_params['construction_cost_m2'] *= (1 + variacao_custo / 100)
            
            try:
                cenario_simulado = calculate_financials(sim_params)
                st.metric("Novo ROI Anualizado (Simulado)", f"{cenario_simulado.get('roi_anualizado', 0):.2f}%")
                st.metric("Novo Lucro do Investidor (Simulado)", format_currency(cenario_simulado.get('resultado_final_investidor', 0)))
                st.caption(f"Venda m²: {format_currency(sim_params['value_m2'])} | Custo m²: {format_currency(sim_params['construction_cost_m2'])}")
            except Exception as e:
                st.error(f"Erro ao simular cenário: {e}")


        st.divider()

        with st.expander("**Mapa de Calor de Sensibilidade (ROI Anualizado)**", expanded=True):
            st.markdown("Veja como o ROI Anualizado (%) reage a mudanças no Custo da Obra e no Valor de Venda (VGV).")
            
            try:
                base_cost_m2 = results.get('construction_cost_m2', 0)
                base_value_m2 = results.get('value_m2', 0)

                cost_range = np.linspace(base_cost_m2 * 0.8, base_cost_m2 * 1.2, 5)
                value_range = np.linspace(base_value_m2 * 0.8, base_value_m2 * 1.2, 5)
                
                heatmap_data = []
                for cost in cost_range:
                    row_data = []
                    for value in value_range:
                        temp_params = results.copy()
                        temp_params['construction_cost_m2'] = cost
                        temp_params['value_m2'] = value
                        res = calculate_financials(temp_params)
                        row_data.append(res['roi_anualizado'])
                    heatmap_data.append(row_data)

                x_labels = [format_currency(v) for v in value_range]
                y_labels = [format_currency(c) for c in cost_range]
                
                fig_heatmap = ff.create_annotated_heatmap(
                    z=heatmap_data,
                    x=x_labels,
                    y=y_labels,
                    annotation_text=[[f'{z:.1f}%' for z in row] for row in heatmap_data],
                    colorscale='Viridis',
                    showscale=True
                )
                fig_heatmap.update_layout(
                    title="Sensibilidade: VGV m² (Eixo X) vs. Custo m² (Eixo Y)",
                    xaxis_title="Valor de Venda do m²",
                    yaxis_title="Custo da Obra por m²"
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao gerar mapa de calor: {e}")
              
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
                    key=f"pdf_dl_{unique_id}",
                    disabled=not is_simulation_saved 
                )
                
                if not is_simulation_saved:
                    st.caption("ℹ️ Você deve salvar a simulação na planilha antes de baixar o PDF.")
                
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
