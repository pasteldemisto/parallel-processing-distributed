"""
operacoes.py
------------
Operacoes sobre matrizes: geracao, validacao, multiplicacao serial e paralela.

Responsabilidades:
    - Gerar matrizes aleatorias reprodutiveis via semente
    - Validar dimensoes para multiplicacao
    - Multiplicar matrizes de forma serial (baseline)
    - Multiplicar matrizes de forma paralela usando ProcessPoolExecutor
    - Dividir e reunir blocos de linhas para processamento distribuido/paralelo
"""

from concurrent.futures import ProcessPoolExecutor
import random


# ---------------------------------------------------------------------------
# Geracao de matrizes
# ---------------------------------------------------------------------------

def gerar_matriz(linhas, colunas, semente, val_min=-9, val_max=9):
    """
    Gera uma matriz aleatoria de inteiros com dimensao linhas x colunas.

    Utiliza uma semente fixa para garantir reproducibilidade nos experimentos.
    Os valores sao gerados no intervalo [val_min, val_max].

    Args:
        linhas   : numero de linhas da matriz
        colunas  : numero de colunas da matriz
        semente  : semente para o gerador de numeros aleatorios
        val_min  : valor inteiro minimo dos elementos (padrao -9)
        val_max  : valor inteiro maximo dos elementos (padrao  9)

    Returns:
        Matriz representada como lista de listas de inteiros.
    """
    if linhas <= 0 or colunas <= 0:
        raise ValueError("As dimensoes da matriz devem ser valores positivos.")

    rng = random.Random(semente)
    return [[rng.randint(val_min, val_max) for _ in range(colunas)] for _ in range(linhas)]


# ---------------------------------------------------------------------------
# Utilitarios de forma e validacao
# ---------------------------------------------------------------------------

def dimensoes(matriz):
    """
    Retorna o numero de linhas e colunas da matriz.

    Args:
        matriz : lista de listas representando a matriz

    Returns:
        Tupla (linhas, colunas).
    """
    if not matriz or not matriz[0]:
        raise ValueError("A matriz informada esta vazia.")

    num_colunas = len(matriz[0])
    if any(len(linha) != num_colunas for linha in matriz):
        raise ValueError("A matriz nao e retangular.")

    return len(matriz), num_colunas


def validar_multiplicacao(a, b):
    """
    Verifica se as dimensoes de A e B permitem a operacao A x B.

    Para que a multiplicacao seja valida, o numero de colunas de A
    deve ser igual ao numero de linhas de B.

    Args:
        a : matriz A
        b : matriz B

    Raises:
        ValueError : se as dimensoes forem incompativeis.
    """
    _, colunas_a = dimensoes(a)
    linhas_b, _ = dimensoes(b)
    if colunas_a != linhas_b:
        lin_a, col_a = dimensoes(a)
        lin_b, col_b = dimensoes(b)
        raise ValueError(
            f"Dimensoes incompativeis: A={lin_a}x{col_a}, B={lin_b}x{col_b}. "
            f"Colunas de A devem ser iguais as linhas de B."
        )


# ---------------------------------------------------------------------------
# Multiplicacao serial
# ---------------------------------------------------------------------------

def multiplicar_serial(a, b):
    """
    Multiplica as matrizes A e B de forma sequencial (serial).

    Implementa o algoritmo classico de multiplicacao de matrizes:
    C[i][j] = soma(A[i][k] * B[k][j]) para todo k.

    Serve como baseline para calculo de speedup nos experimentos.

    Args:
        a : matriz A com dimensao M x N
        b : matriz B com dimensao N x P

    Returns:
        Matriz C com dimensao M x P.
    """
    validar_multiplicacao(a, b)
    _, colunas_a = dimensoes(a)
    _, colunas_b = dimensoes(b)

    # Pre-transpoe as colunas de B para acesso sequencial na memoria
    colunas_de_b = [[linha[col] for linha in b] for col in range(colunas_b)]

    return [
        [sum(linha[k] * coluna[k] for k in range(colunas_a)) for coluna in colunas_de_b]
        for linha in a
    ]


# ---------------------------------------------------------------------------
# Divisao e reuniao de blocos (usadas por paralelo e distribuido)
# ---------------------------------------------------------------------------

