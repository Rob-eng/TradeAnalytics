"""
Módulo para geração de gráficos de análise das operações de trading.

Funções para criar gráficos de:
- Ganhos por minuto (scatter plot)
- Ganho acumulado por robô (stack plot ou line plot)
- Evolução diária do saldo (line plot por dia)
- Ganhos acumulados por intervalo (line plot comparativo)
"""
import os
import logging
from typing import List, Dict, Tuple, Any, Optional
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Usa backend não interativo, essencial para Flask/servidores
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import seaborn as sns
from datetime import time

from config import (
    RELATORIOS_DIR_ABS, # Usado se o path não for passado explicitamente
    CHART_DPI,
    CHART_FORMAT,
    CHART_WIDTH_INCHES,
    # Alturas específicas
    STACKPLOT_HEIGHT_INCHES,
    LINEPLOT_HEIGHT_INCHES,
    SCATTER_HEIGHT_INCHES,
    ACCUM_HEIGHT_INCHES,
    TRADING_HOUR_START,
    TRADING_HOUR_END,
    ROBO_COLUMN_NAME,
    IDEAL_LIMIT_PERCENTILE
)
from .utils import minutos_para_horario

logger = logging.getLogger(__name__)

# --- Funções Auxiliares para Gráficos ---

def _configurar_eixo_tempo_diario(ax, horas_inteiras_minutos, horas_labels):
    """Configura o eixo X para mostrar horas do dia (8h-18h)."""
    ax.set_xticks(horas_inteiras_minutos)
    ax.set_xticklabels(horas_labels)
    ax.set_xlabel('Horário da Operação no Dia')
    ax.grid(axis='x', linestyle='--', alpha=0.6)

def _configurar_eixo_tempo_acumulado(ax):
    """Configura o eixo X para mostrar datas e horas ao longo do tempo."""
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%y %Hh'))
    ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=8, prune='both')) # Auto nbins, remove bordas
    plt.xticks(rotation=30, ha='right')
    ax.set_xlabel('Data e Hora da Operação')
    ax.grid(axis='x', linestyle=':', alpha=0.5)

def _salvar_grafico(fig, output_path: str, nome_grafico: str) -> Optional[str]:
    """Salva a figura do Matplotlib no caminho especificado."""
    # Garante que o nome do arquivo é seguro
    safe_nome_grafico = nome_grafico.replace(" ", "_").replace("/", "_").replace("\\", "_")
    caminho_completo = os.path.join(output_path, f"{safe_nome_grafico}.{CHART_FORMAT}")
    try:
        # Cria o diretório se não existir (caso output_path seja multi-nível)
        os.makedirs(os.path.dirname(caminho_completo), exist_ok=True)
        fig.savefig(caminho_completo, dpi=CHART_DPI, bbox_inches='tight')
        plt.close(fig) # Fecha a figura para liberar memória
        logger.info(f"Gráfico salvo com sucesso: {caminho_completo}")
        return caminho_completo
    except Exception as e:
        logger.error(f"Erro ao salvar o gráfico '{caminho_completo}': {e}", exc_info=True)
        plt.close(fig) # Tenta fechar mesmo em caso de erro
        return None

def _calcular_melhor_intervalo(
    df_intervalo: pd.DataFrame,
    result_col: str,
    minutos_col: str = 'Minutos_Dia',
    min_minuto: int = 8 * 60,    # Minuto inicial padrão (8:00)
    max_minuto: int = 18 * 60 -1 # Minuto final padrão (17:59) - Ajustado para ser inclusivo
) -> Tuple[Optional[int], Optional[int], float]:
    """
    Calcula o intervalo de minutos contíguo com o maior ganho acumulado
    usando um algoritmo O(N) baseado em Kadane.

    Args:
        df_intervalo: DataFrame filtrado (ex: por robô, ou geral 8-18h).
                      Deve conter as colunas `result_col` e `minutos_col`.
        result_col: Nome da coluna com os resultados numéricos.
        minutos_col: Nome da coluna com os minutos do dia da operação.
        min_minuto: O primeiro minuto a ser considerado no intervalo total.
        max_minuto: O último minuto a ser considerado no intervalo total.

    Returns:
        Uma tupla contendo:
        - melhor_inicio_global: Minuto de início do melhor intervalo (ou None).
        - melhor_fim_global: Minuto de fim do melhor intervalo (ou None).
        - max_soma_global: O ganho máximo encontrado nesse intervalo (0.0 se todos negativos ou nenhum)."""
    if df_intervalo.empty or minutos_col not in df_intervalo.columns or result_col not in df_intervalo.columns:
        logger.debug("DataFrame vazio ou colunas ausentes para _calcular_melhor_intervalo.")
        return None, None, 0.0
    df_valid = df_intervalo.dropna(subset=[minutos_col, result_col])
    if df_valid.empty:
        logger.debug("Nenhum dado válido após dropna para _calcular_melhor_intervalo.")
        return None, None, 0.0

    # 1. Agrupar por minuto e somar resultados
    soma_por_minuto = df_valid.groupby(minutos_col)[result_col].sum()

    # Garante que minutos sejam inteiros
    soma_por_minuto.index = soma_por_minuto.index.astype(int)

    # 2. Criar Series completa com todos os minutos no range, preenchendo com 0
    #    Ajusta o range para incluir max_minuto
    todos_minutos = pd.RangeIndex(start=min_minuto, stop=max_minuto + 1, name=minutos_col)
    somas_completas = soma_por_minuto.reindex(todos_minutos, fill_value=0.0)

    # 3. Algoritmo de Kadane modificado para encontrar o intervalo
    max_soma_global = 0.0  # Começa com 0, pois um intervalo vazio tem soma 0
    soma_atual = 0.0
    melhor_inicio_global = None
    melhor_fim_global = None
    inicio_atual = min_minuto # Potencial início do intervalo atual

    primeiro_positivo = True

    for minuto, soma_minuto in somas_completas.items():
        soma_atual += soma_minuto

        if soma_atual > max_soma_global:
            max_soma_global = soma_atual
            melhor_inicio_global = inicio_atual
            melhor_fim_global = minuto # Atualiza o fim para o minuto atual
            if primeiro_positivo:
                 logger.debug(f"  -> Primeiro intervalo positivo encontrado: [{minutos_para_horario(melhor_inicio_global)}-{minutos_para_horario(melhor_fim_global)}] Soma: {max_soma_global:.2f}")
                 primeiro_positivo = False
            else:
                 logger.debug(f"  -> Novo melhor intervalo global: [{minutos_para_horario(melhor_inicio_global)}-{minutos_para_horario(melhor_fim_global)}] Soma: {max_soma_global:.2f}")


        # Se a soma atual ficar negativa, ela não contribuirá positivamente
        # para nenhum intervalo futuro que a inclua. Resetamos a soma
        # e começamos a procurar um novo intervalo a partir do *próximo* minuto.
        if soma_atual < 0:
            soma_atual = 0
            inicio_atual = minuto + 1 # Próximo minuto é o novo potencial início

    # Se max_soma_global permaneceu 0 (ou negativo, o que não deveria acontecer com a lógica acima)
    # significa que não houve intervalo com soma positiva. Retornamos 0.
    if melhor_inicio_global is None:
         logger.info("Nenhum intervalo com soma estritamente positiva encontrado.")
         # Poderíamos retornar o intervalo com a menor perda, mas retornar 0 é mais simples.
         return None, None, 0.0

    # Garante que o minuto final seja retornado corretamente
    # A lógica já atualiza melhor_fim_global quando max_soma_global é atualizado.

    logger.info(f"Melhor intervalo (Otimizado): [{minutos_para_horario(melhor_inicio_global)}-{minutos_para_horario(melhor_fim_global)}], Ganho: {max_soma_global:.2f}")
    return melhor_inicio_global, melhor_fim_global, max_soma_global

