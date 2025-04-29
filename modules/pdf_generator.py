"""
Módulo para geração do relatório PDF consolidado.

Combina os gráficos gerados e as tabelas de resultados em um único
documento PDF usando a biblioteca ReportLab.
"""
import os
import logging
import traceback
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from reportlab.platypus import (
    SimpleDocTemplate, Image, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import inch

from config import (
    PDF_PAGE_SIZE, PDF_LEFT_MARGIN, PDF_RIGHT_MARGIN, PDF_TOP_MARGIN, PDF_BOTTOM_MARGIN,
    PDF_IMAGE_WIDTH, PDF_IMAGE_HEIGHT_DEFAULT, PDF_IMAGE_HEIGHT_ACCUM,
    ROBO_COLUMN_NAME, # Usado na tabela final
    IDEAL_LIMIT_PERCENTILE, # Usado na nota do gráfico de linha
    TRADING_HOUR_START, TRADING_HOUR_END # Usado nas notas
)
from .utils import minutos_para_horario

logger = logging.getLogger(__name__)

# --- Estilos Padrão do ReportLab ---
styles = getSampleStyleSheet()

# --- Estilos Personalizados ---
style_title = ParagraphStyle(
    name='TituloRelatorio',
    parent=styles['h1'],
    alignment=TA_CENTER,
    spaceAfter=12,
    fontSize=16
)
style_subtitle = ParagraphStyle(
    name='SubtituloSecao',
    parent=styles['h2'],
    alignment=TA_LEFT,
    spaceAfter=6,
    spaceBefore=12,
    fontSize=12,
    textColor=colors.darkblue
)
style_robo_title = ParagraphStyle(
    name='TituloRobo',
    parent=styles['h3'],
    alignment=TA_LEFT,
    spaceAfter=8,
    spaceBefore=15,
    fontSize=13,
    textColor=colors.darkslategray
)
style_normal_center = ParagraphStyle(
    name='NormalCentro',
    parent=styles['Normal'],
    alignment=TA_CENTER,
    spaceAfter=6,
    fontSize=9
)
style_normal_left = ParagraphStyle(
    name='NormalEsquerda',
    parent=styles['Normal'],
    alignment=TA_LEFT,
    spaceBefore=6,
    spaceAfter=6,
    fontSize=9
)
style_note = ParagraphStyle(
    name='NotaGrafico',
    parent=styles['Italic'],
    fontSize=8,
    alignment=TA_LEFT,
    spaceBefore=2,
    spaceAfter=8,
    leftIndent=10
)
style_table_header = ParagraphStyle(
    name='CabecalhoTabela',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    alignment=TA_CENTER,
    fontSize=8, # Ligeiramente menor para caber mais info
    textColor=colors.whitesmoke
)
style_table_body_center = ParagraphStyle(
    name='CorpoTabelaCentro',
    parent=styles['Normal'],
    alignment=TA_CENTER,
    fontSize=8
)
style_table_body_left = ParagraphStyle(
    name='CorpoTabelaEsquerda',
    parent=styles['Normal'],
    alignment=TA_LEFT,
    fontSize=8
)
style_table_title = ParagraphStyle(
    name='TituloTabela',
    parent=style_table_header, # Baseado no header
    alignment=TA_LEFT, # Alinha à esquerda
    fontSize=9,
    leftIndent=5, # Adiciona um pequeno recuo
)

# --- Estilos de Tabela ReportLab ---
# Estilo para tabelas de resumo (Geral e por Robô)
ts_resumo = TableStyle([
    # Alinhamento e Fonte
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Título da tabela (linha 0)
    ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'), # Cabeçalho das colunas (linha 1)
    ('FONTNAME', (0, 2), (-1, -1), 'Helvetica'),    # Corpo da tabela (a partir linha 2)
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('FONTSIZE', (0, 1), (-1, 1), 8),
    ('FONTSIZE', (0, 2), (-1, -1), 8),
    # Cores
    ('TEXTCOLOR', (0, 0), (-1, 1), colors.whitesmoke), # Título e Cabeçalho
    ('TEXTCOLOR', (0, 2), (-1, -1), colors.black),     # Corpo
    ('BACKGROUND', (0, 0), (-1, 0), colors.darkslategray), # Fundo Título Tabela
    ('BACKGROUND', (0, 1), (-1, 1), colors.dimgray),      # Fundo Cabeçalho
    ('BACKGROUND', (0, 2), (-1, -1), colors.whitesmoke),   # Fundo Corpo (alternar cores seria melhor)
    # Padding
    ('BOTTOMPADDING', (0, 0), (-1, 1), 6),
    ('TOPPADDING', (0, 0), (-1, 1), 6),
    ('BOTTOMPADDING', (0, 2), (-1, -1), 4),
    ('TOPPADDING', (0, 2), (-1, -1), 4),
    # Grid/Linhas
    ('GRID', (0, 1), (-1, -1), 0.5, colors.darkgrey),
    # Mesclagem (Span)
    ('SPAN', (0, 0), (-1, 0)), # Título da tabela ocupa a primeira linha inteira
    ('ALIGN', (0, 0), (-1, 0), 'LEFT'), # Alinha título à esquerda
    ('LEFTPADDING', (0, 0), (-1, 0), 5), # Padding esquerdo para título
])

# Estilo para a tabela final de melhores intervalos
ts_final = TableStyle([
    # Alinhamento e Fonte
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Cabeçalho
    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),    # Corpo
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    # Cores
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Cabeçalho
    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),     # Corpo
    ('BACKGROUND', (0, 0), (-1, 0), colors.darkslategray), # Fundo Cabeçalho
    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),   # Fundo Corpo
     # Padding
    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
    ('TOPPADDING', (0, 0), (-1, 0), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ('TOPPADDING', (0, 1), (-1, -1), 4),
    # Grid/Linhas
    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
])

