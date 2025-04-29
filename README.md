# README.md - Aplicação de Análise de Operações de Trading

## Visão Geral
Esta aplicação web Flask foi desenvolvida para processar dados de operações de trading a partir de arquivos Excel (`.xlsx`, `.xls`) ou múltiplos arquivos CSV (`.csv`). A aplicação realiza análises sobre os dados, gera gráficos relevantes (como desempenho por horário, acumulado por robô, etc.) e consolida os resultados em um relatório PDF detalhado que é automaticamente disponibilizado para download.

O código foi completamente refatorado a partir de uma versão monolítica, seguindo as melhores práticas de desenvolvimento Python, incluindo:
*   **Modularização:** Separação lógica do código em módulos com responsabilidades claras.
*   **Tipagem Estática:** Uso de type hints para melhorar a legibilidade e detecção de erros.
*   **Documentação:** Docstrings detalhadas no estilo Google para funções e módulos.
*   **Tratamento de Erros:** Implementação de logging estruturado e tratamento específico de exceções.
*   **Configuração Centralizada:** Uso de um arquivo `config.py` para parâmetros e constantes.
*   **Segurança:** Validação de arquivos de entrada (tipo, tamanho) e sanitização de nomes.
*   **Interface Web Simples:** Utilização de Flask e HTML básico para interação com o usuário.

## Estrutura do Projeto
```
projeto/
├── app.py                  # Ponto de entrada da aplicação Flask (rotas, lógica principal)
├── config.py               # Configurações centralizadas (nomes de colunas, caminhos, etc.)
├── requirements.txt        # Dependências Python do projeto
├── templates/              # Templates HTML (interface do usuário)
│   └── index.html          # Página principal para upload de arquivos
└── modules/                # Módulos com a lógica de negócio
    ├── __init__.py         # Torna o diretório 'modules' um pacote Python
    ├── utils.py            # Funções utilitárias (manipulação de arquivos, validação, formatação)
    ├── data_processor.py   # Módulo para leitura, limpeza e processamento dos dados brutos
    ├── chart_generator.py  # Módulo para criação dos gráficos de análise (matplotlib/seaborn)
    └── pdf_generator.py    # Módulo para geração do relatório PDF final (reportlab)
```

## Instalação

1.  **Clone o repositório ou extraia os arquivos:**
    ```bash
    git clone <url_do_repositorio>
    cd <diretorio_do_projeto>
    ```
    Ou extraia o arquivo ZIP para uma pasta de sua escolha.

2.  **Crie um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    # No Windows:
    .\venv\Scripts\activate
    # No Linux/macOS:
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

## Uso

1.  **Execute a aplicação Flask:**
    No terminal, dentro da pasta do projeto e com o ambiente virtual ativado, execute:
    ```bash
    python app.py
    ```
    A aplicação estará disponível no seu navegador.

2.  **Acesse a interface web:**
    Abra seu navegador e vá para `http://127.0.0.1:5000` (ou `http://localhost:5000`).

3.  **Escolha o tipo de upload:**
    *   **Arquivo Único (Excel):** Selecione esta opção se seus dados estão em um único arquivo `.xlsx` ou `.xls`.
    *   **Múltiplos Arquivos (CSV):** Selecione esta opção se seus dados estão distribuídos em vários arquivos `.csv` (um por robô, por exemplo).

4.  **Selecione o(s) arquivo(s):**
    Clique no botão "Escolher arquivo" (ou similar) e selecione o(s) arquivo(s) correspondente(s) ao tipo de upload escolhido.

5.  **Processe os dados:**
    Clique no botão "Processar Dados e Gerar Relatório".

6.  **Aguarde o processamento:**
    A aplicação processará os dados, gerará os gráficos e criará o relatório PDF. Isso pode levar alguns segundos ou minutos dependendo do volume de dados. Uma indicação de "Processando..." será exibida.

7.  **Download do Relatório:**
    Após o processamento, o download do arquivo `relatorio_analise_trading.pdf` iniciará automaticamente.

## Detalhes da Implementação e Melhorias