# --- Funções de Geração de Gráficos Específicos ---

def gerar_grafico_ganhos_por_minuto(
    df_filtrado_8_18: pd.DataFrame,
    output_dir: str,
    periodo_str: str,
    num_operacoes: int,
    result_col: str
) -> Dict[str, Any]:
    """
    Gera um gráfico de dispersão (scatter plot) dos ganhos por minuto do dia.

    Usa apenas operações entre 8h e 18h com horário definido.
    Calcula e destaca o melhor intervalo geral (8h-18h).
    Calcula e armazena os melhores intervalos individuais por robô.

    Args:
        df_filtrado_8_18: DataFrame contendo APENAS operações entre 8h e 18h.
                          Deve ter colunas 'Minutos_Dia', result_col, ROBO_COLUMN_NAME.
        output_dir: Diretório onde o gráfico será salvo.
        periodo_str: String formatada do período (ex: "DD/MM/YY a DD/MM/YY").
        num_operacoes: Número de operações consideradas no gráfico (len(df_filtrado_8_18)).
        result_col: Nome da coluna de resultado.

    Returns:
        Um dicionário contendo:
        - 'grafico': Caminho completo para o arquivo de imagem do gráfico salvo, ou None se erro.
        - 'tabela': Dados para a tabela de resumo geral a ser incluída no PDF.
        - 'melhor_intervalo_geral': Tupla (inicio_min, fim_min, ganho_max) do melhor intervalo geral 8-18h.
        - 'melhores_intervalos_robos': DataFrame com os melhores intervalos por robô (Robo, Inicio, Fim, Ganho).
    """
    logger.info("--- Gerando Gráfico: Ganhos por Minuto (Scatter Plot 8h-18h) ---")
    grafico_path = None
    tabela_data = None
    melhor_inicio_geral = None
    melhor_fim_geral = None
    max_ganho_geral = 0.0
    df_melhores_robos = pd.DataFrame()

    # Verifica se ROBO_COLUMN_NAME existe antes de usá-lo
    if ROBO_COLUMN_NAME not in df_filtrado_8_18.columns:
        logger.warning(f"Coluna '{ROBO_COLUMN_NAME}' não encontrada no DataFrame filtrado 8-18h. Usando 'Robo_Desconhecido'.")
        # Cria uma coluna padrão para evitar erros posteriores
        if not df_filtrado_8_18.empty:
             df_filtrado_8_18 = df_filtrado_8_18.copy() # Evita SettingWithCopyWarning
             df_filtrado_8_18[ROBO_COLUMN_NAME] = 'Robo_Desconhecido'


    if df_filtrado_8_18.empty or 'Minutos_Dia' not in df_filtrado_8_18.columns:
        logger.warning("DataFrame filtrado 8h-18h está vazio ou sem 'Minutos_Dia'. Gráfico de scatter não será gerado.")
        # Retorna informações vazias/padrão
        return {
            'grafico': None,
            'tabela': None,
            'melhor_intervalo_geral': (None, None, 0.0),
            'melhores_intervalos_robos': df_melhores_robos
        }

    # --- Cálculo do Melhor Intervalo Geral (8h-18h) ---
    logger.info("Calculando melhor intervalo geral (8h-18h)...")
    melhor_inicio_geral, melhor_fim_geral, max_ganho_geral = _calcular_melhor_intervalo(
        df_filtrado_8_18, result_col, 'Minutos_Dia'
    )
    melhor_inicio_geral_hhmm = minutos_para_horario(melhor_inicio_geral)
    melhor_fim_geral_hhmm = minutos_para_horario(melhor_fim_geral)
    if melhor_inicio_geral is not None:
        logger.info(f"Melhor Intervalo Geral (8-18h) Final: [{melhor_inicio_geral_hhmm}-{melhor_fim_geral_hhmm}], Ganho: {max_ganho_geral:.2f}")
    else:
        logger.info("Nenhum intervalo geral (8-18h) com ganho válido encontrado.")
        # max_ganho_geral já será 0.0 vindo de _calcular_melhor_intervalo

    # --- Cálculo dos Melhores Intervalos Individuais por Robô (8h-18h) ---
    melhores_intervalos_robos_list = []
    robos_unicos_8_18 = df_filtrado_8_18[ROBO_COLUMN_NAME].unique()
    logger.info(f"Calculando melhores intervalos individuais (8-18h) para {len(robos_unicos_8_18)} robôs...")
    for robo in robos_unicos_8_18:
        df_robo_8_18 = df_filtrado_8_18[df_filtrado_8_18[ROBO_COLUMN_NAME] == robo]
        if not df_robo_8_18.empty:
            inicio_robo, fim_robo, ganho_robo = _calcular_melhor_intervalo(
                df_robo_8_18, result_col, 'Minutos_Dia'
            )
            if inicio_robo is not None: # Apenas adiciona se um intervalo válido foi encontrado
                 melhores_intervalos_robos_list.append({
                    'Robo': robo,
                    'Inicio_Intervalo': inicio_robo,
                    'Fim_Intervalo': fim_robo,
                    'Ganho': ganho_robo
                })
            # else:
            #      logger.debug(f"Nenhum intervalo 8-18h válido encontrado para o robô {robo}.")

    df_melhores_robos = pd.DataFrame(melhores_intervalos_robos_list)
    if not df_melhores_robos.empty:
        logger.info("Melhores intervalos individuais (8-18h) calculados.")
        # logger.debug(f"\n{df_melhores_robos.to_string()}") # Log detalhado opcional
    else:
        logger.info("Nenhum melhor intervalo individual (8-18h) pôde ser calculado.")


    # --- Geração do Gráfico Scatter Plot ---
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, SCATTER_HEIGHT_INCHES))

    # Agrega dados por Robo e Minuto para evitar overplotting e calcular tamanho/cor corretamente
    df_agg = df_filtrado_8_18.groupby([ROBO_COLUMN_NAME, 'Minutos_Dia'])[result_col].sum().reset_index()

    # Cria o scatter plot
    try:
        scatter = sns.scatterplot(
            data=df_agg,
            x='Minutos_Dia',
            y=result_col,
            hue=ROBO_COLUMN_NAME,
            size=result_col, # Tamanho proporcional ao resultado (cuidado com negativos)
            sizes=(20, 150), # Intervalo de tamanhos dos pontos1
            alpha=0.65,
            ax=ax,
            legend='auto' # Ou 'brief' ou False
        )
    except Exception as e_scatter:
        logger.error(f"Erro ao gerar scatter plot: {e_scatter}", exc_info=True)
        plt.close(fig)
        return { # Retorna dados vazios mas com a tabela para não quebrar o PDF
            'grafico': None,
            'tabela': None, # Decide se a tabela ainda faz sentido
            'melhor_intervalo_geral': (melhor_inicio_geral, melhor_fim_geral, max_ganho_geral),
            'melhores_intervalos_robos': df_melhores_robos
        }


    # Linha horizontal em y=0
    ax.axhline(y=0, color='black', linestyle='--', linewidth=0.8, alpha=0.7)

    # Linhas verticais para o MELHOR intervalo GERAL (8-18h)
    if melhor_inicio_geral is not None and melhor_fim_geral is not None:
        ax.axvline(x=melhor_inicio_geral, color='purple', linestyle=':', linewidth=1.5,
                   label=f'Melhor Geral ({melhor_inicio_geral_hhmm}-{melhor_fim_geral_hhmm})')
        ax.axvline(x=melhor_fim_geral, color='purple', linestyle=':', linewidth=1.5)

    # Configuração do eixo X (horas)
    horas_inteiras_minutos = range(TRADING_HOUR_START * 60, (TRADING_HOUR_END + 1) * 60, 60)
    horas_labels = [f"{h}h" for h in range(TRADING_HOUR_START, TRADING_HOUR_END + 1)]
    _configurar_eixo_tempo_diario(ax, horas_inteiras_minutos, horas_labels)
    # Define limites do eixo X com uma margem
    ax.set_xlim(TRADING_HOUR_START * 60 - 30, (TRADING_HOUR_END * 60 + 59) + 30)


    # Títulos e Rótulos
    ax.set_title(f'Ganhos por Minuto - Todos Robôs ({periodo_str})\nOperações entre {TRADING_HOUR_START}h-{TRADING_HOUR_END}h (N={num_operacoes})', fontsize=12)
    ax.set_ylabel('Resultado da Operação (Pontos)')
    ax.grid(axis='y', linestyle='--', alpha=0.6)

    # Legenda fora do gráfico para não obstruir os pontos
    # Verifica se há mais de um robô para justificar a legenda de robôs
    if len(robos_unicos_8_18) > 1:
        ax.legend(bbox_to_anchor=(1.04, 1), loc='upper left', title="Robôs", fontsize='small')
        plt.tight_layout(rect=[0, 0, 0.85, 1]) # Ajusta layout para caber a legenda
    else:
        # Se só tem 1 robô, remove a legenda de robô e ajusta layout
        if ax.get_legend() is not None:
            ax.get_legend().remove()
        plt.tight_layout()


    # Salvar gráfico
    grafico_path = _salvar_grafico(fig, output_dir, 'ganhos_por_minuto_todos_robos_8_18')

    # --- Preparar dados da Tabela ---
    # Calcula somas para intervalos específicos (ex: 9:15-12:30) para a tabela
    # Usa o DataFrame filtrado 8-18h que já possui 'Minutos_Dia'
    soma_geral_bruta_placeholder = "{SOMA_GERAL_BRUTA_PLACEHOLDER}" # Será substituído depois
    soma_melhores_individuais_placeholder = "{SOMA_MELHORES_INDIVIDUAIS_PLACEHOLDER}" # Será substituído depois

    # Define os intervalos fixos de interesse
    intervalos_fixos = {
        '9:15-12:30': (9*60+15, 12*60+30),
        '9:00-12:30': (9*60, 12*60+30),
        '10:00-12:30': (10*60, 12*60+30),
    }
    somas_intervalos_fixos = {}
    for nome, (inicio_min, fim_min) in intervalos_fixos.items():
        mask_intervalo = (
            (df_filtrado_8_18['Minutos_Dia'] >= inicio_min) &
            (df_filtrado_8_18['Minutos_Dia'] <= fim_min)
        )
        somas_intervalos_fixos[nome] = df_filtrado_8_18.loc[mask_intervalo, result_col].sum()

    # Monta a estrutura da tabela
    melhor_intervalo_geral_label = f"Melhor ({melhor_inicio_geral_hhmm}-{melhor_fim_geral_hhmm}, 8-18h)" if melhor_inicio_geral is not None else "Melhor (N/A, 8-18h)"

    cabecalho_tabela = ['Geral (Todas Ops Brutas)', melhor_intervalo_geral_label, 'Soma Melhores Indiv. (8-18h)'] + list(intervalos_fixos.keys())
    valores_tabela = [
        f"{soma_geral_bruta_placeholder}", # Valor será preenchido depois
        f"{max_ganho_geral:.2f}",
        f"{soma_melhores_individuais_placeholder}", # Valor será preenchido depois
    ] + [f"{soma:.2f}" for soma in somas_intervalos_fixos.values()]

    # Define um título mais descritivo, mesclado na primeira linha
    titulo_tabela = f'Resultados Consolidados (N Operações 8-18h: {num_operacoes})'
    # A primeira linha da lista de dados será o título mesclado
    tabela_data = [
        [titulo_tabela] + [''] * (len(cabecalho_tabela) - 1), # Linha 0: Título
        cabecalho_tabela,                                     # Linha 1: Cabeçalhos
        valores_tabela                                        # Linha 2: Valores
    ]
    logger.info("Dados da tabela para o gráfico de ganhos por minuto preparados.")

    return {
        'grafico': grafico_path,
        'tabela': tabela_data,
        'melhor_intervalo_geral': (melhor_inicio_geral, melhor_fim_geral, max_ganho_geral),
        'melhores_intervalos_robos': df_melhores_robos
    }

