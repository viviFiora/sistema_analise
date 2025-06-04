import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import numpy as np
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode



filial = ["SC", "PR", "RS"]

meses_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']



def formatar_cnpj(cnpj):
    cnpj = "".join(filter(str.isdigit, cnpj))

    if len(cnpj) == 11:
        return f'{cnpj[:3]}.{cnpj[3:6]}.{cnpj[6:9]}-{cnpj[9:]}'
    elif len(cnpj) == 14:
        return f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'
    else:
        return cnpj

def cargar_df (ruta):
    df_original = pd.read_csv(ruta, dayfirst=True)
    df = df_original.copy()
    columnas = ["Data", "Nfe", "Cnpj", "Cliente", "Valor", "Tipo", "Vendedor", "Comissao", "Simples", "Frete", "Porc_frete"]
    df.columns = columnas
    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    df["Vendedor"] = df["Vendedor"].str.upper()
    #df["Nfe"] = df["Nfe"].str.replace(r"\D","",regex=True)
    df["Valor"] = df["Valor"].astype({"Valor" : "str"})
    df["Valor"] = df["Valor"].str.replace("None","").replace("nan","")
    df["Valor"] = df["Valor"].str.strip()
    df["Valor"] = df["Valor"].str.replace(r"R\$","", regex=True)
    df["Valor"] = df["Valor"].str.replace(r",",".", regex=True)
    df["Valor"] = df["Valor"].str.replace(r"\.(?=\d+\.)", "", regex=True)
    df["Valor"] = df["Valor"].replace("",np.nan)
    df = df.astype({
    "Nfe": np.int64,
    "Valor" : np.float64
    })
    df.set_index("Data", inplace=True)
    df["Ano"] = df.index.year
    df["Mes"] = df.index.month
    df["Nome_Mes"] = df["Mes"].apply(lambda x: meses_pt[x - 1])
    df["Nome_Mes"] = pd.Categorical(df["Nome_Mes"], categories=meses_pt, ordered=True)
    df = df.sort_values(["Cnpj", "Data"])

    df["Cliente_Novo"] = ~df.duplicated(subset=["Cnpj","Vendedor"], keep="first")
    
    return df

def actualizar_df(df, año, tipo, vendedor):
    if "Todos" not in vendedor:
        df = df[df["Vendedor"] == vendedor]

    df = df[df["Tipo"] == tipo]
    df = df[df["Ano"] == año]

    df_nuevo = df.copy()

    df_nuevo["CNPJ"] = df_nuevo["Cnpj"].astype(str).str.replace(r"\D", "", regex=True)
    df_nuevo = df_nuevo[df_nuevo["CNPJ"].str.len().isin([11, 14])].copy()
    df_nuevo["CNPJ"] = df_nuevo["CNPJ"].apply(formatar_cnpj)

    df_nuevo.drop(columns=["Cnpj"], inplace=True,errors="ignore")

    df_nuevo = df_nuevo.sort_values("Nome_Mes")

    return df_nuevo

def clasificar_cliente(score):

    r = int(score[0])
    f = int(score[1])
    m = int(score[2])

    if r == 4 and f >= 3 and m >= 3:
        return "Cliente Premium"
    elif r == 4 and (f < 3 or m < 3):
        return "Cliente Novo/Promissor"
    elif r == 1 and f >= 3 and m >= 3:
        return "Cliente Valioso Inativo"
    elif r == 1:
        return "Cliente Inativo"
    elif r <= 2 and f >= 3 and m >= 2:
        return "Cliente Em risco"
    else:
        return "Cliente Comum"

def recencia_score(d):
    if d <= 30:
            return 4
    elif d <= 90:
        return 3
    elif d <= 180:
        return 2
    else:
        return 1


