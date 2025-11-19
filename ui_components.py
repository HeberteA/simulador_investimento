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
import scipy

THEME_PRIMARY_COLOR = "#E37026"

def display_full_results(results, show_save_button=False, show_download_button=False, save_callback=None, is_simulation_saved=False):
    if 'simulation_id' not in results:
        results['simulation_id'] = f"gen_{int(datetime.now().timestamp())}"
    
    unique_id = results['simulation_id']

    client_name_raw = results.get('client_name', '')
    client_display = client_name_raw if client_name_raw and str(client_name_raw).strip() else "Cliente Não Identificado"

    tab_vencimentos, tab_resumo, tab_sensibilidade = st.tabs(["Cronograma de Vencimentos", "Resumo Financeiro", "Análise de Cenários"])

    with tab_vencimentos:
        st.subheader("Detalhes do Investidor e Cronograma")
        
        st.markdown(f"""
        <div style="display: flex; gap: 20px; margin-bottom: 20px;">
            <div style="flex: 2; background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; border-left: 4px solid #E37026;">
                <p style="font-size: 12px; margin: 0; color: #aaa; text-transform: uppercase;">Nome do Cliente</p>
                <p style="font-size: 20px; margin: 5px 0 0 0; font-weight: bold; color: #FFF;">{client_display}</p>
            </div>
            <div style="flex: 1; background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                <p style="font-size: 12px; margin: 0; color: #aaa;">Total Aportado</p>
                <p style="font-size: 18px; margin: 5px 0 0 0; font-weight: 600; color: #FFF;">{utils.format_currency(results.get('total_contribution', 0))}</p>
            </div>
            <div style="flex: 1; background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                <p style="font-size: 12px; margin: 0; color: #aaa;">Montante Final</p>
                <p style="font-size: 18px; margin: 5px 0 0 0; font-weight: 600; color: #E37026;">{utils.format_currency(results.get('valor_corrigido', 0))}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()

        aportes_list = results.get('aportes', [])
        
        if aportes_list:
            try:
                df_aportes_display = pd.DataFrame([{'Vencimento': a['date'], 'Valor': a['value']} for a in aportes_list])
                df_aportes_display['Vencimento'] = pd.to_datetime(df_aportes_display['Vencimento']).dt.strftime('%d/%m/%Y')
                df_aportes_display['Valor'] = df_aportes_display['Valor'].apply(utils.format_currency)
                st.dataframe(df_aportes_display, use_container_width=True, hide_index=True)
            except Exception:
                st.warning("Erro ao exibir tabela de aportes.")
        else:
            st.info("Nenhum aporte registrado.")

    with tab_resumo:
        lucro_liquido = results.get('resultado_final_investidor', 0)
        roi_anual = results.get('roi_anualizado', 0)
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(227, 112, 38, 0.15) 0%, rgba(0,0,0,0.2) 100%);
            border: 1px solid #E37026;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            backdrop-filter: blur(5px);
        ">
            <h3 style="margin:0; font-size: 0.9rem; color: #ddd; text-transform: uppercase; letter-spacing: 2px;">Resultado Final (Lucro Líquido)</h3>
            <h1 style="margin: 15px 0; font-size: 3.5rem; color: #E37026; font-weight: 800; text-shadow: 0 2px 10px rgba(227, 112, 38, 0.3);">
                {format_currency(lucro_liquido)}
            </h1>
            <div style="display: inline-block; background-color: #E37026; color: white; padding: 8px 20px; border-radius: 25px; font-size: 1rem; font-weight: bold; box-shadow: 0 4px 15px rgba(227, 112, 38, 0.4);">
                ROI Anualizado: {roi_anual:.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_details_1, col_details_2 = st.columns(2)
        
        with col_details_1:
            st.markdown("#### Composição do Retorno")
            with st.container():
                st.markdown(f"""
                <div style="background-color: rgba(255,255,255,0.03); padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span>Resultado Operacional (VGV - Custos)</span>
                        <span style="color:#fff;">{format_currency(results.get('final_operational_result', 0))}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="color:#fff;">Part. SPE ({results.get('spe_percentage', 0):.2f}%)</span>
                        <span style="color:#E37026;">{format_currency(results.get('valor_participacao', 0))}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#fff;">Montante Corrigido</span>
                        <span style="color:#E37026;">+{format_currency(results.get('valor_corrigido', 0))}</span>
                    </div>
                    <hr style="border-color: rgba(255,255,255,0.1);">
                    <div style="display:flex; justify-content:space-between; font-size:1.1rem;">
                        <span style="color:#fff; font-weight:600;">Total Bruto</span>
                        <span style="color:#fff; font-weight:600;">{format_currency(results.get('valor_corrigido', 0) + results.get('valor_participacao', 0))}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with col_details_2:
            st.markdown("#### Dados do Projeto")
            with st.container():
                st.markdown(f"""
                <div style="background-color: rgba(255,255,255,0.03); padding: 15px; border-radius: 8px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="color:#aaa;">VGV Total</span>
                        <span style="color:#fff;">{format_currency(results.get('vgv', 0))}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:#aaa;">Custo Obra Física</span>
                        <span style="color:#fff;">{format_currency(results.get('cost_obra_fisica', 0))}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px; font-size: 0.85rem;">
                        <span style="color:#aaa;">Custo Troca de Área</span>
                        <span style="color:#fff;">+{format_currency(results.get('area_exchange_value', 0))}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size: 0.85rem;">
                        <span style="color:#aaa;">Custo Capital (Juros)</span>
                        <span style="color:#fff;">+{format_currency(results.get('juros_investidor', 0))}</span>
                    </div>
                    <hr style="border-color: rgba(255,255,255,0.1);">
                     <div style="display:flex; justify-content:space-between; font-size:1.1rem;">
                        <span style="color:#E37026; font-weight:600;">Custo Total</span>
                        <span style="color:#E37026; font-weight:600;">= -{format_currency(results.get('total_construction_cost', 0))}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Indicadores Visuais")
        
        g1, g2 = st.columns(2)
        with g1:
            st.space("medium")
            roi_periodo = results.get('roi', 0)
            duracao = results.get('num_months', 0)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=roi_periodo,
                title={'text': f"ROI Período ({duracao} meses)", 'font': {'size': 18, 'color': '#aaa'}},
                number={'suffix': "%", 'font': {'size': 40, 'color': '#E37026'}},
                gauge={'axis': {'range': [0, max(50, roi_periodo*1.5)]}, 'bar': {'color': '#E37026'}, 'bgcolor': "rgba(255,255,255,0.1)"}
            ))
            fig_gauge.update_layout(height=300, margin=dict(t=50,b=50,l=30,r=30), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
            st.plotly_chart(fig_gauge, use_container_width=True)
            
        with g2:
            aportes_df = pd.DataFrame(results.get('aportes', []))
            if not aportes_df.empty:
                aportes_df.rename(columns={'date': 'Data', 'value': 'Valor'}, inplace=True)
                aportes_df['Tipo'] = 'Aporte'
                aportes_df['Valor'] = -aportes_df['Valor']
                
                data_final = pd.to_datetime(results.get('project_end_date'))
                retorno_total = results.get('valor_corrigido', 0) + results.get('valor_participacao', 0)
                
                df_retorno = pd.DataFrame([{'Data': data_final, 'Valor': retorno_total, 'Tipo': 'Retorno Total'}])
                df_fluxo = pd.concat([aportes_df, df_retorno], ignore_index=True)
                
                fig_fluxo = px.bar(df_fluxo, x='Data', y='Valor', color='Tipo', 
                                   title="Fluxo de Caixa",
                                   color_discrete_map={'Aporte': '#D32F2F', 'Retorno Total': '#388E3C'})
                fig_fluxo.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font={'color': "white"}, showlegend=True)
                st.plotly_chart(fig_fluxo, use_container_width=True)

    with tab_sensibilidade:
        st.subheader("Matriz de Cenários")
        base_params = results.copy()
        scenarios = {}
        
        try:
            scenarios['Realista'] = calculate_financials(base_params)
            
            pessimistic = base_params.copy()
            pessimistic['value_m2'] *= 0.85
            pessimistic['construction_cost_m2'] *= 1.15
            scenarios['Pessimista'] = calculate_financials(pessimistic)
            
            optimistic = base_params.copy()
            optimistic['value_m2'] *= 1.15
            optimistic['construction_cost_m2'] *= 0.85
            scenarios['Otimista'] = calculate_financials(optimistic)

            c_pess, c_real, c_opt = st.columns(3)
            
            def render_scenario_card(title, color, data):
                st.markdown(f"""
                <div style="border: 1px solid {color}; border-radius: 10px; padding: 15px; text-align: center; background: rgba(255,255,255,0.02);">
                    <h4 style="color: {color}; margin: 0;">{title}</h4>
                    <p style="font-size: 24px; font-weight: bold; margin: 10px 0; color: #fff;">{data['roi_anualizado']:.2f}% <span style="font-size:12px; color:#888;">a.a.</span></p>
                    <p style="font-size: 14px; margin: 0; color: #aaa;">Lucro: {format_currency(data['resultado_final_investidor'])}</p>
                </div>
                """, unsafe_allow_html=True)

            with c_pess: render_scenario_card("Pessimista", "#D32F2F", scenarios['Pessimista'])
            with c_real: render_scenario_card("Realista", "#1976D2", scenarios['Realista'])
            with c_opt: render_scenario_card("Otimista", "#388E3C", scenarios['Otimista'])
        
        except Exception:
            st.error("Erro ao calcular cenários.")

        st.divider()
        st.subheader("Simulação Interativa (What-If)")
        
        col_sliders, col_res_sim = st.columns(2)
        with col_sliders:
            variacao_vgv = st.slider("Variação do Valor de Venda (%)", -25.0, 25.0, 0.0, 0.5)
            variacao_custo = st.slider("Variação do Custo da Obra (%)", -25.0, 25.0, 0.0, 0.5)
        
        with col_res_sim:
            sim_params = results.copy()
            sim_params['value_m2'] = sim_params['value_m2'] * (1 + variacao_vgv/100)
            sim_params['construction_cost_m2'] = sim_params['construction_cost_m2'] * (1 + variacao_custo/100)
            
            try:
                cenario_simulado = calculate_financials(sim_params)
                roi_sim = cenario_simulado.get('roi_anualizado', 0)
                lucro_sim = cenario_simulado.get('resultado_final_investidor', 0)
                
                delta_roi = roi_sim - results.get('roi_anualizado', 0)
                color_delta = "#388E3C" if delta_roi >= 0 else "#D32F2F"
                
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; text-align: center;">
                    <p style="color: #aaa; margin:0;">ROI Simulado</p>
                    <p style="font-size: 28px; font-weight: bold; color: {color_delta}; margin:0;">{roi_sim:.2f}%</p>
                    <p style="font-size: 14px; margin:0; color: #fff;">Lucro: {format_currency(lucro_sim)}</p>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Erro: {e}")

        st.write("")
        with st.expander("Mapa de Calor de Sensibilidade", expanded=True):
            try:
                base_cost = results.get('construction_cost_m2', 0)
                base_val = results.get('value_m2', 0)
                
                costs = np.linspace(base_cost * 0.8, base_cost * 1.2, 5)
                values = np.linspace(base_val * 0.8, base_val * 1.2, 5)
                
                z_data = []
                for c in costs:
                    row_z = []
                    for v in values:
                        p = results.copy()
                        p['construction_cost_m2'] = c
                        p['value_m2'] = v
                        r = calculate_financials(p)
                        row_z.append(r['roi_anualizado'])
                    z_data.append(row_z)
                
                fig_heat = px.imshow(
                    z_data,
                    x=[format_currency(v) for v in values],
                    y=[format_currency(c) for c in costs],
                    text_auto='.1f',
                    aspect="auto",
                    labels=dict(x="Valor de Venda (R$/m²)", y="Custo de Obra (R$/m²)", color="ROI %"),
                    color_continuous_scale='Magma'
                )
                
                fig_heat.update_layout(
                    title={'text': "ROI Anualizado (%)", 'font': {'color': 'white'}},
                    xaxis={'title': 'Valor de Venda (R$/m²)', 'tickfont': {'color': 'white'}},
                    yaxis={'title': 'Custo de Obra (R$/m²)', 'tickfont': {'color': 'white'}},
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    font={'color': 'white'}
                )
                st.plotly_chart(fig_heat, use_container_width=True)

            except Exception as e:
                 st.error(f"Não foi possível gerar o mapa de calor: {e}")
                
    buttons_to_show = []
    if show_download_button: buttons_to_show.append("download")
    if show_save_button: buttons_to_show.append("save")

    if buttons_to_show:
        st.divider()
        cols = st.columns(len(buttons_to_show) or 1)
        col_index = 0
        
        if "download" in buttons_to_show:
            with cols[col_index]:
                can_download = is_simulation_saved or results.get('simulation_id', '').startswith('sim_')
                
                pdf_data = results.copy()
                pdf_data['aportes'] = results.get('aportes', []) 
                pdf_bytes = utils.generate_pdf(pdf_data)
                
                client_name_safe = "".join(c for c in results.get('client_name', 'simulacao') if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_').lower()
                file_name = f"relatorio_{client_name_safe}_{datetime.now().strftime('%Y%m%d')}.pdf"

                st.download_button(
                    label="Baixar Relatório PDF",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"pdf_dl_{unique_id}",
                    disabled=not can_download 
                )
                if not can_download: st.caption("⚠️ Salve a simulação antes de baixar.")
            col_index += 1

        if "save" in buttons_to_show:
            with cols[col_index]:
                if is_simulation_saved:
                    st.button("✅ Simulação Salva", use_container_width=True, disabled=True, key=f"saved_btn_{unique_id}")
                else:
                    if st.button("Salvar Simulação", use_container_width=True, type="primary", key=f"save_btn_{unique_id}"):
                        if save_callback: 
                            save_callback()
                            st.rerun()
