import os
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from io import BytesIO
from tempfile import TemporaryDirectory

det_ns = "http://www.portalfiscal.inf.br/nfe"

def clean_and_format(column):
    column = column.str.replace('.', '')
    column = column.replace('-', '0', regex=True)
    column = column.str.replace(',', '.')
    return pd.to_numeric(column)

def extract_nfe_data(folder_path, caminho_espelho):
    extracted_data = []

    if not os.path.exists(folder_path):
        st.error("Pasta temporária não encontrada.")
        return None, None, None

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.xml'):
            file_path = os.path.join(folder_path, file_name)
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                chave = root.find(f".//{{{det_ns}}}chNFe")
                chave = chave.text if chave is not None else "Chave não encontrada"

                for item in root.findall(f".//{{{det_ns}}}det"):
                    quantidade = item.find(f".//{{{det_ns}}}qCom")
                    valor_prod = item.find(f".//{{{det_ns}}}vProd")
                    
                    extracted_data.append({
                        "Chave de acesso de 44 posições": chave,
                        "Quantidade": quantidade.text if quantidade is not None else "0",
                        "Valor": valor_prod.text if valor_prod is not None else "0",
                        "Contador de itens": 1
                    })
            except Exception as e:
                st.error(f"Erro ao processar o arquivo {file_name}: {e}")

    df = pd.DataFrame(extracted_data)
    if df.empty:
        st.warning("Nenhum dado foi extraído dos XMLs.")
        return None, None, None

    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0)
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

    df_pivot = df.pivot_table(
        index='Chave de acesso de 44 posições',
        values=['Contador de itens', 'Valor', 'Quantidade'],
        aggfunc='sum'
    )
    
    df_merged = df_pivot
    if caminho_espelho is not None:
        try:
            colunas = ['Chave de acesso de 44 posições', 'Local de negócios', 'Quantidade', 'Valor', 'CFOP', 'Data de lançamento', 'Nº doc SAP']
            df_esp = pd.read_csv(caminho_espelho, sep=';', decimal=',', usecols=colunas, dtype=str, encoding='latin-1')
            df_esp = df_esp[df_esp['Local de negócios'].isin(['0054', '0056'])]
            df_esp['Contador de itens'] = 1
            df_esp['Quantidade'] = clean_and_format(df_esp['Quantidade'])
            df_esp['Valor'] = clean_and_format(df_esp['Valor'])
            
            df_pivot_esp = df_esp.pivot_table(
                index='Chave de acesso de 44 posições',
                values=['Contador de itens', 'Valor', 'Quantidade'],
                aggfunc='sum'
            )
            
            df_merged = df_pivot_esp.join(df_pivot, on='Chave de acesso de 44 posições', how="outer", lsuffix='_espelho', rsuffix='_xml', sort=False, validate='many_to_many')
            df_temp = df_esp[['Chave de acesso de 44 posições', 'Nº doc SAP', 'CFOP','Data de lançamento', 'Local de negócios' ]]
            df_temp=df_temp.set_index("Chave de acesso de 44 posições")
            df_merged = df_merged.join(df_temp, on="Chave de acesso de 44 posições", how="left", lsuffix = '_dwt', rsuffix = '_pg')
            df_merged = df_merged[['Nº doc SAP', 'CFOP','Data de lançamento', 'Local de negócios', 'Contador de itens_espelho',
                                   	'Quantidade_espelho',	'Valor_espelho', 'Contador de itens_xml',	'Quantidade_xml',	'Valor_xml'
]]
            df_merged=df_merged.reset_index()
            df_merged=df_merged.drop_duplicates(subset=['Chave de acesso de 44 posições'])
        except Exception as e:
            st.error(f"Erro ao processar o espelho de notas: {e}")
    
    return df, df_pivot, df_merged

# Interface Streamlit
st.title("Espelho vs XML !")

folder_path = st.sidebar.file_uploader("Selecione os arquivos XML", accept_multiple_files=True, type=["xml"])
caminho_espelho = st.sidebar.file_uploader("Selecione o espelho de notas", type=["csv"])

if st.button("Comparar"):
    if folder_path:
        with TemporaryDirectory() as temp_folder:
            for uploaded_file in folder_path:
                file_path = os.path.join(temp_folder, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
            df, df_pivot, df_merged = extract_nfe_data(temp_folder, caminho_espelho)
        
            if df is not None:
            #base_output = BytesIO()
                pivot_output = BytesIO()
            #df.to_excel(base_output, index=False, engine='openpyxl')
                df_merged.to_excel(pivot_output, engine='openpyxl')
            #base_output.seek(0)
            pivot_output.seek(0)
            
            #st.download_button("Baixar Base de Dados", data=base_output, file_name="base.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.download_button("Baixar Tabela Pivot", data=pivot_output, file_name="pivot.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
                st.success("Dados extraídos. Baixe os arquivos usando os botões acima.")
                st.dataframe(df_merged.head())
            #st.dataframe(df_pivot.head())
            # Apagar arquivos da pasta temp_xmls após a execução
            
             else:
            st.error("Nenhum dado foi extraído. Verifique os arquivos carregados.")
    else:
        st.error("Por favor, selecione pelo menos um arquivo XML.")



