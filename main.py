import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_option_menu import option_menu
from dateutil.relativedelta import relativedelta 
import utils
from ui_components import display_full_results
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="Simulador Financeiro",
    page_icon="Lavie1.png",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://www.transparenttextures.com/patterns/handmade-paper.png");
    background-repeat: repeat;
}
</style>
""", unsafe_allow_html=True)


DEFAULT_STATE = {
    'authenticated': False,
    'user_name': '',
    'page': "Nova Simulação",
    
    'current_step': 1,
    'results_ready': False,
    'show_results_page': False,
    'simulation_saved': False,
    
    'client_name': "", 
    'client_code': "", 
    'annual_interest_rate': 12.0, 
    'spe_percentage': 65.0,
    'total_contribution': 100000.0, 
    'num_months': 24, 
    'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 
    'construction_cost_m2': 3500.0, 
    'value_m2': 10000.0, 
    'area_exchange_percentage': 20.0,
    'aportes': [], 
    
    'new_aporte_date': datetime.today().date(),
    'new_aporte_value': 0.0,
    'parcelado_total_valor': 0.0,
    'parcelado_num_parcelas': 1,
    'parcelado_data_inicio': datetime.today().date(),
    
    'simulation_results': {},
    'simulation_to_view': None,
    'simulation_to_edit': None,
    'editing_row': None,
    'confirming_delete': None,
    'save_error': None
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

worksheets = utils.init_gsheet_connection()

def check_authentication():
    if not st.session_state.authenticated:
        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            st.image("Lavie.png", use_column_width=True)
            st.title("Login")
            st.markdown("---")
            
            try:
                creds = st.secrets["credentials"]
                users_dict = creds.get("users", creds) 
                user_list = list(users_dict.keys())
            except Exception:
                st.error("Erro ao carregar usuários do secrets.toml")
                st.stop()

            selected_user = st.selectbox("Usuário", user_list, index=None, placeholder="Selecione...")
            password = st.text_input("Senha", type="password")

            if st.button("Entrar", type="primary", use_container_width=True):
                if selected_user and password:
                    if password == users_dict.get(selected_user):
                        st.session_state.authenticated = True
                        st.session_state.user_name = selected_user
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.warning("Preencha todos os campos.")
        st.stop()
check_authentication() 


def reset_simulation_form():
    """Reseta apenas os dados do formulário de simulação."""
    keys_to_reset = [
        'client_name', 'client_code', 'annual_interest_rate', 'spe_percentage',
        'total_contribution', 'num_months', 'start_date', 'project_end_date',
        'land_size', 'construction_cost_m2', 'value_m2', 'area_exchange_percentage',
        'aportes', 'simulation_results', 'results_ready', 'show_results_page', 
        'simulation_saved', 'current_step'
    ]
    for key in keys_to_reset:
        st.session_state[key] = DEFAULT_STATE[key]
    
    st.session_state.new_aporte_value = 0.0
    st.session_state.parcelado_total_valor = 0.0

with st.sidebar:
    st.image("Lavie.png")
    st.info(f"**Logado como:** {st.session_state.user_name}")
    
    selected = option_menu(
        menu_title=None,
        options=["Nova Simulação", "Carregar", "Histórico", "Dashboard"],
        icons=["plus-circle", "cloud-upload", "clock-history", "graph-up"],
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#E37026"}}
    )
    
    if selected == "Nova Simulação" and st.session_state.page != "Nova Simulação":
        reset_simulation_form()
    
    st.session_state.page = selected

    st.markdown("---")
    if st.button("Sair"):
        st.session_state.authenticated = False
        st.rerun()

def render_new_simulation():
    st.markdown("""
    <style>
        .step-container {display: flex; justify-content: space-between; margin-bottom: 20px;}
        .step-item {text-align: center; width: 33%; color: #666; font-weight: 500;}
        .step-circle {width: 30px; height: 30px; border-radius: 50%; border: 2px solid #666; display: flex; align-items: center; justify-content: center; margin: 0 auto 5px; background: transparent;}
        .step-item.active {color: #E37026;}
        .step-item.active .step-circle {border-color: #E37026; background: #E37026; color: white;}
        .stButton button {width: 100%;}
    </style>
    """, unsafe_allow_html=True)

    if st.session_state.show_results_page:
        st.title("Resultados da Simulação")
        if st.button("Voltar aos Parâmetros"):
            st.session_state.show_results_page = False
            st.rerun()
        
        if st.session_state.results_ready:
            display_full_results(
                st.session_state.simulation_results,
                show_save_button=True, 
                show_download_button=True,
                save_callback=save_simulation,
                is_simulation_saved=st.session_state.simulation_saved
            )
        return

    c1, c2 = st.columns([3, 1])
    c1.title("Nova Simulação")
    if c2.button("Limpar Dados"):
        reset_simulation_form()
        st.rerun()

    step = st.session_state.current_step
    st.markdown(f"""
    <div class="step-container">
        <div class="step-item {'active' if step >= 1 else ''}"><div class="step-circle">1</div>Projeto</div>
        <div class="step-item {'active' if step >= 2 else ''}"><div class="step-circle">2</div>Investidor</div>
        <div class="step-item {'active' if step >= 3 else ''}"><div class="step-circle">3</div>Aportes</div>
    </div>
    """, unsafe_allow_html=True)

    col_form, col_summary = st.columns([2, 1])

    with col_form:
        if step == 1:
            with st.container(border=True):
                st.subheader("1. Dados do Projeto")
                c_a, c_b = st.columns(2)
                c_a.number_input("Área Vendável (m²)", min_value=0, step=100, key="land_size")
                c_a.number_input("Custo Obra (R$/m²)", min_value=0.0, step=100.0, key="construction_cost_m2")
                c_b.number_input("VGV (R$/m²)", min_value=0.0, step=100.0, key="value_m2")
                c_b.number_input("% Permuta", min_value=0.0, max_value=100.0, step=1.0, key="area_exchange_percentage")

        elif step == 2:
            with st.container(border=True):
                st.subheader("2. Dados do Investidor")
                c_a, c_b = st.columns(2)
                c_a.text_input("Nome do Cliente", key="client_name")
                c_a.text_input("Código", key="client_code")
                c_a.number_input("Taxa Juros Anual (%)", min_value=0.0, step=0.1, key="annual_interest_rate")
                c_b.number_input("Participação SPE (%)", min_value=0.0, max_value=100.0, step=1.0, key="spe_percentage")
                c_b.date_input("Fim do Projeto", key="project_end_date")

        elif step == 3:
            with st.container(border=True):
                st.subheader("3. Aportes")
                t1, t2 = st.tabs(["Único", "Parcelado"])
                
                with t1:
                    cc1, cc2, cc3 = st.columns([2,2,1])
                    cc1.date_input("Data", key="new_aporte_date")
                    cc2.number_input("Valor", min_value=0.0, step=10000.0, key="new_aporte_value")
                    cc3.write("‎")
                    if cc3.button("Add"):
                        if st.session_state.new_aporte_value > 0:
                            st.session_state.aportes.append({
                                "date": st.session_state.new_aporte_date,
                                "value": st.session_state.new_aporte_value
                            })
                            st.success("Adicionado!")
                        else:
                            st.warning("Valor > 0")

                with t2:
                    pp1, pp2, pp3 = st.columns(3)
                    pp1.number_input("Total", min_value=0.0, key="parcelado_total_valor")
                    pp2.number_input("Parcelas", min_value=1, key="parcelado_num_parcelas")
                    pp3.date_input("Início", key="parcelado_data_inicio")
                    if st.button("Gerar Parcelas"):
                        if st.session_state.parcelado_total_valor > 0:
                            val = round(st.session_state.parcelado_total_valor / st.session_state.parcelado_num_parcelas, 2)
                            for i in range(st.session_state.parcelado_num_parcelas):
                                st.session_state.aportes.append({
                                    "date": st.session_state.parcelado_data_inicio + relativedelta(months=i),
                                    "value": val
                                })
                            st.success("Parcelas geradas!")

            if st.session_state.aportes:
                st.write("##### Cronograma")
                df_ap = pd.DataFrame(st.session_state.aportes)
                df_ap['date'] = pd.to_datetime(df_ap['date']).dt.date
                st.dataframe(df_ap, use_container_width=True, hide_index=True)
                if st.button("Limpar Lista"):
                    st.session_state.aportes = []
                    st.rerun()

        st.write("---")
        cb, _, cn = st.columns([1, 2, 1])
        if step > 1:
            if cb.button("Voltar"):
                st.session_state.current_step -= 1
                st.rerun()
        
        if step < 3:
            if cn.button("Próximo", type="primary"):
                st.session_state.current_step += 1
                st.rerun()
        else:
            if cn.button("Calcular", type="primary"):
                if not st.session_state.aportes:
                    st.error("Adicione pelo menos um aporte.")
                else:
                    params = {k: st.session_state[k] for k in defaults.keys() if k in st.session_state}
                    params['aportes'] = st.session_state.aportes
                    
                    st.session_state.simulation_results = utils.calculate_financials(params)
                    st.session_state.simulation_results['simulation_id'] = f"sim_{int(datetime.now().timestamp())}"
                    
                    st.session_state.results_ready = True
                    st.session_state.show_results_page = True
                    st.rerun()

    with col_summary:
        with st.container(border=True):
            st.subheader("Resumo")
            try: st.image("Burj.jpeg", use_column_width=True)
            except: pass
            
            total = sum(a['value'] for a in st.session_state.aportes)
            st.metric("Total Aportado", utils.format_currency(total))
            
            vgv = st.session_state.land_size * st.session_state.value_m2
            custo = st.session_state.land_size * st.session_state.construction_cost_m2
            st.metric("VGV Estimado", utils.format_currency(vgv))
            st.metric("Custo Estimado", utils.format_currency(custo))


def render_load_page():
    st.title("Carregar Simulação")
    if not worksheets: st.error("Sem conexão."); return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: st.info("Vazio."); return

    cli = st.selectbox("Cliente", df["client_name"].unique())
    if st.button("Carregar", type="primary"):
        row = df[df["client_name"] == cli].iloc[0]
        
        for k in defaults.keys():
            if k in row:
                val = row[k]
                if isinstance(defaults[k], (int, float)):
                    try: st.session_state[k] = type(defaults[k])(val)
                    except: pass
                elif "date" in k:
                    try: st.session_state[k] = pd.to_datetime(val).date()
                    except: pass
                else:
                    st.session_state[k] = val
        
        sid = row['simulation_id']
        df_ap = utils.load_data_from_sheet(worksheets["aportes"])
        my_aps = df_ap[df_ap['simulation_id'] == sid]
        
        st.session_state.aportes = []
        for _, r in my_aps.iterrows():
            st.session_state.aportes.append({
                "date": pd.to_datetime(r['data_aporte']).date(),
                "value": float(r['valor_aporte'])
            })
            
        st.session_state.page = "Nova Simulação"
        st.session_state.current_step = 3
        st.success("Carregado!")
        st.rerun()

def render_history_page():
    st.title("Histórico")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: return
    
    for _, row in df.sort_values("created_at", ascending=False).iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.metric("Cliente", row['client_name'])
            c2.metric("ROI Anual", f"{row.get('roi_anualizado', 0):.2f}%")
            c3.write(pd.to_datetime(row['created_at']).strftime("%d/%m/%Y"))
            if c4.button("👁️", key=f"v_{row['simulation_id']}"):
                st.session_state.simulation_to_view = row.to_dict()
                st.session_state.page = "Ver Simulação"
                st.rerun()

def render_view_page():
    st.title("Detalhes")
    if st.button("Voltar"): 
        st.session_state.page = "Histórico"
        st.rerun()
        
    sim = st.session_state.simulation_to_view
    if not sim: return
    
    df_ap = utils.load_data_from_sheet(worksheets["aportes"])
    aps = df_ap[df_ap['simulation_id'] == sim['simulation_id']]
    sim['aportes'] = [{'date': r['data_aporte'], 'value': r['valor_aporte']} for _, r in aps.iterrows()]
    
    res = utils.calculate_financials(sim)
    display_full_results(res, show_download_button=True)

def render_dashboard_page():
    st.title("Dashboard")
    if not worksheets: return
    df = utils.load_data_from_sheet(worksheets["simulations"])
    if df.empty: return
    
    c1, c2, c3 = st.columns(3)
    c1.metric("VGV Total", utils.format_currency(df['vgv'].sum()))
    c2.metric("Capital Total", utils.format_currency(df['total_contribution'].sum()))
    c3.metric("Total Simulações", len(df))
    
    st.divider()
    fig = px.bar(df, x='client_name', y='vgv', title="VGV por Cliente")
    st.plotly_chart(fig, use_container_width=True)

def save_simulation():
    if not worksheets: return
    try:
        res = st.session_state.simulation_results
        sid = res['simulation_id']
        
        row = [
            sid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(res.get('client_name', '')), str(res.get('client_code', '')),
            str(st.session_state.user_name),
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
        worksheets["simulations"].append_row(row, value_input_option='USER_ENTERED')
        
        aps_rows = []
        for ap in res.get('aportes', []):
            aps_rows.append([sid, pd.to_datetime(ap['date']).strftime('%Y-%m-%d'), float(ap['value'])])
        
        if aps_rows:
            worksheets["aportes"].append_rows(aps_rows, value_input_option='USER_ENTERED')
            
        st.session_state.simulation_saved = True
        st.toast("Salvo com sucesso!", icon="✅")
        
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

if st.session_state.page == "Nova Simulação": render_new_simulation()
elif st.session_state.page == "Carregar": render_load_page()
elif st.session_state.page == "Histórico": render_history_page()
elif st.session_state.page == "Ver Simulação": render_view_page()
elif st.session_state.page == "Dashboard": render_dashboard_page()
