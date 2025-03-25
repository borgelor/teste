import os
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from io import BytesIO
from tempfile import TemporaryDirectory

det_ns = "http://www.portalfiscal.inf.br/nfe"

def clean_and_format(column):
    column = column.str.replace('.', '', regex=False)
    column = column.replace('-', '0', regex=True)
    column = column.str.replace(',', '.')
    return pd.to_numeric(column, errors='coerce')

def extract_all_xmls_from_zip(zip_file, temp_folder):
    """Extrai todos os arquivos XML de todas as pastas dentro do ZIP."""
    try:
        with zipfile.ZipFile(BytesIO(zip_file.read()), 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('.xml'):
                    file_info.filename = os.path.basename(file_info.filename)  # Remove path interno
                    zip_ref.extract(file_info, temp_folder)
    except Exception as e:
        st.error(f"Erro ao extrair arquivos do ZIP: {e}")

def extract_nfe_data(temp_folder, caminho_espelho):
    extracted_data = []
    
    xml_files = [f for f in os.listdir(temp_folder) if f.endswith('.xml')]
    if not xml_files:
        st.error("Nenhum arquivo XML encontrado na pasta temporária.")
        return None, None, None
    
    for file_name in xml_files:
        file_path = os.path.join(temp_folder, file_name)
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
    
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    
    df_pivot = df.pivot_table(
        index="Chave de acesso de 44 posições",
        values=["Contador de itens", "Valor", "Quantidade"],
        aggfunc="sum"
    )
    
    df_merged = df_pivot
    if caminho_espelho:
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
            
            df_merged = df_pivot_esp.join(df_pivot, on='Chave de acesso de 44 posições', how="outer", lsuffix='_espelho', rsuffix='_xml')
            df_temp = df_esp[['Chave de acesso de 44 posições', 'Nº doc SAP', 'CFOP','Data de lançamento', 'Local de negócios' ]]
            df_temp = df_temp.set_index("Chave de acesso de 44 posições")
            df_merged = df_merged.join(df_temp, on="Chave de acesso de 44 posições", how="left")
            
            df_merged = df_merged[['Nº doc SAP', 'CFOP','Data de lançamento', 'Local de negócios', 'Contador de itens_espelho',
                                    'Quantidade_espelho', 'Valor_espelho', 'Contador de itens_xml', 'Quantidade_xml', 'Valor_xml']]
            df_merged = df_merged.reset_index().drop_duplicates(subset=['Chave de acesso de 44 posições'])
        except Exception as e:
            st.error(f"Erro ao processar o espelho de notas: {e}")
    
    return df, df_pivot, df_merged

st.title("Espelho vs XML ! 2 ")
zip_file = st.sidebar.file_uploader("Faça upload de um ZIP contendo os XMLs", type=["zip"])
caminho_espelho = st.sidebar.file_uploader("Selecione o espelho de notas", type=["csv"])

if st.button("Processar"):
    if zip_file:
        with TemporaryDirectory() as temp_folder:
            extract_all_xmls_from_zip(zip_file, temp_folder)
            df, df_pivot, df_merged = extract_nfe_data(temp_folder, caminho_espelho)
            
            if df is not None:
                pivot_output = BytesIO()
                df_merged.to_excel(pivot_output, engine='openpyxl')
                pivot_output.seek(0)
                
                st.download_button("Baixar Tabela Pivot", data=pivot_output, file_name="pivot.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.success("Dados extraídos. Baixe os arquivos usando os botões acima.")
                st.dataframe(df_merged.head())
            else:
                st.error("Nenhum dado foi extraído. Verifique os arquivos carregados.")
    else:       
        st.error("Por favor, selecione um arquivo ZIP com XMLs.")