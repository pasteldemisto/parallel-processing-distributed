"""
main.py
-------

Configure os parametros abaixo conforme necessario e execute:
    python main.py

O script ira:
    1. Subir os processos servidores TCP na maquina local
    2. Executar os 4 modos de multiplicacao para cada caso de teste
    3. Salvar os resultados em results/resultados.csv
    4. Gerar os graficos de desempenho em results/plots/
"""

from avaliacao import executar_tudo


# ---------------------------------------------------------------------------
# Casos de teste: 10 dimensoes MxN de matrizes retangulares
#
# Cada tupla representa (linhas, colunas) da matriz A.
# A matriz B e gerada como (colunas x colunas) para garantir multiplicacao valida.
# Resultado C = A x B tem dimensao (linhas x colunas).
#
# Caso  |  A (MxN)    |  B (NxN)
# ------+-------------+----------
#   1   |   50 x 100  | 100 x 100
#   2   |  200 x 100  | 100 x 100
#   3   |  250 x 500  | 500 x 500
#   4   |  500 x 300  | 300 x 300
#   5   | 1000 x 1200 | 1200 x 1200
#   6   | 1350 x 1350 | 1350 x 1350
#   7   | 1500 x 1400 | 1400 x 1400
#   8   | 1450 x 1600 | 1600 x 1600
#   9   | 2000 x 3000 | 3000 x 3000
#  10   | 3000 x 2100 | 2100 x 2100
# ---------------------------------------------------------------------------
CASOS_DE_TESTE = [
    (50,   100),   # Caso 1  - matriz pequena, poucos elementos
    (200,  100),   # Caso 2  - mais linhas, mesma coluna
    (250,   500),   # Caso 3  - poucas linhas, coluna grande
    (500,  300),   # Caso 4  - muitas linhas, coluna media
    (1000, 1200),   # Caso 5  - alto numero de linhas
    (1350,  1350),   # Caso 6  - dimensoes medianas equilibradas
    (1500,  1400)   # Caso 7  - coluna maior que linhas
    # (1450,  1600),   # Caso 8  - matriz de porte elevado
    # (2000,   3000),   # Caso 9  - muitas linhas, coluna pequena
    # (3000, 2100),   # Caso 10 - maior caso de teste
]

# Numero de vezes que cada caso e repetido (os tempos sao medios das repeticoes)
REPETICOES = 2

# Semente base para reproducibilidade dos dados aleatorios entre execucoes
SEMENTE = 42

# Quantidade de processos servidores TCP simulados na maquina local
QUANTIDADE_SERVIDORES = 2

# Numero de processos paralelos usados no modo "Paralelo local"
WORKERS_LOCAIS = 4

# Numero de processos paralelos dentro de cada servidor (modo "Distribuido hibrido")
WORKERS_POR_SERVIDOR = 4

# Se True, executa pytest antes dos experimentos para verificar corretude do codigo
RODAR_TESTES = False

# Se True, salva todos os resultados em results/resultados.csv ao final
SALVAR_RESULTADOS = True

# Se True, abre a janela interativa com os graficos ao final da execucao
EXIBIR_GRAFICOS = True


if __name__ == "__main__":
    qtd_servidores = input("Digite a quantidade de servidores: ")
    linhas = input("Digite a quantidade de linhas: ")
    colunas = input("Digite a quantidade de colunas: ")

    executar_tudo(
        casos_de_teste=CASOS_DE_TESTE,
        repeticoes=REPETICOES,
        quantidade_servidores=QUANTIDADE_SERVIDORES,
        workers_locais=WORKERS_LOCAIS,
        workers_por_servidor=WORKERS_POR_SERVIDOR,
        semente=SEMENTE,
        rodar_testes=RODAR_TESTES,
        salvar_resultados=SALVAR_RESULTADOS,
        exibir_graficos=EXIBIR_GRAFICOS,
    )