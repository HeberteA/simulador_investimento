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
        
st.set_page_config(
    page_title="Simulador Financeiro",
    page_icon="Lavie1.png",
    layout="wide"
)

defaults = {
    'page': "Nova Simulação", 'results_ready': False, 'simulation_results': {},
    'editing_row': None, 'simulation_to_edit': None, 'show_results_page': False,
    'client_name': "", 'client_code': "", 'annual_interest_rate': 12.0, 'spe_percentage': 65.0,
    'total_contribution': 100000.0, 'num_months': 24, 'start_date': datetime.today().date(),
    'project_end_date': (datetime.today() + relativedelta(years=2)).date(),
    'land_size': 1000, 'construction_cost_m2': 3500.0, 'value_m2': 10000.0, 'area_exchange_percentage': 20.0,
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
        if 'save_error' in st.session_state and st.session_state.save_error:
            st.error(st.session_state.save_error)
            del st.session_state.save_error
        
        if st.button("Voltar para os Parâmetros"):
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
                                    if key == 'monthly_interest_rate' and 'annual_interest_rate' in st.session_state:
                                        st.session_state['annual_interest_rate'] = float(value)
                                    elif key in st.session_state:
                                        if isinstance(st.session_state[key], float): st.session_state[key] = float(value)
                                        elif isinstance(st.session_state[key], int): st.session_state[key] = int(value)
                                        elif isinstance(st.session_state[key], type(datetime.today().date())): st.session_state[key] = pd.to_datetime(value).date()
                                        else: st.session_state[key] = value
                            
                            df_aportes_all = utils.load_data_from_sheet(worksheets["aportes"])
                            sim_id = latest_sim['simulation_id']
                            aportes_do_cliente = df_aportes_all[df_aportes_all['simulation_id'] == sim_id]
                            
                            st.session_state.aportes = []
                            
                            try:
                                for _, row in aportes_do_cliente.iterrows():
                                    st.session_state.aportes.append({
                                        "data": pd.to_datetime(row['data_aporte']).date(),
                                        "valor": float(row['valor_aporte'])
                                    })
                            except KeyError:
                                st.error(f"Erro de 'KeyError' ao carregar aportes (Sim_ID: {sim_id}). As colunas 'data_aporte' ou 'valor_aporte' não foram encontradas no DataFrame.")
                            except Exception as e:
                                st.warning(f"Aporte com dados inválidos na planilha (Sim_ID: {sim_id}). Pulando linha. Erro: {e}")

                            
                            st.success(f"Dados e {len(st.session_state.aportes)} aportes carregados para '{selected_client_to_load}'.")
                            st.rerun()

    def add_aporte_callback():
        if st.session_state.new_aporte_value > 0:
            st.session_state.aportes.append({"data": st.session_state.new_aporte_date, "valor": st.session_state.new_aporte_value})
            st.session_state.new_aporte_value = 0.0
        else:
            st.warning("O valor do aporte deve ser maior que zero.")
            
            
    def add_aportes_parcelados_callback():
        total_valor = st.session_state.get('parcelado_total_valor', 0.0)
        num_parcelas = st.session_state.get('parcelado_num_parcelas', 1)
        data_inicio = st.session_state.get('parcelado_data_inicio', datetime.today().date())
        
        if total_valor <= 0:
            st.warning("O valor total do aporte deve ser maior que zero.")
            return
        if num_parcelas <= 0:
            st.warning("O número de parcelas deve ser pelo menos 1.")
            return
            
        valor_parcela = round(total_valor / num_parcelas, 2)
        
        novos_aportes = []
        for i in range(num_parcelas):
            data_vencimento = data_inicio + relativedelta(months=i)
            novos_aportes.append({"data": data_vencimento, "valor": valor_parcela})
            
        st.session_state.aportes.extend(novos_aportes)
        st.success(f"{num_parcelas} aportes parcelados adicionados com sucesso!")
        st.session_state.parcelado_total_valor = 0.0
        st.session_state.parcelado_num_parcelas = 1

    with st.expander("Lançamento de Aportes", expanded=True):
        
        tab_unico, tab_parcelado = st.tabs(["📈 Aporte Único", "🗓️ Aporte Parcelado"])

        with tab_unico:
            st.subheader("Adicionar Aporte Único")
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.date_input("Data de Vencimento", key="new_aporte_date")
            c2.number_input("Valor do Aporte", min_value=0.0, step=10000.0, format="%.2f", key="new_aporte_value")
            with c3:
                st.write("‎") 
                st.button("Adicionar Aporte", on_click=add_aporte_callback, use_container_width=True, key="btn_aporte_unico")

        with tab_parcelado:
            st.subheader("Adicionar Aportes Parcelados")
            p1, p2, p3 = st.columns(3)
            p1.number_input("Valor Total do Aporte", min_value=0.0, step=10000.0, format="%.2f", key="parcelado_total_valor")
            p2.number_input("Número de Parcelas", min_value=1, step=1, key="parcelado_num_parcelas")
            p3.date_input("Data do Primeiro Vencimento", key="parcelado_data_inicio")
            
            st.button("Adicionar Aportes Parcelados", on_click=add_aportes_parcelados_callback, use_container_width=True, key="btn_aporte_parcelado")

        if st.session_state.aportes:
            st.divider()

            st.subheader("Cronograma de Vencimentos")
            
            try:
                aportes_df = pd.DataFrame(st.session_state.aportes)
                
                if not aportes_df.empty:
                    aportes_df['data'] = pd.to_datetime(aportes_df['data'])
                    aportes_df = aportes_df.sort_values(by="data").reset_index(drop=True)
                
                edited_df = st.data_editor(
                    aportes_df,
                    column_config={
                        "data": st.column_config.DateColumn(
                            "Data de Vencimento",
                            format="DD/MM/YYYY",
                            step=1,
                        ),
                        "valor": st.column_config.NumberColumn(
                            "Valor (R$)",
                            format="R$ %.2f",
                        ),
                    },
                    use_container_width=True,
                    num_rows="dynamic",
                    key="aportes_editor"
                )
                
                st.session_state.aportes = edited_df.to_dict('records')
            
            except Exception as e:
                st.error(f"Erro ao processar aportes: {e}")
                st.warning("Se o erro persistir, tente 'Limpar Todos os Aportes'.")
            
            if st.button("Limpar Todos os Aportes", type="secondary"):
                st.session_state.aportes = []
                st.rerun()

    with st.expander("Parâmetros Gerais", expanded=True):
        
        tab_invest, tab_proj = st.tabs(["Investidor e Datas", "Parâmetros do Projeto"])
        
        with tab_invest:
            st.subheader("Dados do Investidor e Prazos")

            current_start_date = datetime.today().date()
            if st.session_state.aportes:
                try:
                    valid_dates = [pd.to_datetime(a['data']).date() for a in st.session_state.aportes if a.get('data')]
                    if valid_dates:
                        current_start_date = min(valid_dates)
                except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime):
                    if 'start_date' in st.session_state:
                        current_start_date = st.session_state.start_date
                    else:
                        pass 

            col1, col2 = st.columns(2)
            total_aportes = sum(a['valor'] for a in st.session_state.aportes if isinstance(a, dict) and a.get('valor'))

            with col1:
                st.text_input("Nome do Cliente", key="client_name")
                st.text_input("Código do Cliente", key="client_code")
                st.metric("Valor Total dos Aportes", utils.format_currency(total_aportes))
            with col2:
                st.date_input("Data de Início (Primeiro Vencimento)", 
                              value=current_start_date, 
                              disabled=True)
                def update_project_end_date():
                    st.session_state.project_end_date = st.session_state.project_end_date_widget

                st.date_input("Data Final do Projeto", 
                              value=st.session_state.project_end_date,
                              key="project_end_date_widget", 
                              on_change=update_project_end_date 
                              )


    with tab_proj:
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Área Vendável (m²)", min_value=0, step=100, key="land_size")
            st.number_input("Custo da Obra por m²", min_value=0.0, step=100.0, format="%.2f", key="construction_cost_m2", help="Custo total de construção dividido pela área do terreno.")
            st.number_input(
                "Taxa de Juros Anual (%)", 
                min_value=0.0, 
                step=0.1, 
                format="%.2f", 
                key="annual_interest_rate",
                help="Taxa de juros nominal anual. O cálculo de juros compostos será feito com base na taxa diária equivalente."
            )
        with c2:
            st.number_input("Valor de Venda do m²", min_value=0.0, step=100.0, format="%.2f", key="value_m2", help="Valor de Venda Geral (VGV) dividido pela área do terreno.")
            st.number_input("Participação na SPE (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="spe_percentage", help="Percentual do resultado do projeto destinado ao investidor.")
            st.slider("% de Troca de Área", 0.0, 100.0, key="area_exchange_percentage", format="%.1f%%", help="Percentual do VGV que será pago em permuta (ex: troca pelo terreno).")

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
    if 'save_error' in st.session_state:
        del st.session_state.save_error

    if not worksheets or not worksheets.get("simulations") or not worksheets.get("aportes"):
        st.session_state.save_error = "Conexão com as planilhas não disponível."
        return

    with st.spinner("Salvando simulação..."):
        results = st.session_state.simulation_results
        
        if not results or 'total_contribution' not in results:
            st.session_state.save_error = "Erro: Resultados da simulação não encontrados. Tente calcular novamente antes de salvar."
            return

        sim_id = f"sim_{int(datetime.now().timestamp())}"
        
        main_data_headers = [
            'simulation_id', 'created_at', 'client_name', 'client_code', 
            'total_contribution', 'num_months', 'annual_interest_rate', 'spe_percentage', 
            'land_size', 'construction_cost_m2', 'value_m2', 'area_exchange_percentage', 
            'vgv', 'total_construction_cost', 'final_operational_result', 
            'valor_participacao', 'resultado_final_investidor', 'roi', 'roi_anualizado', 
            'valor_corrigido', 'start_date', 'project_end_date'
        ]
        
        def safe_date_to_string(date_val, fmt='%Y-%m-%d'):
            if pd.isna(date_val): return ""
            try: return pd.to_datetime(date_val).strftime(fmt)
            except (ValueError, TypeError): return ""

        main_data_values = [
            sim_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(results.get('client_name', '')),
            str(results.get('client_code', '')),
            float(results.get('total_contribution', 0)), 
            int(results.get('num_months', 0)),
            float(results.get('annual_interest_rate', 0)),
            float(results.get('spe_percentage', 0)),
            int(results.get('land_size', 0)),
            float(results.get('construction_cost_m2', 0)),
            float(results.get('value_m2', 0)),
            float(results.get('area_exchange_percentage', 0)),
            float(results.get('vgv', 0)), 
            float(results.get('total_construction_cost', 0)),
            float(results.get('final_operational_result', 0)), 
            float(results.get('valor_participacao', 0)),
            float(results.get('resultado_final_investidor', 0)),
            float(results.get('roi', 0)), 
            float(results.get('roi_anualizado', 0)),
            float(results.get('valor_corrigido', 0)),
            safe_date_to_string(results.get('start_date')), 
            safe_date_to_string(results.get('project_end_date'))
        ]
        
        aportes_data_headers = ['simulation_id', 'data_aporte', 'valor_aporte']
        aportes_data_rows = []
        aportes_list = results.get('aportes', []) 
        
        for aporte in aportes_list:
            if isinstance(aporte, dict) and aporte.get('date') is not None and aporte.get('value', 0) > 0:
                try:
                    aportes_data_rows.append([
                        sim_id,
                        safe_date_to_string(aporte.get('date')),
                        float(aporte.get('value', 0))
                    ])
                except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime):
                    pass 
        
        try:
            ws_sims = worksheets["simulations"]
            sim_values = ws_sims.get_all_values()
            if not sim_values:
                ws_sims.append_row(main_data_headers, value_input_option='USER_ENTERED')
            
            ws_sims.append_row(main_data_values, value_input_option='USER_ENTERED')
            
        except BaseException as e: 
            st.session_state.save_error = f"Erro ao salvar dados principais: {e}"
            return

        try:
            if aportes_data_rows:
                ws_aportes = worksheets["aportes"]
                aporte_values = ws_aportes.get_all_values()
                if not aporte_values:
                    ws_aportes.append_row(aportes_data_headers, value_input_option='USER_ENTERED')
                
                ws_aportes.append_rows(aportes_data_rows, value_input_option='USER_ENTERED')
                
        except BaseException as e:
            st.session_state.save_error = f"Erro ao salvar aportes: {e}"
            return

        st.cache_data.clear() # Limpa o cache após salvar com sucesso
        st.toast("✅ Simulação salva com sucesso!", icon="🎉")

