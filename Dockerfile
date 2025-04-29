# Usar uma imagem base oficial do Python
FROM python:3.11-slim-bullseye

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE 1 # Impede Python de gerar arquivos .pyc
ENV PYTHONUNBUFFERED 1      # Força print() a aparecer nos logs do Docker imediatamente

# Definir diretório de trabalho dentro do contêiner
WORKDIR /app

# Instalar dependências do sistema necessárias para as bibliotecas Python
# build-essential: para compilar algumas dependências se necessário
# libgomp1: necessário pelo numpy/scipy/matplotlib em alguns casos
# libfreetype6-dev, libjpeg-dev, libpng-dev, libtiff-dev: para matplotlib/reportlab lidarem com fontes e imagens
# fonts-dejavu-core: Fornece fontes básicas para matplotlib/reportlab
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar apenas o requirements.txt primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar dependências Python
# --no-cache-dir: economiza espaço na imagem
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código da aplicação para o diretório de trabalho
COPY . .

# Expor a porta que o Gunicorn usará dentro do contêiner
EXPOSE 5000

# Comando para rodar a aplicação usando Gunicorn
# bind 0.0.0.0: Permite conexões de fora do contêiner (essencial)
# workers 4: Número de processos workers (ajuste conforme recursos do VPS)
# app:app : Nome do arquivo (app.py) : nome da instância Flask (app)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]