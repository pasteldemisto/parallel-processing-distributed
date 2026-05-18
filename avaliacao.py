"""
avaliacao.py
------------
Conducao dos experimentos e coleta de metricas de desempenho.

Responsabilidades:
    - Cronometrar cada modo de execucao
    - Calcular speedup e eficiencia em relacao ao modo serial
    - Validar corretude dos resultados paralelos/distribuidos
    - Orquestrar o loop de experimentos (casos de teste x repeticoes)
    - Salvar resultados em CSV
    - Coordenar a execucao completa da pipeline
"""

import csv
from pathlib import Path
import subprocess
import sys
import time

from comunicacao import MODO_PARALELO, MODO_SERIAL, multiplicar_distribuido, subir_servidores, encerrar_servidores
from operacoes import gerar_matriz, matrizes_iguais, multiplicar_paralelo, multiplicar_serial
from graficos import plotar_resultados


# ---------------------------------------------------------------------------
# Utilitarios de medicao
# ---------------------------------------------------------------------------

def cronometrar(funcao):
    """
    Executa uma funcao e mede seu tempo de parede (wall time).

    Args:
        funcao : callable sem argumentos a ser executado e cronometrado

    Returns:
        Tupla (resultado, tempo_em_segundos).
    """
    inicio = time.perf_counter()
    resultado = funcao()
    return resultado, time.perf_counter() - inicio


def exibir_registro(reg):
    """
    Imprime um registro de resultado formatado no console.

    Args:
        reg : dicionario com as metricas do experimento
    """
    print(
        f"  [{reg['modo']:<12}] {reg['caso']:<12} "
        f"tempo={reg['tempo']:.6f}s  "
        f"speedup={reg['speedup']:.3f}  "
        f"eficiencia={reg['eficiencia']:.3f}  "
        f"valido={reg['valido']}"
    )


def montar_registro(rotulo, modo, caso, tempo, tempo_serial, valido, servidores=1, workers=1):
    """
    Cria um dicionario com todas as metricas de um experimento.

    Calcula speedup = tempo_serial / tempo e eficiencia = speedup / servidores.

    Args:
        rotulo       : nome legivel do modo (ex: "Paralelo local")
        modo         : identificador interno do modo (ex: "paralelo")
        caso         : rotulo do caso de teste (ex: "500x200")
        tempo        : tempo medido neste modo em segundos
        tempo_serial : tempo do modo serial para o mesmo caso (baseline)
        valido       : True se o resultado confere com o serial
        servidores   : numero de servidores usados (para calculo de eficiencia)
        workers      : numero de processos usados

    Returns:
        Dicionario com todas as metricas do experimento.
    """
    speedup = tempo_serial / tempo if tempo > 0 else 0.0
    # Eficiencia mede o aproveitamento real dos recursos: 1.0 = perfeito
    eficiencia = speedup / servidores if servidores > 0 else speedup
    return {
        "rotulo":       rotulo,
        "modo":         modo,
        "caso":         caso,
        "tempo":        tempo,
        "tempo_serial": tempo_serial,
        "speedup":      speedup,
        "eficiencia":   eficiencia,
        "servidores":   servidores,
        "workers":      workers,
        "valido":       valido,
    }


# ---------------------------------------------------------------------------
# Nucleo do experimento: compara os 4 modos para um caso de teste
# ---------------------------------------------------------------------------

def comparar_todos_os_modos(linhas, colunas, semente, servidores, workers_locais, workers_por_servidor):
    """
    Executa e compara os quatro modos de multiplicacao para um par (linhas, colunas).

    Modos executados:
        1. Serial          - baseline, sem paralelismo
        2. Paralelo local  - ProcessPoolExecutor na mesma maquina
        3. Distribuido serial  - sockets TCP, cada servidor multiplica serialmente
        4. Distribuido hibrido - sockets TCP + ProcessPoolExecutor em cada servidor

    A matriz A tem dimensao linhas x colunas e B tem dimensao colunas x colunas,
    garantindo que a multiplicacao A x B seja sempre valida.

    Args:
        linhas               : numero de linhas de A
        colunas              : numero de colunas de A (e linhas de B)
        semente              : semente para geracao das matrizes
        servidores           : lista de (host, porta) dos servidores ativos
        workers_locais       : processos para o modo paralelo local
        workers_por_servidor : processos internos de cada servidor (modo hibrido)

    Returns:
        Lista de 4 dicionarios de metricas, um por modo.
    """
    rotulo_caso = f"{linhas}x{colunas}"

    # Gera as matrizes com sementes diferentes para A e B
    a = gerar_matriz(linhas, colunas, semente)
    b = gerar_matriz(colunas, colunas, semente + 1)

    # --- Modo 1: Serial (baseline) ---
    resultado_serial, tempo_serial = cronometrar(lambda: multiplicar_serial(a, b))
    registros = [
        montar_registro("Serial", "serial", rotulo_caso, tempo_serial, tempo_serial, True)
    ]

    # --- Modo 2: Paralelo local ---
    resultado_paralelo, tempo_paralelo = cronometrar(lambda: multiplicar_paralelo(a, b, workers_locais))
    registros.append(
        montar_registro(
            "Paralelo local",
            "paralelo",
            rotulo_caso,
            tempo_paralelo,
            tempo_serial,
            matrizes_iguais(resultado_serial, resultado_paralelo),  # verifica corretude
            workers=workers_locais,
        )
    )

    # --- Modo 3: Distribuido serial ---
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

    # --- Modo 4: Distribuido hibrido (sockets + processos em cada no) ---
    dist_hibrido = multiplicar_distribuido(a, b, servidores, modo=MODO_PARALELO, workers_por_servidor=workers_por_servidor)
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