def mostrar_metrica(opcion, df, df_completo, vendedor_sel, año_sel):
    df = df.reset_index()

    if opcion == "Clientes vendidos por mes":
        df["Mes"] = df["Data"].dt.to_period("M")
        cliente_mes = df.groupby("Mes")["CNPJ"].nunique()
        meses_nome = df.groupby("Mes")["Nome_Mes"].first()
        cliente_mes.index = meses_nome
        st.line_chart(cliente_mes)

    elif opcion == "Ticket Medio":
        ticket_medio = df.groupby("Mes").apply(
            lambda x: x["Valor"].sum() / x["Cliente"].nunique()
        ).sort_index()

        meses_nome = df.groupby("Mes")["Nome_Mes"].first().sort_index()
        ticket_medio.index = meses_nome

        df_plot = ticket_medio.reset_index()
        df_plot.columns = ["Mes", "Ticket Medio"]

        fig = px.bar(
            df_plot,
            x="Mes",
            y="Ticket Medio",
            text= df_plot["Ticket Medio"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")),
            labels={"Ticket Médio": "Ticket Médio (R$)"},
            title="Ticket Médio por Mês"
        )

        fig.update_traces(textposition = "outside")
        fig.update_layout(yaxis_tickformat = "R$,.2f")

        st.plotly_chart(fig, use_container_width=True)


    elif opcion == "Primeira compra de cada cliente":

        modo_abc = st.selectbox("Primeira Compra", ["Geral", "Por Vendedor"])

        df_dist = df_completo[df_completo["Tipo"] == "DIST"].reset_index()

        primera_compra = df_dist.loc[
            df_dist.groupby("Cnpj")["Data"].idxmin()
        ].reset_index(drop=True)

        primera_compra["Ano"] = pd.to_datetime(primera_compra["Data"]).dt.year
        
        primera_compra_ano = primera_compra[primera_compra["Ano"] == año_sel]

        st.markdown(f"### Todos os clientes que compraron pela primeira vez em {año_sel}")
        st.dataframe(primera_compra_ano.reset_index(drop=True))

        clientes_por_vendedor = (
            primera_compra_ano.groupby("Vendedor")["Cnpj"]
            .count()
            .sort_values(ascending=False)
            .reset_index(name="Clientes Abertos no Ano")
        )

        st.markdown(f"### Vendedores que mais abriram clientes em {año_sel}")
        st.dataframe(clientes_por_vendedor)

        if modo_abc == "Por Vendedor" and "Todos" not in vendedor_sel:
            primera_compra_vendedor = primera_compra_ano[
                primera_compra_ano["Vendedor"] == vendedor_sel
            ]
            
            total_clientes_vendedor = primera_compra_vendedor["Cnpj"].nunique()

            st.markdown(f"#### Clientes novos do vendedor: {vendedor_sel}  \n**Total de clientes novos:** {total_clientes_vendedor}")
            st.dataframe(primera_compra_vendedor[["Cnpj", "Vendedor", "Data", "Valor"]].reset_index(drop=True))

        elif modo_abc == "Geral" or "Todos" in vendedor_sel:
            total_geral = primera_compra_ano["Cnpj"].nunique()
            st.markdown(f"#### Total geral de clientes novos em {año_sel} : **{total_geral}**")

    elif opcion == "Regularidade de reposição":
        hoy = pd.Timestamp.today().normalize()

        clientes_filtrado = df["CNPJ"].unique()

        df_filtrado_reg = df_completo[
            (df_completo["Cnpj"].isin(clientes_filtrado)) &
            (df_completo["Tipo"] == "DIST")
        ].copy()

        df_filtrado_reg = df_filtrado_reg.reset_index()

        df["Data"] = pd.to_datetime(df["Data"])

        df_sorted = df_filtrado_reg.sort_values(["Cnpj","Data"])

        ultima_compra = df_sorted.groupby("Cnpj").nth(-1).reset_index()
        anteultima_compra = df_sorted.groupby("Cnpj").nth(-2).reset_index()

        ultima_compra = ultima_compra[["Cnpj", "Data"]].rename(columns={"Data":"Ultima Compra"})
        anteultima_compra = anteultima_compra[["Cnpj","Data"]].rename(columns={"Data":"Anteultima Compra"})

        primera_compra = df_sorted.groupby("Cnpj")["Data"].min().reset_index()
        primera_compra.rename(columns={"Data":"Primeira Compra"}, inplace=True)

        regularidade = pd.merge(ultima_compra, anteultima_compra, on="Cnpj", how="inner")
        regularidade = pd.merge(regularidade, primera_compra, on="Cnpj", how="left")
        
        regularidade["Dias Entre Compras"] = (regularidade["Ultima Compra"] - regularidade["Anteultima Compra"]).dt.days
        regularidade["Dias Sem Comprar"] = (hoy - regularidade["Ultima Compra"]).dt.days

        st.markdown(f"### Regularidade de Reposição Vendedor: {vendedor_sel} - Ano: {año_sel}")
        st.dataframe(regularidade.round(0).sort_values("Dias Entre Compras", ascending=False).reset_index(drop=True))

    elif opcion == "Curva ABC de Cliente":

        modo_abc = st.selectbox("Tipo de Curva ABC", ["Geral", "Por Vendedor"])

        if modo_abc == "Por Vendedor":
            df_dist = df_completo[df_completo["Tipo"] == "DIST"]
            if "Todos" not in vendedor_sel:
                df_dist = df_completo[df_completo["Vendedor"] == vendedor_sel]
        else:
            df_dist = df_completo[df_completo["Tipo"] == "DIST"].copy()

        total_vendas = df_dist.groupby("Cnpj")["Valor"].sum().sort_values(ascending=False).reset_index()

        total_vendas["Acumulado"] = total_vendas["Valor"].cumsum().round(2)
        total_vendas["Percentual_Acumulado"] = (100 * total_vendas["Acumulado"] / total_vendas["Valor"].sum()).round(2)

        total_vendas["Categoria"] = total_vendas["Percentual_Acumulado"].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))

        st.subheader(f"Curva ABC - Classificação {modo_abc}")
        st.dataframe(total_vendas)

        st.line_chart(total_vendas.set_index("Cnpj")[["Percentual_Acumulado"]])

        st.subheader("Numero de Clientes por Categoria")
        clientes_por_categoria = total_vendas["Categoria"].value_counts().reset_index()
        clientes_por_categoria.columns = ["Categoria", "Quantidade"]
        st.bar_chart(clientes_por_categoria.set_index("Categoria"))

        st.subheader("Distribuição de Vendas por Categoria (R$)")  
        vendas_por_categoria = total_vendas.groupby("Categoria")["Valor"].sum().reset_index()

        fig = px.pie(vendas_por_categoria, names="Categoria", values="Valor",title="Participação no Total Vendido")
        st.plotly_chart(fig)

        clientes_ano = df["CNPJ"].unique()
        clientes_abc = total_vendas[total_vendas["Cnpj"].isin(clientes_ano)]

        st.subheader(f"Clientes de {año_sel} e sua categoria ABC")
        st.dataframe(clientes_abc.reset_index(drop=True))
    
    elif opcion == "Lucratividade por Vendedor":
        st.markdown("### Vendedores com mais lucratividade (venda com menos bonificações)")

        modo_abc = st.selectbox("Modo de análise", ["Geral", "Por Vendedor"])

        df_filtrado = df_completo.copy()
        df_filtrado = df_filtrado.reset_index()
        df_filtrado = df_filtrado[df_filtrado["Ano"] == año_sel]

        df_filtrado["Tipo"] = df_filtrado["Tipo"].str.lower()
        df_filtrado["Valor"] = pd.to_numeric(df_filtrado["Valor"], errors="coerce")

        if modo_abc == "Por Vendedor" and "Todos" not in vendedor_sel:
            df_modoabc = df_filtrado[df_filtrado["Vendedor"] == vendedor_sel]
        else:
            df_modoabc = df_filtrado

        vendas = df_filtrado[df_filtrado["Tipo"] == "dist"].groupby("Vendedor")["Valor"].sum().reset_index(name="Total_Vendido")
        bonificaciones = df_filtrado[df_filtrado["Tipo"].str.contains("bon")].groupby("Vendedor")["Valor"].sum().reset_index(name="Total_Bonificado")

        lucratividade = pd.merge(vendas, bonificaciones, on="Vendedor", how="outer").fillna(0)
        lucratividade["Total_Entregue"] = lucratividade["Total_Vendido"] + lucratividade["Total_Bonificado"]

        lucratividade = lucratividade[lucratividade["Total_Entregue"] > 0]
        lucratividade["% Bonificado sobre Entregue"] = (lucratividade["Total_Bonificado"] / lucratividade["Total_Entregue"]) * 100
        lucratividade["% Bonificado sobre Vendido"] = ((lucratividade["Total_Bonificado"] / lucratividade["Total_Vendido"].replace(0, np.nan)) * 100).round(2)

        lucratividade = lucratividade.sort_values(by="% Bonificado sobre Vendido", ascending=True).reset_index(drop=True)

        st.dataframe(lucratividade.style.format({
            "Total_Vendido": "R${:,.2f}",
            "Total_Bonificado" : "R${:,.2f}",
            "Total_Entregue" : "R${:,.2f}"
        }))

        clientes_venda = df_modoabc[df_modoabc["Tipo"] == "dist"]["Cnpj"].dropna().unique()
        df_clientes_venda = df_modoabc[df_modoabc["Cnpj"].isin(clientes_venda) & (df_modoabc["Tipo"] == "dist")]
        df_clientes_venda = df_clientes_venda[["Cnpj", "Cliente", "Valor", "Vendedor", "Data", "Nfe"]].drop_duplicates()
        st.markdown(f"### Clientes que compraram em {año_sel}")
        st.dataframe(df_clientes_venda.reset_index(drop=True))

        clientes_bon = df_modoabc[df_modoabc["Tipo"].str.contains("bon")]["Cnpj"].dropna().unique()
        df_clientes_bon = df_modoabc[df_modoabc["Cnpj"].isin(clientes_bon) & (df_modoabc["Tipo"].str.contains("bon"))]
        df_clientes_bon = df_clientes_bon[["Cnpj", "Cliente", "Valor", "Vendedor", "Data", "Nfe"]].drop_duplicates()
        st.markdown(f"### Clientes que receberam bonificação em {año_sel}")
        st.dataframe(df_clientes_bon.reset_index(drop=True))

