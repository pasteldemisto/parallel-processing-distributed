"""
Ponto de entrada do experimento de Multiplicacao de Matrizes Distribuida.

Configure os parametros abaixo e execute:
    python executar.py
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
#   3   |   50 x 500  | 500 x 500
#   4   |  500 x 100  | 100 x 100
#   5   | 1000 x 100  | 100 x 100
#   6   |  500 x 200  | 200 x 200
#   7   |  100 x 300  | 300 x 300
#   8   |  300 x 600  | 600 x 600
#   9   |  800 x  80  |  80 x  80
#  10   | 1000 x 250  | 250 x 250
# ---------------------------------------------------------------------------
CASOS_DE_TESTE: list[tuple[int, int]] = [
    (50,   100),   # Caso 1
    (200,  100),   # Caso 2
    (50,   500),   # Caso 3
    (500,  100),   # Caso 4
    (1000, 100),   # Caso 5
    (500,  200),   # Caso 6
    (100,  300),   # Caso 7
    (300,  600),   # Caso 8
    (800,   80),   # Caso 9
    (1000, 250),   # Caso 10
]

# Numero de repeticoes por caso de teste (para media dos tempos)
REPETICOES: int = 2

# Semente para reproducibilidade dos dados aleatorios
SEMENTE: int = 42

# Infraestrutura distribuida
QUANTIDADE_SERVIDORES: int = 2
WORKERS_LOCAIS: int = 4           # processos para o modo paralelo local
WORKERS_POR_SERVIDOR: int = 4     # processos em cada no servidor (modo hibrido)

# Controle de execucao
RODAR_TESTES: bool = False        # True para rodar pytest antes dos experimentos
SALVAR_RESULTADOS: bool = True    # salva CSV em results/resultados.csv
EXIBIR_GRAFICOS: bool = True      # abre janela com os graficos ao final


if __name__ == "__main__":
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
