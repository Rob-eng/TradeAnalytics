"""
Módulo contendo funções utilitárias diversas para a aplicação.

Inclui funções para manipulação de sistema de arquivos, conversão de formatos
e validação de arquivos de entrada.
"""
import os
import shutil
import logging
from typing import Optional, Union, IO, Any, Set
import pandas as pd
from werkzeug.utils import secure_filename # Para sanitizar nomes de arquivos
from datetime import time # Para comparar com meia-noite

from config import (
    ALLOWED_EXTENSIONS_EXCEL,
    ALLOWED_EXTENSIONS_CSV,
    MAX_FILE_SIZE_MB
)

logger = logging.getLogger(__name__)

# --- Funções de Sistema de Arquivos ---

def criar_diretorio_seguro(path: str) -> None:
    """
    Cria um diretório de forma segura, se ele ainda não existir.

    Garante que o diretório pai exista e trata possíveis erros de permissão.

    Args:
        path: O caminho completo do diretório a ser criado.

    Raises:
        OSError: Se ocorrer um problema ao criar o diretório (ex: falta de permissão).
    """
    try:
        os.makedirs(path, exist_ok=True)
        logger.info(f"Diretório verificado/criado com sucesso: {path}")
    except OSError as e:
        logger.error(f"Erro crítico ao criar diretório '{path}': {e}", exc_info=True)
        # Relança a exceção para que a aplicação principal possa tratá-la
        raise OSError(f"Não foi possível criar o diretório necessário: {path}. Verifique as permissões.") from e

def limpar_diretorio_seguro(path: str) -> None:
    """
    Remove um diretório e todo o seu conteúdo de forma segura.

    Verifica se o diretório existe antes de tentar removê-lo e loga avisos
    em caso de falha na remoção (mas não interrompe a execução).

    Args:
        path: O caminho completo do diretório a ser removido.
    """
    if os.path.exists(path) and os.path.isdir(path):
        try:
            shutil.rmtree(path)
            logger.info(f"Diretório removido com sucesso: {path}")
        except OSError as e:
            # Loga como aviso, pois a falha na limpeza geralmente não é crítica
            logger.warning(f"AVISO: Não foi possível remover o diretório '{path}': {e}")
    else:
        logger.info(f"Diretório não encontrado para remoção ou não é um diretório: {path}")

def sanitize_filename(filename: str) -> str:
    """
    Sanitiza um nome de arquivo para uso seguro no sistema de arquivos.

    Remove caracteres potencialmente perigosos ou problemáticos, substituindo
    espaços e caracteres especiais. Usa a função `secure_filename` do Werkzeug.

    Args:
        filename: O nome de arquivo original vindo do upload.

    Returns:
        O nome de arquivo sanitizado, seguro para ser salvo no disco.
    """
    if not filename:
        return "_nome_arquivo_vazio_"
    return secure_filename(filename)

# --- Funções de Validação de Arquivo ---

def _validar_arquivo(
    file: IO[Any],
    allowed_extensions: Set[str],
    max_size_mb: int
) -> bool:
    """
    Função interna para validar um objeto de arquivo quanto à extensão e tamanho.

    Usada por `validar_arquivo_excel` e `validar_arquivo_csv`.

    Args:
        file: Objeto de arquivo (como os de request.files['nome_campo']).
        allowed_extensions: Um conjunto de strings contendo as extensões permitidas
                           (ex: {'.csv', '.txt'}). Deve incluir o ponto e ser minúsculo.
        max_size_mb: Tamanho máximo permitido para o arquivo em megabytes.

    Returns:
        True se o arquivo for válido de acordo com os critérios.

    Raises:
        ValueError: Se o arquivo for inválido (sem nome, extensão incorreta,
                    tamanho excedido ou vazio).
        IOError: Se houver um erro ao tentar ler o tamanho do arquivo.
    """
    if not file or not hasattr(file, 'filename') or not file.filename:
        raise ValueError("Nenhum arquivo foi fornecido ou o arquivo não possui um nome.")

    # Sanitiza o nome do arquivo antes de verificar a extensão
    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
         raise ValueError("Nome de arquivo inválido ou vazio após sanitização.")

    _, ext = os.path.splitext(safe_filename)
    if ext.lower() not in allowed_extensions:
        allowed_str = ", ".join(allowed_extensions)
        raise ValueError(f"Tipo de arquivo inválido: '{ext}'. Permitidos: {allowed_str}")

    try:
        # Verifica o tamanho do arquivo de forma eficiente
        file.seek(0, os.SEEK_END) # Vai para o fim do arquivo
        file_length = file.tell() # Pega a posição atual (tamanho em bytes)
        file.seek(0) # IMPORTANTE: Volta o ponteiro para o início para leituras futuras

        max_size_bytes = max_size_mb * 1024 * 1024
        if file_length > max_size_bytes:
            raise ValueError(f"Arquivo '{safe_filename}' ({file_length / (1024*1024):.2f} MB) excede o tamanho máximo permitido de {max_size_mb} MB.")

        if file_length == 0:
            # Considerar se um arquivo vazio é um erro ou apenas um aviso
            # Por enquanto, lançamos um erro pois um arquivo vazio não pode ser processado
            raise ValueError(f"Arquivo '{safe_filename}' está vazio e não pode ser processado.")

    except IOError as e:
        logger.error(f"Erro de I/O ao verificar o tamanho do arquivo '{safe_filename}': {e}", exc_info=True)
        raise IOError(f"Não foi possível verificar o tamanho do arquivo '{safe_filename}'.") from e
    except Exception as e: # Captura outras exceções inesperadas durante a validação
        logger.error(f"Erro inesperado ao validar o arquivo '{safe_filename}': {e}", exc_info=True)
        raise ValueError(f"Ocorreu um erro inesperado ao validar o arquivo '{safe_filename}'.") from e

    logger.info(f"Arquivo '{safe_filename}' validado com sucesso (extensão e tamanho).")
    return True