def top_clientes(df, n=3):
    return (
    df.groupby("Cliente")["Valor"]
    .sum()
    .sort_values(ascending=False)
    .head(n)
    .reset_index()
)

def top_vendedores (df, n=3):
    return (
    df.groupby("Vendedor")["Valor"]
    .sum()
    .sort_values(ascending=False)
    .head(n)
    .reset_index()
    )

def mostrar_podio(df_top, titulo, valor_col, emoji_list=None):
    st.markdown(f"### {titulo}")
    if emoji_list is None:
        emoji_list = ["🥇", "🥈", "🥉"]
    for i, row in df_top.iterrows():
        emoji = emoji_list[i] if i < len(emoji_list) else ""
        nombre = row[0]
        valor = row[valor_col]
        st.markdown(f"{emoji} *{nombre}* - **R$ {valor:,.2f}**")

def aplicar_filtros(df, año, tipo, vendedor):
    df_filtrado = df.copy()
    if vendedor != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Vendedor"] == vendedor]
    df_filtrado = df_filtrado[df_filtrado["Ano"] == año]
    df_filtrado = df_filtrado[df_filtrado["Tipo"] == tipo]
    return df_filtrado

def mostrar_lider(df_sc, df_pr, df_rs, año_sel, tipo, vendedor_sel):
    df_sc_filtrado = aplicar_filtros(df_sc, año_sel, tipo, vendedor_sel)
    df_pr_filtrado = aplicar_filtros(df_pr, año_sel, tipo, vendedor_sel)
    df_rs_filtrado = aplicar_filtros(df_rs, año_sel, tipo, vendedor_sel)

    ventas_sc = df_sc_filtrado["Valor"].sum()
    ventas_pr = df_pr_filtrado["Valor"].sum()
    ventas_rs = df_rs_filtrado["Valor"].sum()

    ventas_por_filial = {
        "SC": ventas_sc,
        "PR": ventas_pr,
        "RS": ventas_rs
    }

    filial_lider = max(ventas_por_filial, key=ventas_por_filial.get)
    ventas_lider = ventas_por_filial[filial_lider]
    return filial_lider, ventas_lider

