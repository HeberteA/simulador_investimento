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

[data-testid="stAppViewContainer"] {
    /* Opção: Papel Artesanal (Sutil e Elegante) */
    background-image: url("https://www.transparenttextures.com/patterns/handmade-paper.png");
    background-repeat: repeat;
}

div[data-baseweb="input"] > div {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: white !important;
    border-radius: 8px;
}

div[data-testid="stNumberInput"] input {
    color: white !important;
}

/* Estilo para o Sidebar Visual na direita */
.visual-sidebar {
    background: rgba(255, 255, 255, 0.02);
    border-left: 1px solid rgba(255, 255, 255, 0.05);
    padding: 20px;
    border-radius: 15px;
    height: 100%;
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

defaults = {
    'page': "Nova Simulação", 'results_ready': False, 'simulation_results': {},
    'editing_row': None, 'simulation_to_edit': None, 'simulation_to_view': None, 
    'show_results_page': False,
    'annual_interest_rate': 12.0, 'spe_percentage': 65.0,
    'total_contribution': 100000.0, 'num_months': 24, 'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 'construction_cost_m2': 3500.0, 'value_m2': 10000.0, 'area_exchange_percentage': 20.0,
    'aportes': [], 'confirming_delete': None, 'simulation_saved': False, 'current_step': 1 
}

def reset_form_to_defaults():
    for key, value in defaults.items():
        if key != 'page': 
            st.session_state[key] = value
            
    st.session_state.new_aporte_date = datetime.today().date()
    st.session_state.new_aporte_value = 0.0
    st.session_state.parcelado_total_valor = 0.0
    st.session_state.parcelado_num_parcelas = 1
    st.session_state.parcelado_data_inicio = datetime.today().date()
    st.session_state.current_step = 1
    st.session_state.show_results_page = False
    st.session_state.results_ready = False
    
for key, value in defaults.items():
    if key not in st.session_state: st.session_state[key] = value
worksheets = utils.init_gsheet_connection()

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
    def go_to_results(): st.session_state.show_results_page = True
    def go_to_inputs(): st.session_state.show_results_page = False

    if st.session_state.show_results_page:
        st.title("Resultado da Simulação")
        
        if st.button("Voltar para os Parâmetros"):
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
                st.number_input("Área Vendável (m²)", min_value=0, step=10, key="land_size", help="Área total privativa vendável do projeto.")
                st.number_input("Custo da Obra (R$/m²)", min_value=0.0, step=100.0, format="%.2f", key="construction_cost_m2", help="Custo estimado de construção por metro quadrado.")
            with c2:
                st.number_input("Valor de Venda (R$/m²)", min_value=0.0, step=100.0, format="%.2f", key="value_m2", help="Valor médio de venda esperado por metro quadrado.")
                st.number_input("Permuta Física/Financeira (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.2f", key="area_exchange_percentage", help="Percentual do VGV destinado à permuta do terreno.")

        elif step == 2:
            st.subheader("Dados do Investidor")
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Nome do Cliente/Investidor", key="client_name", placeholder="Ex: João Silva ou JS Participações", help="Nome que aparecerá no relatório final.")
                st.text_input("Código de Controle", key="client_code", placeholder="Opcional")
                st.number_input("Taxa de Juros Anual (%)", min_value=0.0, step=0.1, format="%.2f", key="annual_interest_rate", help="Custo de oportunidade ou taxa de remuneração do capital.")
            with c2:
                st.number_input("Participação na SPE (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="spe_percentage", help="Percentual de participação do investidor na Sociedade de Propósito Específico.")
                st.date_input("Data Estimada de Término", value=st.session_state.project_end_date, key="project_end_date")

        elif step == 3:
            st.subheader("Fluxo de Aportes")
            nome_atual = st.session_state.get('client_name', 'N/A')
            if nome_atual:
                st.caption(f"Simulando para: **{nome_atual}**")
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
                
                if st.button("Limpar Todos Aportes", type="secondary"): 
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
                    if not st.session_state.aportes: st.warning("Adicione aportes.")
                    else:
                        with st.spinner("Processando..."):
                            params = {
                                'client_name': st.session_state.get('client_name', 'Cliente Não Identificado'), 
                                'client_code': st.session_state.get('client_code', ''),
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
            st.subheader("Resumo do Passo")
            
            step = st.session_state.current_step
            try:
                if step == 1:
                    st.image("tower.png", use_container_width=True, caption="Parâmetros da Obra")
                elif step == 2:
                    st.image("Arc.jpeg", use_container_width=True, caption="Identidade do Investidor")
                elif step == 3:
                    st.image("Burj.jpg", use_container_width=True, caption="Projeção de Crescimento")
            except Exception:
                st.info("Imagem ilustrativa não encontrada.")

            st.divider()
            st.markdown("##### Métricas Preliminares")
            
            try:
                area = float(st.session_state.land_size)
                custo = float(st.session_state.construction_cost_m2)
                venda = float(st.session_state.value_m2)
                
                vgv_est = area * venda
                custo_est = area * custo
                
                st.metric("VGV Estimado", utils.format_currency(vgv_est))
                st.metric("Custo Físico (Obra)", utils.format_currency(custo_est))
                
                total_aportado = sum([a['valor'] for a in st.session_state.aportes])
                if total_aportado > 0:
                     st.metric("Total Aportado", utils.format_currency(total_aportado))
            except:
                st.caption("Preencha os dados para ver os cálculos.")

def render_load_simulation_page():
    st.title("Carregar Simulação")
    if not worksheets or not worksheets.get("simulations"): st.error("Erro de conexão."); return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: st.info("Sem dados."); return
    
    sel_client = st.selectbox("Selecione o Cliente", df["client_name"].unique(), index=None)
    if st.button("Carregar", type="primary") and sel_client:
        row = df[df['client_name'] == sel_client].sort_values('created_at', ascending=False).iloc[0]
        for k, v in row.items():
            if k in st.session_state:
                try:
                     if isinstance(st.session_state[k], float): st.session_state[k] = float(v)
                     elif isinstance(st.session_state[k], int): st.session_state[k] = int(v)
                     else: st.session_state[k] = v
                except: st.session_state[k] = v
        
        df_ap = utils.load_data_from_sheet(worksheets["aportes"])
        aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
        st.session_state.aportes = [{"data": pd.to_datetime(r['data_aporte']).date(), "valor": float(r['valor_aporte'])} for _, r in aps.iterrows()]
        st.session_state.page = "Nova Simulação"; st.session_state.current_step = 3
        st.rerun()

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
        st.session_state.simulation_saved = True; st.toast("Salvo com sucesso!")
    except Exception as e: st.error(f"Erro ao salvar: {e}")

def render_history_page():
    st.title("Histórico")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: st.info("Vazio."); return
    
    for i, row in df.sort_values('created_at', ascending=False).iterrows():
        with st.container():
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <h4 style="margin:0; color:white;">{row.get('client_name')}</h4>
                    <span style="color:#888; font-size: 12px;">{pd.to_datetime(row.get('created_at')).strftime('%d/%m/%Y %H:%M')}</span>
                </div>
                <div style="text-align: right;">
                    <div style="color: #E37026; font-weight: bold;">ROI: {float(row.get('roi_anualizado',0)):.2f}%</div>
                    <div style="color: #aaa; font-size: 12px;">VGV: {utils.format_currency(float(row.get('vgv',0)))}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1,1,8])
            if c1.button("👁️", key=f"v_{i}"): 
                st.session_state.simulation_to_view = row.to_dict(); st.session_state.page = "Ver Simulação"; st.rerun()
            if c2.button("🗑️", key=f"d_{i}"):
                worksheets["simulations"].delete_rows(int(row.get('row_index', i+2)))
                st.rerun()

def render_view_simulation_page():
    st.title("Visualizar Simulação")
    if st.button("Voltar"): st.session_state.page = "Histórico de Simulações"; st.rerun()
    if not st.session_state.simulation_to_view: return
    
    data = st.session_state.simulation_to_view
    df_ap = utils.load_data_from_sheet(worksheets["aportes"])
    aps = df_ap[df_ap['simulation_id'] == data['simulation_id']]
    data['aportes'] = [{'date': pd.to_datetime(r['data_aporte']).date(), 'value': float(r['valor_aporte'])} for _, r in aps.iterrows()]
    
    res = utils.calculate_financials(data)
    display_full_results(res, show_download_button=True, is_simulation_saved=True)

def render_dashboard_page():
    st.title("Dashboard Gerencial")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: return
    
    k1, k2, k3 = st.columns(3)
    k1.metric("VGV Total", utils.format_currency(df['vgv'].sum()))
    k2.metric("ROI Médio", f"{df['roi_anualizado'].mean():.2f}%")
    k3.metric("Simulações", len(df))
    
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.histogram(df, x='roi_anualizado', title="Distribuição de ROI", color_discrete_sequence=['#E37026']), use_container_width=True)
    with c2: st.plotly_chart(px.scatter(df, x='total_contribution', y='roi_anualizado', title="Aporte vs ROI", color_discrete_sequence=['#E37026']), use_container_width=True)

if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if st.session_state.authenticated:
    with st.sidebar:
        st.image("Lavie.png")
        st.caption(f"Logado como: {st.session_state.get('user_name')}")
        sel = option_menu("Menu", ["Nova Simulação", "Carregar Simulação", "Histórico", "Dashboard"], icons=["plus", "upload", "list", "graph-up"], menu_icon="cast", default_index=0, styles={"nav-link-selected": {"background-color": "#E37026"}})
        if st.button("Sair"): st.session_state.authenticated = False; st.rerun()
        
        page_map = {"Nova Simulação": "Nova Simulação", "Carregar Simulação": "Carregar Simulação", "Histórico": "Histórico de Simulações", "Dashboard": "Dashboard"}
        if st.session_state.page != page_map.get(sel) and sel: st.session_state.page = page_map[sel]; reset_form_to_defaults(); st.rerun()

    if st.session_state.page == "Nova Simulação": render_new_simulation_page()
    elif st.session_state.page == "Carregar Simulação": render_load_simulation_page()
    elif st.session_state.page == "Histórico de Simulações": render_history_page()
    elif st.session_state.page == "Ver Simulação": render_view_simulation_page()
    elif st.session_state.page == "Dashboard": render_dashboard_page()
else:
    render_login_page()
