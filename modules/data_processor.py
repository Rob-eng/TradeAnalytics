"""
Módulo responsável pelo processamento e limpeza dos dados de trading.

Contém funções para ler e tratar dados de arquivos Excel e CSV,
consolidá-los e realizar cálculos e transformações iniciais.
"""
import os
import logging
from typing import List, Tuple, Dict, Any, Optional, IO
import pandas as pd
import numpy as np
import traceback # Para log detalhado de erros

from config import (
    RESULT_COLUMN_NAME,
    PRIMARY_RESULT_COLUMN_EXCEL,
    FALLBACK_RESULT_COLUMNS_EXCEL,
    PRIMARY_RESULT_COLUMN_CSV,
    FALLBACK_RESULT_COLUMNS_CSV,
    OPEN_TIME_COLUMNS,
    CLOSE_TIME_COLUMNS,
    ROBO_COLUMN_NAME,
    CSV_ENCODING,
    CSV_SKIPROWS,
    CSV_SEPARATOR,
    CSV_HEADER,
    TRADING_HOUR_START,
    TRADING_HOUR_END
)
from .utils import sanitize_filename, verificar_operacao_sem_horario

logger = logging.getLogger(__name__)

# --- Funções de Leitura e Limpeza Específicas ---

def _find_and_rename_result_column(
    df: pd.DataFrame,
    primary_col: str,
    fallback_cols: List[str],
    target_col: str
) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Encontra a coluna de resultado (primária ou fallback) e a renomeia para o nome padrão.

    Args:
        df: DataFrame de entrada.
        primary_col: Nome da coluna de resultado preferencial.
        fallback_cols: Lista de nomes alternativos para a coluna de resultado.
        target_col: Nome padrão para o qual a coluna encontrada será renomeada.

    Returns:
        Uma tupla contendo:
        - O DataFrame modificado (coluna renomeada).
        - O nome original da coluna de resultado encontrada, ou None se nenhuma foi encontrada.

    Raises:
        ValueError: Se nenhuma coluna de resultado utilizável for encontrada.
    """
    original_col_name: Optional[str] = None
    df_cols_lower = {col.lower(): col for col in df.columns} # Case-insensitive check

    # Check primary column (case-insensitive)
    if primary_col.lower() in df_cols_lower:
        original_col_name = df_cols_lower[primary_col.lower()]
    else:
        # Check fallback columns (case-insensitive)
        for col in fallback_cols:
            if col.lower() in df_cols_lower:
                original_col_name = df_cols_lower[col.lower()]
                logger.info(f"Coluna de resultado primária '{primary_col}' não encontrada (ou case diferente). Usando fallback: '{original_col_name}'")
                break

    if original_col_name:
        logger.info(f"Coluna de resultado encontrada: '{original_col_name}'. Renomeando para '{target_col}'.")
        # Cria coluna de debug ANTES de renomear/converter
        df[f'{target_col}_Original_Debug'] = df[original_col_name].astype(str)
        # Renomeia usando o nome original encontrado
        df = df.rename(columns={original_col_name: target_col})
        return df, original_col_name # Retorna o nome original exato que foi encontrado
    else:
        cols_list = [primary_col] + fallback_cols
        logger.error(f"Nenhuma coluna de resultado utilizável encontrada. Esperado (case-insensitive): {cols_list}. Colunas presentes: {list(df.columns)}")
        raise ValueError(f"Nenhuma coluna de resultado ({', '.join(cols_list)}) encontrada no DataFrame.")

def _clean_numeric_result_column(
    df: pd.DataFrame,
    col_name: str
    ) -> pd.DataFrame:
    """
    Converte a coluna de resultado especificada para numérico (float),
    assumindo que os valores originais representam NÚMEROS INTEIROS,
    podendo conter espaços, pontos ou vírgulas como separadores de milhar.
    Inclui logging detalhado passo a passo.
    """
    if col_name not in df.columns:
        logger.error(f"Tentando limpar coluna numérica '{col_name}', mas ela não existe no DataFrame.")
        raise KeyError(f"Coluna '{col_name}' não encontrada para limpeza numérica.")

    # Nomes das colunas temporárias e de debug
    debug_col_name = f'{col_name}_Original_Debug'
    temp_col = col_name + '_Temp_Clean' # Nome mais claro para a coluna de limpeza
    numeric_col = col_name + '_Numeric'
    # Coluna fonte para limpeza inicial (geralmente a coluna já renomeada)
    source_col_for_cleaning = col_name

    logger.debug(f"--- Iniciando Limpeza Numérica para Coluna: '{col_name}' ---")

    # Garante que é string e remove espaços iniciais/finais
    # Cria a coluna temporária a partir da coluna fonte
    try:
        df[temp_col] = df[source_col_for_cleaning].astype(str).str.strip()
        logger.debug(f"Amostra inicial de '{temp_col}' (após strip):\n{df[temp_col].head(15).to_string(index=False)}")
    except KeyError:
        logger.error(f"Coluna fonte '{source_col_for_cleaning}' não encontrada para iniciar a limpeza.")
        # Tenta usar a coluna de debug se existir como fallback extremo
        if debug_col_name in df.columns:
             logger.warning(f"Tentando usar a coluna de debug '{debug_col_name}' como fonte.")
             df[temp_col] = df[debug_col_name].astype(str).str.strip()
             logger.debug(f"Amostra inicial de '{temp_col}' (do debug, após strip):\n{df[temp_col].head(15).to_string(index=False)}")
        else:
             raise KeyError(f"Colunas '{source_col_for_cleaning}' e '{debug_col_name}' não encontradas para limpeza.")


    # --- LÓGICA DE LIMPEZA REVISADA (Assume '.' como decimal) ---
    # 1. Remover espaços internos
    df[temp_col] = df[temp_col].str.replace(' ', '', regex=False)
    # 2. Remover separador de MILHAR (assumindo que é ',')
    df[temp_col] = df[temp_col].str.replace(',', '', regex=False)
    # 3. NÃO REMOVER PONTO - o ponto é considerado decimal por pd.to_numeric
    # --- LÓGICA DE LIMPEZA SIMPLIFICADA (Passo a Passo com Logs) ---
    try:
        # 1. Remover espaços internos
        df[temp_col] = df[temp_col].str.replace(' ', '', regex=False)
        logger.debug(f"Amostra de '{temp_col}' após replace(' '):\n{df[temp_col].head(15).to_string(index=False)}")

        # 2. Remover PONTOS (tratados como milhar ou lixo)
        df[temp_col] = df[temp_col].str.replace('.', '', regex=False)
        logger.debug(f"Amostra de '{temp_col}' após replace('.'):\n{df[temp_col].head(15).to_string(index=False)}")

        # 3. Remover VÍRGULAS (tratadas como milhar ou lixo)
        df[temp_col] = df[temp_col].str.replace(',', '', regex=False)
        logger.debug(f"Amostra de '{temp_col}' após replace(','):\n{df[temp_col].head(15).to_string(index=False)}")

        # 4. Opcional: Remover outros caracteres não numéricos (exceto sinal de menos)
        # df[temp_col] = df[temp_col].str.replace(r'[^\d\-]', '', regex=True)
        # logger.debug(f"Amostra de '{temp_col}' após regex [^\\d\\-]:\n{df[temp_col].head(15).to_string(index=False)}")

    except Exception as e_clean:
         logger.error(f"Erro durante as etapas de limpeza de string para '{temp_col}': {e_clean}", exc_info=True)
         # Continua para to_numeric, que provavelmente falhará para essas linhas

    # Tenta converter para numérico (float ainda é seguro aqui)
    df[numeric_col] = pd.to_numeric(df[temp_col], errors='coerce')
    logger.debug(f"Amostra de '{numeric_col}' após pd.to_numeric:\n{df[numeric_col].head(15).to_string(index=False)}")


    # --- Logs de Falha e Sucesso ---
    nan_mask = df[numeric_col].isna()
    nan_conversion_count = nan_mask.sum()
    if nan_conversion_count > 0:
        source_debug_col = debug_col_name if debug_col_name in df.columns else source_col_for_cleaning
        failed_values_cleaned = df.loc[nan_mask, temp_col].unique()
        logger.warning(f"{nan_conversion_count} valores na coluna '{col_name}' falharam na conversão para numérico (APÓS limpeza '{temp_col}') e serão substituídos por 0.")
        logger.warning(f"  Exemplos de valores LIMPOS ('{temp_col}') que falharam: {list(failed_values_cleaned[:10])}")
        if debug_col_name in df.columns:
             failed_values_original = df.loc[nan_mask, debug_col_name].unique()
             logger.warning(f"  Valores ORIGINAIS ('{debug_col_name}') correspondentes: {list(failed_values_original[:10])}")

    valid_mask = df[numeric_col].notna()
    if valid_mask.any():
        source_debug_col = debug_col_name if debug_col_name in df.columns else source_col_for_cleaning
        sample_valid = df[valid_mask][[source_debug_col, numeric_col]].head(5)
        logger.debug(f"Exemplos de conversão numérica BEM-SUCEDIDA para '{col_name}':")
        for _, row in sample_valid.iterrows():
             logger.debug(f"  Original ('{source_debug_col}'): '{row[source_debug_col]}' -> Convertido: {row[numeric_col]}")


    # Preenche NaNs e converte tipo
    df[col_name] = df[numeric_col].fillna(0).astype(float)

    # Remove colunas temporárias
    columns_to_drop = [temp_col, numeric_col]
    # Não remove debug_col aqui, deixa para a função chamadora decidir
    # if debug_col_name in df.columns:
    #     columns_to_drop.append(debug_col_name)
    df = df.drop(columns=columns_to_drop, errors='ignore')


    # --- Log da soma ---
    soma_final = df[col_name].sum()
    logger.info(f"Coluna '{col_name}' limpa e convertida para float. Soma após limpeza: {soma_final:.2f}") # Mantém 2 casas decimais
    # Log adicional para verificar a ordem de grandeza
    logger.info(f"Coluna '{col_name}' (tratada como inteiros) limpa e convertida para float. Soma após limpeza: {soma_final:.2f}")
    logger.debug(f"Soma completa (debug): {soma_final}")
    logger.debug(f"--- Finalizada Limpeza Numérica para Coluna: '{col_name}' ---")

    return df

def _parse_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte as colunas de Abertura e Fechamento para datetime.

    Mapeia nomes alternativos para 'Abertura'/'Fechamento', converte
    para datetime (tentando formato DD/MM/YYYY), e cria colunas
    '_Original' para debug.

    Args:
        df: DataFrame de entrada.

    Returns:
        DataFrame com colunas 'Abertura' e 'Fechamento' em formato datetime.
    """
    # Mapear nomes de colunas de data/hora (case-insensitive)
    df_cols_lower = {col.lower(): col for col in df.columns}
    time_mapping = {}
    for potential_col in OPEN_TIME_COLUMNS:
        if potential_col.lower() in df_cols_lower:
            time_mapping[df_cols_lower[potential_col.lower()]] = 'Abertura'
    for potential_col in CLOSE_TIME_COLUMNS:
         if potential_col.lower() in df_cols_lower:
            time_mapping[df_cols_lower[potential_col.lower()]] = 'Fechamento'


    if time_mapping:
        # Garante que não estamos renomeando a mesma coluna para Abertura e Fechamento
        if 'Abertura' in time_mapping.values() and 'Fechamento' in time_mapping.values():
            abertura_orig = [k for k, v in time_mapping.items() if v == 'Abertura']
            fechamento_orig = [k for k, v in time_mapping.items() if v == 'Fechamento']
            if abertura_orig and fechamento_orig and abertura_orig[0] == fechamento_orig[0]:
                 logger.error(f"Erro de mapeamento: A mesma coluna original '{abertura_orig[0]}' foi mapeada para 'Abertura' e 'Fechamento'. Verifique as listas em config.py.")
                 # Decide como tratar: remover um mapeamento, lançar erro? Lançar erro é mais seguro.
                 raise ValueError(f"Conflito de mapeamento: Coluna '{abertura_orig[0]}' mapeada para Abertura e Fechamento.")

        df = df.rename(columns=time_mapping)
        logger.info(f"Colunas de data/hora mapeadas: {time_mapping}")

    # Guardar cópias originais para debug ANTES da conversão
    if 'Abertura' in df.columns:
        df['Abertura_Original'] = df['Abertura'].astype(str)
    else:
        # Não cria a coluna original se 'Abertura' não existe
        logger.warning("Coluna 'Abertura' não encontrada após mapeamento.")

    if 'Fechamento' in df.columns:
        df['Fechamento_Original'] = df['Fechamento'].astype(str)
    else:
        # Não cria a coluna original se 'Fechamento' não existe
        logger.warning("Coluna 'Fechamento' não encontrada após mapeamento.")

    # Tentar converter para datetime
    for col in ['Abertura', 'Fechamento']:
        if col in df.columns:
            original_type = df[col].dtype
            logger.info(f"Convertendo coluna '{col}' (tipo original: {original_type}) para datetime...")
            # Tenta inferir o formato, mas prioriza dayfirst=True (DD/MM/...)
            # Usar format=... se o formato for conhecido e consistente
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True, infer_datetime_format=True)
                nat_count = df[col].isna().sum()
                if nat_count > 0:
                    logger.warning(f"{nat_count} valores na coluna '{col}' não puderam ser convertidos para datetime (resultaram em NaT).")
                    # Opcional: Logar exemplos de valores que falharam
                    original_col_debug = f'{col}_Original'
                    if original_col_debug in df.columns:
                         failed_dates = df.loc[df[col].isna(), original_col_debug].unique()
                         logger.warning(f"  Exemplos de valores originais que falharam na conversão de '{col}': {list(failed_dates[:10])}")
                    else:
                         logger.warning(f"  Não foi possível mostrar exemplos originais (coluna {original_col_debug} não encontrada).")

            except Exception as e_dt:
                 logger.error(f"Erro inesperado ao converter coluna '{col}' para datetime: {e_dt}", exc_info=True)
                 # Define a coluna como NaT para forçar a remoção posterior
                 df[col] = pd.NaT
        else:
            logger.warning(f"Coluna '{col}' não presente para conversão datetime.")

    return df

