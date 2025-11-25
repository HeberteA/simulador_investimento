import streamlit as st
import pandas as pd
from datetime import datetime, date
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

def ensure_date(val):
    """Garante que o valor seja um objeto date do python."""
    if isinstance(val, date): return val
    if isinstance(val, datetime): return val.date()
    try: return pd.to_datetime(val).date()
    except: return datetime.today().date()

def safe_load_icon(image_name, fallback_emoji="🏗️"):
    import os
    if os.path.exists(image_name): return image_name
    return fallback_emoji

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

state_keys = {
    'page': "Nova Simulação", 'results_ready': False, 'simulation_results': {},
    'editing_row': None, 'simulation_to_edit': None, 'simulation_to_view': None, 
    'show_results_page': False,
    'client_name': '', 'client_code': '',
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
    'aportes': [], 'confirming_delete': None, 'simulation_saved': False, 'current_step': 1,
    'new_aporte_date': datetime.today().date(),
    'new_aporte_value': 0.0,
    'parcelado_total_valor': 0.0,
    'parcelado_num_parcelas': 1,
    'parcelado_data_inicio': datetime.today().date()
}

for k, v in state_keys.items():
    if k not in st.session_state: st.session_state[k] = v

worksheets = utils.init_gsheet_connection()

def manual_reset():
    """Limpa os campos mantendo a estrutura."""
    st.session_state.client_name = ''
    st.session_state.client_code = ''
    st.session_state.land_size = 0
    st.session_state.construction_cost_m2 = 0.0
    st.session_state.value_m2 = 0.0
    st.session_state.area_exchange_percentage = 0.0
    st.session_state.annual_interest_rate = 0.0
    st.session_state.spe_percentage = 0.0
    st.session_state.project_end_date = datetime.today().date()
    st.session_state.aportes = []
    st.session_state.current_step = 1
    st.session_state.show_results_page = False
    st.session_state.results_ready = False