def render_history_page():
    st.title("Histórico de Simulações")
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
                st.session_state.page = "Editar Simulação"
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
                    try:
                        for _, aporte_row in aportes_sim.iterrows():
                             aportes_list.append({
                                 'date': pd.to_datetime(aporte_row['data_aporte']).date(),
                                 'value': float(aporte_row['valor_aporte'])
                             })
                    except KeyError:
                         st.error(f"Erro de 'KeyError' ao carregar aportes (Sim_ID: {sim_id}). As colunas 'data_aporte' ou 'valor_aporte' não foram encontradas no DataFrame.")
                    except Exception as e:
                         st.warning(f"Aporte com dados inválidos na planilha (Sim_ID: {sim_id}). Pulando linha. Erro: {e}")
                    
                    sim_data['aportes'] = aportes_list
                    
                    if 'annual_interest_rate' not in sim_data:
                         sim_data['annual_interest_rate'] = sim_data.get('monthly_interest_rate', 12.0) 
                         
                    full_results = utils.calculate_financials(sim_data)
                    display_full_results(full_results, show_download_button=True)

def render_edit_page():
    st.title("Editando Simulação")
    if 'simulation_to_edit' not in st.session_state or st.session_state.simulation_to_edit is None:
        st.warning("Nenhuma simulação selecionada para edição.")
        if st.button("Voltar para o Histórico"):
            st.session_state.page = "Histórico de Simulações"
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
            default_rate = sim.get('annual_interest_rate', sim.get('monthly_interest_rate', 0))
            st.number_input(
                "Taxa de Juros Anual (%)", 
                value=float(default_rate), 
                key="edit_annual_interest_rate"
            )
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
            
            aportes_list = []
            try:
                for _, r in aportes_do_cliente.iterrows():
                    aportes_list.append({
                        'date': pd.to_datetime(r['data_aporte']).date(), 
                        'value': float(r['valor_aporte'])
                    })
            except KeyError:
                st.error("Erro de 'KeyError' ao ler aportes salvos. Colunas 'data_aporte' ou 'valor_aporte' não encontradas.")
            
            params = sim.copy()
            params.update({
                'client_name': st.session_state.edit_client_name,
                'client_code': st.session_state.edit_client_code,
                'annual_interest_rate': st.session_state.edit_annual_interest_rate, 
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
                new_results['annual_interest_rate'], 
                new_results['spe_percentage'],
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

            st.cache_data.clear() # Limpa o cache após salvar com sucesso
            st.session_state.editing_row = None
            st.session_state.simulation_to_edit = None
            st.session_state.page = "Histórico de Simulações"
            st.toast("Simulação atualizada com sucesso!", icon="🎉")
            st.rerun()

def render_dashboard_page():
    st.title("Dashboard")
    if worksheets and worksheets.get("simulations"):
        df_sim = utils.load_data_from_sheet(worksheets["simulations"])
    else:
        st.error("Conexão com a planilha de simulações não disponível.")
        return
        
    if df_sim.empty:
        st.info("Ainda não há dados para exibir no dashboard.")
        return

    THEME_COLOR = "#E37026"

    st.subheader("Indicadores Chave de Performance (KPIs)")
    k1, k2, k3, k4 = st.columns(4)
    
    total_vgv = df_sim['vgv'].sum()
    avg_roi_anual = df_sim['roi_anualizado'].mean()
    total_investido = df_sim['total_contribution'].sum()
    total_sims = len(df_sim)
    
    k1.metric("VGV Total Simulado", utils.format_currency(total_vgv))
    k2.metric("ROI Anualizado Médio", f"{avg_roi_anual:.2f}%")
    k3.metric("Capital Aportado Total", utils.format_currency(total_investido))
    k4.metric("Total de Simulações", f"{total_sims} simulações")
    
    st.divider()

    st.subheader("Análise de Rentabilidade e Risco")
    c1, c2 = st.columns(2)
    
    with c1:
        fig_hist_roi = px.histogram(
            df_sim, 
            x='roi_anualizado', 
            nbins=20, 
            title="Distribuição do ROI Anualizado",
            labels={'roi_anualizado': 'ROI Anualizado (%)'}
        )
        fig_hist_roi.update_traces(marker_color=THEME_COLOR)
        st.plotly_chart(fig_hist_roi, use_container_width=True)

    with c2:
        fig_scatter_roi = px.scatter(
            df_sim, 
            x='total_contribution', 
            y='roi_anualizado', 
            title="ROI vs. Valor Aportado",
            labels={'total_contribution': 'Valor Total Aportado', 'roi_anualizado': 'ROI Anualizado (%)'},
            hover_data=['client_name'],
            trendline="ols",
            trendline_color_override="red"
        )
        fig_scatter_roi.update_traces(marker_color=THEME_COLOR)
        st.plotly_chart(fig_scatter_roi, use_container_width=True)

    st.divider()
    st.subheader("Análise de Clientes e Projetos")
    c3, c4 = st.columns(2)

    with c3:
        df_client_agg = df_sim.groupby('client_name').agg(
            vgv_total=('vgv', 'sum'),
            aportes_total=('total_contribution', 'sum'),
            roi_medio=('roi_anualizado', 'mean'),
            contagem_sims=('simulation_id', 'count')
        ).reset_index().sort_values(by='aportes_total', ascending=False)
        
        fig_bar_client = px.bar(
            df_client_agg.head(10), 
            x='client_name', 
            y='aportes_total', 
            title="Top 10 Clientes por Valor Total Aportado",
            labels={'client_name': 'Cliente', 'aportes_total': 'Valor Total Aportado'},
            hover_data=['roi_medio', 'contagem_sims'],
            color_discrete_sequence=[THEME_COLOR]
        )
        st.plotly_chart(fig_bar_client, use_container_width=True)

    with c4:
        df_sim['created_at_month'] = pd.to_datetime(df_sim['created_at']).dt.to_period('M').astype(str)
        sims_per_month = df_sim.groupby('created_at_month').agg(
            contagem_sims=('simulation_id', 'count'),
            vgv_total_mes=('vgv', 'sum')
        ).reset_index()
        
        fig_line_time = px.line(
            sims_per_month, 
            x='created_at_month', 
            y='contagem_sims', 
            title="Volume de Simulações ao Longo do Tempo",
            labels={'created_at_month': 'Mês', 'contagem_sims': 'Número de Simulações'},
            markers=True
        )
        fig_line_time.update_traces(line_color=THEME_COLOR)
        st.plotly_chart(fig_line_time, use_container_width=True)

    if worksheets.get("aportes"):
        df_aportes = utils.load_data_from_sheet(worksheets["aportes"])
        if not df_aportes.empty:
            st.divider()
            st.subheader("Análise de Captação (Aportes)")

            date_col = 'data_aporte'
            value_col = 'valor_aporte'

            if date_col not in df_aportes.columns or value_col not in df_aportes.columns:
                st.error("Erro de 'KeyError' no Dashboard. As colunas 'data_aporte' ou 'valor_aporte' não foram encontradas. Verifique a Linha 1 da GSheet 'aportes'.")
                return

            df_aportes[date_col] = pd.to_datetime(df_aportes[date_col])
            df_aportes['mes_aporte'] = df_aportes[date_col].dt.to_period('M').astype(str)
            aportes_agg = df_aportes.groupby('mes_aporte')[value_col].sum().reset_index()

            fig_bar_aportes = px.bar(
                aportes_agg,
                x='mes_aporte',
                y=value_col,
                title="Volume Total de Aportes Recebidos por Mês",
                labels={'mes_aporte': 'Mês', value_col: 'Valor Aportado'},
                color_discrete_sequence=[THEME_COLOR]
            )
            st.plotly_chart(fig_bar_aportes, use_container_width=True)


with st.sidebar:
    st.image("Lavie1.png")
    st.markdown("<br>", unsafe_allow_html=True)
    
    page_options = ["Nova Simulação", "Histórico", "Dashboard"]
    page_icons = ["plus-circle", "list-task", "bar-chart-fill"]
    
    if st.session_state.get('editing_row') is not None:
        if "Editar Simulação" not in page_options:
            page_options.append("Editar Simulação")
            page_icons.append("pencil-square")
        default_index = page_options.index("Editar Simulação")
    else:
        page_map = {"Nova Simulação": "Nova Simulação", "Histórico de Simulações": "Histórico", "Dashboard": "Dashboard"}
        current_page_title = page_map.get(st.session_state.page, "Nova Simulação")
        default_index = page_options.index(current_page_title)

    selected_page_key = option_menu(
        menu_title="Menu Principal", options=page_options, icons=page_icons,
        menu_icon="cast", 
        default_index=default_index, 
        orientation="vertical",
        styles={ 
                "container": {"padding": "5px !important", "background-color": "transparent"},
                "icon": {"font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px"},
                "nav-link-selected": {"background-color": "#E37026"}, 
            }
        
    )
    
    page_map_to_state = {
        "Nova Simulação": "Nova Simulação", "Histórico": "Histórico de Simulações",
        "Dashboard": "Dashboard", "Editar Simulação": "Editar Simulação"
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

if st.session_state.page == "Nova Simulação":
    render_new_simulation_page()
elif st.session_state.page == "Histórico de Simulações":
    render_history_page()
elif st.session_state.page == "Editar Simulação":
    render_edit_page()
elif st.session_state.page == "Dashboard":
    render_dashboard_page()
