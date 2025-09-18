import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_option_menu import option_menu
from dateutil.relativedelta import relativedelta 
import utils
from ui_components import display_full_results

st.set_page_config(
    page_title="Simulador Financeiro Avançado",
    page_icon="Lavie1.png",
    layout="wide"
)
defaults = {
    'page': "➕ Nova Simulação", 'results_ready': False, 'simulation_results': {},
    'editing_row': None, 'simulation_to_edit': None, 'show_results_page': False,
    'client_name': "", 'client_code': "", 'monthly_interest_rate': 1.0, 'spe_percentage': 50.0,
    'total_contribution': 100000.0, 'num_months': 24, 'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 'construction_cost_m2': 2500.0, 'value_m2': 6000.0, 'area_exchange_percentage': 10.0,
    'aportes': [], 'confirming_delete': None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

worksheets = utils.init_gsheet_connection()


def render_new_simulation_page():
    if 'show_results_page' not in st.session_state:
        st.session_state.show_results_page = False

    def go_to_results():
        st.session_state.show_results_page = True

    def go_to_inputs():
        st.session_state.show_results_page = False

    if st.session_state.show_results_page:
        st.title("Resultados da Simulação")
        
        if st.button("⬅️ Voltar para os Parâmetros"):
            go_to_inputs()
        
        if st.session_state.get('results_ready', False):
            display_full_results(
                st.session_state.simulation_results,
                show_save_button=True,
                show_download_button=True,
                save_callback=save_simulation_callback
            )
        return

    st.title("Nova Simulação Financeira")

    with st.expander("Carregar Simulação Salva", expanded=False):
        if worksheets and worksheets.get("simulations"):
            df_simulations = utils.load_data_from_sheet(worksheets["simulations"])
            
            if not df_simulations.empty:
                client_list = df_simulations["client_name"].unique().tolist()
                selected_client_to_load = st.selectbox(
                    "Selecione o cliente para carregar os dados da sua última simulação",
                    options=client_list, index=None, placeholder="Escolha um cliente..."
                )
                
                if st.button("Carregar Dados do Cliente"):
                    if selected_client_to_load:
                        with st.spinner("Carregando dados..."):
                            client_sims = df_simulations[df_simulations['client_name'] == selected_client_to_load]
                            latest_sim = client_sims.sort_values(by="created_at", ascending=False).iloc[0]
                            
                            for key, value in latest_sim.items():
                                if key in st.session_state:
                                    if isinstance(st.session_state[key], float):
                                        st.session_state[key] = float(value)
                                    elif isinstance(st.session_state[key], int):
                                        st.session_state[key] = int(value)
                                    elif isinstance(st.session_state[key], type(datetime.today().date())):
                                        st.session_state[key] = pd.to_datetime(value).date()
                                    else:
                                        st.session_state[key] = value
                            
                            df_aportes_all = utils.load_data_from_sheet(worksheets["aportes"])
                            sim_id = latest_sim['simulation_id']
                            aportes_do_cliente = df_aportes_all[df_aportes_all['simulation_id'] == sim_id]
                            
                            st.session_state.aportes = []
                            for _, row in aportes_do_cliente.iterrows():
                                st.session_state.aportes.append({
                                    "data": pd.to_datetime(row['data_aporte']).date(),
                                    "valor": float(row['valor_aporte'])
                                })
                            
                            st.success(f"Dados e {len(st.session_state.aportes)} aportes carregados para '{selected_client_to_load}'.")
                            st.rerun()

    def add_aporte_callback():
        if st.session_state.new_aporte_value > 0:
            st.session_state.aportes.append({"data": st.session_state.new_aporte_date, "valor": st.session_state.new_aporte_value})
            st.session_state.new_aporte_value = 0.0 # Limpa o campo
        else:
            st.warning("O valor do aporte deve ser maior que zero.")

    with st.expander("Lançamento de Aportes", expanded=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.date_input("Data do Aporte", key="new_aporte_date")
        c2.number_input("Valor do Aporte", min_value=0.0, step=500.0, format="%.2f", key="new_aporte_value")
        with c3:
            st.write("‎")
            st.button("Adicionar Aporte", on_click=add_aporte_callback, use_container_width=True)

        if st.session_state.aportes:
            st.divider()
            st.subheader("Aportes a Simular")
            aportes_df = pd.DataFrame(st.session_state.aportes).sort_values(by="data").reset_index(drop=True)
            aportes_df_display = aportes_df.copy()
            aportes_df_display.index += 1
            aportes_df_display["data"] = pd.to_datetime(aportes_df_display["data"]).dt.strftime('%d/%m/%Y')
            aportes_df_display["valor"] = aportes_df_display["valor"].apply(utils.format_currency)
            st.dataframe(aportes_df_display, use_container_width=True)
            
            if st.button("Limpar Todos os Aportes", type="secondary"):
                st.session_state.aportes = []
                st.rerun()
    with st.expander("Parâmetros Gerais da Simulação", expanded=True):
        st.subheader("Dados do Investidor e Projeto")
        col1, col2 = st.columns(2)
        total_aportes = sum(a['valor'] for a in st.session_state.aportes)

        with col1:
            st.text_input("Nome do Cliente", key="client_name")
            st.text_input("Código do Cliente", key="client_code")
            st.metric("Valor Total dos Aportes", utils.format_currency(total_aportes))
        with col2:
            st.date_input("Data de Início (Primeiro Aporte)", value=st.session_state.aportes[0]['data'] if st.session_state.aportes else datetime.today().date(), key="start_date", disabled=True)
            st.date_input("Data Final do Projeto", key="project_end_date")

        st.divider()
        st.subheader("Dados do Projeto Imobiliário")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Tamanho do Terreno (m²)", min_value=0, step=100, key="land_size")
            st.number_input("Custo da Obra por m²", min_value=0.0, step=100.0, format="%.2f", key="construction_cost_m2")
            st.number_input("Taxa de Juros Mensal (%)", min_value=0.0, step=0.1, format="%.2f", key="monthly_interest_rate")
        with c2:
            st.number_input("Valor de Venda do m²", min_value=0.0, step=100.0, format="%.2f", key="value_m2")
            st.number_input("Participação na SPE (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="spe_percentage")
            st.slider("% de Troca de Área", 0.0, 100.0, key="area_exchange_percentage", format="%.1f%%")

    st.divider()
    if st.button("📈 Calcular Resultado Completo", use_container_width=True, type="primary"):
        if not st.session_state.aportes:
            st.warning("Adicione pelo menos um aporte para calcular.")
        else:
            with st.spinner("Realizando cálculos..."):
                params = {k: st.session_state[k] for k in defaults.keys()}
                params['aportes'] = [{'date': a['data'], 'value': a['valor']} for a in st.session_state.aportes]
                
                st.session_state.simulation_results = utils.calculate_financials(params)
                st.session_state.results_ready = True
                go_to_results()
                st.rerun()
    
def save_simulation_callback():
    if not worksheets or not worksheets.get("simulations") or not worksheets.get("aportes"):
        st.error("Conexão com as planilhas não disponível.")
        return

    with st.spinner("Salvando simulação..."):
        results = st.session_state.simulation_results
        sim_id = f"sim_{int(datetime.now().timestamp())}"
        
        main_data = [
            sim_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.client_name, st.session_state.client_code,
            results.get('total_contribution', 0), results.get('num_months', 0),
            st.session_state.monthly_interest_rate, st.session_state.spe_percentage,
            st.session_state.land_size, st.session_state.construction_cost_m2,
            st.session_state.value_m2, st.session_state.area_exchange_percentage,
            results.get('vgv', 0), results.get('total_construction_cost', 0),
            results.get('final_operational_result', 0), results.get('valor_participacao', 0),
            results.get('resultado_final_investidor', 0),
            results.get('roi', 0), results.get('roi_anualizado', 0),
            results.get('valor_corrigido', 0),
            st.session_state.start_date.strftime('%Y-%m-%d'), 
            st.session_state.project_end_date.strftime('%Y-%m-%d')
        ]
        worksheets["simulations"].append_row(main_data, value_input_option='USER_ENTERED')
        
        aportes_data = []
        for aporte in st.session_state.aportes:
            aportes_data.append([
                sim_id,
                aporte['data'].strftime('%Y-%m-%d'),
                aporte['valor']
            ])
        worksheets["aportes"].append_rows(aportes_data, value_input_option='USER_ENTERED')

        st.cache_data.clear()
        st.toast("✅ Simulação salva com sucesso!", icon="🎉")

def render_history_page():
    st.title("🗂️ Histórico de Simulações")
    if not worksheets or not worksheets.get("simulations"):
        st.error("Conexão com a planilha de simulações não disponível.")
        return

    df_simulations = utils.load_data_from_sheet(worksheets["simulations"])

    if df_simulations.empty:
        st.info("Nenhuma simulação salva encontrada.")
        return

    client_list = ["Todos"] + df_simulations["client_name"].unique().tolist()
    selected_client = st.selectbox("Filtre por cliente:", client_list)

    filtered_df = df_simulations if selected_client == "Todos" else df_simulations[df_simulations["client_name"] == selected_client]

    for index, row in filtered_df.sort_values(by="created_at", ascending=False).iterrows():
        with st.container(border=True):
            row_index = row.get('row_index', index)
            sim_id = row.get('simulation_id', '')

            c1, c2, c3, c4, c5, c6 = st.columns([2.5, 3, 2, 4, 0.8, 0.8])
            c1.metric("Cliente", row.get('client_name', 'N/A'))
            created_at = pd.to_datetime(row.get('created_at')).strftime("%d/%m/%Y %H:%M")
            c2.metric("Data", created_at)
            c3.metric("ROI Anualizado", f"{row.get('roi_anualizado', 0):.2f}%")
            c4.metric("VGV", utils.format_currency(row.get('vgv', 0)))
            
            if c5.button("📝", key=f"edit_{row_index}", help="Editar simulação"):
                st.session_state.editing_row = row_index
                st.session_state.simulation_to_edit = row.to_dict()
                st.session_state.page = "📝 Editar Simulação"
                st.rerun()
            
            if c6.button("🗑️", key=f"del_{row_index}", help="Excluir simulação"):
                st.session_state.confirming_delete = row_index 
                st.rerun()

            if st.session_state.get('confirming_delete') == row_index:
                st.warning(f"**Tem certeza que deseja excluir a simulação de '{row.get('client_name')}'?** Essa ação não pode ser desfeita.")
                btn_c1, btn_c2 = st.columns(2)
                if btn_c1.button("Sim, excluir permanentemente", key=f"confirm_del_{row_index}", type="primary"):
                    with st.spinner("Excluindo simulação e aportes..."):
                        worksheets["simulations"].delete_rows(int(row_index))
                        
                        if sim_id and worksheets.get("aportes"):
                            ws_aportes = worksheets["aportes"]
                            df_aportes = utils.load_data_from_sheet(ws_aportes)
                            aportes_to_delete = df_aportes[df_aportes['simulation_id'] == sim_id]
                            for idx_to_del in sorted(aportes_to_delete['row_index'].tolist(), reverse=True):
                                ws_aportes.delete_rows(int(idx_to_del))

                        st.cache_data.clear()
                        st.session_state.confirming_delete = None
                        st.toast("Simulação excluída com sucesso!", icon="✅")
                        st.rerun()
                
                if btn_c2.button("Cancelar", key=f"cancel_del_{row_index}"):
                    st.session_state.confirming_delete = None
                    st.rerun()

            with st.expander("Ver resultado completo"):
                with st.spinner("Carregando detalhes..."):
                    sim_data = row.to_dict()
                    df_aportes_all = utils.load_data_from_sheet(worksheets["aportes"])
                    aportes_sim = df_aportes_all[df_aportes_all['simulation_id'] == sim_id]
                    
                    aportes_list = []
                    for _, aporte_row in aportes_sim.iterrows():
                        aportes_list.append({
                            'date': pd.to_datetime(aporte_row['data_aporte']).date(),
                            'value': float(aporte_row['valor_aporte'])
                        })
                    sim_data['aportes'] = aportes_list
                    full_results = utils.calculate_financials(sim_data)
                    display_full_results(full_results, show_download_button=True)

def render_edit_page():
    st.title("📝 Editando Simulação")
    if 'simulation_to_edit' not in st.session_state or st.session_state.simulation_to_edit is None:
        st.warning("Nenhuma simulação selecionada para edição.")
        if st.button("Voltar para o Histórico"):
            st.session_state.page = "🗂️ Histórico de Simulações"
            st.rerun()
        return

    sim = st.session_state.simulation_to_edit
    st.subheader(f"Editando Simulação de: **{sim.get('client_name', 'N/A')}**")
    st.info("Atenção: A edição de aportes individuais não está disponível nesta tela. Para isso, carregue a simulação na página 'Nova Simulação'.")

    with st.container(border=True):
        st.subheader("Parâmetros do Investidor e Projeto")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Nome do Cliente", value=sim.get('client_name'), key="edit_client_name")
            st.text_input("Código do Cliente", value=sim.get('client_code'), key="edit_client_code")
            st.number_input("Taxa de Juros Mensal (%)", value=float(sim.get('monthly_interest_rate',0)), key="edit_monthly_interest_rate")
            st.number_input("Participação na SPE (%)", value=float(sim.get('spe_percentage',0)), key="edit_spe_percentage")
        with c2:
            st.number_input("Tamanho do Terreno (m²)", value=int(sim.get('land_size',0)), key="edit_land_size")
            st.number_input("Custo da Obra por m²", value=float(sim.get('construction_cost_m2',0)), key="edit_construction_cost_m2")
            st.number_input("Valor de Venda do m²", value=float(sim.get('value_m2',0)), key="edit_value_m2")
            st.slider("% de Troca de Área", 0.0, 100.0, value=float(sim.get('area_exchange_percentage',0)), key="edit_area_exchange_percentage")
    
    if st.button("💾 Salvar Alterações", use_container_width=True, type="primary"):
        with st.spinner("Recalculando e salvando..."):
            sim_id = sim.get('simulation_id')

            df_aportes_all = utils.load_data_from_sheet(worksheets["aportes"])
            aportes_do_cliente = df_aportes_all[df_aportes_all['simulation_id'] == sim_id]
            aportes_list = [{'date': pd.to_datetime(r['data_aporte']).date(), 'value': float(r['valor_aporte'])} for _, r in aportes_do_cliente.iterrows()]

            params = sim.copy()
            params.update({
                'client_name': st.session_state.edit_client_name,
                'client_code': st.session_state.edit_client_code,
                'monthly_interest_rate': st.session_state.edit_monthly_interest_rate,
                'spe_percentage': st.session_state.edit_spe_percentage,
                'land_size': st.session_state.edit_land_size,
                'construction_cost_m2': st.session_state.edit_construction_cost_m2,
                'value_m2': st.session_state.edit_value_m2,
                'area_exchange_percentage': st.session_state.edit_area_exchange_percentage,
                'aportes': aportes_list
            })
            new_results = utils.calculate_financials(params)

            main_data_updated = [
                sim_id, pd.to_datetime(sim.get('created_at')).strftime("%Y-%m-%d %H:%M:%S"),
                new_results['client_name'], new_results['client_code'],
                new_results.get('total_contribution', 0), new_results.get('num_months', 0),
                new_results['monthly_interest_rate'], new_results['spe_percentage'],
                new_results['land_size'], new_results['construction_cost_m2'], new_results['value_m2'],
                new_results['area_exchange_percentage'], new_results.get('vgv', 0),
                new_results.get('total_construction_cost', 0), new_results.get('final_operational_result', 0),
                new_results.get('valor_participacao', 0), new_results.get('resultado_final_investidor', 0),
                new_results.get('roi', 0), new_results.get('roi_anualizado', 0), new_results.get('valor_corrigido', 0),
                pd.to_datetime(sim.get('start_date')).strftime('%Y-%m-%d'), 
                pd.to_datetime(sim.get('project_end_date')).strftime('%Y-%m-%d')
            ]
            
            row_to_edit = st.session_state.editing_row
            worksheets["simulations"].update(f'A{row_to_edit}:V{row_to_edit}', [main_data_updated])

            st.cache_data.clear()
            st.session_state.editing_row = None
            st.session_state.simulation_to_edit = None
            st.session_state.page = "🗂️ Histórico de Simulações"
            st.toast("Simulação atualizada com sucesso!", icon="🎉")
            st.rerun()

def render_dashboard_page():
    st.title("📊 Dashboard de Simulações")
    if worksheets and worksheets.get("simulations"):
        df = utils.load_data_from_sheet(worksheets["simulations"])
    else:
        st.error("Conexão com a planilha de simulações não disponível.")
        return

    if df.empty:
        st.info("Ainda não há dados para exibir no dashboard.")
        return
        
    st.subheader("Indicadores Gerais")
    col1, col2, col3 = st.columns(3)
    vgv_total = df['vgv'].sum()
    roi_medio = df['roi_anualizado'].mean()
    col1.metric("VGV Total Simulado", utils.format_currency(vgv_total))
    col2.metric("ROI Anualizado Médio", f"{roi_medio:.2f}%")
    col3.metric("Total de Simulações", len(df))
    st.divider()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Últimas Simulações")
        cols_to_display = ['created_at', 'client_name', 'roi_anualizado', 'vgv']
        df_display = df[cols_to_display].copy()
        df_display['created_at'] = pd.to_datetime(df_display['created_at']).dt.strftime('%d/%m/%Y')
        df_display['roi_anualizado'] = df_display['roi_anualizado'].apply(lambda x: f"{x:.2f}%")
        df_display['vgv'] = df_display['vgv'].apply(utils.format_currency)
        st.dataframe(df_display.sort_values(by="created_at", ascending=False).head(5), hide_index=True, use_container_width=True)

    with col2:
        st.subheader("Simulações por Mês")
        df['created_at'] = pd.to_datetime(df['created_at'])
        simulations_per_month = df['created_at'].dt.to_period('M').value_counts().sort_index()
        simulations_per_month.index = simulations_per_month.index.strftime('%Y-%m')
        st.bar_chart(simulations_per_month)

with st.sidebar:
    st.image("Lavie.png")
    st.markdown("<br>", unsafe_allow_html=True)
    
    page_options = ["Nova Simulação", "Histórico", "Dashboard"]
    page_icons = ["plus-circle", "list-task", "bar-chart-fill"]
    
    if st.session_state.get('editing_row') is not None:
        if "Editar Simulação" not in page_options:
            page_options.append("Editar Simulação")
            page_icons.append("pencil-square")
        default_index = page_options.index("Editar Simulação")
    else:
        page_map = {"➕ Nova Simulação": "Nova Simulação", "🗂️ Histórico de Simulações": "Histórico", "📊 Dashboard": "Dashboard"}
        current_page_title = page_map.get(st.session_state.page, "Nova Simulação")
        default_index = page_options.index(current_page_title)

    selected_page_key = option_menu(
        menu_title="Menu Principal", options=page_options, icons=page_icons,
        menu_icon="cast", default_index=default_index, orientation="vertical"
    )
    
    page_map_to_state = {
        "Nova Simulação": "➕ Nova Simulação", "Histórico": "🗂️ Histórico de Simulações",
        "Dashboard": "📊 Dashboard", "Editar Simulação": "📝 Editar Simulação"
    }
    
    new_page_state = page_map_to_state.get(selected_page_key)

    if st.session_state.page != new_page_state:
        if st.session_state.page == "📝 Editar Simulação":
            st.session_state.editing_row = None
            st.session_state.simulation_to_edit = None
        
        st.session_state.page = new_page_state
        st.rerun()

    if selected_page_key != "Editar Simulação" and st.session_state.get('editing_row') is not None:
        st.session_state.editing_row = None
        st.session_state.simulation_to_edit = None
        st.rerun()

if st.session_state.page == "➕ Nova Simulação":
    render_new_simulation_page()
elif st.session_state.page == "🗂️ Histórico de Simulações":
    render_history_page()
elif st.session_state.page == "📝 Editar Simulação":
    render_edit_page()
elif st.session_state.page == "📊 Dashboard":
    render_dashboard_page()