# --- NOVA FUNÇÃO ---
def gerar_grafico_acumulado_total(
    df_geral_com_data: pd.DataFrame, # Recebe o DF com todas as operações com data válida
    output_dir: str,
    periodo_str: str,
    result_col: str
) -> Dict[str, Any]:
    """
    Gera um gráfico de linha mostrando APENAS o acumulado total geral,
    usando todas as operações com data válida.

    Args:
        df_geral_com_data: DataFrame com todas as operações com data de abertura válida.
                           Deve ter colunas 'Abertura', result_col.
        output_dir: Diretório onde o gráfico será salvo.
        periodo_str: String formatada do período (ex: "DD/MM/YY a DD/MM/YY").
        result_col: Nome da coluna de resultado.

    Returns:
        Um dicionário contendo:
        - 'grafico': Caminho completo para o arquivo de imagem do gráfico salvo, ou None se erro.
        - 'tabela': None.
    """
    logger.info("--- Gerando Gráfico: Acumulado Total Geral (Linha) ---")
    grafico_path = None

    required_cols = ['Abertura', result_col]
    if df_geral_com_data.empty or any(col not in df_geral_com_data.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df_geral_com_data.columns]
        logger.warning(f"DataFrame geral vazio ou sem colunas necessárias ({missing}) para gráfico acumulado total.")
        return {'grafico': None, 'tabela': None}

    # --- GARANTIR ORDEM CRONOLÓGICA ---
    df_sorted = df_geral_com_data.sort_values('Abertura').copy()

    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES * 1.2, ACCUM_HEIGHT_INCHES))

    # --- Calcular e Plotar Acumulado Total ---
    df_sorted['Acumulado_Total'] = df_sorted[result_col].cumsum()
    ax.plot(df_sorted['Abertura'], df_sorted['Acumulado_Total'],
            label='Total Geral (Todas Ops Consideradas)', color='black', linewidth=2) # Legenda simples

    # --- Configurações Finais do Gráfico ---
    ax.axhline(y=0, color='grey', linestyle='-', linewidth=0.8)
    ax.set_title(f'Resultado Acumulado Total Geral ({periodo_str})', fontsize=12)
    ax.set_ylabel('Ganho Acumulado (Pontos)')
    _configurar_eixo_tempo_acumulado(ax)
    # Não precisa de legenda complexa aqui, só a do plot
    ax.legend(loc='best', fontsize='small')
    ax.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()

    # Salvar gráfico
    grafico_path = _salvar_grafico(fig, output_dir, 'ganho_acumulado_total_geral') # Nome específico

    return {'grafico': grafico_path, 'tabela': None}