def fatiar_em_blocos(matriz, num_partes):
    """
    Divide a matriz em blocos de linhas para processamento paralelo/distribuido.

    O resto da divisao e distribuido nas primeiras fatias, garantindo que
    nenhum bloco fique com mais de uma linha a mais que os demais.

    Args:
        matriz    : matriz a ser dividida
        num_partes: numero de blocos desejados

    Returns:
        Lista de tuplas (inicio, fim, bloco), onde:
            - inicio : indice da primeira linha do bloco na matriz original
            - fim    : indice exclusivo da ultima linha do bloco
            - bloco  : sub-lista de linhas correspondente
    """
    total_linhas, _ = dimensoes(matriz)
    if num_partes <= 0:
        raise ValueError("O numero de partes deve ser positivo.")

    # Garante que nao criamos mais partes do que linhas existem
    num_partes = min(num_partes, total_linhas)
    base = total_linhas // num_partes
    resto = total_linhas % num_partes
    blocos = []
    inicio = 0

    for indice in range(num_partes):
        # As primeiras `resto` fatias recebem uma linha extra
        tamanho = base + (1 if indice < resto else 0)
        fim = inicio + tamanho
        blocos.append((inicio, fim, matriz[inicio:fim]))
        inicio = fim

    return blocos


def reunir_blocos(blocos):
    """
    Recompoe a matriz final a partir dos blocos de resultado.

    Ordena os blocos pelo indice de inicio para garantir a ordem correta,
    independente da ordem em que os servidores responderam.

    Args:
        blocos : iteravel de tuplas (inicio, fim, bloco)

    Returns:
        Matriz completa resultante da concatenacao dos blocos.
    """
    resultado = []
    proximo_inicio = 0

    for inicio, fim, bloco in sorted(blocos, key=lambda item: item[0]):
        if inicio != proximo_inicio:
            raise ValueError("Blocos ausentes ou fora de sequencia.")
        if fim - inicio != len(bloco):
            raise ValueError("Intervalo de linhas inconsistente no bloco.")
        resultado.extend(bloco)
        proximo_inicio = fim

    return resultado


# ---------------------------------------------------------------------------
# Multiplicacao paralela local
# ---------------------------------------------------------------------------

def _processar_bloco(args):
    """
    Funcao auxiliar executada em cada processo filho do pool.

    Recebe um bloco de linhas de A e a matriz B completa,
    e retorna o bloco de resultado C correspondente.

    Args:
        args : tupla ((inicio, fim, bloco_a), b)

    Returns:
        Tupla (inicio, fim, bloco_c).
    """
    inicio, fim, bloco = args[0]
    b = args[1]
    return inicio, fim, multiplicar_serial(bloco, b)


def multiplicar_paralelo(a, b, num_workers):
    """
    Multiplica as matrizes A e B usando multiplos processos locais.

    Divide A em blocos de linhas e distribui entre `num_workers` processos
    usando ProcessPoolExecutor. Os resultados sao reunidos na ordem correta.

    Obs: para matrizes pequenas o overhead de criacao dos processos pode
    tornar esta versao mais lenta que a serial (ver Lei de Amdahl).

    Args:
        a           : matriz A com dimensao M x N
        b           : matriz B com dimensao N x P
        num_workers : numero de processos paralelos

    Returns:
        Matriz C com dimensao M x P.
    """
    validar_multiplicacao(a, b)

    # Para casos triviais nao vale o overhead do pool
    if num_workers <= 1 or len(a) == 1:
        return multiplicar_serial(a, b)

    blocos = fatiar_em_blocos(a, num_workers)
    with ProcessPoolExecutor(max_workers=min(num_workers, len(blocos))) as executor:
        blocos_resultado = list(
            executor.map(_processar_bloco, [(bloco, b) for bloco in blocos])
        )

    return reunir_blocos(blocos_resultado)


# ---------------------------------------------------------------------------
# Validacao de corretude
# ---------------------------------------------------------------------------

def matrizes_iguais(a, b):
    """
    Verifica se duas matrizes sao identicas elemento a elemento.

    Usada nos experimentos para confirmar que os modos paralelo e distribuido
    produzem o mesmo resultado que o modo serial (corretude).

    Args:
        a : primeira matriz
        b : segunda matriz

    Returns:
        True se as matrizes forem iguais, False caso contrario.
    """
    return a == b