"""
avaliacao.py
------------
Conducao dos experimentos e coleta de metricas de desempenho.

Responsabilidades:
    - Cronometrar cada modo de execucao (serial, paralelo, distribuido, hibrido)
    - Calcular speedup e eficiencia em relacao ao modo serial
    - Validar corretude dos resultados contra o serial
    - Orquestrar o loop de experimentos (casos de teste x repeticoes)
    - Salvar metricas de desempenho em CSV (results/resultados.csv)
    - Salvar as matrizes A, B e C em CSV (results/matrizes/)
    - Modo batch  : executa os casos de teste pre-definidos em main.py
    - Modo interativo: o usuario informa dimensoes, numero de servidores
                       e quantidade de processos em tempo de execucao
"""

import csv
import os
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
        funcao : callable sem argumentos

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

    speedup    = tempo_serial / tempo
    eficiencia = speedup / servidores  (quao bem os recursos sao aproveitados)

    Args:
        rotulo       : nome legivel do modo (ex: "Paralelo local")
        modo         : identificador interno (ex: "paralelo")
        caso         : rotulo do caso (ex: "500x200")
        tempo        : tempo medido em segundos
        tempo_serial : tempo do modo serial (baseline)
        valido       : True se o resultado confere com o serial
        servidores   : numero de servidores usados
        workers      : numero de processos usados

    Returns:
        Dicionario com todas as metricas.
    """
    speedup = tempo_serial / tempo if tempo > 0 else 0.0
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
# Salvamento das matrizes em CSV
# ---------------------------------------------------------------------------

def salvar_matriz_csv(matriz, caminho):
    """
    Salva uma matriz como CSV (uma linha da matriz por linha do arquivo).

    Args:
        matriz  : lista de listas com os valores
        caminho : caminho do arquivo CSV de saida
    """
    saida = Path(caminho)
    saida.parent.mkdir(parents=True, exist_ok=True)

    with saida.open("w", newline="", encoding="utf-8") as arq:
        escritor = csv.writer(arq)
        escritor.writerows(matriz)

    print(f"  [Matriz CSV] {saida}")


def salvar_matrizes_execucao(a, b, c, rotulo_caso, identificador, diretorio="results/matrizes"):
    """
    Salva as matrizes A, B e C de uma execucao em arquivos CSV separados.

    Nome dos arquivos: {rotulo_caso}_{identificador}_A.csv  (e _B.csv, _C.csv)
    Exemplo: 300x600_rep2_A.csv

    Args:
        a            : matriz A (entrada)
        b            : matriz B (entrada)
        c            : matriz C (resultado = A x B)
        rotulo_caso  : identificador do caso (ex: "300x600")
        identificador: sufixo para diferenciar execucoes (ex: "rep1", "custom_1")
        diretorio    : pasta raiz onde os CSVs serao salvos
    """
    prefixo = f"{rotulo_caso}_{identificador}"
    salvar_matriz_csv(a, os.path.join(diretorio, f"{prefixo}_A.csv"))
    salvar_matriz_csv(b, os.path.join(diretorio, f"{prefixo}_B.csv"))
    salvar_matriz_csv(c, os.path.join(diretorio, f"{prefixo}_C.csv"))


# ---------------------------------------------------------------------------
# Nucleo do experimento: compara os 4 modos para um caso de teste
# ---------------------------------------------------------------------------

def comparar_todos_os_modos(linhas, colunas, semente, servidores, workers_locais, workers_por_servidor, rotulo_identificador, salvar_matrizes=True):
    """
    Executa e compara os 4 modos de multiplicacao para (linhas, colunas).

    Modos:
        1. Serial              - baseline, loop puro Python
        2. Paralelo local      - ProcessPoolExecutor na mesma maquina
        3. Distribuido serial  - sockets TCP, servidores multiplicam serialmente
        4. Distribuido hibrido - sockets TCP + ProcessPoolExecutor em cada servidor

    A = linhas x colunas | B = colunas x colunas | C = linhas x colunas

    Args:
        linhas                : linhas de A
        colunas               : colunas de A (= linhas de B)
        semente               : semente para geracao das matrizes
        servidores            : lista de (host, porta) dos servidores ativos
        workers_locais        : processos para o modo paralelo local
        workers_por_servidor  : processos internos de cada servidor (modo hibrido)
        rotulo_identificador  : sufixo usado no nome dos arquivos CSV das matrizes
        salvar_matrizes       : se True, salva A, B e C em CSV

    Returns:
        Lista de 4 dicionarios de metricas.
    """
    rotulo_caso = f"{linhas}x{colunas}"

    # Matrizes geradas com sementes diferentes para A e B
    a = gerar_matriz(linhas, colunas, semente)
    b = gerar_matriz(colunas, colunas, semente + 1)

    # --- Modo 1: Serial (baseline) ---
    resultado_serial, tempo_serial = cronometrar(lambda: multiplicar_serial(a, b))
    registros = [
        montar_registro("Serial", "serial", rotulo_caso, tempo_serial, tempo_serial, True)
    ]

    # Salva A, B e C (resultado serial) como referencia permanente
    if salvar_matrizes:
        print(f"\n  Salvando matrizes ({rotulo_caso})...")
        salvar_matrizes_execucao(a, b, resultado_serial, rotulo_caso, rotulo_identificador)

    # --- Modo 2: Paralelo local ---
    resultado_paralelo, tempo_paralelo = cronometrar(
        lambda: multiplicar_paralelo(a, b, workers_locais)
    )
    registros.append(
        montar_registro(
            "Paralelo local", "paralelo", rotulo_caso,
            tempo_paralelo, tempo_serial,
            matrizes_iguais(resultado_serial, resultado_paralelo),  # corretude
            workers=workers_locais,
        )
    )

    # --- Modo 3: Distribuido serial ---
    dist_serial = multiplicar_distribuido(
        a, b, servidores, modo=MODO_SERIAL, workers_por_servidor=1
    )
    registros.append(
        montar_registro(
            "Distribuido serial", "distribuido", rotulo_caso,
            dist_serial["tempo_total"], tempo_serial,
            matrizes_iguais(resultado_serial, dist_serial["matriz"]),
            servidores=len(servidores), workers=1,
        )
    )

    # --- Modo 4: Distribuido hibrido (sockets + processos em cada no) ---
    dist_hibrido = multiplicar_distribuido(
        a, b, servidores, modo=MODO_PARALELO, workers_por_servidor=workers_por_servidor
    )
    registros.append(
        montar_registro(
            "Distribuido hibrido", "hibrido", rotulo_caso,
            dist_hibrido["tempo_total"], tempo_serial,
            matrizes_iguais(resultado_serial, dist_hibrido["matriz"]),
            servidores=len(servidores), workers=workers_por_servidor,
        )
    )

    return registros


# ---------------------------------------------------------------------------
# Leitura validada de input do usuario
# ---------------------------------------------------------------------------

def ler_inteiro(mensagem, minimo=1):
    """
    Le e valida um inteiro >= minimo do input do usuario.

    Continua pedindo ate receber um valor valido.

    Args:
        mensagem : texto exibido antes do input
        minimo   : valor minimo aceito (padrao 1)

    Returns:
        Inteiro valido informado pelo usuario.
    """
    while True:
        try:
            valor = int(input(mensagem).strip())
            if valor < minimo:
                print(f"  O valor deve ser >= {minimo}. Tente novamente.")
                continue
            return valor
        except ValueError:
            print("  Entrada invalida. Digite um numero inteiro.")


# ---------------------------------------------------------------------------
# Modo batch: casos de teste pre-definidos
# ---------------------------------------------------------------------------

def executar_experimentos(casos_de_teste, repeticoes, quantidade_servidores, workers_locais, workers_por_servidor, semente, salvar_matrizes=True):
    """
    Itera pelos casos de teste pre-definidos executando os 4 modos.

    Sobe os servidores antes do loop e os encerra ao final (mesmo em erro).

    Args:
        casos_de_teste        : lista de tuplas (linhas, colunas)
        repeticoes            : repeticoes por caso (para media dos tempos)
        quantidade_servidores : servidores TCP a subir
        workers_locais        : processos para o modo paralelo local
        workers_por_servidor  : processos internos por servidor
        semente               : semente base para geracao das matrizes
        salvar_matrizes       : se True, salva A, B e C em CSV

    Returns:
        Lista de todos os registros de metricas.
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
                    # Varia a semente por repeticao e caso para evitar resultados identicos
                    semente=semente + rep + linhas + colunas,
                    servidores=servidores,
                    workers_locais=workers_locais,
                    workers_por_servidor=workers_por_servidor,
                    rotulo_identificador=f"rep{rep + 1}",
                    salvar_matrizes=salvar_matrizes,
                )
                todos_registros.extend(registros)
                for reg in registros:
                    exibir_registro(reg)
    finally:
        encerrar_servidores(processos)

    return todos_registros


