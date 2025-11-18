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
    if pd.isna(date_val):
        return ""
    try:
        return pd.to_datetime(date_val).strftime(fmt)
    except (ValueError, TypeError):
        return ""

def update_val(key):
    st.session_state[key] = st.session_state[f"_{key}"]

st.set_page_config(
    page_title="Simulador Financeiro",
    page_icon="Lavie1.png",
    layout="wide"
)

background_texture_css = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://www.transparenttextures.com/patterns/handmade-paper.png");
    background-repeat: repeat;
}
</style>
"""
st.markdown(background_texture_css, unsafe_allow_html=True)

defaults = {
    'page': "Nova Simulação", 'results_ready': False, 'simulation_results': {},
    'editing_row': None, 'simulation_to_edit': None, 'simulation_to_view': None,
    'show_results_page': False,
    'client_name': "", 'client_code': "", 'annual_interest_rate': 12.0, 'spe_percentage': 65.0,
    'total_contribution': 100000.0, 'num_months': 24, 'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 'construction_cost_m2': 3500.0, 'value_m2': 10000.0, 'area_exchange_percentage': 20.0,
    'aportes': [], 'confirming_delete': None, 'simulation_saved': False, 'current_step': 1,
    'new_aporte_date': datetime.today().date(), 'new_aporte_value': 0.0,
    'parcelado_total_valor': 0.0, 'parcelado_num_parcelas': 1,
    'parcelado_data_inicio': datetime.today().date()
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_form_to_defaults():
    for key, value in defaults.items():
        st.session_state[key] = value
    st.session_state.current_step = 1
    st.session_state.show_results_page = False
    st.session_state.results_ready = False

worksheets = utils.init_gsheet_connection()

def render_step_1_projeto():
    with st.container(border=True):
        st.subheader("Etapa 1: Parâmetros do Projeto")
        st.markdown("Defina os dados fundamentais do empreendimento.")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Área Vendável (m²)", min_value=0, step=100, value=st.session_state.land_size, key="_land_size", on_change=update_val, args=('land_size',))
            st.number_input("Custo da Obra por m²", min_value=0.0, step=100.0, format="%.2f", value=st.session_state.construction_cost_m2, key="_construction_cost_m2", on_change=update_val, args=('construction_cost_m2',))
        with c2:
            st.number_input("Valor de Venda do m²", min_value=0.0, step=100.0, format="%.2f", value=st.session_state.value_m2, key="_value_m2", on_change=update_val, args=('value_m2',))
            st.number_input("% de Troca de Área", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", value=st.session_state.area_exchange_percentage, key="_area_exchange_percentage", on_change=update_val, args=('area_exchange_percentage',))

def render_step_2_investidor():
    with st.container(border=True):
        st.subheader("Etapa 2: Dados do Investidor e Prazos")
        st.markdown("Insira as informações do cliente e as condições do investimento.")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Nome do Cliente", value=st.session_state.client_name, key="_client_name", on_change=update_val, args=('client_name',))
            st.text_input("Código do Cliente", value=st.session_state.client_code, key="_client_code", on_change=update_val, args=('client_code',))
            st.number_input("Taxa de Juros Anual (%)", min_value=0.0, step=0.1, format="%.2f", value=st.session_state.annual_interest_rate, key="_annual_interest_rate", on_change=update_val, args=('annual_interest_rate',))
        with c2:
            st.number_input("Participação na SPE (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", value=st.session_state.spe_percentage, key="_spe_percentage", on_change=update_val, args=('spe_percentage',))
            st.date_input("Data Final do Projeto", value=st.session_state.project_end_date, key="_project_end_date", on_change=update_val, args=('project_end_date',))

def render_step_3_aportes():
    def add_aporte_callback():
        if st.session_state._new_aporte_value > 0:
            st.session_state.aportes.append({"data": st.session_state._new_aporte_date, "valor": st.session_state._new_aporte_value})
            st.session_state.new_aporte_value = 0.0 
        else:
            st.warning("Valor deve ser maior que zero.")
            
    def add_parcelado_callback():
        total = st.session_state._parcelado_total_valor
        num = st.session_state._parcelado_num_parcelas
        inicio = st.session_state._parcelado_data_inicio
        if total <= 0 or num < 1:
            st.warning("Verifique os valores.")
            return
        val = round(total / num, 2)
        novos = [{"data": inicio + relativedelta(months=i), "valor": val} for i in range(num)]
        st.session_state.aportes.extend(novos)
        st.success(f"{num} parcelas adicionadas!")

    with st.container(border=True):
        st.subheader("Etapa 3: Lançamento de Aportes")
        st.markdown("Adicione os aportes únicos ou parcelados.")
        st.divider()
        tab1, tab2 = st.tabs(["Aporte Único", "Parcelado"])
        with tab1:
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.date_input("Data", value=st.session_state.new_aporte_date, key="_new_aporte_date", on_change=update_val, args=('new_aporte_date',))
            c2.number_input("Valor", min_value=0.0, step=10000.0, value=st.session_state.new_aporte_value, key="_new_aporte_value", on_change=update_val, args=('new_aporte_value',))
            c3.write("‎"); c3.button("Adicionar", on_click=add_aporte_callback, use_container_width=True)
        with tab2:
            p1, p2, p3 = st.columns(3)
            p1.number_input("Valor Total", min_value=0.0, step=10000.0, value=st.session_state.parcelado_total_valor, key="_parcelado_total_valor", on_change=update_val, args=('parcelado_total_valor',))
            p2.number_input("Nº Parcelas", min_value=1, step=1, value=st.session_state.parcelado_num_parcelas, key="_parcelado_num_parcelas", on_change=update_val, args=('parcelado_num_parcelas',))
            p3.date_input("1º Vencimento", value=st.session_state.parcelado_data_inicio, key="_parcelado_data_inicio", on_change=update_val, args=('parcelado_data_inicio',))
            st.button("Gerar Parcelas", on_click=add_parcelado_callback, use_container_width=True)

        if st.session_state.aportes:
            st.divider()
            st.subheader("Cronograma")
            try:
                df = pd.DataFrame(st.session_state.aportes)
                if not df.empty:
                    df['data'] = pd.to_datetime(df['data'])
                    df = df.sort_values(by="data").reset_index(drop=True)
                    edited = st.data_editor(df, column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")}, use_container_width=True, num_rows="dynamic", key="aportes_editor")
                    st.session_state.aportes = edited.to_dict('records')
            except Exception as e: st.error(f"Erro: {e}")
            if st.button("Limpar Tudo", type="secondary"):
                st.session_state.aportes = []
                st.rerun()

def render_visuals_sidebar():
    st.subheader("Resumo do Projeto")
    st.markdown("---")
    try:
        st.image("Burj.jpeg", caption="Parâmetros do empreendimento.", use_column_width=True)
    except:
        st.caption("Imagem 'Burj.jpeg' não encontrada.")
    st.markdown("---")
    
    total = sum(a['valor'] for a in st.session_state.aportes) if st.session_state.aportes else 0
    st.metric("Total Aportado", utils.format_currency(total))

    try:
        area = float(st.session_state.land_size)
        custo = float(st.session_state.construction_cost_m2)
        valor = float(st.session_state.value_m2)
        vgv = area * valor
        custo_total = area * custo
        st.metric("VGV Preliminar", utils.format_currency(vgv))
        st.metric("Custo Físico", utils.format_currency(custo_total))
        if vgv > 0:
            df = pd.DataFrame([{"Tipo": "VGV", "Val": vgv}, {"Tipo": "Custo", "Val": -custo_total}])
            fig = px.bar(df, x="Tipo", y="Val", color="Tipo", color_discrete_sequence=["#388E3C", "#D32F2F"])
            fig.update_layout(showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=200)
            st.plotly_chart(fig, use_container_width=True)
    except: pass

def render_new_simulation_page():
    st.markdown("""
    <style>
        .step-container {display: flex; justify-content: space-between; margin-bottom: 30px;}
        .step-item {display: flex; flex-direction: column; align-items: center; width: 33%; color: #888;}
        .step-number {width: 30px; height: 30px; border-radius: 50%; border: 2px solid #888; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-bottom: 8px;}
        .step-item.active {color: #E37026; font-weight: bold;}
        .step-item.active .step-number {border-color: #E37026; background-color: #E37026; color: white;}
        .stButton button {width: 100%;}
    </style>
    """, unsafe_allow_html=True)

    if st.session_state.show_results_page:
        st.title("Resultados")
        if st.button("⬅️ Voltar"): 
            st.session_state.show_results_page = False
            st.rerun()
        
        if st.session_state.results_ready:
            display_full_results(st.session_state.simulation_results, show_save_button=True, show_download_button=True, save_callback=save_simulation_callback, is_simulation_saved=st.session_state.simulation_saved)
        return

    c_tit, c_res = st.columns([3, 1])
    c_tit.title("Nova Simulação")
    c_res.write("‎"); 
    if c_res.button("🔄 Limpar"): 
        reset_form_to_defaults()
        st.rerun()

    step = st.session_state.current_step
    st.markdown(f"""
    <div class="step-container">
        <div class="step-item {'active' if step >= 1 else ''}"><div class="step-number">1</div>Projeto</div>
        <div class="step-item {'active' if step >= 2 else ''}"><div class="step-number">2</div>Investidor</div>
        <div class="step-item {'active' if step >= 3 else ''}"><div class="step-number">3</div>Aportes</div>
    </div>""", unsafe_allow_html=True)

    c_form, c_view = st.columns([2, 1.2])
    
    with c_form:
        if step == 1: render_step_1_projeto()
        elif step == 2: render_step_2_investidor()
        elif step == 3: render_step_3_aportes()
        
        c_back, _, c_next = st.columns([1, 2, 1])
        if step > 1:
            if c_back.button("⬅️ Voltar"):
                st.session_state.current_step -= 1
                st.rerun()
        if step < 3:
            if c_next.button("Próximo ➡️", type="primary"):
                st.session_state.current_step += 1
                st.rerun()
        else:
            if c_next.button("🚀 Calcular", type="primary"):
                if not st.session_state.aportes:
                    st.warning("Adicione aportes.")
                else:
                    with st.spinner("Calculando..."):
                        params = {k: st.session_state[k] for k in defaults.keys() if k in st.session_state}
                        aps = []
                        for a in st.session_state.aportes:
                             aps.append({'date': a['data'], 'value': a['valor']})
                        params['aportes'] = aps
                        st.session_state.simulation_results = utils.calculate_financials(params)
                        st.session_state.simulation_results['simulation_id'] = f"gen_{int(datetime.now().timestamp())}"
                        st.session_state.results_ready = True
                        st.session_state.simulation_saved = False
                        st.session_state.show_results_page = True
                        st.rerun()

    with c_view:
        with st.container(border=True):
            render_visuals_sidebar()

def render_login_page():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.image("Lavie.png", use_column_width=True)
        st.title("Simulador Lavie")
        try: user_list = list(st.secrets["credentials"].keys())
        except: st.error("Erro de credenciais."); st.stop()
        user = st.selectbox("Usuário", user_list)
        pwd = st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary"):
            if pwd == st.secrets["credentials"].get(user):
                st.session_state.authenticated = True
                st.session_state.user_name = user
                st.rerun()
            else: st.error("Senha incorreta.")

def save_simulation_callback():
    if not worksheets: return
    try:
        res = st.session_state.simulation_results
        sid = res.get('simulation_id')
        main_data = [
            sid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(res.get('client_name', '')), str(res.get('client_code', '')),
            str(st.session_state.get('user_name', '')),
            float(res.get('total_contribution', 0)), int(res.get('num_months', 0)),
            float(res.get('annual_interest_rate', 0)), float(res.get('spe_percentage', 0)),
            int(res.get('land_size', 0)), float(res.get('construction_cost_m2', 0)),
            float(res.get('value_m2', 0)), float(res.get('area_exchange_percentage', 0)),
            float(res.get('vgv', 0)), float(res.get('total_construction_cost', 0)),
            float(res.get('final_operational_result', 0)), float(res.get('valor_participacao', 0)),
            float(res.get('resultado_final_investidor', 0)), float(res.get('roi', 0)),
            float(res.get('roi_anualizado', 0)), float(res.get('valor_corrigido', 0)),
            pd.to_datetime(res.get('start_date')).strftime('%Y-%m-%d'),
            pd.to_datetime(res.get('project_end_date')).strftime('%Y-%m-%d')
        ]
        worksheets["simulations"].append_row(main_data, value_input_option='USER_ENTERED')
        
        aps_data = []
        for a in res.get('aportes', []):
            aps_data.append([sid, pd.to_datetime(a['date']).strftime('%Y-%m-%d'), float(a['value'])])
        if aps_data: worksheets["aportes"].append_rows(aps_data, value_input_option='USER_ENTERED')
        
        st.session_state.simulation_saved = True
        st.toast("Salvo com sucesso!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def render_history_page():
    st.title("Histórico")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: st.info("Sem histórico."); return
    
    c1, c2 = st.columns(2)
    cli = c1.selectbox("Cliente", ["Todos"] + df["client_name"].unique().tolist())
    if cli != "Todos": df = df[df["client_name"] == cli]

    for idx, row in df.sort_values(by="created_at", ascending=False).iterrows():
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])
            c1.metric("Cliente", row['client_name'])
            c2.metric("Data", pd.to_datetime(row['created_at']).strftime("%d/%m %H:%M"))
            c3.metric("ROI Anual", f"{row.get('roi_anualizado', 0):.2f}%")
            if c4.button("👁️", key=f"v_{idx}"):
                st.session_state.simulation_to_view = row.to_dict()
                st.session_state.page = "Ver Simulação"
                st.rerun()
            if c5.button("🗑️", key=f"d_{idx}"):
                 worksheets["simulations"].delete_rows(int(row['row_index']))
                 st.cache_data.clear(); st.rerun()

def render_view_page():
    st.title("Detalhes")
    if st.button("⬅️ Voltar"): st.session_state.page = "Histórico de Simulações"; st.rerun()
    if not st.session_state.simulation_to_view: return
    
    with st.spinner("Carregando..."):
        sim = st.session_state.simulation_to_view
        df_ap = utils.load_data_from_sheet(worksheets["aportes"])
        aps = df_ap[df_ap['simulation_id'] == sim['simulation_id']]
        sim['aportes'] = [{'date': r['data_aporte'], 'value': r['valor_aporte']} for _, r in aps.iterrows()]
        res = utils.calculate_financials(sim)
        display_full_results(res, show_download_button=True)

def render_load_page():
    st.title("Carregar")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: st.info("Vazio."); return
    
    sel = st.selectbox("Cliente", df["client_name"].unique())
    if st.button("Carregar", type="primary"):
        row = df[df["client_name"] == sel].iloc[0]
        for k, v in row.items(): 
            if k in defaults: st.session_state[k] = v
        st.session_state.page = "Nova Simulação"
        st.session_state.current_step = 3
        st.rerun()

def render_edit_page():
     st.info("Edição simplificada via Histórico em breve.")

def render_dashboard_page():
     st.title("Dashboard")
     if worksheets and worksheets.get("simulations"):
        df_sim = utils.load_data_from_sheet(worksheets["simulations"])
     else: return
     if df_sim.empty: return
     THEME_COLOR = "#E37026"
     k1, k2, k3, k4 = st.columns(4)
     k1.metric("VGV Total", utils.format_currency(df_sim['vgv'].sum()))
     k2.metric("ROI Médio", f"{df_sim['roi_anualizado'].mean():.2f}%")
     k3.metric("Capital Total", utils.format_currency(df_sim['total_contribution'].sum()))
     k4.metric("Simulações", len(df_sim))
     st.divider()
     c1, c2 = st.columns(2)
     with c1:
         fig = px.histogram(df_sim, x='roi_anualizado', nbins=20, title="Distribuição ROI")
         fig.update_traces(marker_color=THEME_COLOR)
         st.plotly_chart(fig, use_container_width=True)

if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    render_login_page()
else:
    with st.sidebar:
        st.image("Lavie.png")
        st.info(f"User: {st.session_state.get('user_name')}")
        
        menu = ["Nova Simulação", "Carregar", "Histórico", "Dashboard"]
        choice = option_menu("Menu", menu, icons=["plus", "upload", "list", "bar-chart"], default_index=0)
        
        if st.session_state.get('page_selection') != choice:
            st.session_state.page = choice
            if choice == "Nova Simulação": reset_form_to_defaults()
            st.rerun()

        if st.button("Sair"):
            st.session_state.authenticated = False
            st.rerun()
            
    if st.session_state.page == "Nova Simulação": render_new_simulation_page()
    elif st.session_state.page == "Carregar": render_load_page()
    elif st.session_state.page == "Histórico": render_history_page()
    elif st.session_state.page == "Ver Simulação": render_view_page()
    elif st.session_state.page == "Dashboard": render_dashboard_page()
