"""Conducao dos experimentos e coleta de metricas de desempenho."""

from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys
import time

from comunicacao import (
    MODO_PARALELO,
    MODO_SERIAL,
    multiplicar_distribuido,
    subir_servidores,
    encerrar_servidores,
)
from operacoes import (
    gerar_matriz,
    matrizes_iguais,
    multiplicar_paralelo,
    multiplicar_serial,
)
from graficos import plotar_resultados


# ---------------------------------------------------------------------------
# Utilitarios de medicao
# ---------------------------------------------------------------------------

def cronometrar(funcao) -> tuple[object, float]:
    """Executa `funcao` e retorna (resultado, tempo_decorrido_em_segundos)."""
    inicio = time.perf_counter()
    resultado = funcao()
    return resultado, time.perf_counter() - inicio


def exibir_registro(reg: dict) -> None:
    """Imprime um registro de resultado formatado no console."""
    print(
        f"  [{reg['modo']:<12}] {reg['caso']:<12} "
        f"tempo={reg['tempo']:.6f}s  "
        f"speedup={reg['speedup']:.3f}  "
        f"eficiencia={reg['eficiencia']:.3f}  "
        f"valido={reg['valido']}"
    )


def montar_registro(
    rotulo: str,
    modo: str,
    caso: str,
    tempo: float,
    tempo_serial: float,
    valido: bool,
    servidores: int = 1,
    workers: int = 1,
) -> dict:
    """Cria um dicionario com todas as metricas de um experimento."""
    speedup = tempo_serial / tempo if tempo > 0 else 0.0
    eficiencia = speedup / servidores if servidores > 0 else speedup
    return {
        "rotulo": rotulo,
        "modo": modo,
        "caso": caso,
        "tempo": tempo,
        "tempo_serial": tempo_serial,
        "speedup": speedup,
        "eficiencia": eficiencia,
        "servidores": servidores,
        "workers": workers,
        "valido": valido,
    }


# ---------------------------------------------------------------------------
# Nucleo do experimento
# ---------------------------------------------------------------------------

def comparar_todos_os_modos(
    linhas: int,
    colunas: int,
    semente: int,
    servidores: list[tuple[str, int]],
    workers_locais: int,
    workers_por_servidor: int,
) -> list[dict]:
    """
    Executa os quatro modos de multiplicacao para a dimensao informada:
      1. Serial
      2. Paralelo local (ProcessPoolExecutor)
      3. Distribuido serial (sockets)
      4. Distribuido hibrido (sockets + processos nos nos)
    """
    rotulo_caso = f"{linhas}x{colunas}"

    # Gera A (linhas x colunas) e B (colunas x colunas) para multiplicacao valida
    a = gerar_matriz(linhas, colunas, semente)
    b = gerar_matriz(colunas, colunas, semente + 1)

    # --- Serial ---
    resultado_serial, tempo_serial = cronometrar(lambda: multiplicar_serial(a, b))
    registros = [
        montar_registro("Serial", "serial", rotulo_caso, tempo_serial, tempo_serial, True)
    ]

    # --- Paralelo local ---
    resultado_paralelo, tempo_paralelo = cronometrar(
        lambda: multiplicar_paralelo(a, b, workers_locais)
    )
    registros.append(
        montar_registro(
            "Paralelo local",
            "paralelo",
            rotulo_caso,
            tempo_paralelo,
            tempo_serial,
            matrizes_iguais(resultado_serial, resultado_paralelo),
            workers=workers_locais,
        )
    )

    # --- Distribuido serial ---
    dist_serial = multiplicar_distribuido(a, b, servidores, modo=MODO_SERIAL, workers_por_servidor=1)
    registros.append(
        montar_registro(
            "Distribuido serial",
            "distribuido",
            rotulo_caso,
            dist_serial["tempo_total"],
            tempo_serial,
            matrizes_iguais(resultado_serial, dist_serial["matriz"]),
            servidores=len(servidores),
            workers=1,
        )
    )

    # --- Distribuido hibrido ---
    dist_hibrido = multiplicar_distribuido(
        a, b, servidores, modo=MODO_PARALELO, workers_por_servidor=workers_por_servidor
    )
    registros.append(
        montar_registro(
            "Distribuido hibrido",
            "hibrido",
            rotulo_caso,
            dist_hibrido["tempo_total"],
            tempo_serial,
            matrizes_iguais(resultado_serial, dist_hibrido["matriz"]),
            servidores=len(servidores),
            workers=workers_por_servidor,
        )
    )

    return registros


def executar_experimentos(
    casos_de_teste: list[tuple[int, int]],
    repeticoes: int,
    quantidade_servidores: int,
    workers_locais: int,
    workers_por_servidor: int,
    semente: int,
) -> list[dict]:
    """Loop principal: sobe servidores, itera pelos casos de teste e coleta resultados."""
    servidores, processos = subir_servidores(quantidade_servidores, workers_por_servidor)
    todos_registros: list[dict] = []

    try:
        for linhas, colunas in casos_de_teste:
            for rep in range(repeticoes):
                print(f"\n>>> Caso {linhas}x{colunas} | repeticao {rep + 1}/{repeticoes}")
                registros = comparar_todos_os_modos(
                    linhas=linhas,
                    colunas=colunas,
                    semente=semente + rep + linhas + colunas,
                    servidores=servidores,
                    workers_locais=workers_locais,
                    workers_por_servidor=workers_por_servidor,
                )
                todos_registros.extend(registros)
                for reg in registros:
                    exibir_registro(reg)
    finally:
        encerrar_servidores(processos)

    return todos_registros


# ---------------------------------------------------------------------------
# Persistencia e execucao completa
# ---------------------------------------------------------------------------

def salvar_csv(resultados: list[dict], caminho: str = "results/resultados.csv") -> None:
    """Salva os resultados dos experimentos em arquivo CSV."""
    saida = Path(caminho)
    saida.parent.mkdir(parents=True, exist_ok=True)

    with saida.open("w", newline="", encoding="utf-8") as arq:
        escritor = csv.DictWriter(arq, fieldnames=list(resultados[0].keys()))
        escritor.writeheader()
        escritor.writerows(resultados)

    print(f"[CSV] Resultados salvos em: {saida}")


def executar_testes_automatizados() -> None:
    """Roda a suite de testes com pytest."""
    print("\nExecutando suite de testes automatizados...")
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], check=False)
    if proc.returncode != 0:
        raise RuntimeError("Falha na suite de testes. Verifique os erros acima.")


def executar_tudo(
    casos_de_teste: list[tuple[int, int]],
    repeticoes: int,
    quantidade_servidores: int,
    workers_locais: int,
    workers_por_servidor: int,
    semente: int,
    rodar_testes: bool,
    salvar_resultados: bool,
    exibir_graficos: bool,
) -> list[dict]:
    """Ponto de entrada da pipeline completa de experimentos."""
    if rodar_testes:
        executar_testes_automatizados()

    resultados = executar_experimentos(
        casos_de_teste=casos_de_teste,
        repeticoes=repeticoes,
        quantidade_servidores=quantidade_servidores,
        workers_locais=workers_locais,
        workers_por_servidor=workers_por_servidor,
        semente=semente,
    )

    if salvar_resultados:
        salvar_csv(resultados)

    plotar_resultados(resultados, exibir=exibir_graficos)
    return resultados