#------------------------------------------ Streamlit ---------------------------------------

df_sc = cargar_df("filial_1.csv")
df_pr = cargar_df("filial_2.csv")
df_rs = cargar_df("filial_3.csv")

st.set_page_config(
    page_title="Vendas DSH",
    layout="centered"
)

st.image("images_fondo.jpg")

with st.sidebar:
    st.header("Menu")
    filial_selecionada = st.selectbox("Selecione a filial:", filial)
    if filial_selecionada == "SC":
        df = df_sc
    elif filial_selecionada == "PR":
        df = df_pr
    else:
        if filial_selecionada == "RS":            
            df = df_rs

    año = sorted(df["Ano"].dropna().unique())
    año_sel = st.sidebar.selectbox("Selecione um ano", año)
    
    df_filtrado_por_año = df[df["Ano"] == año_sel]
    vendedores = sorted(df_filtrado_por_año["Vendedor"].str.upper().dropna().unique().tolist())
    op_vend = ["Todos"] + vendedores
    op_vend = op_vend
    vendedor_sel = st.sidebar.selectbox("Vendedor", op_vend)


    tipos_ventas = sorted(df["Tipo"].dropna().unique())
    dist = "DIST"
    tipo = st.sidebar.selectbox("Tipo de Venda", tipos_ventas, placeholder="Selecione um tipo de Venda")

    datos = actualizar_df(df, año_sel, tipo, vendedor_sel)
    filial_lider, ventas_lider = mostrar_lider(df_sc, df_pr, df_rs, año_sel, tipo, vendedor_sel)