# --- Funções Principais de Processamento por Tipo de Arquivo ---

def processar_dados_excel(
    file: IO[Any],
    output_dir: str # Diretório para salvar temporariamente, se necessário
) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Processa dados de um arquivo Excel (.xlsx ou .xls).

    Lê o arquivo, encontra e renomeia a coluna de resultado, limpa a coluna
    de resultado para formato numérico, processa colunas de data/hora,
    e adiciona a coluna 'Robo' se não existir.

    Args:
        file: Objeto de arquivo Excel (de request.files).
        output_dir: Caminho para o diretório onde arquivos temporários podem ser salvos.
                    (Nota: a leitura direta com BytesIO é preferível se possível).

    Returns:
        Uma tupla contendo:
        - banco_geral_bruto: DataFrame com os dados processados do Excel.
                             Pode estar vazio se o arquivo for inválido ou vazio.
        - original_result_col_name: Nome original da coluna de resultado encontrada.

    Raises:
        ValueError: Se o arquivo for inválido, vazio, ou não contiver coluna de resultado.
        Exception: Para outros erros de leitura ou processamento do Pandas/Openpyxl.
    """
    filename = sanitize_filename(getattr(file, 'filename', 'arquivo_excel_desconhecido'))
    logger.info(f"--- Iniciando processamento do arquivo Excel: {filename} ---")

    try:
        # Tenta ler diretamente do objeto de arquivo em memória
        # openpyxl é necessário para .xlsx
        # Adiciona 'xlrd' se precisar suportar .xls antigos (pip install xlrd)
        banco_geral = pd.read_excel(file, engine='openpyxl')
        logger.info(f"Arquivo Excel '{filename}' lido com sucesso. Shape inicial: {banco_geral.shape}")
        logger.debug(f"Colunas encontradas: {list(banco_geral.columns)}")

    except Exception as e:
        logger.error(f"Erro ao ler o arquivo Excel '{filename}': {e}", exc_info=True)
        # Tentar salvar e reler pode ser um fallback, mas geralmente indica problema no arquivo/engine
        # temp_path = os.path.join(output_dir, "temp_upload_" + filename)
        # try:
        #     with open(temp_path, 'wb') as f:
        #         file.seek(0)
        #         f.write(file.read())
        #     banco_geral = pd.read_excel(temp_path, engine='openpyxl')
        #     logger.info("Leitura do arquivo Excel após salvar temporariamente bem-sucedida.")
        #     os.remove(temp_path) # Limpa o arquivo temporário
        # except Exception as e_save:
        #     logger.error(f"Falha também ao salvar e ler arquivo Excel temporário: {e_save}", exc_info=True)
        #     if os.path.exists(temp_path): os.remove(temp_path)
        raise ValueError(f"Erro ao ler o arquivo Excel '{filename}'. Verifique se o formato é válido.") from e

    if banco_geral.empty:
        logger.warning(f"Arquivo Excel '{filename}' está vazio ou não contém dados.")
        # Retorna DataFrame vazio e None para nome da coluna
        return pd.DataFrame(), None

    # 1. Processar colunas de Data/Hora
    banco_geral = _parse_datetime_columns(banco_geral)

    # 2. Encontrar e Renomear Coluna de Resultado
    try:
        banco_geral, original_result_col_name = _find_and_rename_result_column(
            banco_geral,
            PRIMARY_RESULT_COLUMN_EXCEL,
            FALLBACK_RESULT_COLUMNS_EXCEL,
            RESULT_COLUMN_NAME
        )
    except ValueError as e:
        logger.error(f"Erro fatal no arquivo Excel '{filename}': {e}")
        raise ValueError(f"Arquivo Excel '{filename}' não contém uma coluna de resultado válida ({PRIMARY_RESULT_COLUMN_EXCEL}, etc.).") from e

    # 3. Remover linhas onde o resultado original era NaN (antes da limpeza numérica)
    #    Fazemos isso após renomear para usar RESULT_COLUMN_NAME + '_Original_Debug'
    debug_col = f'{RESULT_COLUMN_NAME}_Original_Debug'
    if debug_col in banco_geral.columns:
         # Considera NaN, None, strings vazias como inválidos
         original_nan_mask = banco_geral[debug_col].isnull() | \
                             banco_geral[debug_col].astype(str).str.strip().str.lower().isin(['nan', 'none', ''])
         original_nan_count = original_nan_mask.sum()
         if original_nan_count > 0:
              logger.info(f"Removendo {original_nan_count} linhas onde o valor original do resultado ('{original_result_col_name}') estava vazio ou era NaN.")
              banco_geral = banco_geral[~original_nan_mask].copy() # Usa copy() para evitar SettingWithCopyWarning
              logger.info(f"Shape após remover NaNs originais de resultado: {banco_geral.shape}")
         # Não remove a coluna de debug aqui, _clean_numeric_result_column fará isso
    else:
         logger.warning(f"Coluna de debug '{debug_col}' não encontrada para checagem de NaNs originais.")

    if banco_geral.empty:
        logger.warning(f"Nenhuma linha com valor de resultado original válido encontrada no Excel '{filename}' após remover NaNs.")
        return pd.DataFrame(), original_result_col_name # Retorna DF vazio mas com nome da coluna

    # 4. Limpar Coluna de Resultado para Numérico
    try:
        # Remove o parâmetro input_format
        banco_geral = _clean_numeric_result_column(banco_geral, RESULT_COLUMN_NAME)
    except KeyError as e:
         # Isso não deveria acontecer se _find_and_rename funcionou, mas por segurança
         logger.error(f"Erro inesperado ao tentar limpar resultado: {e}", exc_info=True)
         raise ValueError(f"Erro ao processar coluna de resultado em '{filename}'.")
    # --- REMOVER COLUNA DE DEBUG APÓS A LIMPEZA ---
    debug_col_name = f'{RESULT_COLUMN_NAME}_Original_Debug'
    if debug_col_name in banco_geral.columns:
        banco_geral = banco_geral.drop(columns=[debug_col_name], errors='ignore')
        logger.debug(f"Coluna de debug '{debug_col_name}' removida após limpeza.")
        
    # 5. Garantir coluna 'Robo'
    # Verifica case-insensitive
    robo_col_present = False
    actual_robo_col = None
    for col in banco_geral.columns:
        if col.lower() == ROBO_COLUMN_NAME.lower():
            robo_col_present = True
            actual_robo_col = col
            break

    if not robo_col_present:
        logger.info(f"Coluna '{ROBO_COLUMN_NAME}' não encontrada (ou case diferente). Adicionando com valor 'Excel_Data'.")
        banco_geral[ROBO_COLUMN_NAME] = 'Excel_Data' # Nome padrão
    elif actual_robo_col != ROBO_COLUMN_NAME:
        # Se encontrou com case diferente, renomeia para o padrão
        logger.info(f"Renomeando coluna '{actual_robo_col}' para o padrão '{ROBO_COLUMN_NAME}'.")
        banco_geral = banco_geral.rename(columns={actual_robo_col: ROBO_COLUMN_NAME})

    # 6. Selecionar e Reordenar Colunas Finais (opcional, mas bom para consistência)
    colunas_finais_desejadas = [
        'Abertura', 'Fechamento', ROBO_COLUMN_NAME, RESULT_COLUMN_NAME,
        'Abertura_Original', 'Fechamento_Original' # Colunas de debug no final
    ]
    # Adiciona outras colunas que possam existir e não foram explicitamente removidas/renomeadas
    colunas_essenciais = ['Abertura', 'Fechamento', ROBO_COLUMN_NAME, RESULT_COLUMN_NAME]
    colunas_debug = ['Abertura_Original', 'Fechamento_Original']
    outras_colunas = [col for col in banco_geral.columns if col not in colunas_essenciais and col not in colunas_debug]

    # Garante a ordem: essenciais, outras, debug
    colunas_finais = colunas_essenciais + outras_colunas + colunas_debug
    # Apenas colunas que realmente existem no DataFrame
    colunas_presentes = [col for col in colunas_finais if col in banco_geral.columns]
    banco_geral = banco_geral[colunas_presentes]

    logger.info(f"--- Finalizado processamento do arquivo Excel: {filename}. Shape final: {banco_geral.shape} ---")
    return banco_geral, original_result_col_name


def processar_dados_csv(
    files: List[IO[Any]],
    output_dir: str # Diretório não usado na leitura direta, mas mantido por consistência
) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Processa dados de um ou mais arquivos CSV.

    Lê cada CSV, aplica limpeza, extrai o nome do robô do nome do arquivo,
    padroniza colunas e concatena os resultados em um único DataFrame.

    Args:
        files: Lista de objetos de arquivo CSV (de request.files.getlist).
        output_dir: Diretório base (atualmente não usado para salvar CSVs).

    Returns:
        Uma tupla contendo:
        - banco_geral_bruto: DataFrame consolidado com dados de todos os CSVs válidos.
                             Pode estar vazio se nenhum CSV válido for encontrado.
        - original_result_col_name: Nome original da coluna de resultado encontrada
                                    (assume-se que seja o mesmo em todos os CSVs válidos).

    Raises:
        ValueError: Se a lista de arquivos estiver vazia ou nenhum CSV válido for processado.
    """
    if not files:
        raise ValueError("Nenhum arquivo CSV foi fornecido para processamento.")

    dfs: List[pd.DataFrame] = []
    original_result_col_name_found: Optional[str] = None
    processed_files_count = 0
    failed_files: List[str] = []

    for file_index, file in enumerate(files):
        filename = sanitize_filename(getattr(file, 'filename', f'arquivo_csv_{file_index+1}'))
        logger.info(f"\n--- Iniciando processamento do CSV: {filename} ---")

        try:
            # 1. Leitura do CSV
            # Resetar ponteiro do arquivo antes da leitura
            file.seek(0)
            df = pd.read_csv(
                file,
                skiprows=CSV_SKIPROWS,
                encoding=CSV_ENCODING,
                sep=CSV_SEPARATOR,
                header=CSV_HEADER,
                # Adicionar outras opções se necessário, ex: decimal=','
                # low_memory=False pode ajudar com mixed types, mas consome mais memória
                low_memory=False
            )
            logger.info(f"Arquivo CSV '{filename}' lido. Shape inicial: {df.shape}")
            logger.debug(f"Colunas encontradas: {list(df.columns)}")
            
            logger.debug(f"dtypes após leitura CSV:\n{df.dtypes}")
            potential_res_cols = [PRIMARY_RESULT_COLUMN_CSV] + FALLBACK_RESULT_COLUMNS_CSV
            original_res_col_in_csv = None
            df_cols_lower_map = {col.lower(): col for col in df.columns}
            for col in potential_res_cols:
                if col.lower() in df_cols_lower_map:
                    original_res_col_in_csv = df_cols_lower_map[col.lower()]
                    logger.debug(f"Coluna de resultado original detectada no CSV: '{original_res_col_in_csv}'")
                    try:
                        # Tenta mostrar a amostra; pode falhar se a coluna tiver dados estranhos
                        logger.debug(f"Amostra RAW da coluna '{original_res_col_in_csv}' (antes de limpar nomes de colunas):\n{df[original_res_col_in_csv].head(15).to_string(index=False)}")
                    except Exception as e_log:
                        logger.warning(f"Não foi possível logar amostra RAW da coluna '{original_res_col_in_csv}': {e_log}")
                    break
            if original_res_col_in_csv is None:
                 logger.error("Não foi possível encontrar a coluna de resultado original no CSV para debug inicial.")

            if df.empty:
                logger.warning(f"Arquivo CSV '{filename}' está vazio ou não contém dados após pular linhas. Pulando.")
                failed_files.append(f"{filename} (Vazio)")
                continue

            # Limpar nomes de colunas (remover espaços extras)
            original_columns = list(df.columns)
            df.columns = df.columns.str.strip()
            new_columns = list(df.columns)
            if original_columns != new_columns:
                 logger.debug(f"Nomes de colunas ajustados (removido strip).")
                 # Logar novamente a amostra após strip se o nome original foi encontrado
                 if original_res_col_in_csv and original_res_col_in_csv.strip() in df.columns:
                     logger.debug(f"Amostra da coluna '{original_res_col_in_csv.strip()}' (após strip):\n{df[original_res_col_in_csv.strip()].head(15).to_string(index=False)}")

            # 2. Adicionar Coluna 'Robo' a partir do nome do arquivo
            robo_name = os.path.splitext(filename)[0]
            df[ROBO_COLUMN_NAME] = robo_name
            logger.info(f"Nome do robô extraído do arquivo: '{robo_name}'")

            # 3. Processar Colunas de Data/Hora
            df = _parse_datetime_columns(df)

            # 4. Encontrar e Renomear Coluna de Resultado
            df, current_original_result_col = _find_and_rename_result_column(
                df,
                PRIMARY_RESULT_COLUMN_CSV,
                FALLBACK_RESULT_COLUMNS_CSV,
                RESULT_COLUMN_NAME
            )
            # Armazena o nome da coluna original do primeiro arquivo processado com sucesso
            if original_result_col_name_found is None and current_original_result_col:
                original_result_col_name_found = current_original_result_col
                
            # Log após renomear, mostrando a coluna de debug
            debug_col_name = f'{RESULT_COLUMN_NAME}_Original_Debug'
            if debug_col_name in df.columns:
                logger.debug(f"Amostra da coluna de debug '{debug_col_name}' (criada após renomear):\n{df[debug_col_name].head(15).to_string(index=False)}")

            # 5. Remover linhas onde o resultado original era NaN
            debug_col = f'{RESULT_COLUMN_NAME}_Original_Debug'
            if debug_col in df.columns:
                 # Considera NaN, None, strings vazias como inválidos
                 original_nan_mask = df[debug_col].isnull() | \
                                     df[debug_col].astype(str).str.strip().str.lower().isin(['nan', 'none', ''])
                 original_nan_count = original_nan_mask.sum()
                 if original_nan_count > 0:
                     logger.info(f"Removendo {original_nan_count} linhas onde o valor original do resultado ('{current_original_result_col}') estava vazio/NaN.")
                     df = df[~original_nan_mask].copy()
                     logger.info(f"Shape após remover NaNs originais de resultado: {df.shape}")
                 # Não remove a coluna de debug aqui, _clean_numeric_result_column fará isso
            else:
                 logger.warning(f"Coluna de debug '{debug_col}' não encontrada para checagem de NaNs originais.")


            if df.empty:
                logger.warning(f"Nenhuma linha com valor de resultado original válido encontrada no CSV '{filename}' após remover NaNs. Pulando.")
                failed_files.append(f"{filename} (Sem resultados válidos)")
                continue

            # 6. Limpar Coluna de Resultado para Numérico
            df = _clean_numeric_result_column(df, RESULT_COLUMN_NAME)

            # 7. Selecionar Colunas Finais (garantir ordem e presença das essenciais)
            colunas_essenciais = ['Abertura', 'Fechamento', ROBO_COLUMN_NAME, RESULT_COLUMN_NAME]
            colunas_debug = ['Abertura_Original', 'Fechamento_Original']
             # Adiciona outras colunas que possam existir e não foram explicitamente removidas/renomeadas
            outras_colunas = [col for col in df.columns if col not in colunas_essenciais and col not in colunas_debug]
            # Garante a ordem: essenciais, outras, debug
            colunas_finais = colunas_essenciais + outras_colunas + colunas_debug
            # Apenas colunas que realmente existem no DataFrame
            colunas_presentes = [col for col in colunas_finais if col in df.columns]
            df_final = df[colunas_presentes].copy()


            missing_essentials = [col for col in colunas_essenciais if col not in df_final.columns]
            if missing_essentials:
                 logger.error(f"ERRO CRÍTICO: Colunas essenciais {missing_essentials} ausentes no DataFrame final de '{filename}' mesmo após processamento. Pulando arquivo.")
                 failed_files.append(f"{filename} (Colunas essenciais ausentes)")
                 continue


            dfs.append(df_final)
            processed_files_count += 1
            logger.info(f"--- Processamento do CSV '{filename}' concluído com sucesso. Shape final: {df_final.shape} ---")

        except (ValueError, KeyError, pd.errors.EmptyDataError) as e:
             logger.error(f"Erro ao processar o arquivo CSV '{filename}': {e}", exc_info=True)
             failed_files.append(f"{filename} ({type(e).__name__})")
             continue # Pula para o próximo arquivo
        except Exception as e_proc:
            logger.error(f"Erro inesperado durante o processamento do CSV '{filename}': {e_proc}", exc_info=True)
            logger.error(traceback.format_exc())
            failed_files.append(f"{filename} (Erro inesperado)")
            continue # Pula para o próximo arquivo

    # --- Consolidação ---
    if not dfs:
        logger.error(f"Nenhum arquivo CSV foi processado com sucesso. Arquivos com falha: {failed_files}")
        raise ValueError("Nenhum dado CSV válido pôde ser processado. Verifique os arquivos e os logs.")

    if failed_files:
         logger.warning(f"Alguns arquivos CSV não puderam ser processados ou estavam vazios: {failed_files}")

    logger.info(f"Concatenando dados de {len(dfs)} arquivos CSV processados...")
    banco_geral_bruto = pd.concat(dfs, ignore_index=True)
    logger.info(f"--- DataFrame Consolidado Pós Concatenação ---")
    logger.info(f"Shape total: {banco_geral_bruto.shape}")

    if RESULT_COLUMN_NAME not in banco_geral_bruto.columns:
        logger.critical(f"Erro crítico: Coluna resultado '{RESULT_COLUMN_NAME}' ausente no DataFrame final após concatenação!")
        # Isso indica um problema sério na lógica anterior
        raise ValueError(f"Erro interno: Coluna resultado '{RESULT_COLUMN_NAME}' não encontrada após consolidar os CSVs.")

    logger.info(f"Soma total da coluna '{RESULT_COLUMN_NAME}' no DataFrame consolidado: {banco_geral_bruto[RESULT_COLUMN_NAME].sum():.2f}")

    return banco_geral_bruto, original_result_col_name_found


