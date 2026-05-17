"""Operacoes sobre matrizes: geracao, validacao, multiplicacao serial e paralela."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import random
from typing import Iterable


# Tipos auxiliares
Matriz = list[list[int | float]]
Bloco = tuple[int, int, Matriz]


def gerar_matriz(linhas: int, colunas: int, semente: int, val_min: int = -9, val_max: int = 9) -> Matriz:
    """Gera uma matriz aleatoria de dimensao linhas x colunas."""
    if linhas <= 0 or colunas <= 0:
        raise ValueError("As dimensoes da matriz devem ser valores positivos.")

    rng = random.Random(semente)
    return [[rng.randint(val_min, val_max) for _ in range(colunas)] for _ in range(linhas)]


def dimensoes(matriz: Matriz) -> tuple[int, int]:
    """Retorna (linhas, colunas) da matriz."""
    if not matriz or not matriz[0]:
        raise ValueError("A matriz informada esta vazia.")

    num_colunas = len(matriz[0])
    if any(len(linha) != num_colunas for linha in matriz):
        raise ValueError("A matriz nao e retangular.")

    return len(matriz), num_colunas


def validar_multiplicacao(a: Matriz, b: Matriz) -> None:
    """Verifica se as dimensoes permitem a multiplicacao A x B."""
    _, colunas_a = dimensoes(a)
    linhas_b, _ = dimensoes(b)
    if colunas_a != linhas_b:
        lin_a, col_a = dimensoes(a)
        lin_b, col_b = dimensoes(b)
        raise ValueError(
            f"Dimensoes incompativeis: A={lin_a}x{col_a}, B={lin_b}x{col_b}. "
            f"Colunas de A devem ser iguais as linhas de B."
        )


def multiplicar_serial(a: Matriz, b: Matriz) -> Matriz:
    """Multiplicacao de matrizes de forma sequencial (serial)."""
    validar_multiplicacao(a, b)
    _, colunas_a = dimensoes(a)
    _, colunas_b = dimensoes(b)
    colunas_de_b = [[linha[col] for linha in b] for col in range(colunas_b)]

    return [
        [sum(linha[k] * coluna[k] for k in range(colunas_a)) for coluna in colunas_de_b]
        for linha in a
    ]


def fatiar_em_blocos(matriz: Matriz, num_partes: int) -> list[Bloco]:
    """Divide a matriz em blocos de linhas para processamento distribuido/paralelo."""
    total_linhas, _ = dimensoes(matriz)
    if num_partes <= 0:
        raise ValueError("O numero de partes deve ser positivo.")

    num_partes = min(num_partes, total_linhas)
    base = total_linhas // num_partes
    resto = total_linhas % num_partes
    blocos: list[Bloco] = []
    inicio = 0

    for indice in range(num_partes):
        tamanho = base + (1 if indice < resto else 0)
        fim = inicio + tamanho
        blocos.append((inicio, fim, matriz[inicio:fim]))
        inicio = fim

    return blocos


def reunir_blocos(blocos: Iterable[Bloco]) -> Matriz:
    """Recompoe a matriz final a partir dos blocos de resultado."""
    resultado: Matriz = []
    proximo_inicio = 0

    for inicio, fim, bloco in sorted(blocos, key=lambda item: item[0]):
        if inicio != proximo_inicio:
            raise ValueError("Blocos ausentes ou fora de sequencia.")
        if fim - inicio != len(bloco):
            raise ValueError("Intervalo de linhas inconsistente no bloco.")
        resultado.extend(bloco)
        proximo_inicio = fim

    return resultado


def _processar_bloco(args: tuple[Bloco, Matriz]) -> Bloco:
    """Funcao auxiliar para multiplicar um bloco pelo pool de processos."""
    inicio, fim, bloco = args[0]
    b = args[1]
    return inicio, fim, multiplicar_serial(bloco, b)


def multiplicar_paralelo(a: Matriz, b: Matriz, num_workers: int) -> Matriz:
    """Multiplicacao de matrizes usando multiplos processos locais."""
    validar_multiplicacao(a, b)
    if num_workers <= 1 or len(a) == 1:
        return multiplicar_serial(a, b)

    blocos = fatiar_em_blocos(a, num_workers)
    with ProcessPoolExecutor(max_workers=min(num_workers, len(blocos))) as executor:
        blocos_resultado = list(
            executor.map(_processar_bloco, [(bloco, b) for bloco in blocos])
        )

    return reunir_blocos(blocos_resultado)


def matrizes_iguais(a: Matriz, b: Matriz) -> bool:
    """Verifica se duas matrizes sao identicas elemento a elemento."""
    return a == b