# ---------------------------------------------------------------------------
# Modo interativo: usuario define tudo em tempo real
# ---------------------------------------------------------------------------

def executar_modo_interativo(semente, salvar_matrizes=True):
    """
    Modo interativo: o usuario informa dimensoes e configuracoes via input.

    Em cada rodada o usuario escolhe:
        - Linhas de A (M)
        - Colunas de A / Linhas de B (N)
        - Numero de servidores (usados nos modos distribuido e hibrido)
        - Workers locais (modo paralelo local)
        - Workers por servidor (modo hibrido)

    Os servidores sao reiniciados a cada rodada para refletir a configuracao
    escolhida. O usuario pode fazer quantas rodadas quiser.

    Args:
        semente         : semente base para geracao das matrizes
        salvar_matrizes : se True, salva A, B e C em CSV apos cada rodada

    Returns:
        Lista de todos os registros de metricas coletados na sessao.
    """
    print("\n" + "=" * 62)
    print("   MODO INTERATIVO - Multiplicacao de Matrizes Distribuida")
    print("=" * 62)
    print("   Configure as dimensoes e os recursos a cada rodada.\n")

    todos_registros = []
    rodada = 1

    while True:
        print(f"\n--- Rodada #{rodada} ---")

        # Dimensoes
        linhas  = ler_inteiro("  Linhas de A (M)                  : ")
        colunas = ler_inteiro("  Colunas de A / Linhas de B (N)   : ")

        # Configuracao de infraestrutura
        qtd_servidores      = ler_inteiro("  Numero de servidores             : ")
        workers_locais      = ler_inteiro("  Workers para paralelismo local   : ")
        workers_por_servidor = ler_inteiro("  Workers por servidor (hibrido)   : ")

        print(
            f"\n  Configuracao: A={linhas}x{colunas} | B={colunas}x{colunas} | "
            f"{qtd_servidores} serv. | {workers_locais} workers locais | "
            f"{workers_por_servidor} workers/servidor"
        )
        print("  Subindo servidores...")

        # Sobe servidores com a configuracao desta rodada
        servidores, processos = subir_servidores(qtd_servidores, workers_por_servidor)

        try:
            registros = comparar_todos_os_modos(
                linhas=linhas,
                colunas=colunas,
                semente=semente + rodada + linhas + colunas,
                servidores=servidores,
                workers_locais=workers_locais,
                workers_por_servidor=workers_por_servidor,
                rotulo_identificador=f"custom_{rodada}",
                salvar_matrizes=salvar_matrizes,
            )
        finally:
            # Encerra os servidores desta rodada antes de continuar
            encerrar_servidores(processos)

        todos_registros.extend(registros)
        print()
        for reg in registros:
            exibir_registro(reg)

        rodada += 1

        print("\n  Deseja fazer outra multiplicacao? (s/n): ", end="", flush=True)
        if input().strip().lower() != "s":
            break

    return todos_registros


