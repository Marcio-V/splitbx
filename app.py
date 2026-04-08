import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Trade Tracker Pro", layout="wide", page_icon="📈")

# --- CSS PARA ESTILIZAÇÃO ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #1e3a8a; }
    [data-testid="stMetricLabel"] { font-size: 0.9rem !important; font-weight: bold; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- DICIONÁRIO DE PRODUTOS ---
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
    if valor is None: return "0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_brl(valor):
    return f"R$ {formatar_br_num(valor)}"

def calcular_gini(df):
    if df.empty or 'produto' not in df.columns: return 0.0
    volumes = df.groupby('produto')['volume'].sum().values
    if len(volumes) <= 1: return 0.0
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
    elif subproduto in ["Oferta Pública de Fundos", "Cetipado / Renda+"]:
        taxa = 0.75 if subproduto == "Oferta Pública de Fundos" else 0.85
        return valor_bruto * taxa * base_especialist
    elif subproduto == "COE":
        return valor_bruto * 0.85 * base_comum
    return valor_bruto

# --- FUNÇÕES DE DADOS (CRÍTICAS PARA PERSISTÊNCIA) ---

def carregar_dados():
    """Lê os dados do Sheets forçando TTL=0 para evitar dados obsoletos no deploy."""
    try:
        df = conn.read(ttl=0) 
        if df is not None and not df.empty:
            df['data_operacao'] = pd.to_datetime(df['data_operacao'])
            df['mes_ano'] = df['data_operacao'].dt.strftime('%m/%Y')
            df['id'] = pd.to_numeric(df['id'], errors='coerce')
            return df
        return pd.DataFrame(columns=["id", "data_hora_registro", "data_operacao", "assessor", "conta", "produto", "subproduto", "ativo", "tipo_operacao", "volume", "roa_global", "comissao", "comissao_liquida"])
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def salvar_dados(novo_registro):
    """Lógica de persistência: Lê a base real antes de salvar para evitar sobrescrita."""
    # 1. Busca a base mais recente da nuvem AGORA
    df_realtime = carregar_dados()
    
    # 2. Gera ID baseado na realidade da planilha
    novo_id = int(df_realtime['id'].max() + 1) if not df_realtime.empty else 1
    novo_registro['id'] = novo_id
    
    # 3. Concatena e remove colunas temporárias/calculadas
    updated_df = pd.concat([df_realtime, pd.DataFrame([novo_registro])], ignore_index=True)
    if 'mes_ano' in updated_df.columns:
        updated_df = updated_df.drop(columns=['mes_ano'])
    
    # 4. Atualiza o Sheets e limpa o cache local
    conn.update(data=updated_df)
    st.cache_data.clear()

def excluir_registro(id_registro):
    """Exclui baseando-se na versão mais recente do Sheets."""
    df_realtime = carregar_dados()
    updated_df = df_realtime[df_realtime['id'] != id_registro]
    if 'mes_ano' in updated_df.columns:
        updated_df = updated_df.drop(columns=['mes_ano'])
    conn.update(data=updated_df)
    st.cache_data.clear()

# --- INTERFACE PRINCIPAL ---
def main():
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

    df_filtrado = df_raw.copy()
    if not df_filtrado.empty:
        if filtro_assessor != "Todos":
            df_filtrado = df_filtrado[df_filtrado['assessor'] == filtro_assessor]
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['mes_ano'] == filtro_mes]

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
            sub_sel = st.selectbox("Subproduto", opcoes_sub, index=None, key="sb"+key_suffix)
            ativo = st.text_input("Ativo (Ticker)", key="at"+key_suffix)
            tipo_op = st.selectbox("Tipo", ["Compra", "Venda"], index=None, key="tp"+key_suffix)
        with col3:
            data_op = st.date_input("Data da Operação", value=datetime.now(), key="dt"+key_suffix)
            volume = st.number_input("Volume (R$)", min_value=0.0, format="%.2f", key="vl"+key_suffix)
            roa_global = st.number_input("ROA Global (%)", min_value=0.0, format="%.2f", key="ro"+key_suffix)
            
            taxa_decimal = roa_global / 100
            comissao_bruta = volume * (taxa_decimal / 12 if sub_sel == "Imóvel" else (taxa_decimal / 6 if sub_sel == "Auto" else taxa_decimal))
            comissao_liq = calcular_comissao_liquida(comissao_bruta, produto_sel, sub_sel)
            
            st.info(f"**Bruta:** {formatar_brl(comissao_bruta)} | **Líquida:** {formatar_brl(comissao_liq)}")
            
            if st.button("Salvar Registro", type="primary", use_container_width=True):
                if all([assessor, conta, produto_sel, sub_sel, ativo, tipo_op]) and volume > 0:
                    salvar_dados({
                        "data_hora_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "data_operacao": data_op.strftime("%Y-%m-%d"),
                        "assessor": assessor, "conta": conta, "produto": produto_sel,
                        "subproduto": sub_sel, "ativo": ativo.upper(),
                        "tipo_operacao": tipo_op, "volume": volume,
                        "roa_global": taxa_decimal, "comissao": comissao_bruta,
                        "comissao_liquida": comissao_liq
                    })
                    st.success("Salvo no Google Sheets!")
                    st.session_state.form_reset += 1
                    st.rerun()

    # --- DASHBOARD & HISTÓRICO ---
    if not df_filtrado.empty:
        st.markdown("---")
        vol_total = df_filtrado['volume'].sum()
        com_liq = df_filtrado['comissao_liquida'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Volume Total", formatar_brl(vol_total))
        c2.metric("Líquida Assessor", formatar_brl(com_liq))
        c3.metric("Índice de Gini", formatar_br_num(calcular_gini(df_filtrado)))
        c4.metric("Nº Operações", len(df_filtrado))

        st.markdown("### 📝 Histórico Detalhado")
        df_vis = df_filtrado.sort_values('data_operacao', ascending=False).copy()
        df_vis = df_vis.rename(columns={'comissao': 'Bruta', 'comissao_liquida': 'Líquida', 'roa_global': 'ROA (%)', 'volume': 'Volume'})
        
        st.dataframe(
            df_vis.style.format({
                'id': '{:.0f}', 
                'conta': '{:.0f}', 
                'Volume': 'R$ {:,.2f}',
                'Bruta': 'R$ {:,.2f}',
                'Líquida': 'R$ {:,.2f}',
                'ROA (%)': '{:.2%}'
            }, decimal=',', thousands='.'),
            column_config={
                "id": st.column_config.NumberColumn("ID", format="%d"),
                "data_operacao": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "data_hora_registro": None, 
                "mes_ano": None
            },
            use_container_width=True, 
            hide_index=True
        )
        
        st.sidebar.markdown("---")
        id_del = st.sidebar.number_input("ID para excluir", min_value=0, step=1)
        if st.sidebar.button("Excluir Registro"):
            excluir_registro(id_del)
            st.rerun()
    else:
        st.warning("Aguardando registros ou filtros...")

if __name__ == "__main__":
    main()