# --- Funções Auxiliares para PDF ---

def _inserir_imagem(elements: List[Any], caminho_imagem: Optional[str], altura: Optional[int] = None):
    """Adiciona uma imagem ao PDF se o caminho for válido."""
    if caminho_imagem and os.path.exists(caminho_imagem):
        try:
            img_height = altura if altura else PDF_IMAGE_HEIGHT_DEFAULT
            img = Image(caminho_imagem, width=PDF_IMAGE_WIDTH, height=img_height)
            elements.append(img)
            # elements.append(Spacer(1, 6)) # Adiciona espaço após a imagem - Removido, notas cuidam disso
        except Exception as e:
            logger.error(f"Erro ao tentar inserir imagem '{caminho_imagem}' no PDF: {e}", exc_info=True)
            elements.append(Paragraph(f"[Erro ao carregar imagem: {os.path.basename(caminho_imagem)}]", style_note))
    # else:
    #     logger.debug(f"Caminho da imagem não fornecido ou inválido: {caminho_imagem}")


def _inserir_tabela(elements: List[Any], dados_tabela: Optional[List[List[str]]], estilo_base: TableStyle, widths: Optional[List[float]] = None): # Renomeado para estilo_base
    """Adiciona uma tabela formatada ao PDF se os dados forem válidos."""
    if dados_tabela and len(dados_tabela) > 2:
        try:
            # --- CORREÇÃO: Criar um novo estilo baseado no estilo_base ---
            # Copia os comandos do estilo base
            comandos_estilo = list(estilo_base.getCommands())
            # Adiciona os comandos específicos para esta tabela (span e align do título)
            num_cols_header = len(dados_tabela[1]) if len(dados_tabela) > 1 else 0
            if num_cols_header > 0:
                comandos_estilo.append(('SPAN', (0, 0), (num_cols_header - 1, 0)))
                comandos_estilo.append(('ALIGN', (0, 0), (-1, 0), 'LEFT')) # Garante alinhamento do título
            else:
                logger.warning("Cabeçalho da tabela (linha 1) não encontrado ou vazio ao adicionar SPAN.")

            # Cria a nova instância de TableStyle para esta tabela específica
            estilo_tabela_instancia = TableStyle(comandos_estilo)
            # -------------------------------------------------------------

            # Converte strings em Paragraphs para aplicar estilos
            table_data_styled = []
            # Linha 0 (Título da Tabela)
            title_row = [Paragraph(str(cell), style_table_title) for cell in dados_tabela[0]]
            table_data_styled.append(title_row)
            # Linha 1 (Cabeçalho)
            header_row = [Paragraph(str(cell), style_table_header) for cell in dados_tabela[1]]
            table_data_styled.append(header_row)
            # Linhas de Corpo (a partir da linha 2)
            for row_data in dados_tabela[2:]:
                body_row = [Paragraph(str(cell), style_table_body_center) for cell in row_data]
                # Se precisar alinhar a primeira coluna à esquerda:
                # if body_row: body_row[0] = Paragraph(str(row_data[0]), style_table_body_left)
                table_data_styled.append(body_row)

            # Calcula larguras se não fornecidas
            if widths is None:
                 num_cols = len(dados_tabela[1]) if len(dados_tabela) > 1 else 0
                 if num_cols > 0:
                     # Use PDF_IMAGE_WIDTH como largura padrão da página útil
                     widths = [PDF_IMAGE_WIDTH / num_cols] * num_cols
                 else:
                     logger.warning("Tabela sem colunas, não é possível calcular larguras.")
                     return

            # Cria o objeto Table
            tabela = Table(table_data_styled, colWidths=widths)
            tabela.setStyle(estilo_tabela_instancia) # <<< USA A INSTÂNCIA DO ESTILO
            elements.append(tabela)
            elements.append(Spacer(1, 12))
        except Exception as e:
            logger.error(f"Erro ao tentar criar ou inserir tabela no PDF: {e}", exc_info=True)
            logger.error(f"Dados da tabela com problema: {dados_tabela}")
            elements.append(Paragraph("[Erro ao gerar tabela]", style_note))
    elif dados_tabela:
         logger.warning(f"Dados da tabela insuficientes para gerar (linhas: {len(dados_tabela)}): {dados_tabela}")