# ---------------------------------------------------------------------------
# Loop principal de experimentos
# ---------------------------------------------------------------------------

def executar_experimentos(casos_de_teste, repeticoes, quantidade_servidores, workers_locais, workers_por_servidor, semente):
    """
    Sobe os servidores e itera por todos os casos de teste e repeticoes.

    Para cada caso de teste, executa os 4 modos `repeticoes` vezes e acumula
    os resultados. Os servidores sao encerrados ao final, mesmo em caso de erro.

    Args:
        casos_de_teste        : lista de tuplas (linhas, colunas)
        repeticoes            : numero de repeticoes por caso (para media dos tempos)
        quantidade_servidores : numero de processos servidores a subir
        workers_locais        : processos para o modo paralelo local
        workers_por_servidor  : processos internos de cada servidor
        semente               : semente base para geracao das matrizes

    Returns:
        Lista de todos os registros de metricas coletados.
    """
    servidores, processos = subir_servidores(quantidade_servidores, workers_por_servidor)
    todos_registros = []

    try:
        for linhas, colunas in casos_de_teste:
            for rep in range(repeticoes):
                print(f"\n>>> Caso {linhas}x{colunas} | repeticao {rep + 1}/{repeticoes}")
                registros = comparar_todos_os_modos(
                    linhas=linhas,
                    colunas=colunas,
                    # Varia a semente a cada repeticao e caso para evitar cache
                    semente=semente + rep + linhas + colunas,
                    servidores=servidores,
                    workers_locais=workers_locais,
                    workers_por_servidor=workers_por_servidor,
                )
                todos_registros.extend(registros)
                for reg in registros:
                    exibir_registro(reg)
    finally:
        # Garante encerramento dos servidores mesmo se ocorrer excecao
        encerrar_servidores(processos)

    return todos_registros


# ---------------------------------------------------------------------------
# Persistencia dos resultados
# ---------------------------------------------------------------------------

def salvar_csv(resultados, caminho="results/resultados.csv"):
    """
    Salva a lista de registros de metricas em arquivo CSV.

    Cria o diretorio pai automaticamente se nao existir.

    Args:
        resultados : lista de dicionarios com as metricas
        caminho    : caminho do arquivo CSV de saida
    """
    saida = Path(caminho)
    saida.parent.mkdir(parents=True, exist_ok=True)

    with saida.open("w", newline="", encoding="utf-8") as arq:
        escritor = csv.DictWriter(arq, fieldnames=list(resultados[0].keys()))
        escritor.writeheader()
        escritor.writerows(resultados)

    print(f"[CSV] Resultados salvos em: {saida}")


def executar_testes_automatizados():
    """
    Executa a suite de testes com pytest e lanca excecao em caso de falha.

    Util para garantir que nenhuma regressao foi introduzida antes de rodar
    os experimentos completos.
    """
    print("\nExecutando suite de testes automatizados...")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
    if proc.returncode != 0:
        raise RuntimeError("Falha na suite de testes. Verifique os erros acima.")


# ---------------------------------------------------------------------------
# Pipeline completa
# ---------------------------------------------------------------------------

def executar_tudo(casos_de_teste, repeticoes, quantidade_servidores, workers_locais, workers_por_servidor, semente, rodar_testes, salvar_resultados, exibir_graficos):
    """
    Ponto de entrada da pipeline completa de experimentos.

    Sequencia de execucao:
        1. (Opcional) Roda pytest para validar o codigo
        2. Executa os experimentos para todos os casos de teste
        3. (Opcional) Salva os resultados em CSV
        4. Gera e exibe os graficos de desempenho

    Args:
        casos_de_teste        : lista de tuplas (linhas, colunas)
        repeticoes            : repeticoes por caso de teste
        quantidade_servidores : numero de servidores TCP simulados
        workers_locais        : processos para o modo paralelo local
        workers_por_servidor  : processos internos de cada servidor
        semente               : semente para reproducibilidade
        rodar_testes          : se True, executa pytest antes dos experimentos
        salvar_resultados     : se True, salva CSV em results/resultados.csv
        exibir_graficos       : se True, abre janela com os graficos ao final

    Returns:
        Lista de todos os registros de metricas coletados.
    """
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