### 1. Modularização
*   **`app.py`:** Orquestra o fluxo, gerencia rotas HTTP, validações iniciais e coordena chamadas aos outros módulos.
*   **`config.py`:** Centraliza constantes como nomes de colunas esperados, caminhos, configurações de gráficos/PDF, limites, etc., facilitando a customização.
*   **`modules/utils.py`:** Contém funções reutilizáveis como validação de arquivos (tamanho, extensão), criação/limpeza de diretórios, formatação de horas.
*   **`modules/data_processor.py`:** Responsável por:
    *   Ler arquivos Excel e CSV.
    *   Identificar e padronizar colunas de resultado e data/hora.
    *   Limpar dados numéricos (converter para float, tratar separadores).
    *   Converter colunas de data/hora para o tipo `datetime`.
    *   Remover dados inválidos (ex: linhas sem resultado, datas inválidas).
    *   Consolidar dados de múltiplos arquivos.
    *   Realizar cálculos básicos (somas, contagens, identificação de período).
    *   Filtrar dados por horário (ex: 8h-18h).
*   **`modules/chart_generator.py`:** Encapsula a lógica de criação de cada tipo de gráfico usando Matplotlib e Seaborn:
    *   Gráfico de dispersão de ganhos por minuto.
    *   Gráfico de área empilhada (montanha) de ganho acumulado.
    *   Gráficos de linha de evolução diária e acumulado por intervalo para cada robô.
    *   Cálculo de métricas associadas aos gráficos (ex: melhor intervalo, limite ideal).
*   **`modules/pdf_generator.py`:** Utiliza a biblioteca ReportLab para montar o documento PDF, inserindo:
    *   Títulos e informações gerais.
    *   Gráficos gerados pelo `chart_generator`.
    *   Tabelas de resumo formatadas.
    *   Estruturação lógica do conteúdo (seções, paginação).

### 2. Tipagem e Documentação
*   Todas as funções possuem *type hints* para clareza e auxílio de ferramentas de análise estática.
*   Docstrings no formato Google explicam o propósito, argumentos, retornos e possíveis exceções de cada função.

### 3. Tratamento de Erros e Logging
*   Uso do módulo `logging` para registrar informações, avisos e erros durante a execução. Logs são exibidos no console (podem ser direcionados para arquivo).
*   Tratamento específico para exceções esperadas (ex: `ValueError` para dados inválidos, `FileNotFoundError`, `pd.errors.EmptyDataError`).
*   Mensagens de erro claras são exibidas ao usuário através de `flash messages` do Flask.
*   Uso de `traceback` para logar detalhes de erros inesperados.

### 4. Otimização e Boas Práticas
*   Operações com Pandas vetorizadas sempre que possível para melhor desempenho.
*   Uso de `.copy()` para evitar `SettingWithCopyWarning` ao modificar DataFrames filtrados.
*   Leitura de arquivos diretamente da memória (`request.files`) quando possível, evitando salvar arquivos temporários desnecessariamente (exceto como fallback).
*   Liberação de memória fechando figuras Matplotlib (`plt.close(fig)`) após salvar.
*   Estrutura de código seguindo princípios SOLID (Single Responsibility Principle).

### 5. Segurança
*   **Validação de Upload:** Verifica extensão e tamanho máximo dos arquivos no backend (`utils.py` e configuração Flask `MAX_CONTENT_LENGTH`).
*   **Sanitização de Nomes:** Usa `secure_filename` para evitar nomes de arquivo maliciosos.
*   **Tratamento de Diretórios:** Cria e remove diretórios temporários de forma segura.

### 6. Interface do Usuário (templates/index.html)
*   Formulário HTML simples e funcional.
*   Uso de JavaScript básico para mostrar/ocultar campos de upload condicionalmente.
*   Exibição de mensagens de feedback (sucesso, erro, aviso) para o usuário.
*   Indicador visual de "Processando..." durante a execução no backend.

## Requisitos
*   Python 3.8+
*   Dependências listadas em `requirements.txt`:
    *   Flask
    *   pandas
    *   numpy
    *   matplotlib
    *   seaborn
    *   reportlab
    *   openpyxl
    *   Werkzeug

## Possíveis Melhorias Futuras
*   Adicionar testes unitários e de integração.
*   Implementar um sistema de filas (ex: Celery) para processamentos longos.
*   Melhorar a interface do usuário (framework CSS/JS).
*   Opções de personalização de análise (seleção de datas, robôs, etc.).
*   Cache de resultados.
*   Autenticação de usuário (se necessário).
*   Empacotamento com Docker.
```