# --- Função de Processamento Consolidado Final ---

def processar_dados_consolidados(
    banco_geral_bruto: pd.DataFrame,
    result_col: str = RESULT_COLUMN_NAME
) -> Dict[str, Any]:
    """
    Realiza o processamento final nos dados brutos consolidados.

    - Remove linhas com datas de Abertura/Fechamento inválidas (NaT).
    - Calcula métricas gerais (somas, contagens, período).
    - Separa dados com e sem horário definido.
    - Filtra operações dentro do horário de trading (8h-18h).
    - Calcula somas por robô.
    - Prepara dados para geração de gráficos e PDF.

    Args:
        banco_geral_bruto: DataFrame consolidado vindo do processamento de Excel ou CSVs.
        result_col: Nome da coluna que contém o resultado numérico das operações.

    Returns:
        Um dicionário contendo vários DataFrames processados e métricas:
        - 'banco_geral': DF após limpeza final de datas.
        - 'banco_com_hora': DF contendo apenas operações com horário definido (não 00:00).
        - 'banco_filtrado_8_18': DF com operações entre 8h e 18h (inclusive).
        - 'soma_absoluta_total': Soma total dos resultados no DF bruto original.
        - 'somas_absolutas_por_robo': Series com soma de resultados por robô (DF bruto).
        - 'count_operacoes_total_originais': Contagem total de linhas no DF bruto.
        - 'count_operacoes_validas': Contagem de operações após limpar datas inválidas.
        - 'count_operacoes_com_hora': Contagem de operações com horário definido.
        - 'count_operacoes_sem_hora': Contagem de operações sem horário (00:00).
        - 'count_operacoes_8_18': Contagem de operações entre 8h e 18h.
        - 'soma_total_filtrado_8_18': Soma dos resultados das operações entre 8h e 18h.
        - 'data_mais_antiga': Data/hora da primeira operação válida.
        - 'data_mais_recente': Data/hora da última operação válida.
        - 'periodo_str': String formatada do período (DD/MM/YY a DD/MM/YY).
        - 'periodo_completo_str': String formatada do período completo (DD/MM/YYYY - DD/MM/YYYY).
    """
    logger.info("\n--- Iniciando Processamento Consolidado Final ---")
    if banco_geral_bruto.empty:
        logger.error("DataFrame bruto de entrada está vazio. Não é possível processar.")
        raise ValueError("Dados de entrada para processamento consolidado estão vazios.")
    if result_col not in banco_geral_bruto.columns:
         logger.error(f"Coluna de resultado '{result_col}' não encontrada no DataFrame bruto.")
         raise KeyError(f"Coluna de resultado '{result_col}' necessária não encontrada.")
    if 'Abertura' not in banco_geral_bruto.columns or 'Fechamento' not in banco_geral_bruto.columns:
         logger.error("Colunas 'Abertura' ou 'Fechamento' não encontradas no DataFrame bruto.")
         raise KeyError("Colunas de data/hora 'Abertura' e 'Fechamento' são necessárias.")
    if ROBO_COLUMN_NAME not in banco_geral_bruto.columns:
         logger.error(f"Coluna '{ROBO_COLUMN_NAME}' não encontrada no DataFrame bruto.")
         raise KeyError(f"Coluna '{ROBO_COLUMN_NAME}' necessária não encontrada.")

    # --- Cálculos Iniciais (usando dados brutos ANTES de remover datas inválidas) ---
    logger.info(f"Shape Bruto (antes de remover datas inválidas): {banco_geral_bruto.shape}")
    soma_absoluta_total = banco_geral_bruto[result_col].sum()
    logger.info(f"Soma Absoluta Total (Bruta): {soma_absoluta_total:.2f}")
    somas_absolutas_por_robo = banco_geral_bruto.groupby(ROBO_COLUMN_NAME)[result_col].sum()
    logger.info("Somas Absolutas por Robô (Bruta):")
    logger.info(f"\n{somas_absolutas_por_robo.to_string()}") # Log formatado
    count_operacoes_total_originais = len(banco_geral_bruto)
    logger.info(f"Total de Operações Originais (com resultado válido): {count_operacoes_total_originais}")
    
     # --- Limpeza e Preparação de Datas (no DF Bruto para contagem 00:00) ---
    banco_geral_bruto_copy = banco_geral_bruto.copy() # Trabalha com cópia
    banco_geral_bruto_copy['Abertura'] = pd.to_datetime(banco_geral_bruto_copy['Abertura'], errors='coerce')
    # Contagem inicial de 00:00 (antes de filtrar por data válida)
    banco_geral_bruto_copy['Sem_Hora_Original'] = banco_geral_bruto_copy['Abertura'].apply(verificar_operacao_sem_horario)
    # Operações que TINHAM horário específico originalmente (não 00:00 e não NaT na Abertura)
    count_com_hora_original = len(banco_geral_bruto_copy[(banco_geral_bruto_copy['Abertura'].notna()) & (~banco_geral_bruto_copy['Sem_Hora_Original'])])
    # Operações que eram 00:00 originalmente (e tinham data de Abertura não NaT)
    count_sem_hora_original_real_0000 = len(banco_geral_bruto_copy[(banco_geral_bruto_copy['Abertura'].notna()) & (banco_geral_bruto_copy['Sem_Hora_Original'])])
    # >>>>> Contagem que você quer exibir como "Sem Horário Específico" (Total lido - Com hora original) <<<<<
    count_sem_horario_especifico_display = count_operacoes_total_originais - count_com_hora_original

    # --- Limpeza Final de Datas (Abertura) ---
    linhas_com_data_abertura_valida = banco_geral_bruto_copy['Abertura'].notna()
    banco_geral_com_data = banco_geral_bruto_copy[linhas_com_data_abertura_valida].copy()
    count_operacoes_data_valida = len(banco_geral_com_data)

    # --- Limpeza de Fechamento (se necessário) ---
    banco_geral_com_data['Fechamento'] = pd.to_datetime(banco_geral_com_data['Fechamento'], errors='coerce') # Converte fechamento aqui
    linhas_antes_drop_fechamento = len(banco_geral_com_data)
    banco_geral_final = banco_geral_com_data.dropna(subset=['Fechamento'])
    linhas_depois_drop_fechamento = len(banco_geral_final)

    if linhas_antes_drop_fechamento > linhas_depois_drop_fechamento:
        num_removidas_fechamento = linhas_antes_drop_fechamento - linhas_depois_drop_fechamento
        logger.warning(f"{num_removidas_fechamento} linhas foram removidas APÓS filtro de Abertura devido a 'Fechamento' inválido (NaT).")

    logger.info(f"Operações com Data de Abertura Válida: {count_operacoes_data_valida}")
    logger.info(f"Operações usadas para análises com Fechamento: {linhas_depois_drop_fechamento}")

    if banco_geral_final.empty:
        raise ValueError("Não restaram operações com datas válidas após a limpeza completa.")

    # --- Separação e Filtragem por Horário (usando banco_geral_final) ---
    # Recalcula 'Sem_Hora' sobre o dataframe final (já filtrado por data)
    banco_geral_final['Sem_Hora'] = banco_geral_final['Abertura'].apply(verificar_operacao_sem_horario)
    banco_com_hora = banco_geral_final[~banco_geral_final['Sem_Hora']].copy()
    # banco_sem_hora = banco_geral_final[banco_geral_final['Sem_Hora']].copy() # Não precisamos mais desta variável separada
    count_operacoes_com_hora = len(banco_com_hora) # Contagem COM hora específica DENTRO das ops com data válida
    # A contagem de 00:00 DENTRO das ops com data válida é:
    count_operacoes_sem_hora_real_0000_filtrado = count_operacoes_data_valida - count_operacoes_com_hora

    logger.info(f"Operações com horário específico (APÓS filtro de data): {count_operacoes_com_hora}")
    # logger.info(f"Operações sem horário específico - 00:00 (APÓS filtro de data): {count_operacoes_sem_hora_real_0000_filtrado}")
    # Log da contagem para exibição
    logger.info(f"Contagem para exibição 'Sem Horário Específico' (Total Lido - Com Hora Original): {count_sem_horario_especifico_display}")

    banco_filtrado_8_18 = pd.DataFrame()
    count_operacoes_8_18 = 0
    soma_total_filtrado_8_18 = 0.0

    if not banco_com_hora.empty:
        # ... (cálculo de Minutos_Dia, Hora_Abertura, filtro 8-18h - sem mudança) ...
        banco_com_hora['Minutos_Dia'] = banco_com_hora['Abertura'].dt.hour * 60 + banco_com_hora['Abertura'].dt.minute
        banco_com_hora['Hora_Abertura'] = banco_com_hora['Abertura'].dt.hour
        hora_inicio_min = TRADING_HOUR_START * 60
        hora_fim_min = TRADING_HOUR_END * 60 + 59
        filtro_horario = ((banco_com_hora['Minutos_Dia'] >= hora_inicio_min) & (banco_com_hora['Minutos_Dia'] <= hora_fim_min))
        banco_filtrado_8_18 = banco_com_hora[filtro_horario].copy()
        count_operacoes_8_18 = len(banco_filtrado_8_18)
        soma_total_filtrado_8_18 = banco_filtrado_8_18[result_col].sum()
        logger.info(f"Operações COM HORA e entre {TRADING_HOUR_START}h-{TRADING_HOUR_END}h: {count_operacoes_8_18}")
        logger.info(f"Soma dos Resultados (filtrado {TRADING_HOUR_START}h-{TRADING_HOUR_END}h): {soma_total_filtrado_8_18:.2f}")
    else:
        logger.warning("Nenhuma operação com horário específico encontrada para aplicar o filtro de 8h-18h.")
        
    data_mais_antiga = banco_geral_com_data['Abertura'].min()
    data_mais_recente = banco_geral_com_data['Abertura'].max()
    if pd.notna(data_mais_antiga) and pd.notna(data_mais_recente):
        periodo_str = f"{data_mais_antiga.strftime('%d/%m/%y')} a {data_mais_recente.strftime('%d/%m/%y')}"
        periodo_completo_str = f"Período de {data_mais_antiga.strftime('%d/%m/%Y')} a {data_mais_recente.strftime('%d/%m/%Y')}"
        logger.info(f"Período das operações com data válida: {periodo_completo_str}")
    else:
        periodo_str = "N/D"
        periodo_completo_str = "Período não identificado"
        logger.warning("Não foi possível determinar o período das operações (datas inválidas?).")


    # --- Montagem do Dicionário de Resultados ---
    resultados = {
        'banco_geral_com_data': banco_geral_com_data,
        'banco_geral_final': banco_geral_final,
        'banco_com_hora': banco_com_hora,
        # 'banco_sem_hora' não é mais necessário retornar explicitamente
        'banco_filtrado_8_18': banco_filtrado_8_18,
        'soma_absoluta_total': soma_absoluta_total,
        'somas_absolutas_por_robo': somas_absolutas_por_robo,
        'count_operacoes_total_originais': count_operacoes_total_originais,
        'count_operacoes_data_valida': count_operacoes_data_valida,
        'count_operacoes_com_hora': count_operacoes_com_hora,          # Contagem real com hora (após filtro data)
        'count_sem_horario_especifico_display': count_sem_horario_especifico_display, # <<< CONTAGEM PARA EXIBIÇÃO
        'count_operacoes_8_18': count_operacoes_8_18,
        'soma_total_filtrado_8_18': soma_total_filtrado_8_18,
        'data_mais_antiga': data_mais_antiga,
        'data_mais_recente': data_mais_recente,
        'periodo_str': periodo_str,
        'periodo_completo_str': periodo_completo_str,
        'limites_ganho': {} # Inicializa aqui, será preenchido depois
    }

    logger.info("--- Processamento Consolidado Final Concluído ---")
    return resultados