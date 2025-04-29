# Lista de Tarefas e Melhorias - Análise de Trading

## Análise e Planejamento
- [x] Ler o código Python original (`pasted_content.txt`)
- [x] Analisar a estrutura e funcionalidade do código original
- [x] Identificar oportunidades de melhoria (modularização, erros, performance, etc.)
- [x] Planejar a nova estrutura de arquivos (`app.py`, `config.py`, `modules/`)

## Implementação de Melhorias (Refatoração Principal)
- [x] Modularizar o código (separar em arquivos por funcionalidade)
  - [x] Criar módulo `utils.py` para funções utilitárias e validação.
  - [x] Criar módulo `data_processor.py` para leitura e processamento de dados.
  - [x] Criar módulo `chart_generator.py` para geração de gráficos.
  - [x] Criar módulo `pdf_generator.py` para geração de PDF.
  - [x] Criar `config.py` para configurações centralizadas.
  - [x] Adaptar `app.py` para orquestrar os módulos.
- [x] Melhorar o tratamento de erros
  - [x] Implementar tratamento de exceções mais específico (ValueError, KeyError, IOError, etc.).
  - [x] Adicionar logging estruturado (`logging` module) em todos os módulos.
  - [x] Usar `flash messages` para feedback ao usuário no Flask.
  - [x] Tratar erro de arquivo muito grande (`MAX_CONTENT_LENGTH`).
- [x] Otimizar o desempenho (inicial)
  - [x] Priorizar leitura de arquivos em memória.
  - [x] Usar operações vetorizadas do Pandas onde aplicável.
  - [x] Fechar figuras Matplotlib (`plt.close`) para liberar memória.
- [x] Implementar boas práticas
  - [x] Adicionar tipagem (type hints) em funções e métodos.
  - [x] Adicionar/Melhorar a documentação (docstrings no estilo Google).
  - [x] Seguir PEP 8 (feito implicitamente pelas IDEs modernas).
  - [x] Mover constantes e configurações para `config.py`.
- [x] Melhorar a segurança básica
  - [x] Validar extensão e tamanho dos arquivos (`utils.py`).
  - [x] Sanitizar nomes de arquivos (`secure_filename`).
  - [x] Gerenciar diretório temporário de forma segura.

## Testes e Documentação
- [ ] ~~Implementar testes unitários (pytest)~~ *(Não implementado nesta fase)*
  - [ ] Criar `tests/test_utils.py`
  - [ ] Criar `tests/test_data_processor.py` (com arquivos de exemplo)
  - [ ] Criar `tests/test_chart_generator.py`
  - [ ] Criar `tests/test_pdf_generator.py`
- [x] Testar o código refatorado manualmente (upload Excel, CSV, erros)
- [x] Documentar as mudanças e a nova estrutura (README.md)
- [x] Preparar o código final refatorado

## Entrega
- [x] Entregar o código refatorado completo (todos os arquivos .py, .html, .txt, .md)

## Melhorias Futuras (Pós-Entrega)
- [ ] Implementar Testes Unitários e de Integração.
- [ ] Adicionar interface de usuário mais rica (ex: Bootstrap, Vue, React).
- [ ] Permitir seleção de intervalo de datas para análise.
- [ ] Permitir seleção de robôs específicos para análise.
- [ ] Adicionar mais tipos de gráficos e métricas (ex: Drawdown, Sharpe Ratio).
- [ ] Implementar processamento assíncrono (Celery) para uploads grandes/demorados.
- [ ] Adicionar caching de resultados.
- [ ] Melhorar a gestão de diretórios temporários (UUIDs por requisição).
- [ ] Considerar o uso de banco de dados para armazenar resultados ou metadados.
- [ ] Empacotar aplicação com Docker.