# --- NOVA FUNÇÃO ---
def gerar_grafico_acumulado_por_robo(
    df_geral_com_data: pd.DataFrame, # Recebe o DF com todas as operações com data válida
    output_dir: str,
    periodo_str: str,
    result_col: str
) -> Dict[str, Any]:
    """
    Gera um gráfico de linha mostrando APENAS o acumulado individual
    de cada robô, usando todas as operações com data válida.

    Args:
        df_geral_com_data: DataFrame com todas as operações com data de abertura válida.
                           Deve ter colunas 'Abertura', result_col, ROBO_COLUMN_NAME.
        output_dir: Diretório onde o gráfico será salvo.
        periodo_str: String formatada do período (ex: "DD/MM/YY a DD/MM/YY").
        result_col: Nome da coluna de resultado.

    Returns:
        Um dicionário contendo:
        - 'grafico': Caminho completo para o arquivo de imagem do gráfico salvo, ou None se erro.
        - 'tabela': None.
    """
    logger.info("--- Gerando Gráfico: Acumulado Individual por Robô (Linhas) ---")
    grafico_path = None

    required_cols = ['Abertura', result_col, ROBO_COLUMN_NAME]
    if df_geral_com_data.empty or any(col not in df_geral_com_data.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df_geral_com_data.columns]
        logger.warning(f"DataFrame geral vazio ou sem colunas necessárias ({missing}) para gráfico acumulado por robô.")
        return {'grafico': None, 'tabela': None}

    # --- GARANTIR ORDEM CRONOLÓGICA ---
    df_sorted = df_geral_com_data.sort_values('Abertura').copy()

    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES * 1.2, ACCUM_HEIGHT_INCHES))

    # --- Calcular e Plotar Acumulado por Robô ---
    robos_unicos = sorted(df_sorted[ROBO_COLUMN_NAME].unique())
    # Usar um colormap com cores distintas. 'tab20' ou 'Vega20' são boas opções.
    # Se tiver mais de 20 robôs, as cores podem repetir ou precisar de outra estratégia.
    try:
        colors = plt.cm.get_cmap('tab20', len(robos_unicos))
    except ValueError: # Fallback se o número de robôs for muito pequeno/grande para cmap
        colors = plt.cm.get_cmap('tab10', len(robos_unicos))


    for i, robo_name in enumerate(robos_unicos):
        df_robo = df_sorted[df_sorted[ROBO_COLUMN_NAME] == robo_name]
        if not df_robo.empty:
            df_robo['Acumulado_Robo'] = df_robo[result_col].cumsum()
            ax.plot(df_robo['Abertura'], df_robo['Acumulado_Robo'],
                    label=robo_name,
                    color=colors(i % colors.N), # Usa módulo para repetir cores se necessário
                    linewidth=1.2, # Linhas mais finas
                    alpha=0.85)
        else:
            logger.debug(f"Sem dados para plotar acumulado do robô: {robo_name}")


    # --- Configurações Finais do Gráfico ---
    ax.axhline(y=0, color='grey', linestyle='-', linewidth=0.8)
    ax.set_title(f'Resultado Acumulado Individual por Robô ({periodo_str})', fontsize=12)
    ax.set_ylabel('Ganho Acumulado (Pontos)')
    _configurar_eixo_tempo_acumulado(ax)

    # Ajusta legenda
    if len(robos_unicos) > 15:
        ax.legend(loc='best', fontsize='x-small', title="Robôs", ncol=2)
    elif len(robos_unicos) > 0:
         ax.legend(loc='best', fontsize='small', title="Robôs")

    ax.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()

    # Salvar gráfico
    grafico_path = _salvar_grafico(fig, output_dir, 'ganho_acumulado_por_robo') # Nome específico

    return {'grafico': grafico_path, 'tabela': None}