def render_login_page():
    c1, c2, c3 = st.columns([1, 2, 1]) 
    with c2:
        try: st.image("Lavie.png", use_column_width=True) 
        except: st.title("Lavie")
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
                st.number_input("Área Vendável (m²)", value=int(st.session_state.land_size), min_value=0, step=10, key="land_size")
                st.number_input("Custo da Obra (R$/m²)", value=float(st.session_state.construction_cost_m2), min_value=0.0, step=100.0, format="%.2f", key="construction_cost_m2")
            with c2:
                st.number_input("Valor de Venda (R$/m²)", value=float(st.session_state.value_m2), min_value=0.0, step=100.0, format="%.2f", key="value_m2")
                st.number_input("Permuta Física/Financeira (%)", value=float(st.session_state.area_exchange_percentage), min_value=0.0, max_value=100.0, step=0.5, format="%.2f", key="area_exchange_percentage")

        elif step == 2:
            st.subheader("Dados do Investidor")
            st.text_input("Nome do Cliente", value=st.session_state.client_name, key="client_name")
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Código do Cliente", value=st.session_state.client_code, key="client_code")
                st.number_input("Taxa de Juros Anual (%)", value=float(st.session_state.annual_interest_rate), min_value=0.0, step=0.5, format="%.2f", key="annual_interest_rate")
            with c2:
                st.number_input("Participação na SPE (%)", value=float(st.session_state.spe_percentage), min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="spe_percentage")
                safe_end = ensure_date(st.session_state.project_end_date)
                st.date_input("Data Estimada de Término", value=safe_end, key="project_end_date")

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
                p1.number_input("Valor Total", min_value=0.0, step=50000.0, key="parcelado_total_valor")
                p2.number_input("Qtd. Parcelas", min_value=1, step=1, key="parcelado_num_parcelas")
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
                    if not st.session_state.aportes: st.warning("Adicione pelo menos um aporte.")
                    elif st.session_state.land_size <= 0 or st.session_state.value_m2 <= 0: 
                        st.error("Preencha os dados da Etapa 1 (Área e Venda).")
                    else:
                        with st.spinner("Processando..."):
                            p = {
                                'client_name': st.session_state.client_name,
                                'client_code': st.session_state.client_code,
                                'annual_interest_rate': st.session_state.annual_interest_rate,
                                'spe_percentage': st.session_state.spe_percentage,
                                'land_size': st.session_state.land_size,
                                'construction_cost_m2': st.session_state.construction_cost_m2,
                                'value_m2': st.session_state.value_m2,
                                'area_exchange_percentage': st.session_state.area_exchange_percentage,
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
                # Lógica para exibir imagem apenas se arquivo existir
                import os
                if step == 1 and os.path.exists("tower.jpg"):
                    st.image("tower.jpg", use_container_width=True, caption="Parâmetros da Obra")
                elif step == 2 and os.path.exists("Lavie.png"):
                    st.image("Lavie.png", use_container_width=True, caption="Identidade do Investidor")
                elif step == 3 and os.path.exists("Burj.jpg"):
                    st.image("Burj.jpg", use_container_width=True, caption="Projeção de Crescimento")
            except Exception: pass

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
            except:
                st.caption("Preencha os dados...")

def save_simulation_callback():
    if not worksheets: return
    res = st.session_state.simulation_results
    sim_id = f"sim_{int(datetime.now().timestamp())}"
    
    try:
        row = [
            sim_id, 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            str(res.get('client_name','')), 
            str(res.get('client_code','')),
            st.session_state.get('user_name',''), 
            float(res.get('total_contribution',0)), 
            int(res.get('num_months',0)),
            float(res.get('annual_interest_rate',0)), 
            float(res.get('spe_percentage',0)), 
            int(res.get('land_size',0)),
            float(res.get('construction_cost_m2',0)), 
            float(res.get('value_m2',0)), 
            float(res.get('area_exchange_percentage',0)),
            float(res.get('vgv',0)), 
            float(res.get('total_construction_cost',0)), 
            float(res.get('final_operational_result',0)),
            float(res.get('valor_participacao',0)), 
            float(res.get('resultado_final_investidor',0)), 
            float(res.get('roi',0)),
            float(res.get('roi_anualizado',0)), 
            float(res.get('valor_corrigido',0)),
            str(res.get('start_date')), 
            str(res.get('project_end_date'))
        ]
        worksheets["simulations"].append_row(row, value_input_option='USER_ENTERED')
        
        aps_rows = [[sim_id, str(a['date']), float(a['value'])] for a in res.get('aportes',[])]
        if aps_rows: 
            worksheets["aportes"].append_rows(aps_rows, value_input_option='USER_ENTERED')
            
        st.session_state.simulation_saved = True
        st.toast("Salvo com sucesso!", icon="✅")
    except Exception as e: 
        st.error(f"Erro ao salvar: {e}")
        
def render_history_page():
    st.title("Histórico de Simulações")
    if not worksheets: 
        st.error("Erro de conexão com banco de dados.")
        return
        
    with st.spinner("Carregando histórico..."):
        df = utils.load_data_from_sheet(worksheets["simulations"])
    
    if df.empty: 
        st.info("Nenhuma simulação encontrada.")
        return
    
    c_search, c_sort = st.columns([3, 1])
    search = c_search.text_input("🔍 Buscar Cliente", placeholder="Digite o nome...")
    if search:
        df = df[df['client_name'].str.lower().str.contains(search.lower(), na=False)]
    
    df = df.sort_values('created_at', ascending=False)
    st.write("")
    
    for i, row in df.iterrows():
        client_n = row.get('client_name', 'Cliente sem nome')
        roi_val = float(row.get('roi_anualizado', 0))
        date_fmt = safe_date_to_string(row.get('created_at'), "%d/%m/%Y às %H:%M")
        profit = utils.format_currency(row.get('resultado_final_investidor', 0))
        border_color = "#4CAF50" if roi_val > 15 else "#FF9800" if roi_val > 0 else "#F44336"
        
        with st.container():
            c_info, c_actions = st.columns([3, 1.5]) 
            with c_info:
                st.markdown(f"""
                <div style="border-left: 4px solid {border_color}; padding-left: 15px; margin-bottom: 10px;">
                    <h3 style="margin:0; font-size:1.3rem; color: white;">{client_n}</h3>
                    <p style="margin:0; color: #888; font-size: 0.8rem;">📅 {date_fmt}</p>
                    <div style="margin-top: 8px; display: flex; gap: 20px;">
                        <div><span style="color:#aaa; font-size:0.8rem;">ROI Anual</span><br><strong style="color:{border_color}; font-size:1.1rem;">{roi_val:.2f}%</strong></div>
                        <div><span style="color:#aaa; font-size:0.8rem;">Lucro Líquido</span><br><strong style="color:white; font-size:1.1rem;">{profit}</strong></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with c_actions:
                st.write("") 
                b_col1, b_col2, b_col3 = st.columns(3)
                
                if b_col1.button("✏️", key=f"edit_{i}", help="Editar"):
                    for k, v in row.items():
                        if k in st.session_state:
                            if k in ['start_date', 'project_end_date']:
                                st.session_state[k] = ensure_date(v)
                            else:
                                st.session_state[k] = v
                    
                    df_ap = utils.load_data_from_sheet(worksheets["aportes"])
                    if not df_ap.empty:
                        aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
                        st.session_state.aportes = [{'data': ensure_date(r['data_aporte']), 'valor': float(r['valor_aporte'])} for _, r in aps.iterrows()]
                    else:
                        st.session_state.aportes = []
                    
                    st.session_state.client_name = row.get('client_name', '')
                    st.session_state.client_code = row.get('client_code', '')
                    st.session_state.page = "Nova Simulação"
                    st.session_state.current_step = 3
                    st.session_state.simulation_saved = True
                    st.rerun()
                
                if b_col2.button("👁️", key=f"view_{i}", help="Visualizar"):
                    view_obj = row.to_dict()
                    df_ap = utils.load_data_from_sheet(worksheets["aportes"])
                    if not df_ap.empty:
                        aps = df_ap[df_ap['simulation_id'] == row['simulation_id']]
                        view_obj['aportes'] = [{'date': ensure_date(r['data_aporte']), 'value': float(r['valor_aporte'])} for _, r in aps.iterrows()]
                    else:
                        view_obj['aportes'] = []
                    
                    st.session_state.simulation_to_view = view_obj
                    st.session_state.page = "Ver Simulação"
                    st.rerun()

                if b_col3.button("🗑️", key=f"del_{i}", help="Excluir"):
                    try:
                        row_idx = int(row['row_index'])
                        worksheets["simulations"].delete_rows(row_idx)
                        utils.load_data_from_sheet.clear()
                        st.toast("Excluído!", icon="🗑️")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
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
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    
    if df.empty:
        st.info("Dados insuficientes.")
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
    </style>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    def kpi_html(label, value):
        return f"""<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>"""

    with k1: st.markdown(kpi_html("VGV Potencial", utils.format_currency(total_vgv)), unsafe_allow_html=True)
    with k2: st.markdown(kpi_html("Capital Captado", utils.format_currency(total_investido)), unsafe_allow_html=True)
    with k3: st.markdown(kpi_html("Lucro Projetado", utils.format_currency(lucro_total)), unsafe_allow_html=True)
    with k4: st.markdown(kpi_html("ROI Médio (a.a.)", f"{avg_roi:.2f}%"), unsafe_allow_html=True)

    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        fig_scatter = px.scatter(df, x='total_contribution', y='roi_anualizado', size='resultado_final_investidor', color='roi_anualizado', title="Risco x Retorno")
        fig_scatter.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_scatter, use_container_width=True)
    with c2:
        fig_hist = px.histogram(df, x='roi_anualizado', nbins=10, title="Histograma ROI")
        fig_hist.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_hist, use_container_width=True)

if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if st.session_state.authenticated:
    with st.sidebar:
        try: st.image("Lavie.png")
        except: pass
        st.divider()
        st.caption(f"Logado: {st.session_state.get('user_name')}")
        
        page_list = ["Nova Simulação", "Histórico", "Dashboard"]
        current = st.session_state.page if st.session_state.page in page_list else "Histórico"
        try: ix = page_list.index(current)
        except: ix = 0
            
        sel = option_menu("Menu", page_list, icons=["calculator", "clock", "graph-up"], default_index=ix)
        st.divider()
        
        if st.button("Sair", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

        if sel != st.session_state.page:
            st.session_state.page = sel
            if sel == "Nova Simulação": manual_reset()
            st.rerun()

    if st.session_state.page == "Nova Simulação": render_new_simulation_page()
    elif st.session_state.page == "Histórico": render_history_page()
    elif st.session_state.page == "Ver Simulação": render_view_simulation_page()
    elif st.session_state.page == "Dashboard": render_dashboard_page()
else:
    render_login_page()
