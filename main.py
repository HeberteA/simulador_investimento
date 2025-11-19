import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_option_menu import option_menu
from dateutil.relativedelta import relativedelta 
import utils
from ui_components import display_full_results
import plotly.express as px
import numpy as np

def safe_date_to_string(date_val, fmt='%Y-%m-%d'):
    if pd.isna(date_val): return ""  
    try: return pd.to_datetime(date_val).strftime(fmt)
    except (ValueError, TypeError): return ""  

st.set_page_config(page_title="Simulador Financeiro", page_icon="Lavie1.png", layout="wide")

APP_STYLE_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 10% 20%, #1e1e24 0%, #050505 90%);
    background-attachment: fixed;
}
/* Ajustes de Inputs para contraste */
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: white !important;
}
div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input {
    color: white !important;
}
/* Steps */
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

defaults = {
    'page': "Nova Simulação", 'results_ready': False, 'simulation_results': {},
    'editing_row': None, 'simulation_to_edit': None, 'simulation_to_view': None, 
    'show_results_page': False,
    'client_name': '', 'client_code': '',
    'annual_interest_rate': 12.0, 'spe_percentage': 65.0,
    'total_contribution': 100000.0, 'num_months': 24, 
    'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 'construction_cost_m2': 3500.0, 'value_m2': 10000.0, 'area_exchange_percentage': 20.0,
    'aportes': [], 'confirming_delete': None, 'simulation_saved': False, 'current_step': 1 
}

for key, value in defaults.items():
    if key not in st.session_state: st.session_state[key] = value

if 'new_aporte_date' not in st.session_state: st.session_state.new_aporte_date = datetime.today().date()
if 'new_aporte_value' not in st.session_state: st.session_state.new_aporte_value = 0.0
if 'parcelado_total_valor' not in st.session_state: st.session_state.parcelado_total_valor = 0.0
if 'parcelado_num_parcelas' not in st.session_state: st.session_state.parcelado_num_parcelas = 1
if 'parcelado_data_inicio' not in st.session_state: st.session_state.parcelado_data_inicio = datetime.today().date()

worksheets = utils.init_gsheet_connection()

def manual_reset():
    """Reseta apenas os campos do formulário, mantendo a autenticação."""
    for key, value in defaults.items():
        if key != 'page': 
            st.session_state[key] = value
    st.session_state.current_step = 1
    st.session_state.show_results_page = False
    st.toast("Formulário limpo para nova simulação!")

def render_login_page():
    c1, c2, c3 = st.columns([1, 2, 1]) 
    with c2:
        st.image("Lavie.png", use_column_width=True) 
        st.markdown("<h2 style='text-align: center;'>Simulador Financeiro</h2>", unsafe_allow_html=True)
        st.markdown("---")
        try: user_list = list(st.secrets["credentials"].keys())
        except Exception: st.error("Credenciais não configuradas."); st.stop()
        
        selected_user = st.selectbox("Usuário", options=user_list, index=None, placeholder="Selecione seu usuário")
        access_code = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        
        if st.button("Entrar", use_container_width=True, type="primary"):
            if selected_user and access_code:
                if access_code == st.secrets["credentials"].get(selected_user):
                    st.session_state.authenticated = True
                    st.session_state.user_name = selected_user
                    st.rerun()
                else: st.error("Senha incorreta.")
            else: st.warning("Preencha todos os campos.")

