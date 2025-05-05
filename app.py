"""
Aplicação Flask para análise de dados de operações de trading.

Permite o upload de arquivos Excel ou múltiplos CSVs, processa os dados,
gera gráficos de análise e retorna um relatório PDF consolidado.
"""
import os
import shutil
import logging
import traceback
from flask import (
    Flask, request, render_template, send_file, after_this_request, flash, redirect, url_for, jsonify
)
from werkzeug.exceptions import RequestEntityTooLarge # Para tratar erro de tamanho de arquivo

# Importações locais (módulos do projeto)
from config import (
    RELATORIOS_DIR_ABS,
    RESULT_COLUMN_NAME,
    MAX_FILE_SIZE_MB, # Importa para usar no Flask config
    TRADING_HOUR_START, # Usado para info no HTML
    TRADING_HOUR_END # Usado para info no HTML
)
from modules.utils import (
    criar_diretorio_seguro,
    validar_arquivo_excel,
    validar_arquivo_csv,
    limpar_diretorio_seguro # Importa função de limpeza
)
from modules.data_processor import (
    processar_dados_excel,
    processar_dados_csv,
    processar_dados_consolidados
)
from modules.chart_generator import (
    # Não importa mais as funções individuais, a lógica está encapsulada
    gerar_grafico_ganhos_por_minuto,
    #gerar_grafico_montanha,
    #gerar_grafico_acumulado_comparativo,
    #gerar_grafico_acumulado_total_e_por_robo,
    gerar_grafico_acumulado_total,       # <<< NOVA FUNÇÃO
    gerar_grafico_acumulado_por_robo,
    gerar_graficos_por_robo
)
from modules.pdf_generator import gerar_pdf