def _gerar_grafico_linha_diaria_robo(
    df_robo_full: pd.DataFrame,
    robo_name: str,
    output_dir: str,
    periodo_robo_str: str,
    result_col: str
) -> Tuple[Optional[str], int]:
    """
    Gera gráfico de linha da evolução do saldo DENTRO de cada dia para um robô.
    Calcula e retorna o limite ideal sugerido (percentil dos picos diários).
    """
    logger.debug(f"--- Gerando Gráfico: Evolução Diária do Saldo para {robo_name} ---")
    grafico_path = None
    melhor_limite = 0
    
    df_robo_com_data = df_robo_full # Mantem nome interno para consistência

    if df_robo_com_data.empty or 'Abertura' not in df_robo_com_data.columns:
        logger.warning(f"Dados insuficientes para gerar gráfico de linha diária para {robo_name}.")
        return None, 0

    df_linha = df_robo_com_data.dropna(subset=['Abertura', result_col]).sort_values('Abertura').copy()
    if df_linha.empty:
         logger.warning(f"Dados insuficientes após dropna para gráfico de linha diária para {robo_name}.")
         return None, 0

    df_linha['Dia'] = df_linha['Abertura'].dt.date
    dias_com_operacoes = sorted(df_linha['Dia'].unique())

    if not dias_com_operacoes:
        logger.warning(f"Nenhum dia com operações encontrado para {robo_name}.")
        return None, 0

    # --- Cálculo do Limite Ideal (Percentil dos Picos Diários Positivos) ---
    picos_diarios = []
    for dia in dias_com_operacoes:
        df_dia = df_linha[df_linha['Dia'] == dia]
        # Calcula o saldo acumulado dentro do dia
        ganhos_acumulados_dia = df_dia[result_col].cumsum().tolist()
        # Adiciona 0 no início e pega o máximo (pico) do dia
        pico_dia = max([0] + ganhos_acumulados_dia) if ganhos_acumulados_dia else 0
        picos_diarios.append(pico_dia)

    picos_positivos = [p for p in picos_diarios if p > 0]
    if picos_positivos:
        # Usa o percentil definido em config.py
        try:
             melhor_limite = int(np.percentile(picos_positivos, IDEAL_LIMIT_PERCENTILE))
             logger.info(f"Limite ideal (P{IDEAL_LIMIT_PERCENTILE} picos+) para {robo_name}: {melhor_limite} pts")
        except Exception as e_perc:
             logger.error(f"Erro ao calcular percentil {IDEAL_LIMIT_PERCENTILE} para {robo_name}: {e_perc}", exc_info=True)
             melhor_limite = 0 # Define como 0 em caso de erro
    else:
        melhor_limite = 0
        logger.info(f"Nenhum pico diário positivo encontrado para {robo_name}, limite ideal definido como 0.")


    # --- Preparação dos Dados para Plotagem (Eixo X Contínuo) ---
    tempos_plot_global = [] # Lista de arrays numpy de tempos (x) para cada dia
    ganhos_plot_global = [] # Lista de arrays numpy de ganhos (y) para cada dia
    inicios_dias_x = []     # Posição X do início de cada dia no plot contínuo
    labels_dias = []        # Labels para o eixo X (DD/MM)
    tempo_total_plot = 0    # Contador para deslocar o eixo X

    for dia_dt in dias_com_operacoes:
        df_dia_plot = df_linha[df_linha['Dia'] == dia_dt].sort_values('Abertura')
        if df_dia_plot.empty:
            continue

        try:
            # Ponto inicial do dia (tempo 0, ganho 0 relativo ao início do dia no plot)
            inicio_dia_base_dt = pd.to_datetime(f"{dia_dt.strftime('%Y-%m-%d')} 00:00:00")
            tempos_dia_rel = [0] # Tempo relativo em minutos desde meia-noite
            ganhos_dia_acum = [0] # Ganho acumulado no dia
            ganho_acum_atual = 0.0

            for _, row in df_dia_plot.iterrows():
                if pd.isna(row['Abertura']): continue
                # Calcula minutos desde a meia-noite daquele dia
                minutos_desde_meia_noite = (row['Abertura'] - inicio_dia_base_dt).total_seconds() / 60
                # Adiciona ponto ANTES da operação (mantém valor anterior)
                tempos_dia_rel.append(minutos_desde_meia_noite)
                ganhos_dia_acum.append(ganho_acum_atual)
                # Atualiza ganho e adiciona ponto APÓS a operação
                ganho_acum_atual += row[result_col]
                tempos_dia_rel.append(minutos_desde_meia_noite)
                ganhos_dia_acum.append(ganho_acum_atual)

            # Garante que a linha vá até o fim do dia (23:59) com o último valor
            minutos_fim_dia = 24 * 60 - 1
            if not tempos_dia_rel or tempos_dia_rel[-1] < minutos_fim_dia:
                tempos_dia_rel.append(minutos_fim_dia)
                ganhos_dia_acum.append(ganho_acum_atual) # Mantém o último ganho

            if len(tempos_dia_rel) > 1: # Só adiciona se houve alguma operação no dia
                 # Desloca os tempos relativos pela posição atual no eixo X global
                 tempos_plot_global.append(np.array(tempos_dia_rel) + tempo_total_plot)
                 ganhos_plot_global.append(np.array(ganhos_dia_acum))
                 inicios_dias_x.append(tempo_total_plot) # Marca o início do dia
                 labels_dias.append(dia_dt.strftime('%d/%m'))
                 tempo_total_plot += (24 * 60) # Avança o eixo X em 1 dia (em minutos)

        except Exception as e_dia:
             logger.error(f"Erro ao processar dia {dia_dt} para gráfico de linha de {robo_name}: {e_dia}", exc_info=True)
             continue # Pula para o próximo dia

    # --- Geração do Gráfico de Linha ---
    if not tempos_plot_global:
        logger.warning(f"Nenhum dado válido para plotar no gráfico de linha diária de {robo_name}.")
        return None, melhor_limite # Retorna o limite calculado, mesmo sem gráfico

    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES * 1.3, LINEPLOT_HEIGHT_INCHES)) # Mais largo
    max_y = 0
    min_y = 0

    # Plota a linha para cada dia
    for idx_dia, (tempos_dia, ganhos_dia) in enumerate(zip(tempos_plot_global, ganhos_plot_global)):
        ax.plot(tempos_dia, ganhos_dia,
                label='_nolegend_' if idx_dia > 0 else f'{robo_name} - Saldo Diário', # Legenda só na primeira linha
                color='royalblue', linewidth=1.2)
        # Atualiza limites Y
        if ganhos_dia.size > 0:
            max_y = max(max_y, ganhos_dia.max())
            min_y = min(min_y, ganhos_dia.min())

    # Linhas verticais separando os dias
    for inicio_dia_x in inicios_dias_x[1:]: # Pula a primeira (posição 0)
        ax.axvline(x=inicio_dia_x, color='grey', linestyle=':', linewidth=0.7, alpha=0.6)

    # Linha horizontal do limite ideal, se aplicável
    if melhor_limite != 0:
        ax.axhline(y=melhor_limite, color='darkorange', linestyle='--', linewidth=1.5,
                   label=f'Limite Ideal (P{IDEAL_LIMIT_PERCENTILE}={melhor_limite} pts)')

    # Linha horizontal em y=0
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

    # Configuração do Eixo X (Marcadores de Dia)
    ax.set_xticks(inicios_dias_x)
    ax.set_xticklabels(labels_dias, rotation=45, ha='right', fontsize=8)
    # Controla o número de ticks para não poluir
    ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=min(len(inicios_dias_x), 30), integer=True))

    # Títulos e Rótulos
    ax.set_title(f'Evolução Diária do Saldo - Robô {robo_name} ({periodo_robo_str})', fontsize=11)
    ax.set_xlabel('Dias')
    ax.set_ylabel('Saldo Acumulado no Dia (Pontos)')
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend(loc='best', fontsize='small')

    # Ajusta limites Y para melhor visualização
    padding_y = (max_y - min_y) * 0.1 + 5 # Adiciona padding mínimo de 5 pontos
    # Garante que 0 esteja visível se os limites forem ambos positivos ou negativos
    final_min_y = min(min_y - padding_y, -padding_y if min_y > 0 else min_y - padding_y)
    final_max_y = max(max_y + padding_y, padding_y if max_y < 0 else max_y + padding_y)
    ax.set_ylim(final_min_y, final_max_y)


    plt.tight_layout()

    # Salvar gráfico
    safe_robo_name = robo_name.replace(" ", "_").replace("/", "_").replace("\\", "_") # Nome seguro para arquivo
    grafico_path = _salvar_grafico(fig, output_dir, f'linha_ganho_diario_{safe_robo_name}')

    return grafico_path, melhor_limite


