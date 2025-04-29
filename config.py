"""
Configurações centralizadas para a aplicação de análise de dados de trading.
"""
import os
from reportlab.lib.pagesizes import A4 # Importa A4 para uso nas constantes

# --- Diretórios ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RELATORIOS_DIR_NAME = 'relatorios'
# Usar caminho absoluto para garantir consistência entre ambientes
RELATORIOS_DIR_ABS = os.path.join(BASE_DIR, RELATORIOS_DIR_NAME)

# --- Nomes de Colunas ---
# Coluna alvo padronizada para armazenar os resultados numéricos após limpeza
RESULT_COLUMN_NAME = 'Resultado_Valor'

# Colunas de resultado potenciais em arquivos Excel (primária e alternativas)
PRIMARY_RESULT_COLUMN_EXCEL = 'Res. Operação (%)'
FALLBACK_RESULT_COLUMNS_EXCEL = ['Res. Operação', 'Resultado', 'Profit']

# Colunas de resultado potenciais em arquivos CSV (primária e alternativas)
PRIMARY_RESULT_COLUMN_CSV = 'Res. Operação (%)'
FALLBACK_RESULT_COLUMNS_CSV = ['Res. Operação', 'Resultado', 'Profit']

# Colunas de data/hora potenciais que serão mapeadas para 'Abertura' e 'Fechamento'
OPEN_TIME_COLUMNS = ['Abertura', 'Data Abertura', 'Open Time']
CLOSE_TIME_COLUMNS = ['Fechamento', 'Data Fechamento', 'Close Time']

# Coluna que identifica o robô (criada se não existir no Excel)
ROBO_COLUMN_NAME = 'Robo'

# --- Configurações de Processamento de Dados ---
# Encoding padrão para leitura de arquivos CSV
CSV_ENCODING = 'latin-1'
# Número de linhas a serem puladas no início dos arquivos CSV (cabeçalho, etc.)
CSV_SKIPROWS = 5
# Separador de colunas esperado nos arquivos CSV
CSV_SEPARATOR = ';'
# Indica se a primeira linha após skiprows é o cabeçalho no CSV
CSV_HEADER = 0 # 0 significa que a primeira linha lida é o cabeçalho

# --- Configurações de Gráficos ---
CHART_DPI = 150  # Resolução (dots per inch) para salvar os gráficos
CHART_FORMAT = 'png' # Formato de arquivo para os gráficos
CHART_WIDTH_INCHES = 10 # Largura padrão dos gráficos em polegadas
CHART_HEIGHT_INCHES = 5 # Altura padrão dos gráficos em polegadas
# Alturas específicas para tipos de gráficos (ajustar conforme necessário)
STACKPLOT_HEIGHT_INCHES = 6
LINEPLOT_HEIGHT_INCHES = 5
SCATTER_HEIGHT_INCHES = 5
ACCUM_HEIGHT_INCHES = 6

# --- Configurações de Horários (Filtro de Operações) ---
# Horário de início (inclusive) para filtrar operações (ex: 8 para 08:00)
TRADING_HOUR_START = 8
# Horário de fim (inclusive) para filtrar operações (ex: 18 para 18:00 a 18:59)
TRADING_HOUR_END = 18

# --- Configurações de Segurança e Validação ---
# Conjunto de extensões permitidas para upload de arquivo único
ALLOWED_EXTENSIONS_EXCEL = {'.xlsx', '.xls'}
# Conjunto de extensões permitidas para upload de múltiplos arquivos
ALLOWED_EXTENSIONS_CSV = {'.csv'}
# Tamanho máximo permitido por arquivo em Megabytes
MAX_FILE_SIZE_MB = 20

# --- Configurações de Geração de PDF ---
# Tamanho da página do PDF (usando A4 importado de reportlab)
PDF_PAGE_SIZE = A4
# Margens da página do PDF em pontos (points)
PDF_LEFT_MARGIN = 40
PDF_RIGHT_MARGIN = 40
PDF_TOP_MARGIN = 40
PDF_BOTTOM_MARGIN = 40
# Largura padrão para as imagens inseridas no PDF em pontos
PDF_IMAGE_WIDTH = 500
# Alturas específicas para imagens no PDF (ajustar conforme layout)
PDF_IMAGE_HEIGHT_DEFAULT = 250
PDF_IMAGE_HEIGHT_ACCUM = 280 # Altura para gráficos acumulados, se diferente

# --- Percentil para Limite Ideal (Gráfico de Linha Diária) ---
IDEAL_LIMIT_PERCENTILE = 80 # Percentil 80 dos picos diários positivos