def validar_arquivo_excel(file: IO[Any]) -> bool:
    """
    Valida um arquivo enviado como sendo um Excel permitido (extensão e tamanho).

    Args:
        file: Objeto de arquivo do upload (Flask request.files).

    Returns:
        True se a validação passar.

    Raises:
        ValueError: Se o arquivo for inválido.
        IOError: Se houver erro ao ler o arquivo.
    """
    logger.debug(f"Iniciando validação para arquivo Excel: {getattr(file, 'filename', 'N/A')}")
    return _validar_arquivo(file, ALLOWED_EXTENSIONS_EXCEL, MAX_FILE_SIZE_MB)

def validar_arquivo_csv(file: IO[Any]) -> bool:
    """
    Valida um arquivo enviado como sendo um CSV permitido (extensão e tamanho).

    Args:
        file: Objeto de arquivo do upload (Flask request.files).

    Returns:
        True se a validação passar.

    Raises:
        ValueError: Se o arquivo for inválido.
        IOError: Se houver erro ao ler o arquivo.
    """
    logger.debug(f"Iniciando validação para arquivo CSV: {getattr(file, 'filename', 'N/A')}")
    return _validar_arquivo(file, ALLOWED_EXTENSIONS_CSV, MAX_FILE_SIZE_MB)


# --- Funções de Conversão e Formatação ---

def minutos_para_horario(minutos: Optional[Union[int, float]]) -> str:
    """
    Converte um número de minutos desde a meia-noite para o formato de horário "HH:MM".

    Trata casos de entrada None, NaN ou tipos inválidos retornando "N/A" ou "Inválido".

    Args:
        minutos: O número de minutos desde a meia-noite. Pode ser int, float,
                 None ou um valor que o pandas reconhece como NA.

    Returns:
        Uma string formatada como "HH:MM" (ex: "09:05", "14:30"),
        "N/A" se a entrada for None ou NaN, ou
        "Inválido" se a conversão para inteiro falhar.

    Exemplos:
        >>> minutos_para_horario(125)
        '02:05'
        >>> minutos_para_horario(540)
        '09:00'
        >>> minutos_para_horario(None)
        'N/A'
        >>> minutos_para_horario(pd.NA)
        'N/A'
        >>> minutos_para_horario("texto")
        'Inválido'
        >>> minutos_para_horario(75.5) # Floats são truncados
        '01:15'
    """
    if pd.isna(minutos):
        return "N/A"
    try:
        minutos_int = int(minutos) # Tenta converter para int, truncando floats
        if not (0 <= minutos_int < 24 * 60): # Valida se está dentro de um dia
             logger.warning(f"Valor de minutos fora do intervalo esperado (0-1439): {minutos_int}")
             # Pode retornar "Inválido" ou o cálculo, dependendo do requisito
             # return "Fora Intervalo"
        horas = minutos_int // 60
        mins = minutos_int % 60
        return f"{horas:02d}:{mins:02d}"
    except (ValueError, TypeError):
        # Ocorre se a entrada não puder ser convertida para int
        logger.warning(f"Falha ao converter minutos para horário. Entrada: {minutos} (Tipo: {type(minutos)})")
        return "Inválido"

def verificar_operacao_sem_horario(timestamp: pd.Timestamp) -> bool:
    """
    Verifica se um timestamp representa uma operação sem horário específico (00:00:00).

    Args:
        timestamp: O objeto Timestamp do pandas.

    Returns:
        True se o horário for meia-noite (00:00:00), False caso contrário.
        Retorna False também se o timestamp for NaT (Not a Time).
    """
    if pd.isna(timestamp):
        return False # NaT não é considerado "sem horário" para este propósito
    return timestamp.time() == time(0, 0, 0)