# --- Função Principal de Geração de PDF ---

def gerar_pdf(
    output_dir: str,
    graficos_gerais: List[Dict[str, Any]],
    graficos_por_robo: List[Dict[str, Any]],
    resultados_consolidados: Dict[str, Any],
    soma_melhores_ganhos_ind_8_18: float,
    df_melhores_robos_8_18: pd.DataFrame, # DataFrame com melhores intervalos 8-18 por robô
    original_result_col_name: Optional[str]
) -> str:
    """
    Gera o relatório PDF final com todos os gráficos e tabelas.

    Args:
        output_dir: Diretório onde o PDF será salvo.
        graficos_gerais: Lista de dicionários com infos dos gráficos gerais (scatter, montanha).
        graficos_por_robo: Lista de dicionários com infos dos gráficos de cada robô.
        resultados_consolidados: Dicionário com DataFrames e métricas processadas.
        soma_melhores_ganhos_ind_8_18: Soma dos melhores ganhos (8-18h) individuais.
        df_melhores_robos_8_18: DataFrame com detalhes dos melhores intervalos 8-18h por robô.
        original_result_col_name: Nome original da coluna de resultado (para info).


    Returns:
        O caminho completo para o arquivo PDF gerado.

    Raises:
        Exception: Se ocorrer um erro grave durante a construção do PDF.
    """
    pdf_path = os.path.join(output_dir, 'relatorio_analise_trading.pdf')
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=PDF_PAGE_SIZE,
        leftMargin=PDF_LEFT_MARGIN,
        rightMargin=PDF_RIGHT_MARGIN,
        topMargin=PDF_TOP_MARGIN,
        bottomMargin=PDF_BOTTOM_MARGIN
    )
    elements: List[Any] = []
    logger.info(f"--- Iniciando Geração do PDF: {pdf_path} ---")

    # --- Título e Informações Gerais ---
    periodo_completo = resultados_consolidados.get('periodo_completo_str', 'N/D')
    elements.append(Paragraph(f"Relatório de Análise de Operações ({periodo_completo})", style_title))

    count_total_orig = resultados_consolidados.get('count_operacoes_total_originais', 'N/D')
    count_data_valida = resultados_consolidados.get('count_operacoes_data_valida', 'N/D')
    count_com_hora = resultados_consolidados.get('count_operacoes_com_hora', 'N/D')
    # <<< USA A NOVA CONTAGEM PARA EXIBIÇÃO >>>
    count_sem_horario_display = resultados_consolidados.get('count_sem_horario_especifico_display', 'N/D')
    count_8_18 = resultados_consolidados.get('count_operacoes_8_18', 'N/D')
    result_col_info = f"(Coluna Original: '{original_result_col_name}')" if original_result_col_name else ""

    # --- USA A NOVA CONTAGEM NO TEXTO ---
    # Ajuste na descrição para clareza
    info_text = (f"Total Operações Lidas (com resultado {result_col_info}): <b>{count_total_orig}</b> | "
                 f"Total Operações Consideradas*: <b>{count_data_valida}</b><br/>" # <<< Alterado aqui
                 f"  ↳ Com Horário Específico (não 00:00): <b>{count_com_hora}</b> | " # Ajuste na descrição
                 f"  ↳ Sem Horário Específico (calculado**): <b>{count_sem_horario_display}</b> | " # Ajuste na descrição
                 f"  ↳ Com Horário entre {TRADING_HOUR_START}h-{TRADING_HOUR_END}h: <b>{count_8_18}</b>")
    elements.append(Paragraph(info_text, style_normal_center))
    elements.append(Spacer(1, 18))

    # --- Seção de Gráficos e Tabelas Gerais ---
    elements.append(Paragraph("Visão Geral Consolidada", style_subtitle))

    tabela_geral_atualizada = False
    tabela_geral_inserida = False
    for item in graficos_gerais:
        # Atualiza placeholders e título na tabela geral ANTES de inseri-la
        if item.get('tabela') and 'ganhos_por_minuto' in item.get('grafico', '') and not tabela_geral_atualizada:
            try:
                dados_tabela_geral = item['tabela']
                if len(dados_tabela_geral) > 2 and len(dados_tabela_geral[1]) > 2:
                    # ... (atualização dos placeholders de soma - sem mudança) ...
                    cabecalhos = dados_tabela_geral[1]
                    valores_row = dados_tabela_geral[2]
                    idx_soma_geral = cabecalhos.index('Geral (Todas Ops Brutas)')
                    idx_soma_melhores = cabecalhos.index('Soma Melhores Indiv. (8-18h)')
                    soma_bruta_real = resultados_consolidados.get('soma_absoluta_total', 0.0)
                    valores_row[idx_soma_geral] = f"{soma_bruta_real:.2f}"
                    valores_row[idx_soma_melhores] = f"{soma_melhores_ganhos_ind_8_18:.2f}"


                    # --- USA AS NOVAS CONTAGENS NO TÍTULO DA TABELA ---
                    # (Ajuste na descrição para clareza)
                    novo_titulo_tabela = (f"Resultados Consolidados (Ops Data Válida: {count_data_valida} | "
                                          f"c/ Hora Específica: {count_com_hora} | s/ Hora Específica: {count_sem_horario_display}* | " # Adiciona *
                                          f"{TRADING_HOUR_START}h-{TRADING_HOUR_END}h: {count_8_18})")
                    dados_tabela_geral[0][0] = novo_titulo_tabela

                    logger.info("Placeholders e título da tabela geral atualizados.")
                    tabela_geral_atualizada = True


                    # Define larguras das colunas (exemplo: dividir igualmente)
                    num_cols = len(cabecalhos)
                    if num_cols > 0:
                        # doc.width já considera as margens
                        col_width = doc.width / num_cols
                        table_widths = [col_width] * num_cols
                        _inserir_tabela(elements, dados_tabela_geral, ts_resumo, widths=table_widths)
                        tabela_geral_inserida = True
                    else:
                        logger.warning("Tabela geral não possui colunas.")
                else:
                     logger.warning("Estrutura inesperada para a tabela geral.")

            except (IndexError, ValueError, KeyError) as e:
                 logger.error(f"Erro ao tentar atualizar/inserir tabela geral: {e}", exc_info=True)
                 elements.append(Paragraph("[Erro ao processar tabela geral]", style_note))

        # Insere o gráfico geral (mesmo que a tabela tenha falhado)
        altura_img = PDF_IMAGE_HEIGHT_DEFAULT
        _inserir_imagem(elements, item.get('grafico'), altura=altura_img)

        # Adiciona notas específicas
        if item.get('grafico'):
            nome_arquivo_grafico = os.path.basename(item['grafico'])
            if 'ganhos_por_minuto' in nome_arquivo_grafico:
                 elements.append(Paragraph(f"<i>Obs: Gráfico considera apenas operações com horário definido entre {TRADING_HOUR_START}h e {TRADING_HOUR_END}h. Tamanho dos pontos proporcional ao resultado. Linhas pontilhadas roxas indicam o melhor intervalo geral ({TRADING_HOUR_START}h-{TRADING_HOUR_END}h).</i>", style_note))
            elif 'acumulado_total_geral' in nome_arquivo_grafico: # <<< Nota para Acumulado Total
                 count_data_valida = resultados_consolidados.get('count_operacoes_data_valida', 'N/A')
                 elements.append(Paragraph(f"<i>Obs: Linha preta representa o acumulado de todas as operações consideradas ({count_data_valida} ops).</i>", style_note))
            elif 'acumulado_por_robo' in nome_arquivo_grafico: # <<< Nota para Acumulado por Robô
                 elements.append(Paragraph(f"<i>Obs: Linhas coloridas representam o acumulado individual de cada robô (usando todas as suas operações com data válida).</i>", style_note))


    # Garante que a tabela geral seja inserida mesmo que não associada ao gráfico scatter
    if not tabela_geral_inserida:
         logger.warning("A tabela geral não foi inserida junto com o gráfico scatter. Tentando inserir separadamente.")
         # Tenta encontrar a tabela na lista geral novamente
         for item in graficos_gerais:
             if item.get('tabela') and 'Geral (Todas Ops Brutas)' in item['tabela'][1]: # Heurística para encontrar a tabela certa
                if not tabela_geral_atualizada:
                    # Tenta atualizar placeholders se ainda não o fez
                    try:
                        dados_tabela_geral = item['tabela']
                        if len(dados_tabela_geral) > 2 and len(dados_tabela_geral[1]) > 2:
                            cabecalhos = dados_tabela_geral[1]
                            valores_row = dados_tabela_geral[2]
                            idx_soma_geral = cabecalhos.index('Geral (Todas Ops Brutas)')
                            idx_soma_melhores = cabecalhos.index('Soma Melhores Indiv. (8-18h)')
                            soma_bruta_real = resultados_consolidados.get('soma_absoluta_total', 0.0)
                            valores_row[idx_soma_geral] = f"{soma_bruta_real:.2f}"
                            valores_row[idx_soma_melhores] = f"{soma_melhores_ganhos_ind_8_18:.2f}"
                            tabela_geral_atualizada = True
                    except Exception as e_upd:
                         logger.error(f"Erro ao tentar atualizar tabela geral (tentativa 2): {e_upd}")
                # Insere a tabela se ela existe e foi (ou não precisava ser) atualizada
                if tabela_geral_atualizada or '{' not in str(item['tabela']): # Verifica se placeholders ainda existem
                    num_cols = len(item['tabela'][1])
                    if num_cols > 0:
                        col_width = doc.width / num_cols
                        table_widths = [col_width] * num_cols
                        _inserir_tabela(elements, item['tabela'], ts_resumo, widths=table_widths)
                        tabela_geral_inserida = True
                        break # Sai do loop após inserir
         if not tabela_geral_inserida:
             logger.error("Falha ao inserir a tabela geral no PDF.")

         if tabela_geral_inserida: # Adiciona após a tabela geral e gráficos gerais
                 elements.append(Paragraph("<i>*Total Operações Consideradas: Refere-se às operações lidas que possuem uma data de abertura válida.</i>", style_note))
                 elements.append(Paragraph("<i>**Sem Horário Específico (calculado): Total de Operações Lidas - Operações com Horário Específico (não 00:00) com data válida.</i>", style_note))

    # --- Seção de Gráficos e Tabelas por Robô ---
    elements.append(PageBreak())
    elements.append(Paragraph("Análise Individual por Robô", style_title))
    elements.append(Spacer(1, 12))

    limites_ganho = resultados_consolidados.get('limites_ganho', {})

    for item_robo in graficos_por_robo:
        robo_name = item_robo.get('robo', 'Robô Desconhecido')
        elements.append(Paragraph(f"Robô: {robo_name}", style_robo_title))

        # Tabela de Resumo do Robô
        if 'tabela' in item_robo and isinstance(item_robo['tabela'], list) and len(item_robo['tabela']) > 1:
            try:
                # Encontra a contagem total BRUTA do robô (pode vir do dict original)
                # Precisamos ter acesso ao count original por robô
                # Adicionar isso ao 'resultados_consolidados' seria ideal.
                # Por agora, vamos usar a soma das contagens como aproximação, ou buscar no DF geral.
                # --- OPÇÃO 1 (Buscar no DF original) ---
                #df_robo_original = resultados_consolidados['banco_geral_bruto'][resultados_consolidados['banco_geral_bruto'][ROBO_COLUMN_NAME] == robo_name]
                #count_robo_total_lido = len(df_robo_original)
                df_com_data_geral = resultados_consolidados.get('banco_geral_com_data') # OK
                # --- OPÇÃO 2 (Aproximar pelas contagens filtradas - MENOS PRECISO) ---
                # count_robo_data_valida = len(resultados_consolidados['banco_geral_com_data'][resultados_consolidados['banco_geral_com_data'][ROBO_COLUMN_NAME] == robo_name])
                # ----> Vamos usar a contagem de 'banco_geral_com_data' que reflete ops com data válida para o robô <----
                count_robo_data_valida = 0
                if isinstance(df_com_data_geral, pd.DataFrame) and not df_com_data_geral.empty and ROBO_COLUMN_NAME in df_com_data_geral.columns:
                    try:
                         # USA df_com_data_geral - OK
                         count_robo_data_valida = len(df_com_data_geral.query(f"`{ROBO_COLUMN_NAME}` == @robo_name"))
                    except Exception as e_query:
                         logger.error(f"Erro ao executar query para robô '{robo_name}': {e_query}")
                         count_robo_data_valida = (df_com_data_geral[ROBO_COLUMN_NAME] == robo_name).sum()

                # Atualizar o título da tabela
                if isinstance(item_robo['tabela'][0], list) and len(item_robo['tabela'][0]) > 0:
                # --- ALTERAÇÃO AQUI ---
                    novo_titulo_robo = f'Resultados - {robo_name} (N={count_robo_data_valida} Operações Consideradas)' # <<< Alterado aqui
                    item_robo['tabela'][0][0] = novo_titulo_robo
                else:
                    logger.warning(f"Estrutura inesperada para a linha de título da tabela do robô {robo_name}.")

                # Preparar e inserir a tabela
                num_cols_robo = len(item_robo['tabela'][1])
                if num_cols_robo > 0:
                    col_width_robo = doc.width / num_cols_robo
                    table_widths_robo = [col_width_robo] * num_cols_robo
                    _inserir_tabela(elements, item_robo['tabela'], ts_resumo, widths=table_widths_robo) # OK
                else:
                    logger.warning(f"Tabela do robô {robo_name} não possui colunas de cabeçalho (linha 1).")
            except Exception as e_tab_robo:
                logger.error(f"Erro ao processar/inserir tabela do robô {robo_name}: {e_tab_robo}")

        # Gráfico Scatter do Robô (8-18h)
        _inserir_imagem(elements, item_robo.get('grafico_scatter'), altura=PDF_IMAGE_HEIGHT_DEFAULT)
        if item_robo.get('grafico_scatter'):
             elements.append(Paragraph(f"<i>Obs: Considera operações {TRADING_HOUR_START}h-{TRADING_HOUR_END}h com horário. Linhas pontilhadas vermelhas indicam o melhor intervalo <u>deste robô</u> ({TRADING_HOUR_START}h-{TRADING_HOUR_END}h).</i>", style_note))

        # Gráfico de Linha Diária do Robô
        _inserir_imagem(elements, item_robo.get('grafico_linha'), altura=PDF_IMAGE_HEIGHT_DEFAULT)
        if item_robo.get('grafico_linha'):
            limite_robo = item_robo.get('limite', 0)
            elements.append(Paragraph(f"Limite Ideal Sugerido (P{IDEAL_LIMIT_PERCENTILE} picos+): <b>{limite_robo} pts</b>", style_normal_left))
            # elements.append(Spacer(1, 6)) # Removido, nota abaixo serve de espaço

        # Gráfico Acumulado por Intervalo do Robô
        _inserir_imagem(elements, item_robo.get('grafico_acum_intervalo'), altura=PDF_IMAGE_HEIGHT_ACCUM)
        if item_robo.get('grafico_acum_intervalo'):
             elements.append(Paragraph(f"<i>Obs: Linha preta: acumulado total do robô (todas as operações consideradas). Linhas coloridas: acumulado DENTRO dos intervalos indicados (requer ops c/ hora).</i>", style_note))

        elements.append(Spacer(1, 18))

    # --- Tabela Final: Melhores Intervalos 8-18h por Robô ---
    if not df_melhores_robos_8_18.empty:
        elements.append(PageBreak()) # Nova página para esta tabela
        elements.append(Paragraph(f"Resumo: Melhores Intervalos por Robô ({TRADING_HOUR_START}h-{TRADING_HOUR_END}h)", style_subtitle))

        # Prepara dados para a tabela final
        df_melhores_robos_8_18['Inicio_Horario'] = df_melhores_robos_8_18['Inicio_Intervalo'].apply(minutos_para_horario)
        df_melhores_robos_8_18['Fim_Horario'] = df_melhores_robos_8_18['Fim_Intervalo'].apply(minutos_para_horario)
        df_melhores_robos_8_18['Ganho_Formatado'] = df_melhores_robos_8_18['Ganho'].apply(lambda x: f"{x:.2f}")
        
        # Certifica que as colunas existem antes de aplicar
        if 'Inicio_Intervalo' in df_melhores_robos_8_18.columns:
            df_melhores_robos_8_18['Inicio_Horario'] = df_melhores_robos_8_18['Inicio_Intervalo'].apply(minutos_para_horario)
        else: df_melhores_robos_8_18['Inicio_Horario'] = "N/A"

        if 'Fim_Intervalo' in df_melhores_robos_8_18.columns:
            df_melhores_robos_8_18['Fim_Horario'] = df_melhores_robos_8_18['Fim_Intervalo'].apply(minutos_para_horario)
        else: df_melhores_robos_8_18['Fim_Horario'] = "N/A"

        if 'Ganho' in df_melhores_robos_8_18.columns:
            df_melhores_robos_8_18['Ganho_Formatado'] = df_melhores_robos_8_18['Ganho'].apply(lambda x: f"{x:.2f}")
        else: df_melhores_robos_8_18['Ganho_Formatado'] = "N/A"

        # Seleciona e renomeia colunas para a tabela
        
        #df_tabela_final = df_melhores_robos_8_18[[
        #    ROBO_COLUMN_NAME, 'Inicio_Horario', 'Fim_Horario', 'Ganho_Formatado'
        #]].rename(columns={
        #    ROBO_COLUMN_NAME: 'Robô',
        #    'Inicio_Horario': f'Início (Melhor {TRADING_HOUR_START}h-{TRADING_HOUR_END}h)',
        #    'Fim_Horario': f'Fim (Melhor {TRADING_HOUR_START}h-{TRADING_HOUR_END}h)',
        #    'Ganho_Formatado': 'Ganho no Intervalo'
        #}) 
        
        colunas_tabela_final = [ROBO_COLUMN_NAME, 'Inicio_Horario', 'Fim_Horario', 'Ganho_Formatado']
        # Garante que apenas colunas existentes sejam selecionadas
        colunas_existentes_tabela = [col for col in colunas_tabela_final if col in df_melhores_robos_8_18.columns]

        if not colunas_existentes_tabela:
             logger.error("Nenhuma coluna válida encontrada para a tabela final de melhores intervalos.")
             elements.append(Paragraph("[Erro: dados insuficientes para tabela final]", style_note))
        else:
            df_tabela_final = df_melhores_robos_8_18[colunas_existentes_tabela].rename(columns={
                ROBO_COLUMN_NAME: 'Robô',
                'Inicio_Horario': f'Início (Melhor {TRADING_HOUR_START}h-{TRADING_HOUR_END}h)',
                'Fim_Horario': f'Fim (Melhor {TRADING_HOUR_START}h-{TRADING_HOUR_END}h)',
                'Ganho_Formatado': 'Ganho no Intervalo'
            })    
        
        # Converte para lista de listas para ReportLab
        header_final = [Paragraph(h, style_table_header) for h in df_tabela_final.columns.tolist()]
        body_rows_final = []
        for _, row in df_tabela_final.iterrows():
                # Centraliza tudo, exceto talvez o nome do robô
                styled_row = [Paragraph(str(cell), style_table_body_center) for cell in row]
                if 'Robô' in df_tabela_final.columns: # Se a coluna Robô existe
                    idx_robo = df_tabela_final.columns.get_loc('Robô')
                    styled_row[idx_robo] = Paragraph(str(row['Robô']), style_table_body_left) # Nome do Robô à esquerda
                body_rows_final.append(styled_row)


        table_data_final = [header_final] + body_rows_final

        # Define larguras (exemplo: 4 colunas, Robô maior)
        col_widths_final = [doc.width * 0.35, doc.width * 0.20, doc.width * 0.20, doc.width * 0.25]

        try:
            tabela_final_obj = Table(table_data_final, colWidths=col_widths_final)
            tabela_final_obj.setStyle(ts_final)
            elements.append(tabela_final_obj)
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<i>Obs: Calculado usando apenas operações com horário definido entre {TRADING_HOUR_START}h e {TRADING_HOUR_END}h.</i>", style_note))
        except Exception as e:
            logger.error(f"Erro ao criar tabela final de melhores intervalos: {e}", exc_info=True)
            elements.append(Paragraph("[Erro ao gerar tabela de melhores intervalos]", style_note))
    else:
        logger.info(f"DataFrame de melhores intervalos {TRADING_HOUR_START}h-{TRADING_HOUR_END}h vazio. Tabela final não será gerada.")


    # --- Mensagem Final ---
    elements.append(Spacer(1, 24))
    mensagem_final_texto = (
        "<b>Atenção:</b> Estes dados referem-se ao passado e análises de backtesting. "
        "Resultados passados não são garantia de resultados futuros. "
        "Opere com consciência e gerenciamento de risco."
    )
    elements.append(Paragraph(mensagem_final_texto, style_normal_left))
    elements.append(Spacer(1, 24))

    # --- Construir o PDF ---
    try:
        logger.info(f"Construindo o documento PDF em: {pdf_path}")
        doc.build(elements)
        logger.info(f"Documento PDF construído com sucesso!")
    except Exception as e:
        logger.critical(f"!!!!!!!! ERRO FATAL AO CONSTRUIR O PDF !!!!!!!!", exc_info=True)
        logger.critical(traceback.format_exc())
        # Relança a exceção para que a rota Flask saiba que falhou
        raise RuntimeError(f"Falha ao gerar o relatório PDF: {e}") from e

    return pdf_path