def _gerar_grafico_acumulado_intervalos_robo(
    df_robo_com_data: pd.DataFrame, # <<< Renomeado, recebe DF com data válida
    df_robo_filtrado_8_18: pd.DataFrame,
    robo_name: str,
    output_dir: str,
    periodo_robo_str: str,
    result_col: str,
    melhor_inicio_robo_8_18: Optional[int],
    melhor_fim_robo_8_18: Optional[int]
) -> Optional[str]:
    """
    Gera gráfico de linha comparando o resultado acumulado (com data válida) com o
    acumulado de diferentes intervalos de operação diária para um robô.
    """
    logger.debug(f"--- Gerando Gráfico: Acumulado por Intervalo para {robo_name} ---")
    grafico_path = None

    if df_robo_com_data.empty or 'Abertura' not in df_robo_com_data.columns: #<<< Checa DF correto
        logger.warning(f"Dados com data válida insuficientes para gerar gráfico acumulado por intervalo para {robo_name}.")
        return None
    
    # Ordena ambos os dataframes pela coluna 'Abertura' antes de qualquer cálculo cumulativo
    df_acum = df_robo_com_data.sort_values('Abertura').copy()
    df_robo_filtrado_8_18 = df_robo_filtrado_8_18.sort_values('Abertura').copy()

    df_acum = df_robo_com_data.dropna(subset=['Abertura', result_col]).sort_values('Abertura').copy() #<<< Usa DF correto
    if df_acum.empty:
        logger.warning(f"Dados insuficientes após dropna para gráfico acumulado por intervalo para {robo_name}.")
        return None

    # --- Calcula Acumulado Total (Ops com Data Válida) ---
    df_acum['Resultado_Acumulado_Total'] = df_acum[result_col].cumsum()

    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES * 1.2, ACCUM_HEIGHT_INCHES))

    # --- Plota Acumulado Total ---
    ax.plot(df_acum['Abertura'], df_acum['Resultado_Acumulado_Total'],
            label='Total Robô (Todas Ops Consideradas)', color='black', linewidth=1.8, zorder=3)

    # --- CORREÇÃO 1: Calcular e Plotar Acumulado 8h-18h ---
    if not df_robo_filtrado_8_18.empty:
        df_robo_filtrado_8_18['Acumulado_8_18'] = df_robo_filtrado_8_18[result_col].cumsum()
        ax.plot(df_robo_filtrado_8_18['Abertura'], df_robo_filtrado_8_18['Acumulado_8_18'],
                label=f'Acumulado {TRADING_HOUR_START}h-{TRADING_HOUR_END}h', color='mediumblue', linestyle='-.', # Cor/estilo diferente
                linewidth=1.5, alpha=0.9, zorder=4)
    else:
        logger.warning(f"Sem dados {TRADING_HOUR_START}h-{TRADING_HOUR_END}h para {robo_name} para plotar linha acumulada específica.")
    # -----------------------------------------------------

    # --- Plotar Acumulados por Intervalos (usando df_com_hora) ---
    df_com_hora = df_acum[
        df_acum['Abertura'].apply(lambda x: not pd.isna(x) and x.time() != time(0, 0, 0))
        ].copy() # Filtra a partir do df_acum já ordenado

    if not df_com_hora.empty:
         if 'Minutos_Dia' not in df_com_hora.columns:
              try:
                  df_com_hora['Minutos_Dia'] = df_com_hora['Abertura'].dt.hour * 60 + df_com_hora['Abertura'].dt.minute
              except AttributeError:
                  logger.warning(f"Não foi possível calcular 'Minutos_Dia' para {robo_name} em acum_intervalo. Intervalos não serão plotados.")
                  df_com_hora = pd.DataFrame()

         if not df_com_hora.empty:
             melhor_inicio_hhmm = minutos_para_horario(melhor_inicio_robo_8_18)
             melhor_fim_hhmm = minutos_para_horario(melhor_fim_robo_8_18)
             label_melhor = f'Melhor ({melhor_inicio_hhmm}-{melhor_fim_hhmm})' if melhor_inicio_robo_8_18 is not None else None
             intervals_robo = {}
             if label_melhor:
                  intervals_robo[label_melhor] = (melhor_inicio_robo_8_18, melhor_fim_robo_8_18, 'green', '--')
             intervals_robo.update({
                '9:15-12:30': (9*60+15, 12*60+30, 'dodgerblue', ':'),
                '9:00-12:30': (9*60, 12*60+30, 'red', ':'),
                '10:00-12:30': (10*60, 12*60+30, 'darkviolet', ':'),
             })
             for label, (start_min, end_min, color, linestyle) in intervals_robo.items():
                if start_min is None or end_min is None: continue
                mask_intervalo = (
                    (df_com_hora['Minutos_Dia'] >= start_min) &
                    (df_com_hora['Minutos_Dia'] <= end_min)
                )
                # Filtra df_com_hora que já está ordenado por Abertura
                df_intervalo = df_com_hora[mask_intervalo].copy()
                if not df_intervalo.empty:
                    # Não precisa reordenar aqui
                    df_intervalo['Resultado_Acumulado_Intervalo'] = df_intervalo[result_col].cumsum()
                    ax.plot(df_intervalo['Abertura'], df_intervalo['Resultado_Acumulado_Intervalo'],
                            label=f'Acum. {label}', color=color, linestyle=linestyle,
                            linewidth=1.2, alpha=0.85)
                else:
                    logger.debug(f"Nenhuma operação encontrada para o intervalo '{label}' do robô {robo_name}.")

    else:
        logger.warning(f"Nenhuma operação COM HORA encontrada para plotar intervalos no gráfico acumulado de {robo_name}.")

    # --- Configurações Finais do Gráfico ---
    ax.set_title(f'Resultado Acumulado - {robo_name} ({periodo_robo_str})\nTotal vs Acumulados por Intervalo Diário', fontsize=11) # <<< Simplificado
    ax.set_ylabel('Resultado Acumulado (Pontos)')
    _configurar_eixo_tempo_acumulado(ax)
    ax.legend(loc='best', fontsize='small')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    ax.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()

    # Salvar gráfico
    safe_robo_name = robo_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    grafico_path = _salvar_grafico(fig, output_dir, f'acumulado_intervalos_{safe_robo_name}')

    return grafico_path