if datos.shape[0] != 0:

    st.header(f"Filial: {filial_selecionada}",divider=True)
    
    col1, col2 = st.columns(2)

    with col1:
        valor = datos["Valor"].sum()
        st.metric(label="Total", value=f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        max_venda = datos["Valor"].max()
        st.metric(label="Maxima Venda",  value=f"R$ {max_venda:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    with col2:
        comissao = datos["Comissao"].sum()
        st.metric(label="Total Comissao", value=f"R$ {comissao:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        frete = datos["Frete"].sum()
        st.metric(label="Total Frete", value=f"R$ {frete:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.divider()
    
    st.markdown(f"### 🏆 Filial líder: **{filial_lider}** com R$ {ventas_lider:,.2f}")
    st.divider()

    clientes_top = top_clientes(datos)
    vendedores_top = top_vendedores(datos)

    st.subheader("Top 3 Valor de Vendas")
    col3,col4 = st.columns(2)
    with col3:
        mostrar_podio(clientes_top, "🏅 Top Clientes", "Valor")
    with col4:
        mostrar_podio(vendedores_top, "🏅 Top Vendedores", "Valor")

    st.divider()
    st.header("Dados Completos")
    st.dataframe(datos)
    st.divider()

    valor_mes = datos.groupby("Nome_Mes", as_index=False, observed=True).agg({"Valor": "sum"})
    valor_mes["texto"] = valor_mes["Valor"].apply(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    st.header(f"Vendedor: {vendedor_sel} - Ano: {año_sel}")
    figura = go.Figure()
    figura.add_trace(go.Bar(x=valor_mes["Nome_Mes"], 
                            y=valor_mes["Valor"], 
                            name="Valor NFE", 
                            marker_color="skyblue", 
                            text=valor_mes["texto"],
                            textposition="outside",
                            textfont=dict(size=6, color="white")))
    figura.update_layout(margin=dict(t=60))
    st.plotly_chart (figura)
    st.divider()

    st.title("Metricas de Clientes")
    opcion = st.selectbox("Selecione uma metrica", [
        "Clientes vendidos por mes",
        "Ticket Medio",
        "Primeira compra de cada cliente",
        "Regularidade de reposição",
        "Curva ABC de Cliente",
        "Lucratividade por Vendedor"
    ])

    mostrar_metrica(opcion, datos, df, vendedor_sel, año_sel)