# Configuração básica de logging
# Em produção, considere usar FileHandler, RotatingFileHandler, etc.
logging.basicConfig(
    level=logging.INFO, # Nível INFO captura informações gerais, avisos e erros
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Envia logs para o console
        # Adicionar FileHandler se quiser salvar em arquivo:
        # logging.FileHandler("app_trading_analysis.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__) # Cria um logger específico para este módulo

# Inicialização da aplicação Flask
app = Flask(__name__)

# --- Configurações do Flask ---
# Chave secreta para mensagens flash e sessões (mude para algo seguro)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'uma-chave-secreta-muito-forte-padrao')
# Limite máximo de tamanho para o payload da requisição (inclui arquivos)
# +1MB de margem para outros dados do formulário
app.config['MAX_CONTENT_LENGTH'] = (MAX_FILE_SIZE_MB + 1) * 1024 * 1024

# Passa configs para o template
@app.context_processor
def inject_config():
    return dict(config=app.config)

# --- Tratador de Erro para Arquivo Muito Grande ---
@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(e):
    """Trata o erro quando o upload excede o MAX_CONTENT_LENGTH."""
    logger.warning(f"Tentativa de upload excedeu o limite de {MAX_FILE_SIZE_MB}MB.")
    flash(f"Erro: O arquivo enviado é muito grande. O limite máximo é de {MAX_FILE_SIZE_MB}MB por requisição.", 'error')
    return redirect(url_for('index')) # Redireciona de volta para a página inicial

# --- Rota Principal ---
@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Rota principal da aplicação.

    GET: Renderiza o template HTML (templates/index.html).
    POST: Recebe o(s) arquivo(s), processa os dados, gera gráficos,
          cria o relatório PDF e o envia para download.
    """
    # Cria um diretório temporário específico para esta requisição
    # Usar um ID único seria melhor em ambiente multiusuário, mas para simplificar:
    request_report_dir = RELATORIOS_DIR_ABS # Usa o diretório base definido em config

    try:
        # --- Lógica para requisição POST (envio de formulário) ---
        if request.method == 'POST':
            logger.info("="*40)
            logger.info(">>> Nova requisição POST recebida na rota '/' <<<")
            logger.info(f"Formulário recebido: {request.form}")
            logger.info(f"Arquivos recebidos: {list(request.files.keys())}")

            # Cria o diretório de relatórios para esta requisição
            criar_diretorio_seguro(request_report_dir)
            logger.info(f"Diretório de relatórios da requisição: {request_report_dir}")

            # Determina o tipo de upload a partir do formulário
            upload_type = request.form.get('upload_type') # 'single' ou 'multiple'
            logger.info(f"Tipo de upload selecionado: {upload_type}")

            banco_geral_bruto = None
            original_result_col_name = None # Nome original da coluna de resultado

            # --- Processamento baseado no Tipo de Upload ---
            if upload_type == 'single':
                file_single = request.files.get('file_single')
                if not file_single or not file_single.filename:
                    logger.error("Upload 'single' selecionado, mas nenhum arquivo 'file_single' foi enviado.")
                    flash("Erro: Nenhum arquivo Excel foi fornecido.", 'error')
                    return redirect(url_for('index'))

                logger.info(f"Validando arquivo Excel: {file_single.filename}")
                try:
                    validar_arquivo_excel(file_single) # Valida extensão e tamanho
                    logger.info(f"Arquivo Excel '{file_single.filename}' validado.")
                    # Processa os dados do Excel
                    banco_geral_bruto, original_result_col_name = processar_dados_excel(file_single, request_report_dir)
                except (ValueError, IOError) as val_err:
                     logger.error(f"Erro de validação/leitura do Excel '{file_single.filename}': {val_err}")
                     flash(f"Erro no arquivo Excel: {val_err}", 'error')
                     limpar_diretorio_seguro(request_report_dir) # Limpa diretório em caso de erro
                     return redirect(url_for('index'))

            elif upload_type == 'multiple':
                files_multiple = request.files.getlist('files_multiple')
                if not files_multiple or all(not f.filename for f in files_multiple):
                    logger.error("Upload 'multiple' selecionado, mas nenhum arquivo 'files_multiple' foi enviado.")
                    flash("Erro: Nenhum arquivo CSV foi fornecido.", 'error')
                    return redirect(url_for('index'))

                logger.info(f"Recebidos {len(files_multiple)} arquivos para upload múltiplo (CSV).")
                valid_csv_files = []
                for file in files_multiple:
                    if file and file.filename:
                        try:
                            logger.info(f"Validando arquivo CSV: {file.filename}")
                            validar_arquivo_csv(file) # Valida extensão e tamanho
                            valid_csv_files.append(file)
                            logger.info(f"Arquivo CSV '{file.filename}' validado.")
                        except (ValueError, IOError) as val_err:
                            logger.warning(f"Arquivo CSV inválido ou erro de leitura '{file.filename}': {val_err}. Pulando.")
                            flash(f"Aviso: Arquivo CSV '{file.filename}' ignorado - {val_err}", 'warning')
                            # Não interrompe o processo, apenas ignora o arquivo inválido

                if not valid_csv_files:
                    logger.error("Nenhum arquivo CSV válido encontrado após validação.")
                    flash("Erro: Nenhum arquivo CSV válido foi fornecido ou todos falharam na validação.", 'error')
                    limpar_diretorio_seguro(request_report_dir)
                    return redirect(url_for('index'))

                logger.info(f"Processando {len(valid_csv_files)} arquivos CSV válidos.")
                try:
                    # Processa os dados dos CSVs válidos
                    banco_geral_bruto, original_result_col_name = processar_dados_csv(valid_csv_files, request_report_dir)
                except ValueError as proc_err: # Erro durante o processamento/concatenação
                     logger.error(f"Erro ao processar arquivos CSV: {proc_err}")
                     flash(f"Erro no processamento dos CSVs: {proc_err}", 'error')
                     limpar_diretorio_seguro(request_report_dir)
                     return redirect(url_for('index'))

            else:
                logger.error(f"Tipo de upload inválido recebido: {upload_type}")
                flash("Erro: Tipo de upload desconhecido.", 'error')
                limpar_diretorio_seguro(request_report_dir)
                return redirect(url_for('index'))

            # --- Verificação Pós-Leitura ---
            if banco_geral_bruto is None or banco_geral_bruto.empty:
                logger.error("Nenhum dado foi carregado ou processado (DataFrame bruto vazio).")
                flash("Erro: Não foi possível carregar dados válidos dos arquivos fornecidos.", 'error')
                limpar_diretorio_seguro(request_report_dir)
                return redirect(url_for('index'))

            # --- Processamento Consolidado e Geração de Gráficos/PDF ---
            logger.info("Iniciando processamento consolidado dos dados...")
            resultados_consolidados = processar_dados_consolidados(banco_geral_bruto, RESULT_COLUMN_NAME)

            logger.info("Gerando gráficos gerais...")
            # Gráfico Ganhos por Minuto (Scatter 8-18h)
            grafico_ganhos_minuto_info = gerar_grafico_ganhos_por_minuto(
                resultados_consolidados['banco_filtrado_8_18'],
                request_report_dir,
                resultados_consolidados['periodo_str'],
                resultados_consolidados['count_operacoes_8_18'],
                RESULT_COLUMN_NAME
            )
            # Gráfico Acumulado (Acumulado por Robô)
            grafico_acumulado_total_info = gerar_grafico_acumulado_total( # <<< Chama func total
                resultados_consolidados['banco_geral_com_data'],
                request_report_dir,
                resultados_consolidados['periodo_str'],
                RESULT_COLUMN_NAME
            )
            grafico_acumulado_robo_info = gerar_grafico_acumulado_por_robo( # <<< Chama func por robô
                resultados_consolidados['banco_geral_com_data'],
                request_report_dir,
                resultados_consolidados['periodo_str'],
                RESULT_COLUMN_NAME
            )
            # A ordem na lista determina a ordem no PDF
            graficos_gerais = [
                g for g in [
                    grafico_ganhos_minuto_info,
                    grafico_acumulado_total_info,    # Gráfico Acumulado Total
                    grafico_acumulado_robo_info      # Gráfico Acumulado por Robô
                ] if g and g.get('grafico') # Verifica se existe e tem a chave 'grafico'
            ]


            logger.info("Gerando gráficos individuais por robô...")
            graficos_por_robo_list, soma_melhores_individuais, limites_robo = gerar_graficos_por_robo( # <<< Correto
                resultados_consolidados['banco_geral_com_data'],
                resultados_consolidados['banco_filtrado_8_18'],
                request_report_dir,
                resultados_consolidados['somas_absolutas_por_robo'],
                resultados_consolidados['periodo_str'],
                RESULT_COLUMN_NAME
            )
            resultados_consolidados['limites_ganho'] = limites_robo

            logger.info("Gerando o relatório PDF...")
            pdf_path = gerar_pdf(
                request_report_dir,
                graficos_gerais,
                graficos_por_robo_list,
                resultados_consolidados, # Passa todo o dicionário
                soma_melhores_individuais,
                grafico_ganhos_minuto_info['melhores_intervalos_robos'], # Passa o DF com melhores intervalos 8-18
                original_result_col_name # Passa o nome original da coluna de resultado
            )

            # --- Limpeza e Resposta ---
            # Define a função de limpeza para ser executada APÓS a requisição ser completada
            @after_this_request
            def cleanup(response):
                logger.info(f"Iniciando limpeza do diretório: {request_report_dir}")
                limpar_diretorio_seguro(request_report_dir)
                logger.info(f"Limpeza do diretório {request_report_dir} concluída após a requisição.")
                return response # Retorna a resposta original

            logger.info(f"Enviando arquivo PDF gerado: {pdf_path}")
            # Envia o arquivo PDF como anexo para download
            return send_file(
                pdf_path,
                as_attachment=True,
                # Usa um nome de arquivo fixo para o download
                download_name='GPTrading - Analytics.pdf',
                mimetype='application/pdf'
            )

        # --- Lógica para requisição GET (carregar a página inicial) ---
        else:
            logger.debug("Requisição GET recebida, renderizando template index.html")
            # Passa as configurações para o template poder usar MAX_FILE_SIZE_MB
            return render_template('index.html', MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB)

    
    # --- Tratamento Genérico de Erros ---
    except RequestEntityTooLarge:
        logger.warning(f"Upload excedeu o limite de {MAX_FILE_SIZE_MB}MB.")
        limpar_diretorio_seguro(request_report_dir)
        # Retorna JSON de erro em vez de flash/redirect
        return jsonify({"error": f"Erro: O arquivo enviado é muito grande. O limite máximo é de {MAX_FILE_SIZE_MB}MB por requisição."}), 413 # 413 Payload Too Large
    except (ValueError, KeyError, IOError, FileNotFoundError) as app_err:
        error_message = str(app_err)
        logger.error(f"Erro conhecido na aplicação: {error_message}", exc_info=False)
        limpar_diretorio_seguro(request_report_dir)
        # Retorna JSON de erro 400 (Bad Request)
        return jsonify({"error": f"Erro: {error_message}"}), 400
    except RuntimeError as pdf_err: # Erro específico da geração do PDF
         error_message = str(pdf_err)
         logger.critical(f"Erro CRÍTICO ao gerar PDF: {error_message}", exc_info=True)
         limpar_diretorio_seguro(request_report_dir)
         # Retorna JSON de erro 500 (Internal Server Error)
         return jsonify({"error": f"Erro interno ao gerar o PDF: {error_message}. Consulte os logs."}), 500
    except Exception as e: # Outros erros inesperados
        error_details = traceback.format_exc()
        logger.error(f"Erro inesperado na aplicação: {e}", exc_info=True)
        logger.error(f"Detalhes do Erro:\n{error_details}")
        limpar_diretorio_seguro(request_report_dir)
        # Retorna JSON de erro 500
        return jsonify({"error": f"Erro interno inesperado: {str(e)}. Consulte os logs."}), 500


# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    # Cria diretório base de relatórios se não existir ao iniciar
    # criar_diretorio_seguro(RELATORIOS_DIR_ABS) # Removido - criar por requisição

    # Executa a aplicação Flask
    # debug=True é útil para desenvolvimento, mas DESATIVE em produção!
    # use_reloader=False evita recarregamento duplo que pode causar problemas com logs/setup
    # host='0.0.0.0' permite acesso de outras máquinas na rede
    # port=5000 é a porta padrão do Flask
    logger.info("Iniciando a aplicação Flask...")
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
    logger.info("Aplicação Flask finalizada.")