# --- Função Principal de Geração por Robô ---

def gerar_graficos_por_robo(
    df_geral_com_data: pd.DataFrame, # <<< Renomeado para clareza
    df_filtrado_8_18: pd.DataFrame,
    output_dir: str,
    somas_absolutas_por_robo: pd.Series,
    periodo_geral_str: str,
    result_col: str
) -> Tuple[List[Dict[str, Any]], float, Dict[str, int]]:
    """
    Gera um conjunto de gráficos e tabelas para cada robô individualmente.
    # ... (docstring) ...
    """
    graficos_por_robo_list: List[Dict[str, Any]] = []
    limites_ganho: Dict[str, int] = {}
    soma_melhores_ganhos_individuais_8_18 = 0.0

    if ROBO_COLUMN_NAME not in df_geral_com_data.columns: # <<< Verifica no DF correto
         logger.error(f"Coluna '{ROBO_COLUMN_NAME}' não encontrada no DataFrame geral com data. Não é possível gerar gráficos por robô.")
         return [], 0.0, {}

    robos_unicos = sorted(df_geral_com_data[ROBO_COLUMN_NAME].unique()) # <<< Pega robôs do DF correto
    logger.info(f"--- Iniciando geração de gráficos para {len(robos_unicos)} robôs individuais ---")

    for robo_name in robos_unicos:
        logger.info(f"\n--- Processando Robô: {robo_name} ---")

        # Filtra dados para o robô atual
        df_robo_full_com_data = df_geral_com_data[df_geral_com_data[ROBO_COLUMN_NAME] == robo_name].copy() # <<< Usa DF com data válida
        df_robo_filtrado_8_18 = pd.DataFrame()
        if ROBO_COLUMN_NAME in df_filtrado_8_18.columns: # Checa se a coluna existe no DF 8-18
            df_robo_filtrado_8_18 = df_filtrado_8_18[df_filtrado_8_18[ROBO_COLUMN_NAME] == robo_name].copy()

        if df_robo_full_com_data.empty: # <<< Checa o DF com data válida
            logger.warning(f"Nenhuma operação com data válida encontrada para o robô {robo_name}. Pulando.")
            continue

        # Calcula período específico do robô (usando DF com data válida)
        data_min_robo = df_robo_full_com_data['Abertura'].min() # <<< Usa DF com data válida
        data_max_robo = df_robo_full_com_data['Abertura'].max() # <<< Usa DF com data válida
        periodo_robo_str = f"{data_min_robo.strftime('%d/%m/%y')} a {data_max_robo.strftime('%d/%m/%y')}" if pd.notna(data_min_robo) and pd.notna(data_max_robo) else periodo_geral_str
        count_robo_data_valida = len(df_robo_full_com_data) # <<< Usa contagem do DF com data válida
        count_robo_8_18 = len(df_robo_filtrado_8_18)


        # --- Calcular Melhor Intervalo (8h-18h) específico do Robô ---
        logger.info(f"Calculando melhor intervalo 8-18h para {robo_name}...")
        melhor_inicio_robo, melhor_fim_robo, max_ganho_robo_8_18 = _calcular_melhor_intervalo(
            df_robo_filtrado_8_18, result_col, 'Minutos_Dia'
        )
        melhor_inicio_robo_hhmm = minutos_para_horario(melhor_inicio_robo)
        melhor_fim_robo_hhmm = minutos_para_horario(melhor_fim_robo)

        if melhor_inicio_robo is not None:
            logger.info(f"Melhor intervalo (8-18h) para {robo_name}: [{melhor_inicio_robo_hhmm}-{melhor_fim_robo_hhmm}], Ganho: {max_ganho_robo_8_18:.2f}")
            soma_melhores_ganhos_individuais_8_18 += max_ganho_robo_8_18 # Acumula na soma geral
        else:
            logger.info(f"Nenhum intervalo válido 8h-18h com ganho encontrado para {robo_name}. Ganho considerado 0.0 para a soma.")
            max_ganho_robo_8_18 = 0.0 # Garante que seja 0 se nenhum intervalo foi achado


        # --- Gerar Gráfico Scatter Plot do Robô (8h-18h) ---
        caminho_grafico_scatter = None
        if not df_robo_filtrado_8_18.empty and 'Minutos_Dia' in df_robo_filtrado_8_18.columns:
            logger.debug(f"Gerando scatter plot 8-18h para {robo_name}...")
            fig_sc, ax_sc = plt.subplots(figsize=(CHART_WIDTH_INCHES, SCATTER_HEIGHT_INCHES))
            try:
                sns.scatterplot(data=df_robo_filtrado_8_18, x='Minutos_Dia', y=result_col, alpha=0.7, ax=ax_sc,
                                color='tab:blue', size=result_col, sizes=(20, 200), legend=False) # Sem legenda aqui
                ax_sc.axhline(y=0, color='black', linestyle='--', linewidth=0.8)

                # Adiciona linhas do melhor intervalo 8-18h do robô
                if melhor_inicio_robo is not None:
                    ax_sc.axvline(x=melhor_inicio_robo, color='red', linestyle='--', linewidth=1.5,
                                   label=f'Melhor ({melhor_inicio_robo_hhmm}-{melhor_fim_robo_hhmm}, 8-18h)')
                    ax_sc.axvline(x=melhor_fim_robo, color='red', linestyle='--', linewidth=1.5)

                # Highlight intervalo 9:15-12:30 (opcional)
                # ax_sc.axvspan(9*60+15, 12*60+30, color='lightgrey', alpha=0.3, label='Intervalo 9:15-12:30')

                horas_inteiras_minutos = range(TRADING_HOUR_START * 60, (TRADING_HOUR_END + 1) * 60, 60)
                horas_labels = [f"{h}h" for h in range(TRADING_HOUR_START, TRADING_HOUR_END + 1)]
                _configurar_eixo_tempo_diario(ax_sc, horas_inteiras_minutos, horas_labels)
                # Define limites do eixo X com uma margem
                ax_sc.set_xlim(TRADING_HOUR_START * 60 - 30, (TRADING_HOUR_END * 60 + 59) + 30)


                ax_sc.set_title(f'Operações por Minuto - {robo_name} ({periodo_robo_str})\n(N={count_robo_8_18} ops entre {TRADING_HOUR_START}h-{TRADING_HOUR_END}h)', fontsize=11)
                ax_sc.set_ylabel('Resultado da Operação (Pontos)')
                ax_sc.grid(axis='y', linestyle='--', alpha=0.6)
                if melhor_inicio_robo is not None: # Mostra legenda apenas se houver linha do melhor intervalo
                    ax_sc.legend(loc='best', fontsize='small')

                plt.tight_layout()
                safe_robo_name = robo_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                caminho_grafico_scatter = _salvar_grafico(fig_sc, output_dir, f'ganhos_por_minuto_robo_{safe_robo_name}_8_18')
            except Exception as e_sc_robo:
                logger.error(f"Erro ao gerar scatter plot para robô {robo_name}: {e_sc_robo}", exc_info=True)
                plt.close(fig_sc) # Garante fechar a figura
                caminho_grafico_scatter = None # Falha na geração
        else:
            logger.warning(f"Sem dados 8h-18h suficientes para gerar scatter plot para o robô {robo_name}.")


        # --- Preparar Tabela de Resumo do Robô ---
        ganho_total_real_robo = somas_absolutas_por_robo.get(robo_name, 0) # Pega soma bruta
        # Calcula somas para intervalos fixos para este robô
        intervalos_fixos_robo = {
            '9:15-12:30': (9*60+15, 12*60+30),
            '9:00-12:30': (9*60, 12*60+30),
            '10:00-12:30': (10*60, 12*60+30),
        }
        somas_intervalos_fixos_robo = {}
        if 'Minutos_Dia' in df_robo_filtrado_8_18.columns: # Só calcula se a coluna existe
            for nome, (inicio_min, fim_min) in intervalos_fixos_robo.items():
                 mask_intervalo = (
                     (df_robo_filtrado_8_18['Minutos_Dia'] >= inicio_min) &
                     (df_robo_filtrado_8_18['Minutos_Dia'] <= fim_min)
                 )
                 somas_intervalos_fixos_robo[nome] = df_robo_filtrado_8_18.loc[mask_intervalo, result_col].sum()
        else:
            # Se não tem Minutos_Dia, define somas como 0
            for nome in intervalos_fixos_robo:
                somas_intervalos_fixos_robo[nome] = 0.0


        melhor_intervalo_robo_label = f"Melhor ({melhor_inicio_robo_hhmm}-{melhor_fim_robo_hhmm}, 8-18h)" if melhor_inicio_robo is not None else "Melhor (N/A, 8-18h)"
        cabecalho_tabela_robo = ['Geral (Todas Ops Brutas)', melhor_intervalo_robo_label] + list(intervalos_fixos_robo.keys())
        valores_tabela_robo = [
             f"{ganho_total_real_robo:.2f}",
             f"{max_ganho_robo_8_18:.2f}",
        ] + [f"{soma:.2f}" for soma in somas_intervalos_fixos_robo.values()]

        titulo_tabela_robo = f'Resultados - {robo_name} (N={count_robo_data_valida} ops c/ data válida)'
        tabela_robo_data = [
            [titulo_tabela_robo] + [''] * (len(cabecalho_tabela_robo) - 1),
            cabecalho_tabela_robo,
            valores_tabela_robo
        ]
        logger.info(f"Tabela Resumo {robo_name}: Geral={ganho_total_real_robo:.2f}, Melhor(8-18)={max_ganho_robo_8_18:.2f}")


        # --- Gerar Gráfico de Linha Diária do Robô ---
        logger.debug(f"Gerando gráfico de linha diária para {robo_name}...")
        caminho_grafico_linha, limite_ideal_robo = _gerar_grafico_linha_diaria_robo(
            df_robo_full_com_data, robo_name, output_dir, periodo_robo_str, result_col
        )
        limites_ganho[robo_name] = limite_ideal_robo

        # --- Gerar Gráfico Acumulado por Intervalo do Robô ---
        logger.debug(f"Gerando gráfico acumulado por intervalo para {robo_name}...")
        caminho_grafico_acum_intervalo = _gerar_grafico_acumulado_intervalos_robo(
            df_robo_full_com_data,
            df_robo_filtrado_8_18, # Passa o filtrado para os intervalos
            robo_name, output_dir, periodo_robo_str, result_col,
            melhor_inicio_robo, melhor_fim_robo
        )

        # --- Adicionar resultados ao dicionário do robô ---
        graficos_por_robo_list.append({
            'robo': robo_name,
            'grafico_scatter': caminho_grafico_scatter, # Pode ser None
            'tabela': tabela_robo_data,
            'grafico_linha': caminho_grafico_linha, # Pode ser None
            'limite': limite_ideal_robo,
            'grafico_acum_intervalo': caminho_grafico_acum_intervalo # Pode ser None
        })

    logger.info(f"--- Geração de gráficos individuais concluída ---")
    logger.info(f"Soma dos melhores ganhos individuais (8-18h) de todos robôs: {soma_melhores_ganhos_individuais_8_18:.2f}")

    return graficos_por_robo_list, soma_melhores_ganhos_individuais_8_18, limites_ganho