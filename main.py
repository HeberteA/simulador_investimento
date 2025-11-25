import streamlit as st
import pandas as pd
from datetime import datetime, date
from streamlit_option_menu import option_menu
from dateutil.relativedelta import relativedelta 
import utils
from ui_components import display_full_results
import plotly.express as px
import numpy as np
import os

def safe_load_icon(image_name, fallback_emoji="🏗️"):
    if os.path.exists(image_name): return image_name
    return fallback_emoji

def ensure_date(val):
    """Garante conversão segura para data."""
    if isinstance(val, date): return val
    if isinstance(val, datetime): return val.date()
    try: return pd.to_datetime(val).date()
    except: return datetime.today().date()

app_icon = safe_load_icon("Lavie1.png")
st.set_page_config(page_title="Simulador Financeiro", page_icon=app_icon, layout="wide")

APP_STYLE_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 10% 20%, #3b3b3b 0%, #000000 100%);
    font-family: 'Inter', sans-serif;
    color: #ffffff;
}
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: white !important;
}
div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input {
    color: white !important;
}
.step-container {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px;
    background: rgba(255,255,255,0.03); padding: 20px; border-radius: 50px; border: 1px solid rgba(255,255,255,0.05);
}
.step-item {
    display: flex; align-items: center; flex-direction: column; color: #666; font-weight: 500; width: 33%; position: relative;
}
.step-item .step-number {
    width: 35px; height: 35px; border-radius: 50%; border: 2px solid #555; display: flex; align-items: center; justify-content: center;
    font-weight: bold; margin-bottom: 8px; transition: all 0.3s ease; background-color: #111;
}
.step-item.active { color: #E37026; }
.step-item.active .step-number { border-color: #E37026; background-color: #E37026; color: #FFFFFF; box-shadow: 0 0 15px rgba(227, 112, 38, 0.5); }
</style>
"""
st.markdown(APP_STYLE_CSS, unsafe_allow_html=True)

initial_state = {
    'page': "Nova Simulação", 
    'results_ready': False, 
    'simulation_results': {},
    'show_results_page': False,
    'current_step': 1,
    'client_name': '', 
    'client_code': '',
    'annual_interest_rate': 0.0, 
    'spe_percentage': 0.0,
    'total_contribution': 0.0, 
    'num_months': 0, 
    'start_date': datetime.today().date(),
    'project_end_date': datetime.today().date(), 
    'land_size': 0,              
    'construction_cost_m2': 0.0, 
    'value_m2': 0.0,             
    'area_exchange_percentage': 0.0, 
    'aportes': [], 
    'simulation_saved': False,
    'new_aporte_date': datetime.today().date(),
    'new_aporte_value': 0.0,
    'parcelado_total_valor': 0.0,
    'parcelado_num_parcelas': 1,
    'parcelado_data_inicio': datetime.today().date()
}

for key, default_value in initial_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

worksheets = utils.init_gsheet_connection()

def manual_reset():
    """Reseta os valores para o estado inicial."""
    for k, v in initial_state.items():
        if k not in ['page']: 
            st.session_state[k] = v

def render_login_page():
    c1, c2, c3 = st.columns([1, 2, 1]) 
    with c2:
        try: st.image("Lavie.png", use_column_width=True) 
        except: pass
        st.markdown("<h2 style='text-align: center;'>Simulador Financeiro</h2>", unsafe_allow_html=True)
        st.markdown("---")
        
        try: user_list = list(st.secrets["credentials"].keys())
        except: st.error("Credenciais não configuradas."); st.stop()
        
        selected_user = st.selectbox("Usuário", options=user_list, index=None)
        access_code = st.text_input("Senha", type="password")
        
        if st.button("Entrar", use_container_width=True, type="primary"):
            if selected_user and access_code == st.secrets["credentials"].get(selected_user):
                st.session_state.authenticated = True
                st.session_state.user_name = selected_user
                st.rerun()
            else: st.error("Senha incorreta.")

def render_new_simulation_page():
    def go_to_results(): st.session_state.show_results_page = True
    def go_to_inputs(): st.session_state.show_results_page = False

    if st.session_state.show_results_page:
        st.title("Resultado da Simulação")
        if st.button("Voltar para osParâmetros"):
            go_to_inputs()
            st.rerun()

        if st.session_state.get('results_ready', False):
            display_full_results(
                st.session_state.simulation_results,
                show_save_button=True, 
                show_download_button=True,
                save_callback=save_simulation_callback,
                is_simulation_saved=st.session_state.get('simulation_saved', False)
            )
        return

    col_form, col_visual = st.columns([2, 1], gap="large")

    with col_form:
        step = st.session_state.current_step
        st.markdown(f"""
        <div class="step-container">
            <div class="step-item {'active' if step >= 1 else ''}"><div class="step-number">1</div><div class="step-label">Empreendimento</div></div>
            <div class="step-item {'active' if step >= 2 else ''}"><div class="step-number">2</div><div class="step-label">Investidor</div></div>
            <div class="step-item {'active' if step >= 3 else ''}"><div class="step-number">3</div><div class="step-label">Financeiro</div></div>
        </div>
        """, unsafe_allow_html=True)

        if step == 1:
            st.subheader("Parâmetros do Projeto")
            c1, c2 = st.columns(2)
            with c1:
                st.number_input("Área Vendável (m²)", key="land_size", value=int(st.session_state.land_size), min_value=0, step=10)
                st.number_input("Custo da Obra (R$/m²)", key="construction_cost_m2", value=float(st.session_state.construction_cost_m2), min_value=0.0, step=100.0, format="%.2f")
            with c2:
                st.number_input("Valor de Venda (R$/m²)", key="value_m2", value=float(st.session_state.value_m2), min_value=0.0, step=100.0, format="%.2f")
                st.number_input("Permuta Física/Financeira (%)", key="area_exchange_percentage", value=float(st.session_state.area_exchange_percentage), min_value=0.0, max_value=100.0, step=0.5, format="%.2f")

        elif step == 2:
            st.subheader("Dados do Investidor")
            st.text_input("Nome do Cliente", key="client_name", value=st.session_state.client_name)
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Código do Cliente", key="client_code", value=st.session_state.client_code)
                st.number_input("Taxa de Juros Anual (%)", key="annual_interest_rate", value=float(st.session_state.annual_interest_rate), min_value=0.0, step=0.5, format="%.2f")
            with c2:
                st.number_input("Participação na SPE (%)", key="spe_percentage", value=float(st.session_state.spe_percentage), min_value=0.0, max_value=100.0, step=1.0, format="%.2f")
                safe_dt = ensure_date(st.session_state.project_end_date)
                st.date_input("Data Estimada de Término", key="project_end_date", value=safe_dt)

        elif step == 3:
            st.subheader("Fluxo de Aportes")
            if st.session_state.client_name:
                st.caption(f"Simulando para: **{st.session_state.client_name}**")
            
            tab_unico, tab_parcelado = st.tabs(["Aporte Único", "Gerar Parcelas"])

            with tab_unico:
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.date_input("Data", key="new_aporte_date")
                c2.number_input("Valor (R$)", key="new_aporte_value", min_value=0.0, step=10000.0, format="%.2f")
                with c3:
                    st.write("")
                    def add_single_contribution():
                        val = st.session_state.new_aporte_value
                        dt = ensure_date(st.session_state.new_aporte_date)
                        if val > 0:
                            st.session_state.aportes.append({"data": dt, "valor": val})
                            st.session_state.new_aporte_value = 0.0 
                    
                    st.button("Adicionar", use_container_width=True, on_click=add_single_contribution)

            with tab_parcelado:
                p1, p2, p3 = st.columns(3)
                p1.number_input("Valor Total", key="parcelado_total_valor", min_value=0.0, step=50000.0)
                p2.number_input("Qtd. Parcelas", key="parcelado_num_parcelas", min_value=1, step=1)
                p3.date_input("1º Vencimento", key="parcelado_data_inicio")

                def add_parcelas():
                    total = st.session_state.parcelado_total_valor
                    num = int(st.session_state.parcelado_num_parcelas)
                    start = ensure_date(st.session_state.parcelado_data_inicio)
                    if total > 0 and num > 0:
                        val_parcela = total / num
                        for i in range(num):
                            st.session_state.aportes.append({
                                "data": start + relativedelta(months=i),
                                "valor": val_parcela
                            })
                        st.toast("Parcelas geradas!")

                st.button("Gerar Parcelas", use_container_width=True, on_click=add_parcelas)

            if st.session_state.aportes:
                st.divider()
                df_show = pd.DataFrame(st.session_state.aportes)
                if not df_show.empty:
                    if 'date' in df_show.columns: df_show.rename(columns={'date':'data', 'value':'valor'}, inplace=True)
                    df_show['data'] = pd.to_datetime(df_show['data'])
                    
                    edited = st.data_editor(
                        df_show, 
                        column_config={
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")
                        },
                        num_rows="dynamic", 
                        use_container_width=True,
                        key="editor_aportes"
                    )
                    recs = []
                    for r in edited.to_dict('records'):
                         recs.append({'data': ensure_date(r['data']), 'valor': float(r['valor'])})
                    st.session_state.aportes = recs

                if st.button("Limpar Lista"): 
                    st.session_state.aportes = []
                    st.rerun()

        st.divider()
        nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
        with nav_c1:
            if step > 1: st.button("Anterior", on_click=lambda: st.session_state.update(current_step=st.session_state.current_step-1), use_container_width=True)
        with nav_c3:
            if step < 3: st.button("Próximo", on_click=lambda: st.session_state.update(current_step=st.session_state.current_step+1), use_container_width=True)
            else:
                if st.button("Calcular Resultados", type="primary", use_container_width=True):
                    errors = []
                    if st.session_state.land_size <= 0: errors.append("Área Vendável (Etapa 1)")
                    if st.session_state.value_m2 <= 0: errors.append("Valor de Venda (Etapa 1)")
                    if not st.session_state.aportes: errors.append("Aportes (Etapa 3)")
                    
                    if errors:
                        st.error(f"Preencha os dados obrigatórios: {', '.join(errors)}.")
                    else:
                        with st.spinner("Processando..."):
                            p = {
                                'client_name': st.session_state.client_name,
                                'client_code': st.session_state.client_code,
                                'annual_interest_rate': float(st.session_state.annual_interest_rate),
                                'spe_percentage': float(st.session_state.spe_percentage),
                                'land_size': int(st.session_state.land_size),
                                'construction_cost_m2': float(st.session_state.construction_cost_m2),
                                'value_m2': float(st.session_state.value_m2),
                                'area_exchange_percentage': float(st.session_state.area_exchange_percentage),
                                'start_date': ensure_date(st.session_state.start_date),
                                'project_end_date': ensure_date(st.session_state.project_end_date),
                                'aportes': [{'date': ensure_date(x.get('data')), 'value': x.get('valor')} for x in st.session_state.aportes]
                            }
                            st.session_state.simulation_results = utils.calculate_financials(p)
                            st.session_state.simulation_results['simulation_id'] = f"gen_{int(datetime.now().timestamp())}"
                            st.session_state.results_ready = True
                            st.session_state.show_results_page = True
                            st.rerun()
    
    with col_visual:
        with st.container(border=True):
            st.subheader("Resumo do Passo")
            
            step = st.session_state.current_step
            try:
                import os
                if step == 1 and os.path.exists("tower.jpg"):
                    st.image("tower.jpg", use_container_width=True, caption="Parâmetros")
                elif step == 2 and os.path.exists("Lavie.png"):
                    st.image("Lavie.png", use_container_width=True, caption="Investidor")
                elif step == 3 and os.path.exists("Burj.jpg"):
                    st.image("Burj.jpg", use_container_width=True, caption="Projeção")
            except: pass

            st.divider()
            st.markdown("##### Métricas Preliminares")
            
            try:
                area = float(st.session_state.land_size)
                custo = float(st.session_state.construction_cost_m2)
                venda = float(st.session_state.value_m2)
                
                if area > 0:
                    vgv_est = area * venda
                    custo_est = area * custo
                    st.metric("VGV Estimado", utils.format_currency(vgv_est))
                    st.metric("Custo Físico (Obra)", utils.format_currency(custo_est))
                
                total_aportado = sum([a['valor'] for a in st.session_state.aportes])
                if total_aportado > 0:
                     st.metric("Total Aportado", utils.format_currency(total_aportado))
            except: pass

def save_simulation_callback():
    if not worksheets: return
    res = st.session_state.simulation_results
    sim_id = f"sim_{int(datetime.now().timestamp())}"
    try:
        row = [
            sim_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            str(res.get('client_name','')), str(res.get('client_code','')),
            st.session_state.get('user_name',''), 
            float(res.get('total_contribution',0)), int(res.get('num_months',0)),
            float(res.get('annual_interest_rate',0)), float(res.get('spe_percentage',0)), 
            int(res.get('land_size',0)), float(res.get('construction_cost_m2',0)), 
            float(res.get('value_m2',0)), float(res.get('area_exchange_percentage',0)),
            float(res.get('vgv',0)), float(res.get('total_construction_cost',0)), 
            float(res.get('final_operational_result',0)), float(res.get('valor_participacao',0)), 
            float(res.get('resultado_final_investidor',0)), float(res.get('roi',0)),
            float(res.get('roi_anualizado',0)), float(res.get('valor_corrigido',0)),
            str(res.get('start_date')), str(res.get('project_end_date'))
        ]
        worksheets["simulations"].append_row(row, value_input_option='USER_ENTERED')
        aps_rows = [[sim_id, str(a['date']), float(a['value'])] for a in res.get('aportes',[])]
        if aps_rows: worksheets["aportes"].append_rows(aps_rows, value_input_option='USER_ENTERED')
        st.session_state.simulation_saved = True
        st.toast("Salvo!", icon="✅")
    except Exception as e: st.error(f"Erro ao salvar: {e}")
        
def render_history_page():
    st.title("Histórico")
    if not worksheets: st.error("Erro BD"); return
    with st.spinner("Carregando..."):
        df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: st.info("Vazio."); return
    
    c_search, c_sort = st.columns([3, 1])
    search = c_search.text_input("Buscar", placeholder="Nome...")
    if search: df = df[df['client_name'].str.lower().str.contains(search.lower(), na=False)]
    
    df = df.sort_values('created_at', ascending=False)
    st.write("")
    
    for i, row in df.iterrows():
        with st.container():
            c1, c2 = st.columns([3, 1.5])
            with c1:
                st.markdown(f"**{row.get('client_name', 'N/A')}**")
                st.caption(safe_date_to_string(row.get('created_at'), "%d/%m/%Y %H:%M"))
                st.write(f"ROI: {float(row.get('roi_anualizado',0)):.2f}% | Lucro: {utils.format_currency(row.get('resultado_final_investidor',0))}")
            with c2:
                c_b1, c_b2, c_b3 = st.columns(3)
                if c_b1.button("✏️", key=f"ed_{i}"):
                    for k, v in row.items():
                        if k in st.session_state: st.session_state[k] = v
                    df_ap = utils.load_data_from_sheet(worksheets["aportes"])
                    if not df_ap.empty:
                        aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
                        st.session_state.aportes = [{'data': pd.to_datetime(r['data_aporte']).date(), 'valor': float(r['valor_aporte'])} for _, r in aps.iterrows()]
                    st.session_state.page = "Nova Simulação"; st.session_state.current_step = 3; st.rerun()
                
                if c_b2.button("👁️", key=f"vi_{i}"):
                    view = row.to_dict()
                    df_ap = utils.load_data_from_sheet(worksheets["aportes"])
                    if not df_ap.empty:
                        aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
                        view['aportes'] = [{'date': pd.to_datetime(r['data_aporte']).date(), 'value': float(r['valor_aporte'])} for _, r in aps.iterrows()]
                    st.session_state.simulation_to_view = view; st.session_state.page = "Ver Simulação"; st.rerun()
                
                if c_b3.button("🗑️", key=f"de_{i}"):
                    try:
                        worksheets["simulations"].delete_rows(int(row['row_index']))
                        utils.load_data_from_sheet.clear()
                        st.rerun()
                    except: pass
            st.divider()

def render_view_simulation_page():
    st.title("Visualizar Simulação")
    if st.button("Voltar ao Histórico"):
        st.session_state.page = "Histórico"
        st.rerun()
    
    if st.session_state.simulation_to_view:
        res = utils.calculate_financials(st.session_state.simulation_to_view)
        display_full_results(res, show_download_button=True, is_simulation_saved=True)


def render_dashboard_page():
    st.title("Intelligence Dashboard")
    st.markdown("Análise estratégica de viabilidade e performance de portfólio.")
    
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"], "simulations")
    
    if df.empty:
        st.info("Dados insuficientes para gerar dashboard.")
        return

    total_vgv = df['vgv'].sum()
    avg_roi = df['roi_anualizado'].mean()
    total_investido = df['total_contribution'].sum()
    lucro_total = df['resultado_final_investidor'].sum()

    st.markdown("""
    <style>
    .kpi-card {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .kpi-label { font-size: 14px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
    .kpi-value { font-size: 28px; font-weight: bold; color: #fff; margin: 10px 0; }
    .kpi-sub { font-size: 12px; color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    
    def kpi_html(label, value, subtext=""):
        return f"""<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{subtext}</div></div>"""

    with k1: st.markdown(kpi_html("VGV Potencial", utils.format_currency(total_vgv), f"{len(df)} projetos"), unsafe_allow_html=True)
    with k2: st.markdown(kpi_html("Capital Captado", utils.format_currency(total_investido)), unsafe_allow_html=True)
    with k3: st.markdown(kpi_html("Lucro Projetado", utils.format_currency(lucro_total)), unsafe_allow_html=True)
    with k4: st.markdown(kpi_html("ROI Médio (a.a.)", f"{avg_roi:.2f}%"), unsafe_allow_html=True)

    st.divider()
    
    c_charts_1, c_charts_2 = st.columns([2, 1])
    
    with c_charts_1:
        st.subheader("Risco x Retorno (Dispersão)")
        fig_scatter = px.scatter(
            df, 
            x='total_contribution', 
            y='roi_anualizado',
            size='resultado_final_investidor',
            color='roi_anualizado',
            hover_name='client_name',
            color_continuous_scale='RdYlGn',
            labels={'total_contribution': 'Investimento Total (R$)', 'roi_anualizado': 'ROI Anualizado (%)'},
            title="Eficiência do Capital"
        )
        fig_scatter.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        fig_scatter.add_hline(y=df['roi_anualizado'].mean(), line_dash="dot", annotation_text="Média", annotation_position="bottom right")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with c_charts_2:
        st.subheader("Distribuição de ROI")
        fig_hist = px.histogram(
            df, 
            x='roi_anualizado', 
            nbins=10, 
            color_discrete_sequence=['#E37026'],
            title="Histograma de Rentabilidade"
        )
        fig_hist.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', yaxis_title="Frequência")
        st.plotly_chart(fig_hist, use_container_width=True)
        
    c3, c4 = st.columns(2)
    
    with c3:
        st.subheader("Evolução do Portfólio")
        df_sorted = df.sort_values('created_at')
        fig_line = px.area(
            df_sorted, 
            x='created_at', 
            y='vgv', 
            title="Crescimento do VGV Acumulado (Simulado)",
            line_shape='spline',
            color_discrete_sequence=['#00E676']
        )
        fig_line.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_line, use_container_width=True)
        
    with c4:
        st.subheader("Top 5 Projetos (ROI)")
        st.space("large")
        st.space("small")
        top_5 = df.nlargest(5, 'roi_anualizado')[['client_name', 'roi_anualizado', 'resultado_final_investidor']]
        top_5['roi_anualizado'] = top_5['roi_anualizado'].apply(lambda x: f"{x:.2f}%")
        top_5['resultado_final_investidor'] = top_5['resultado_final_investidor'].apply(utils.format_currency)
        top_5.rename(columns={'client_name': 'Cliente', 'roi_anualizado': 'ROI', 'resultado_final_investidor': 'Lucro'}, inplace=True)
        
        st.dataframe(
            top_5, 
            use_container_width=True, 
            hide_index=True,
            column_config={"ROI": st.column_config.TextColumn("ROI", help="Retorno sobre Investimento Anualizado")}
        )
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if st.session_state.authenticated:
    with st.sidebar:
        try: st.image("Lavie.png")
        except: pass
        st.divider()
        st.caption(f"Logado: {st.session_state.get('user_name')}")
        
        page_list = ["Nova Simulação", "Histórico", "Dashboard"]
        curr = st.session_state.page if st.session_state.page in page_list else "Histórico"
        try: ix = page_list.index(curr)
        except: ix = 0
            
        sel = option_menu("Menu", page_list, icons=["calculator", "clock", "graph-up"], default_index=ix)
        st.divider()
        
        if st.button("Sair", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

        if sel != st.session_state.page and st.session_state.page != "Ver Simulação":
            st.session_state.page = sel
            if sel == "Nova Simulação": manual_reset()
            st.rerun()

    if st.session_state.page == "Nova Simulação": render_new_simulation_page()
    elif st.session_state.page == "Histórico": render_history_page()
    elif st.session_state.page == "Ver Simulação": render_view_simulation_page()
    elif st.session_state.page == "Dashboard": render_dashboard_page()
else:
    render_login_page()
