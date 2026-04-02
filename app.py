import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px
import io
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Trade Tracker Pro", layout="wide", page_icon="📈")

# --- CSS PARA ESTILIZAÇÃO DE KPIs ---
st.markdown("""
    <style>
    /* Reduz o tamanho da fonte dos valores nos st.metric */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
    /* Opcional: Reduz o tamanho do label (título) do KPI */
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DICIONÁRIO DE PRODUTOS E SUBPRODUTOS ---
MAPA_PRODUTOS = {
    "Renda Fixa": ["Emissão Bancária", "Crédito Privado", "Títulos Públicos", "Letras Fin/LIG", "Ofertas Públicas", "Tesouro Direto", "Compromissadas"],
    "Renda Variável": ["Ações", "Produto Estruturado", "Direito de subscrição", "L&S", "Termo"],
    "Alternativo": ["COE"],
    "Fundos": ["Cetipado / Renda+", "Oferta Pública de Fundos", "Fundos"],
    "Internacional": ["Equity", "Bonds", "Treasury", "CDs", "Mutual Funds", "Notes"],
    "Eqseed": ["Oferta Pública"],
    "MB": ["Renda Fixa Digital"],
    "Crédito": ["Clean", "Home Equity", "Capital de giro", "Com garantia"],
    "Consórcio": ["Auto", "Imóvel"],
    "Seguro": ["Vida"],
    "Previdência": ["PGBL", "VGBL"]
}

# --- FUNÇÕES AUXILIARES ---
def formatar_br_num(valor):
    """Formata números para o padrão brasileiro: 1.234,56"""
    if valor is None: return "0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_brl(valor):
    """Formata moeda para o padrão brasileiro: R$ 1.234,56"""
    return f"R$ {formatar_br_num(valor)}"

def calcular_gini(df):
    volumes = df.groupby('produto')['volume'].sum().values
    if len(volumes) <= 1: return 1.0
    volumes = np.sort(volumes)
    n = len(volumes)
    index = np.arange(1, n + 1)
    return (np.sum((2 * index - n - 1) * volumes)) / (n * np.sum(volumes))

def calcular_comissao_liquida(valor_bruto, produto, subproduto):
    base_comum = 0.80 * 0.79
    base_especialist = 0.70 * 0.79
    if produto == "Renda Variável":
        return valor_bruto * 0.75 * 0.85 * base_especialist
    elif produto == "Renda Fixa":
        return valor_bruto * 0.95 * 0.85 * base_comum
    elif subproduto == "Oferta Pública de Fundos":
        return valor_bruto * 0.75 * 0.85 * base_especialist
    elif subproduto == "Cetipado / Renda+":
        return valor_bruto * 0.85 * base_especialist
    elif subproduto == "COE":
        return valor_bruto * 0.85 * base_comum
    return valor_bruto

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio_Operacoes')
    return output.getvalue()

def init_db():
    conn = sqlite3.connect("operacoes_financeiras.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora_registro TEXT,
            data_operacao TEXT,
            assessor TEXT,
            conta TEXT,
            produto TEXT,
            subproduto TEXT,
            ativo TEXT,
            tipo_operacao TEXT,
            volume REAL,
            roa_global REAL,
            comissao REAL,
            comissao_liquida REAL
        )
    ''')
    conn.commit()
    conn.close()

def salvar_dados(dados):
    conn = sqlite3.connect("operacoes_financeiras.db")
    df = pd.DataFrame([dados])
    df.to_sql("operacoes", conn, if_exists="append", index=False)
    conn.close()

def carregar_dados():
    conn = sqlite3.connect("operacoes_financeiras.db")
    try:
        df = pd.read_sql("SELECT * FROM operacoes", conn)
        if not df.empty:
            df['data_operacao'] = pd.to_datetime(df['data_operacao'])
            df['mes_ano'] = df['data_operacao'].dt.strftime('%m/%Y')
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def excluir_registro(id_registro):
    conn = sqlite3.connect("operacoes_financeiras.db")
    c = conn.cursor()
    c.execute("DELETE FROM operacoes WHERE id = ?", (id_registro,))
    conn.commit()
    conn.close()

# --- INTERFACE PRINCIPAL ---
def main():
    init_db()
    st.title("📈 Trade Tracker Pro | Master Analytics")
    
    if 'form_reset' not in st.session_state:
        st.session_state.form_reset = 0

    df_raw = carregar_dados()
    lista_assessores = ["Amanda Ramos", "Bruno Miceli", "João Viegas", "Julio Rodriguez", "Marcio Ventura", "Ronaldo Azevedo"]

    # --- BARRA LATERAL ---
    st.sidebar.header("🔍 Filtros & Exportação")
    filtro_assessor = st.sidebar.selectbox("Selecionar Assessor", ["Todos"] + lista_assessores)
    
    meses_disponiveis = ["Todos"]
    if not df_raw.empty:
        meses_disponiveis += sorted(df_raw['mes_ano'].unique().tolist(), reverse=True)
    filtro_mes = st.sidebar.selectbox("Selecionar Mês/Ano", meses_disponiveis)

    # --- LÓGICA DE FILTRAGEM ---
    df_filtrado = df_raw.copy()
    if not df_filtrado.empty:
        if filtro_assessor != "Todos":
            df_filtrado = df_filtrado[df_filtrado['assessor'] == filtro_assessor]
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['mes_ano'] == filtro_mes]

    if not df_filtrado.empty:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📥 Exportar Dados")
        excel_data = to_excel(df_filtrado)
        st.sidebar.download_button(
            label="Baixar Relatório Excel",
            data=excel_data,
            file_name=f"relatorio_trades_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # --- REGISTRO DE OPERAÇÃO ---
    with st.expander("➕ Registrar Nova Operação", expanded=False):
        key_suffix = str(st.session_state.form_reset)
        col1, col2, col3 = st.columns(3)
        with col1:
            assessor = st.selectbox("Assessor", lista_assessores, index=None, key="as"+key_suffix)
            conta = st.text_input("Conta / Cliente", key="ct"+key_suffix)
            produto_sel = st.selectbox("Produto", list(MAPA_PRODUTOS.keys()), index=None, key="pr"+key_suffix)
        with col2:
            opcoes_sub = MAPA_PRODUTOS.get(produto_sel, [])
            subproduto_sel = st.selectbox("Subproduto", opcoes_sub, index=None, key="sb"+key_suffix)
            ativo = st.text_input("Ativo (Ticker)", key="at"+key_suffix)
            tipo_op = st.selectbox("Tipo", ["Compra", "Venda"], index=None, key="tp"+key_suffix)
        with col3:
            data_op = st.date_input("Data da Operação", value=datetime.now(), key="dt"+key_suffix)
            volume = st.number_input("Volume (R$)", min_value=0.0, format="%.2f", key="vl"+key_suffix)
            roa_global = st.number_input("ROA Global (%)", min_value=0.0, format="%.2f", key="ro"+key_suffix)
            
            taxa_decimal = roa_global / 100
            if produto_sel == "Consórcio":
                div = 12 if subproduto_sel == "Imóvel" else (6 if subproduto_sel == "Auto" else 1)
                comissao_bruta = volume * (taxa_decimal / div)
            else:
                comissao_bruta = volume * taxa_decimal
            
            comissao_liq = calcular_comissao_liquida(comissao_bruta, produto_sel, subproduto_sel)
            st.info(f"**Bruta:** {formatar_brl(comissao_bruta)} | **Líquida:** {formatar_brl(comissao_liq)}")
            
            if st.button("Salvar Registro", type="primary", use_container_width=True):
                if all([assessor, conta, produto_sel, subproduto_sel, ativo, tipo_op]) and volume > 0:
                    salvar_dados({
                        "data_hora_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "data_operacao": data_op.strftime("%Y-%m-%d"),
                        "assessor": assessor, "conta": conta, "produto": produto_sel,
                        "subproduto": subproduto_sel, "ativo": ativo.upper(),
                        "tipo_operacao": tipo_op, "volume": volume,
                        "roa_global": taxa_decimal, "comissao": comissao_bruta,
                        "comissao_liquida": comissao_liq
                    })
                    st.success("Salvo!")
                    st.session_state.form_reset += 1
                    st.rerun()

    # --- DASHBOARD ---
    if not df_filtrado.empty:
        st.markdown("---")
        
        vol_total = df_filtrado['volume'].sum()
        com_total_bruta = df_filtrado['comissao'].sum()
        com_total_liq = df_filtrado['comissao_liquida'].sum()
        num_ops = len(df_filtrado)
        
        roa_medio_real = (com_total_bruta / vol_total * 100) if vol_total > 0 else 0
        eficiencia = (com_total_liq / com_total_bruta * 100) if com_total_bruta > 0 else 0
        gini_score = calcular_gini(df_filtrado)
        payback_esforco = (com_total_liq / num_ops) if num_ops > 0 else 0
        velocity = (num_ops / (vol_total / 1_000_000)) if vol_total > 0 else 0

        # LINHA 1: KPIs Principais
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Volume Total", formatar_brl(vol_total))
        c2.metric("Líquida Assessor", formatar_brl(com_total_liq))
        c3.metric("Payback de Esforço", formatar_brl(payback_esforco), help="Receita líquida média gerada por operação realizada.")
        c4.metric("ROA Médio Global", f"{formatar_br_num(roa_medio_real)}%")

        # LINHA 2: Deep Analytics
        st.markdown("#### 🧬 Deep Analytics: Gestão e Eficiência")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Eficiência de Conversão", f"{formatar_br_num(eficiencia)}%", help="Percentual da comissão bruta que sobra líquida.")
        k2.metric("Velocity (Giro)", formatar_br_num(velocity), help="Quantidade de operações para cada R$ 1MM transacionado.")
        k3.metric("Índice de Gini", formatar_br_num(gini_score), help="0 = Diversificado | 1 = Concentrado em um único produto.")
        k4.info("Concentrado" if gini_score > 0.7 else "Diversificado")

        # LINHA 3: Tabelas de Pareto e Segmento
        st.markdown("---")
        col_pareto, col_segmento = st.columns(2)
        
        with col_pareto:
            st.write("**Concentração de Receita (Pareto por Assessor)**")
            pareto_df = df_filtrado.groupby('assessor')['comissao_liquida'].sum().sort_values(ascending=False).reset_index()
            pareto_df['Participação %'] = (pareto_df['comissao_liquida'] / com_total_liq * 100).round(2)
            st.dataframe(
                pareto_df.style.format({
                    'comissao_liquida': 'R$ {:,.2f}',
                    'Participação %': '{:,.2f}%'
                }, decimal=',', thousands='.'), 
                hide_index=True, use_container_width=True
            )

        with col_segmento:
            st.write("**Ticket Médio e ROA por Segmento**")
            segmento_stats = df_filtrado.groupby('produto').agg({
                'volume': 'mean',
                'comissao': 'sum'
            }).reset_index()
            vol_por_prod = df_filtrado.groupby('produto')['volume'].sum()
            segmento_stats['ROA %'] = (segmento_stats['comissao'] / vol_por_prod.values * 100)
            segmento_stats = segmento_stats.rename(columns={'volume': 'Ticket Médio (R$)'}).drop(columns=['comissao'])
            st.dataframe(
                segmento_stats.style.format({
                    'Ticket Médio (R$)': 'R$ {:,.2f}', 
                    'ROA %': '{:,.2f}%'
                }, decimal=',', thousands='.'), 
                hide_index=True, use_container_width=True
            )

        # Gráficos
        st.markdown("### 📊 Visualização de Performance")
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            df_rank_com = df_filtrado.groupby('assessor')['comissao_liquida'].sum().reset_index().sort_values('comissao_liquida', ascending=True)
            fig_rank_com = px.bar(df_rank_com, x='comissao_liquida', y='assessor', orientation='h', title="Ranking: Comissão Líquida por Assessor", color='comissao_liquida', color_continuous_scale='Greens')
            st.plotly_chart(fig_rank_com, use_container_width=True)
        with r2c2:
            fig_pizza = px.pie(df_filtrado, values='volume', names='produto', title="Alocação por Produto (%)", hole=0.4)
            st.plotly_chart(fig_pizza, use_container_width=True)

        # --- TABELA DETALHADA (HISTÓRICO) COM FORMATAÇÃO SOLICITADA ---
        st.markdown("### 📝 Histórico Detalhado")
        
        # Preparando a visualização com .style.format()
        df_visualizacao = df_filtrado.sort_values('data_operacao', ascending=False).copy()
        
        # Renomeando internamente apenas para o display (Bruta/Líquida) conforme seu pedido anterior
        df_visualizacao = df_visualizacao.rename(columns={
            'comissao': 'Bruta',
            'comissao_liquida': 'Líquida',
            'roa_global': 'ROA (%)',
            'volume': 'Volume'
        })

        st.dataframe(
            df_visualizacao.style.format({
                'Volume': 'R$ {:,.2f}',
                'Bruta': 'R$ {:,.2f}',
                'Líquida': 'R$ {:,.2f}',
                'ROA (%)': '{:.2%}' # Converte decimal 0.05 em 5,00%
            }, decimal=',', thousands='.'),
            column_config={
                "data_operacao": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "data_hora_registro": None, 
                "mes_ano": None
            },
            use_container_width=True, 
            hide_index=True
        )
        
        # Sidebar Exclusão
        st.sidebar.markdown("---")
        id_del = st.sidebar.number_input("ID para excluir", min_value=0, step=1)
        if st.sidebar.button("Excluir Registro"):
            excluir_registro(id_del)
            st.rerun()
    else:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")

if __name__ == "__main__":
    main()