def render_new_simulation_page():
    col_tit, col_btn = st.columns([4, 1])
    with col_tit: st.empty() 
    with col_btn: 
        if st.button("Nova Simulação", help="Limpa todos os campos para começar do zero", use_container_width=True):
            manual_reset()
            st.rerun()

    def go_to_results(): st.session_state.show_results_page = True
    def go_to_inputs(): st.session_state.show_results_page = False

    if st.session_state.show_results_page:
        st.title("Resultado da Simulação")
        
        if st.button("⬅️ Voltar para os Parâmetros"):
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
            <div class="step-item {'active' if step >= 1 else ''}"><div class="step-number">1</div><div class="step-label">Obra</div></div>
            <div class="step-item {'active' if step >= 2 else ''}"><div class="step-number">2</div><div class="step-label">Cliente</div></div>
            <div class="step-item {'active' if step >= 3 else ''}"><div class="step-number">3</div><div class="step-label">Financeiro</div></div>
        </div>
        """, unsafe_allow_html=True)

        if step == 1:
            st.subheader("Parâmetros do Projeto")
            c1, c2 = st.columns(2)
            with c1:
                st.number_input("Área Vendável (m²)", min_value=0, step=10, key="land_size", help="Área total privativa vendável do projeto.")
                st.number_input("Custo da Obra (R$/m²)", min_value=0.0, step=100.0, format="%.2f", key="construction_cost_m2")
            with c2:
                st.number_input("Valor de Venda (R$/m²)", min_value=0.0, step=100.0, format="%.2f", key="value_m2")
                st.number_input("Permuta (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.2f", key="area_exchange_percentage")

        elif step == 2:
            st.subheader("Dados do Investidor")
            c1, c2 = st.columns(2)
            with c1:
                c_name = st.text_input("Nome do Cliente", value=st.session_state.client_name, key="widget_client_name")
                st.session_state.client_name = c_name
                
                c_code = st.text_input("Código de Controle", value=st.session_state.client_code, key="widget_client_code")
                st.session_state.client_code = c_code
                
                st.number_input("Taxa de Juros Anual (%)", min_value=0.0, step=0.1, format="%.2f", key="annual_interest_rate")
            with c2:
                st.number_input("Participação na SPE (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="spe_percentage")
                st.date_input("Data Estimada de Término", value=st.session_state.project_end_date, key="project_end_date")

        elif step == 3:
            st.subheader("Fluxo de Aportes")
            if st.session_state.client_name:
                st.caption(f"Simulando para: **{st.session_state.client_name}**")
            
            tab_unico, tab_parcelado = st.tabs(["Aporte Único", "Gerar Parcelas"])
            
            with tab_unico:
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.date_input("Data", key="new_aporte_date")
                c2.number_input("Valor (R$)", min_value=0.0, step=10000.0, format="%.2f", key="new_aporte_value")
                with c3:
                    st.space("small")
                    def add_single_contribution():
                        val = st.session_state.new_aporte_value
                        dt = st.session_state.new_aporte_date
                        if val > 0:
                            st.session_state.aportes.append({"data": dt, "valor": val})
                            st.session_state.new_aporte_value = 0.0 
                    st.button("Adicionar", use_container_width=True, on_click=add_single_contribution)
            
            with tab_parcelado:
                p1, p2, p3 = st.columns(3)
                p1.number_input("Valor Total", min_value=0.0, step=50000.0, key="parcelado_total_valor")
                p2.number_input("Qtd. Parcelas", min_value=1, step=1, key="parcelado_num_parcelas")
                p3.date_input("1º Vencimento", key="parcelado_data_inicio")
                
                def add_parcelas():
                    total = st.session_state.parcelado_total_valor
                    num = int(st.session_state.parcelado_num_parcelas)
                    start = st.session_state.parcelado_data_inicio
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
                df_ap = pd.DataFrame(st.session_state.aportes)
                if not df_ap.empty:
                    df_ap['data'] = pd.to_datetime(df_ap['data'])
                    edited = st.data_editor(
                        df_ap, 
                        column_config={
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), 
                            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")
                        }, 
                        use_container_width=True, 
                        num_rows="dynamic", 
                        key="editor_aportes"
                    )
                    st.session_state.aportes = edited.to_dict('records')
                
                if st.button("Limpar Aportes", type="secondary"): 
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
                    if not st.session_state.aportes: st.warning("Adicione pelo menos um aporte.")
                    else:
                        with st.spinner("Processando..."):
                            params = {
                                'client_name': st.session_state.client_name, 
                                'client_code': st.session_state.client_code,
                                'annual_interest_rate': st.session_state.get('annual_interest_rate', 12.0),
                                'spe_percentage': st.session_state.get('spe_percentage', 65.0),
                                'land_size': st.session_state.get('land_size', 0),
                                'construction_cost_m2': st.session_state.get('construction_cost_m2', 0),
                                'value_m2': st.session_state.get('value_m2', 0),
                                'area_exchange_percentage': st.session_state.get('area_exchange_percentage', 0),
                                'start_date': st.session_state.get('start_date', datetime.today().date()),
                                'project_end_date': st.session_state.get('project_end_date', datetime.today().date()),
                                'aportes': [{'date': a['data'], 'value': a['valor']} for a in st.session_state.aportes if a.get('valor')]
                            }
                            
                            st.session_state.simulation_results = utils.calculate_financials(params)
                            st.session_state.simulation_results['simulation_id'] = f"gen_{int(datetime.now().timestamp())}"
                            
                            st.session_state.results_ready = True
                            st.session_state.simulation_saved = False
                            go_to_results()
                            st.rerun()
    
    with col_visual:
        with st.container(border=True):
            st.subheader("Resumo")
            step = st.session_state.current_step
            try:
                if step == 1: st.image("tower.png", use_container_width=True)
                elif step == 2: st.image("Arc.jpeg", use_container_width=True)
                elif step == 3: st.image("Burj.jpg", use_container_width=True)
            except: pass

            st.divider()
            try:
                vgv = float(st.session_state.land_size) * float(st.session_state.value_m2)
                st.metric("VGV Estimado", utils.format_currency(vgv))
                total_ap = sum([a['valor'] for a in st.session_state.aportes])
                if total_ap > 0: st.metric("Aportes", utils.format_currency(total_ap))
            except: pass

def save_simulation_callback():
    if not worksheets: return
    res = st.session_state.simulation_results
    sim_id = f"sim_{int(datetime.now().timestamp())}"
    try:
        row = [sim_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(res.get('client_name','')), str(res.get('client_code','')),
               st.session_state.get('user_name',''), float(res.get('total_contribution',0)), int(res.get('num_months',0)),
               float(res.get('annual_interest_rate',0)), float(res.get('spe_percentage',0)), int(res.get('land_size',0)),
               float(res.get('construction_cost_m2',0)), float(res.get('value_m2',0)), float(res.get('area_exchange_percentage',0)),
               float(res.get('vgv',0)), float(res.get('total_construction_cost',0)), float(res.get('final_operational_result',0)),
               float(res.get('valor_participacao',0)), float(res.get('resultado_final_investidor',0)), float(res.get('roi',0)),
               float(res.get('roi_anualizado',0)), float(res.get('valor_corrigido',0)),
               str(res.get('start_date')), str(res.get('project_end_date'))]
        worksheets["simulations"].append_row(row, value_input_option='USER_ENTERED')
        
        aps_rows = [[sim_id, str(a['date']), float(a['value'])] for a in res.get('aportes',[])]
        if aps_rows: worksheets["aportes"].append_rows(aps_rows, value_input_option='USER_ENTERED')
        st.session_state.simulation_saved = True
        st.toast("Salvo com sucesso!")
    except Exception as e: st.error(f"Erro ao salvar: {e}")

def render_history_page():
    st.title("Histórico de Simulações")
    
    if not worksheets: 
        st.error("Erro de conexão com Google Sheets.")
        return
    
    df = utils.load_data_from_sheet(worksheets["simulations"], "simulations")
    
    if df.empty:
        st.info("Nenhum histórico encontrado.")
        return

    col_search, col_filter = st.columns([3, 1])
    search = col_search.text_input("🔍 Buscar Cliente", placeholder="Nome do cliente...").lower()
    
    if search:
        df = df[df['client_name'].str.lower().str.contains(search, na=False)]
    
    df = df.sort_values('created_at', ascending=False)
    
    st.write("")
    
    for idx, row in df.iterrows():
        with st.container():
            roi_val = float(row.get('roi_anualizado', 0))
            color = "#388E3C" if roi_val > 15 else "#E37026"
            
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.03); border-left: 4px solid {color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <h4 style="margin:0; color:white;">{row['client_name']}</h4>
                        <span style="color:#888; font-size: 12px;">📅 {safe_date_to_string(row['created_at'], '%d/%m/%Y %H:%M')}</span>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:bold; color:{color}; font-size: 1.2rem;">{roi_val:.2f}% a.a.</div>
                        <div style="color:#aaa; font-size: 0.8rem;">Lucro: {utils.format_currency(row.get('resultado_final_investidor'))}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            b1, b2, b3 = st.columns([1, 1, 6])
            
            if b1.button("✏️", key=f"edit_{idx}"):
                for k, v in row.items():
                    if k in st.session_state:
                        try:
                             if isinstance(st.session_state[k], float): st.session_state[k] = float(v)
                             elif isinstance(st.session_state[k], int): st.session_state[k] = int(v)
                             else: st.session_state[k] = v
                        except: st.session_state[k] = v
                
                df_ap = utils.load_data_from_sheet(worksheets["aportes"], "aportes")
                if not df_ap.empty:
                    aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
                    st.session_state.aportes = [{"data": pd.to_datetime(r['data_aporte']).date(), "valor": float(r['valor_aporte'])} for _, r in aps.iterrows()]
                else:
                    st.session_state.aportes = []

                st.session_state.client_name = row.get('client_name', '')
                st.session_state.client_code = row.get('client_code', '')
                
                st.session_state.page = "Nova Simulação"
                st.session_state.current_step = 3
                st.session_state.simulation_saved = True 
                st.rerun()

            if b2.button("👁️ Ver", key=f"view_{idx}"):
                view_data = row.to_dict()
                df_ap = utils.load_data_from_sheet(worksheets["aportes"], "aportes")
                aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
                view_data['aportes'] = [{"date": pd.to_datetime(r['data_aporte']).date(), "value": float(r['valor_aporte'])} for _, r in aps.iterrows()]
                
                st.session_state.simulation_to_view = view_data
                st.session_state.page = "Ver Simulação"
                st.rerun()
                

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
    st.markdown("Visão estratégica do portfólio.")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"], "simulations")
    if df.empty: st.info("Sem dados."); return

    st.markdown("""
    <style>
    .kpi-box { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #333; }
    .kpi-val { font-size: 24px; font-weight: bold; color: white; }
    .kpi-lbl { color: #aaa; font-size: 12px; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f"<div class='kpi-box'><div class='kpi-lbl'>VGV Total</div><div class='kpi-val'>{utils.format_currency(df['vgv'].sum())}</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='kpi-box'><div class='kpi-lbl'>ROI Médio</div><div class='kpi-val'>{df['roi_anualizado'].mean():.2f}%</div></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='kpi-box'><div class='kpi-lbl'>Simulações</div><div class='kpi-val'>{len(df)}</div></div>", unsafe_allow_html=True)
    with c4: st.markdown(f"<div class='kpi-box'><div class='kpi-lbl'>Lucro Proj.</div><div class='kpi-val'>{utils.format_currency(df['resultado_final_investidor'].sum())}</div></div>", unsafe_allow_html=True)

    st.divider()
    
    g1, g2 = st.columns([2, 1])
    with g1:
        fig = px.scatter(df, x='total_contribution', y='roi_anualizado', size='resultado_final_investidor', color='roi_anualizado',
                         title="Matriz Risco x Retorno (Tamanho = Lucro)", color_continuous_scale='Sunsetdark')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig, use_container_width=True)
    
    with g2:
        top5 = df.nlargest(5, 'roi_anualizado')[['client_name', 'roi_anualizado']]
        st.markdown("##### Top 5 Rentabilidade")
        st.dataframe(top5, hide_index=True, use_container_width=True)

if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if st.session_state.authenticated:
    with st.sidebar:
        st.image("Lavie.png")
        st.caption(f"Logado: {st.session_state.get('user_name')}")
        
        sel = option_menu(
            "Menu", 
            ["Nova Simulação", "Histórico", "Dashboard"], 
            icons=["calculator", "clock-history", "graph-up-arrow"], 
            menu_icon="cast", 
            default_index=0,
            styles={
                "nav-link-selected": {"background-color": "#E37026"},
                "container": {"padding": "0!important", "background-color": "transparent"},
            }
        )
        
        if st.button("Sair", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
        
        page_map = {
            "Nova Simulação": "Nova Simulação", 
            "Histórico": "Histórico", 
            "Dashboard": "Dashboard"
        }
        
        target_page = page_map.get(sel)
        
        if target_page and st.session_state.page != target_page and st.session_state.page != "Ver Simulação":
            st.session_state.page = target_page
            st.rerun()

    if st.session_state.page == "Nova Simulação": render_new_simulation_page()
    elif st.session_state.page == "Histórico": render_history_page()
    elif st.session_state.page == "Ver Simulação": render_view_simulation_page()
    elif st.session_state.page == "Dashboard": render_dashboard_page()

else:
    render_login_page()
