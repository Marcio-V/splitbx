import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Trade Tracker Pro", layout="wide", page_icon="📈")

# --- FUNÇÃO DE FORMATAÇÃO BR ---
def formatar_brl(valor):
    if valor is None: return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- CAMADA DE DADOS (COM CORREÇÃO AUTOMÁTICA DE COLUNAS) ---
DB_NAME = "operacoes_financeiras.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 1. Cria a tabela base se não existir
    c.execute('''
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
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
    
    # 2. VERIFICAÇÃO DE COLUNA (Migração Automática)
    # Tenta ler a tabela para ver se a coluna 'assessor' existe
    c.execute("PRAGMA table_info(operacoes)")
    colunas = [col[1] for col in c.fetchall()]
    
    if 'assessor' not in colunas:
        st.warning("Atualizando estrutura do banco de dados...")
        c.execute("ALTER TABLE operacoes ADD COLUMN assessor TEXT DEFAULT 'Nao Informado'")
    
    conn.commit()
    conn.close()

def salvar_dados(dados):
    conn = sqlite3.connect(DB_NAME)
    df = pd.DataFrame([dados])
    df.to_sql("operacoes", conn, if_exists="append", index=False)
    conn.close()

def carregar_dados():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM operacoes", conn)
    conn.close()
    return df

# --- LÓGICA DE NEGÓCIO ---
def calcular_comissao(volume, roa_percentual):
    return volume * (roa_percentual / 100)

# --- INTERFACE ---
def main():
    init_db()
    
    st.title("🚀 Registro de Operações Financeiras")
    st.markdown("---")

    st.sidebar.header("Configurações e Filtros")
    df_raw = carregar_dados()

    # Lista de Assessores solicitada
    lista_assessores = [
        "Amanda Ramos", "Bruno Miceli", "João Viegas", 
        "Julio Rodriguez", "Marcio Ventura", "Ronaldo Azevedo"
    ]

    # Formulário de Entrada
    with st.expander("➕ Registrar Nova Operação", expanded=True):
        with st.form("form_operacao", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                assessor = st.selectbox("Assessor", lista_assessores)
                conta = st.text_input("Conta / Cliente")
                produto = st.selectbox("Produto", ["Renda Variável", "Renda Fixa", "Derivativos", "Tesouro"])
            
            with col2:
                subproduto = st.text_input("Subproduto", placeholder="Ex: Ação, FII, Opção")
                ativo = st.text_input("Ativo (Ticker)", placeholder="Ex: PETR4, VALE3")
                tipo_op = st.selectbox("Tipo de Operação", ["Compra", "Venda"])
            
            with col3:
                volume = st.number_input("Volume Financeiro (R$)", min_value=0.0, step=100.0, format="%.2f")
                roa_global = st.number_input("ROA Global (%)", min_value=0.0, max_value=100.0, step=0.01, format="%.2f")
                
                # Cálculo da comissão em tempo real para o preview
                valor_comissao_prev = calcular_comissao(volume, roa_global)
                st.markdown("**Comissão Estimada:**")
                st.info(formatar_brl(valor_comissao_prev))
            
            submit = st.form_submit_button("Salvar Operação")

            if submit:
                if conta and ativo and volume > 0:
                    nova_op = {
                        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "assessor": assessor,
                        "conta": conta,
                        "produto": produto,
                        "subproduto": subproduto,
                        "ativo": ativo.upper(),
                        "tipo_operacao": tipo_op,
                        "volume": volume,
                        "roa_global": roa_global / 100,
                        "comissao": calcular_comissao(volume, roa_global)
                    }
                    salvar_dados(nova_op)
                    st.success(f"Operação registrada por {assessor}!")
                    st.rerun()
                else:
                    st.error("Por favor, preencha os campos obrigatórios (Conta, Ativo e Volume).")

    # DASHBOARD
    if not df_raw.empty:
        # Filtros na Barra Lateral
        st.sidebar.subheader("Filtrar Visão")
        
        # Filtro de Assessor
        assessores_no_db = ["Todos"] + sorted(df_raw["assessor"].unique().tolist())
        filtro_assessor = st.sidebar.selectbox("Por Assessor", assessores_no_db)
        
        # Filtro de Conta
        contas_unicas = ["Todos"] + sorted(df_raw["conta"].unique().tolist())
        filtro_conta = st.sidebar.selectbox("Por Conta", contas_unicas)
        
        # Aplicação dos Filtros
        df_display = df_raw.copy()
        if filtro_assessor != "Todos":
            df_display = df_display[df_display["assessor"] == filtro_assessor]
        if filtro_conta != "Todos":
            df_display = df_display[df_display["conta"] == filtro_conta]

        # KPIs com formatação brasileira
        st.subheader("Indicadores de Performance")
        kpi1, kpi2, kpi3 = st.columns(3)
        
        total_vol = df_display["volume"].sum()
        total_com = df_display["comissao"].sum()
        roa_medio = (total_com / total_vol * 100) if total_vol > 0 else 0

        kpi1.metric("Volume Total", formatar_brl(total_vol))
        kpi2.metric("Comissão Total", formatar_brl(total_com))
        kpi3.metric("ROA Médio", f"{roa_medio:.2f}%".replace(".", ","))

        # Tabela com histórico
        st.subheader("Histórico de Operações")
        st.dataframe(
            df_display.sort_values(by="id", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "assessor": "Assessor",
                "volume": st.column_config.NumberColumn("Volume (R$)", format="R$ %.2f"),
                "roa_global": st.column_config.NumberColumn("ROA (%)", format="%.4f"),
                "comissao": st.column_config.NumberColumn("Comissão (R$)", format="R$ %.2f"),
                "data_hora": "Data/Hora",
                "id": None
            }
        )

        # Download CSV
        csv = df_display.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label="📥 Baixar Base em CSV",
            data=csv,
            file_name=f"operacoes_{datetime.now().strftime('%d_%m_%Y')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Aguardando o primeiro registro para exibir o dashboard.")

if __name__ == "__main__":
    main()