import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Trade Tracker Pro", layout="wide", page_icon="📈")

# --- DICIONÁRIO DE PRODUTOS E SUBPRODUTOS ---
MAPA_PRODUTOS = {
    "Renda Fixa": ["Emissão Bancária", "Crédito Privado", "Títulos Públicos", "Letras Fin/LIG", "Ofertas Públicas", "Tesouro Direto", "Compromissadas"],
    "Renda Variável": ["Ações", "Produto Estruturado", "Direito de subscrição", "L&S", "Termo"],
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
def formatar_brl(valor):
    if valor is None: return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def init_db():
    conn = sqlite3.connect("operacoes_financeiras.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            assessor TEXT,
            conta TEXT,
            produto TEXT,
            subproduto TEXT,
            ativo TEXT,
            tipo_operacao TEXT,
            volume REAL,
            roa_global REAL,
            comissao REAL
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
    df = pd.read_sql("SELECT * FROM operacoes", conn)
    conn.close()
    if not df.empty:
        df['data_hora'] = pd.to_datetime(df['data_hora'], dayfirst=True)
        df['mes_ano'] = df['data_hora'].dt.strftime('%m/%Y')
    return df

def excluir_registro(id_registro):
    conn = sqlite3.connect("operacoes_financeiras.db")
    c = conn.cursor()
    c.execute("DELETE FROM operacoes WHERE id = ?", (id_registro,))
    conn.commit()
    conn.close()

# --- INTERFACE PRINCIPAL ---
def main():
    init_db()
    st.title("📈 Trade Tracker Pro | Analytics")
    
    if 'form_reset' not in st.session_state:
        st.session_state.form_reset = 0

    df_raw = carregar_dados()
    lista_assessores = ["Amanda Ramos", "Bruno Miceli", "João Viegas", "Julio Rodriguez", "Marcio Ventura", "Ronaldo Azevedo"]

    # --- BARRA LATERAL (FILTROS) ---
    st.sidebar.header("🔍 Filtros de Performance")
    
    filtro_assessor = st.sidebar.selectbox("Selecionar Assessor", ["Todos"] + lista_assessores)
    
    meses_disponiveis = ["Todos"]
    if not df_raw.empty:
        meses_disponiveis += sorted(df_raw['mes_ano'].unique().tolist(), reverse=True)
    filtro_mes = st.sidebar.selectbox("Selecionar Mês/Ano", meses_disponiveis)

    # --- REGISTRO DE OPERAÇÃO ---
    with st.expander("➕ Registrar Nova Operação", expanded=False):
        key_suffix = str(st.session_state.form_reset)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            assessor = st.selectbox("Assessor", lista_assessores, index=None, placeholder="Assessor", key="as"+key_suffix)
            conta = st.text_input("Conta / Cliente", key="ct"+key_suffix)
            produto_sel = st.selectbox("Produto", list(MAPA_PRODUTOS.keys()), index=None, key="pr"+key_suffix)
        
        with col2:
            opcoes_sub = MAPA_PRODUTOS.get(produto_sel, [])
            subproduto_sel = st.selectbox("Subproduto", opcoes_sub, index=None, key="sb"+key_suffix)
            ativo = st.text_input("Ativo (Ticker)", key="at"+key_suffix)
            tipo_op = st.selectbox("Tipo", ["Compra", "Venda"], index=None, key="tp"+key_suffix)
        
        with col3:
            volume = st.number_input("Volume (R$)", min_value=0.0, format="%.2f", key="vl"+key_suffix)
            roa_global = st.number_input("ROA Global (%)", min_value=0.0, format="%.2f", key="ro"+key_suffix)
            
            # Regra Consórcio
            taxa_decimal = roa_global / 100
            if produto_sel == "Consórcio":
                div = 12 if subproduto_sel == "Imóvel" else (6 if subproduto_sel == "Auto" else 1)
                comissao_calc = volume * (taxa_decimal / div)
            else:
                comissao_calc = volume * taxa_decimal
            
            st.info(f"Comissão: {formatar_brl(comissao_calc)}")
            
            if st.button("Salvar Registro", type="primary", use_container_width=True):
                if all([assessor, conta, produto_sel, subproduto_sel, ativo, tipo_op]) and volume > 0:
                    salvar_dados({
                        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "assessor": assessor, "conta": conta, "produto": produto_sel,
                        "subproduto": subproduto_sel, "ativo": ativo.upper(),
                        "tipo_operacao": tipo_op, "volume": volume,
                        "roa_global": taxa_decimal, "comissao": comissao_calc
                    })
                    st.success("Salvo!")
                    st.session_state.form_reset += 1
                    st.rerun()

    # --- LÓGICA DE FILTRAGEM ---
    df_filtrado = df_raw.copy()
    if not df_filtrado.empty:
        if filtro_assessor != "Todos":
            df_filtrado = df_filtrado[df_filtrado['assessor'] == filtro_assessor]
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['mes_ano'] == filtro_mes]

    # --- DASHBOARD DE PERFORMANCE ---
    if not df_filtrado.empty:
        st.markdown("---")
        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        vol_total = df_filtrado['volume'].sum()
        com_total = df_filtrado['comissao'].sum()
        roa_medio = (com_total / vol_total * 100) if vol_total > 0 else 0
        num_ops = len(df_filtrado)

        c1.metric("Volume Total", formatar_brl(vol_total))
        c2.metric("Receita Estimada", formatar_brl(com_total))
        c3.metric("ROA Médio do Período", f"{roa_medio:.4f}%")
        c4.metric("Qtd. Operações", num_ops)

        # GRÁFICOS
        st.markdown("### 📊 Análise de Alocação")
        g1, g2 = st.columns(2)

        with g1:
            fig_prod = px.pie(df_filtrado, values='volume', names='produto', title="Distribuição por Produto", hole=0.4)
            st.plotly_chart(fig_prod, use_container_width=True)

        with g2:
            df_sub = df_filtrado.groupby('subproduto')['volume'].sum().reset_index().sort_values('volume', ascending=True)
            fig_sub = px.bar(df_sub, x='volume', y='subproduto', orientation='h', title="Volume por Subproduto", color='volume', color_continuous_scale='Blues')
            st.plotly_chart(fig_sub, use_container_width=True)

        # TABELA
        st.markdown("### 📝 Histórico Detalhado")
        st.dataframe(
            df_filtrado.sort_values('data_hora', ascending=False),
            column_config={
                "data_hora": "Data/Hora",
                "roa_global": st.column_config.NumberColumn("ROA (%)", format="%.4f"),
                "volume": st.column_config.NumberColumn("Volume", format="R$ %.2f"),
                "comissao": st.column_config.NumberColumn("Comissão", format="R$ %.2f"),
                "mes_ano": None # Esconde coluna auxiliar
            },
            use_container_width=True, hide_index=True
        )
        
        # Gestão de Exclusão na Sidebar
        st.sidebar.markdown("---")
        id_del = st.sidebar.number_input("ID para excluir", min_value=0, step=1)
        if st.sidebar.button("Excluir Registro", type="secondary"):
            excluir_registro(id_del)
            st.rerun()
    else:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")

if __name__ == "__main__":
    main()