# ---------------------------------------------------------------------------
# Persistencia das metricas
# ---------------------------------------------------------------------------

def salvar_csv(resultados, caminho="results/resultados.csv"):
    """
    Salva os registros de metricas em arquivo CSV.

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

    print(f"[CSV] Metricas salvas em: {saida}")


def executar_testes_automatizados():
    """Roda pytest e lanca excecao se algum teste falhar."""
    print("\nExecutando testes automatizados...")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
    if proc.returncode != 0:
        raise RuntimeError("Falha nos testes. Verifique os erros acima.")


# ---------------------------------------------------------------------------
# Pipeline completa
# ---------------------------------------------------------------------------

def executar_tudo(casos_de_teste, repeticoes, quantidade_servidores, workers_locais, workers_por_servidor, semente, rodar_testes, salvar_resultados, exibir_graficos, modo_interativo=False, salvar_matrizes=True):
    """
    Ponto de entrada da pipeline completa de experimentos.

    Suporta dois modos:
        Batch      (modo_interativo=False): executa os casos pre-definidos
        Interativo (modo_interativo=True) : usuario configura tudo via input

    Sequencia:
        1. (Opcional) Roda pytest
        2. Executa os experimentos (batch ou interativo)
        3. (Opcional) Salva metricas em CSV
        4. Gera graficos de desempenho

    Args:
        casos_de_teste        : lista de (linhas, colunas) — modo batch
        repeticoes            : repeticoes por caso — modo batch
        quantidade_servidores : servidores para o modo batch
        workers_locais        : workers locais para o modo batch
        workers_por_servidor  : workers por servidor para o modo batch
        semente               : semente para reproducibilidade
        rodar_testes          : se True, executa pytest antes
        salvar_resultados     : se True, salva metricas em CSV
        exibir_graficos       : se True, abre janela com graficos
        modo_interativo       : se True, usa input do usuario
        salvar_matrizes       : se True, salva A, B e C em CSV

    Returns:
        Lista de todos os registros de metricas.
    """
    if rodar_testes:
        executar_testes_automatizados()

    if modo_interativo:
        resultados = executar_modo_interativo(
            semente=semente,
            salvar_matrizes=salvar_matrizes,
        )
    else:
        resultados = executar_experimentos(
            casos_de_teste=casos_de_teste,
            repeticoes=repeticoes,
            quantidade_servidores=quantidade_servidores,
            workers_locais=workers_locais,
            workers_por_servidor=workers_por_servidor,
            semente=semente,
            salvar_matrizes=salvar_matrizes,
        )

    if not resultados:
        print("\nNenhum resultado coletado.")
        return resultados

    if salvar_resultados:
        salvar_csv(resultados)

    plotar_resultados(resultados, exibir=exibir_graficos)
    return resultados