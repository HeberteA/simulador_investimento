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
    'editing_row': None, 'simulation_to_edit': None, 'deleting_row_index': None,
    'client_name': "", 'client_code': "", 'monthly_interest_rate': 1.0, 'spe_percentage': 50.0,
    'total_contribution': 100000.0, 'num_months': 24, 'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 'construction_cost_m2': 2500.0, 'value_m2': 6000.0, 'area_exchange_percentage': 10.0
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

worksheet = utils.init_gsheet_connection()


def render_new_simulation_page():
    # --- LÓGICA DE CONTROLE DE TELA (INPUTS VS. RESULTADOS) ---
    if 'show_results_page' not in st.session_state:
        st.session_state.show_results_page = False

    def go_to_results():
        st.session_state.show_results_page = True

    def go_to_inputs():
        st.session_state.show_results_page = False

    # --- TELA DE RESULTADOS ---
    if st.session_state.show_results_page:
        st.title("📊 Resultados da Simulação")
        
        if st.button("⬅️ Voltar para os Parâmetros"):
            go_to_inputs()
        
        if st.session_state.get('results_ready', False):
            # A função de salvar é definida na tela de inputs e armazenada no session_state
            save_callback_func = st.session_state.get('save_callback_ref')
            display_full_results(
                st.session_state.simulation_results,
                show_save_button=True,
                show_download_button=True,
                save_callback=save_callback_func
            )
        return

    # --- TELA DE INPUTS ---
    st.title("Nova Simulação Financeira")
    
    if 'aportes' not in st.session_state:
        st.session_state.aportes = []

    with st.container(border=True):
        st.subheader("Carregar Simulação Salva)")
      
        df_simulations = utils.load_data_from_sheet(worksheets["simulations"])
        
        if not df_simulations.empty:
            client_list = df_simulations["client_name"].unique().tolist()
            
            selected_client_to_load = st.selectbox(
                "Selecione o cliente para carregar os dados da sua última simulação",
                options=client_list,
                index=None,
                placeholder="Escolha um cliente..."
            )
            
            if st.button("Carregar Dados do Cliente"):
                if selected_client_to_load:
                    with st.spinner("Carregando dados..."):
                        client_sims = df_simulations[df_simulations['client_name'] == selected_client_to_load]
                        latest_sim = client_sims.sort_values(by="created_at", ascending=False).iloc[0]
                        
                        df_aportes_all = utils.load_data_from_sheet(worksheets["aportes"])
                        sim_id = latest_sim['simulation_id']
                        aportes_do_cliente = df_aportes_all[df_aportes_all['simulation_id'] == sim_id]
                        st.session_state.client_name = latest_sim.get('client_name', '')
                        st.session_state.client_code = latest_sim.get('client_code', '')
                        st.session_state.aportes = []
                        for index, row in aportes_do_cliente.iterrows():
                            st.session_state.aportes.append({
                                "data": pd.to_datetime(row['data_aporte']).date(),
                                "valor": float(row['valor_aporte'])
                            })
                        
                        st.success(f"{len(st.session_state.aportes)} aportes carregados para '{selected_client_to_load}'.")
                        st.rerun()

    with st.container(border=True):
        st.subheader("Parâmetros do Investidor")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Nome do Cliente", key="client_name")
            st.number_input("Valor do Aporte Total", min_value=0.0, step=1000.0, key="total_contribution")
            st.date_input("Data de Início (Primeira Parcela)", key="start_date")
        with col2:
            st.text_input("Código do Cliente", key="client_code")
            st.number_input("Quantidade de Meses (Parcelas)", min_value=1, step=1, key="num_months")
            st.date_input("Data Final do Projeto", key="project_end_date")

    with st.container(border=True):
        st.subheader("Dados do Projeto Imobiliário")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Tamanho do Terreno (m²)", min_value=0, step=100, key="land_size")
            st.number_input("Participação na SPE (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="spe_percentage")
            st.number_input("Taxa de Juros Mensal (%)", min_value=0.0, step=0.1, format="%.2f", key="monthly_interest_rate")
        with c2:
            st.number_input("Valor de Venda do m²", min_value=0.0, step=100.0, format="%.2f", key="value_m2")
            st.number_input("Custo da Obra por m²", min_value=0.0, step=100.0, format="%.2f", key="construction_cost_m2")
            st.slider("% de Troca de Área", 0.0, 100.0, key="area_exchange_percentage", format="%.1f%%")

    if st.button("📈 Calcular Resultado Completo", use_container_width=True, type="primary"):
        if not st.session_state.aportes:
            st.warning("Adicione ou carregue pelo menos um aporte para calcular.")
        else:
            with st.spinner("Realizando cálculos..."):
                params = {k: st.session_state[k] for k in st.session_state if isinstance(st.session_state[k], (str, int, float, list, bool, type(None)))}
                params['aportes'] = [{'date': a['data'], 'value': a['valor']} for a in st.session_state.aportes]
                params['project_end_date'] = st.session_state.project_end_date 
                
                st.session_state.simulation_results = utils.calculate_financials(params)
                st.session_state.results_ready = True
                go_to_results()
                st.rerun()
    
def save_simulation_callback():
        if not worksheet:
            st.error("Conexão com a planilha não disponível.")
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
            worksheet.append_row(main_data, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            st.toast("✅ Simulação salva com sucesso!", icon="🎉")

if st.session_state.get('results_ready', False):
    st.divider()
    display_full_results(
        st.session_state.simulation_results,
        show_save_button=True,
        show_download_button=True,
        save_callback=save_simulation_callback
    )

def render_history_page():
    st.title("Histórico de Simulações")
    if not worksheet:
        st.error("Conexão com a planilha não disponível.")
        return

    df_simulations = utils.load_data_from_sheet(worksheet)

    if df_simulations.empty:
        st.info("Nenhuma simulação salva encontrada na planilha.")
        return

    st.subheader("Filtro por Cliente")
    client_list = ["Todos"] + df_simulations["client_name"].unique().tolist()
    selected_client = st.selectbox("Selecione um cliente:", client_list, label_visibility="collapsed")

    if selected_client != "Todos":
        filtered_df = df_simulations[df_simulations["client_name"] == selected_client].copy()
    else:
        filtered_df = df_simulations.copy()

    for index, row in filtered_df.sort_values(by="created_at", ascending=False).iterrows():
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([2.5, 3, 2, 4, 0.8, 0.8])
            c1.metric("Cliente", row.get('client_name', 'N/A'))
            
            created_at_date = pd.to_datetime(row.get('created_at'))
            c2.metric("Data", created_at_date.strftime("%d/%m/%Y") if pd.notnull(created_at_date) else "N/A")
            
            c3.metric("ROI Anualizado", f"{row.get('roi_anualizado', 0):.2f}%")
            c4.metric("VGV", utils.format_currency(row.get('vgv', 0)))
            
            if c5.button("📝", key=f"edit_{row.get('row_index', index)}", help="Editar simulação"):
                st.session_state.editing_row = row.get('row_index', index)
                st.session_state.simulation_to_edit = row.to_dict()
                st.session_state.page = "📝 Editar Simulação"
                st.rerun()
            
            if c6.button("🗑️", key=f"del_{row.get('row_index', index)}", help="Excluir simulação"):
                with st.spinner("Excluindo simulação..."):
                    worksheet.delete_rows(int(row.get('row_index', index)))
                    st.cache_data.clear()
                    st.toast("Simulação excluída com sucesso!", icon="✅")
                    st.rerun()

            with st.expander("Ver resultado completo"):
                sim_data = row.to_dict()
                total_contribution = row.get('total_contribution', 0)
                num_months = row.get('num_months', 0)
                start_date_val = row.get('start_date')

                if pd.notnull(total_contribution) and pd.notnull(num_months) and num_months > 0 and pd.notnull(start_date_val):
                    aportes_list = []
                    valor_parcela = total_contribution / num_months
                    start_date = pd.to_datetime(start_date_val).date()
                    for i in range(int(num_months)):
                        aporte_date = start_date + relativedelta(months=i)
                        aportes_list.append({'date': aporte_date, 'value': valor_parcela})
                    sim_data['aportes'] = aportes_list
                
                display_full_results(sim_data, show_download_button=True)
def render_edit_page():
    st.title("Editando Simulação")
    if st.session_state.editing_row is None or st.session_state.simulation_to_edit is None:
        st.warning("Nenhuma simulação selecionada para edição.")
        return

    sim = st.session_state.simulation_to_edit
    st.subheader("Editando Simulação de: " + sim.get('client_name', 'N/A'))
    
    with st.container(border=True):
        st.subheader("Parâmetros do Investidor")
        start_date_val = pd.to_datetime(sim.get('start_date')).date() if pd.notnull(sim.get('start_date')) else datetime.today().date()
        end_date_val = pd.to_datetime(sim.get('project_end_date')).date() if pd.notnull(sim.get('project_end_date')) else datetime.today().date()

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Nome do Cliente", value=sim.get('client_name'), key="edit_client_name")
            st.number_input("Valor do Aporte Total", value=float(sim.get('total_contribution', 0)), key="edit_total_contribution")
            st.date_input("Data de Início (Primeira Parcela)", value=start_date_val, key="edit_start_date")
        with c2:
            st.text_input("Código do Cliente", value=sim.get('client_code'), key="edit_client_code")
            st.number_input("Quantidade de Meses (Parcelas)", value=int(sim.get('num_months', 1)), min_value=1, key="edit_num_months")
            st.date_input("Data Final do Projeto", value=end_date_val, key="edit_project_end_date")

    if st.button("💾 Salvar Alterações", use_container_width=True, type="primary"):
        with st.spinner("Recalculando e salvando..."):
            sim = st.session_state.simulation_to_edit

            aportes_list = []
            valor_parcela = st.session_state.edit_total_contribution / st.session_state.edit_num_months
            for i in range(st.session_state.edit_num_months):
                aporte_date = st.session_state.edit_start_date + relativedelta(months=i)
                aportes_list.append({'date': aporte_date, 'value': valor_parcela})

            params = sim.copy()
            params.update({
                'client_name': st.session_state.edit_client_name,
                'client_code': st.session_state.edit_client_code,
                'total_contribution': st.session_state.edit_total_contribution,
                'num_months': st.session_state.edit_num_months,
                'start_date': st.session_state.edit_start_date,
                'project_end_date': st.session_state.edit_project_end_date,
                'aportes': aportes_list
            })
            new_results = utils.calculate_financials(params)

            main_data_updated = [
                sim.get('simulation_id'), sim.get('created_at').strftime("%Y-%m-%d %H:%M:%S"),
                st.session_state.edit_client_name, st.session_state.edit_client_code,
                new_results.get('total_contribution', 0), new_results.get('num_months', 0),
                sim.get('monthly_interest_rate'), sim.get('spe_percentage'), sim.get('land_size'),
                sim.get('construction_cost_m2'), sim.get('value_m2'), sim.get('area_exchange_percentage'),
                new_results.get('vgv', 0), new_results.get('total_construction_cost', 0),
                new_results.get('final_operational_result', 0), new_results.get('valor_participacao', 0),
                new_results.get('resultado_final_investidor', 0), new_results.get('roi', 0),
                new_results.get('roi_anualizado', 0), new_results.get('valor_corrigido', 0),
                st.session_state.edit_start_date.strftime('%Y-%m-%d'),
                st.session_state.edit_project_end_date.strftime('%Y-%m-%d')
            ]
            worksheet.update(f'A{st.session_state.editing_row}:V{st.session_state.editing_row}', [main_data_updated])

            if sim_id:
                cell_list = ws_aportes.findall(sim_id, in_column=1)
                rows_to_delete = sorted([cell.row for cell in cell_list], reverse=True)
                for row_idx in rows_to_delete:
                    ws_aportes.delete_rows(row_idx)
            for aporte in aportes_list:
                new_aporte_data = [sim_id, aporte['date'].strftime('%Y-%m-%d'), aporte['value']]
                ws_aportes.append_row(new_aporte_data, value_input_option='USER_ENTERED')

            
    
            st.cache_data.clear()
            st.session_state.editing_row = None
            st.session_state.simulation_to_edit = None
            st.session_state.page = "🗂️ Histórico de Simulações"
            st.toast("Simulação atualizada com sucesso!", icon="🎉")
            st.rerun()

def render_dashboard_page():
    st.title("Dashboard de Simulações")
    if worksheets:
        df = utils.load_data_from_sheet(worksheets["simulations"])
    else:
        df = pd.DataFrame()

    if df.empty:
        st.info("Ainda não há dados para exibir.")
        return
        
    st.subheader("Indicadores Gerais")
    col1, col2, col3 = st.columns(3)
    vgv_total = df['vgv'].sum() if 'vgv' in df.columns else 0
    roi_medio = df['roi_anualizado'].mean() if 'roi_anualizado' in df.columns else 0
    col1.metric("VGV Total Simulado", utils.format_currency(vgv_total))
    col2.metric("ROI Anualizado Médio", f"{roi_medio:.2f}%")
    col3.metric("Total de Simulações", len(df))
    st.divider()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Últimas Simulações")
        cols_to_display = ['created_at', 'client_name', 'roi_anualizado', 'vgv']
        existing_cols = [col for col in cols_to_display if col in df.columns]
        if 'created_at' in existing_cols:
            st.dataframe(df[existing_cols].sort_values(by="created_at", ascending=False).head(5), hide_index=True, use_container_width=True)
        else:
            st.dataframe(df[existing_cols].head(5), hide_index=True, use_container_width=True)
    with col2:
        if 'created_at' in df.columns:
            st.subheader("Simulações por Mês")
            df['created_at'] = pd.to_datetime(df['created_at'])
            simulations_per_month = df['created_at'].dt.to_period('M').value_counts().sort_index()
            simulations_per_month.index = simulations_per_month.index.strftime('%Y-%m')
            st.bar_chart(simulations_per_month)

with st.sidebar:
    st.image("Lavie.png")
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    page_map = {
        "Nova Simulação": "➕ Nova Simulação", "Histórico": "🗂️ Histórico de Simulações",
        "Dashboard": "📊 Dashboard", "Editar Simulação": "📝 Editar Simulação"
    }
    page_options = ["Nova Simulação", "Histórico", "Dashboard"]
    page_icons = ["house-add", "card-list", "kanban"]

    if 'editing_row' in st.session_state and st.session_state.editing_row is not None:
        if "Editar Simulação" not in page_options:
            page_options.append("Editar Simulação")
            page_icons.append("pencil-square")
        st.session_state.page = "📝 Editar Simulação"

    try:
        current_page_key = [key for key, value in page_map.items() if value == st.session_state.page][0]
        default_index = page_options.index(current_page_key)
    except (ValueError, IndexError):
        default_index = 0
    
    selected_page_key = option_menu(
        menu_title="Menu Principal", options=page_options, icons=page_icons,
        menu_icon="cast", default_index=default_index, orientation="vertical"
    )
    
    new_page = page_map[selected_page_key]
    if st.session_state.page != new_page:
        st.session_state.results_ready = False
        st.session_state.simulation_results = {}
        
        if st.session_state.page == "📝 Editar Simulação":
            st.session_state.editing_row = None
            st.session_state.simulation_to_edit = None

        st.session_state.page = new_page
        st.rerun()
    if selected_page_key != "Editar Simulação" and st.session_state.editing_row is not None:
        st.session_state.editing_row = None
        st.session_state.simulation_to_edit = None
        st.rerun()

    st.divider()

if st.session_state.page == "➕ Nova Simulação":
    render_new_simulation_page()
elif st.session_state.page == "🗂️ Histórico de Simulações":
    render_history_page()
elif st.session_state.page == "📝 Editar Simulação":
    render_edit_page()
elif st.session_state.page == "📊 Dashboard":
    render_dashboard_page()
