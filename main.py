"""
main.py
-------
Ponto de entrada do experimento de Multiplicacao de Matrizes Distribuida.

Modos de operacao (controlado pela variavel MODO_INTERATIVO):
    False -> Modo batch: executa os 10 casos de teste pre-definidos
             usando as configuracoes fixadas abaixo.
    True  -> Modo interativo: a cada rodada o usuario informa via input:
               - Dimensoes da matriz (M x N)
               - Numero de servidores
               - Workers para paralelismo local
               - Workers por servidor (modo hibrido)

Execute com:
    python main.py
"""

from avaliacao import executar_tudo


# ===========================================================================
# MODO DE OPERACAO
# ===========================================================================

# False = modo batch (usa os casos pre-definidos abaixo)
# True  = modo interativo (usuario informa tudo via input)
MODO_INTERATIVO = True


# ===========================================================================
# CASOS DE TESTE PRE-DEFINIDOS (usados apenas no modo batch)
#
# Cada tupla: (linhas, colunas) da matriz A.
# Matriz B gerada como (colunas x colunas) para multiplicacao valida.
# Resultado C = A x B com dimensao (linhas x colunas).
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
# ===========================================================================
CASOS_DE_TESTE = [
    (50,   100),   # Caso 1  - matriz pequena
    (200,  100),   # Caso 2  - mais linhas, coluna media
    (50,   500),   # Caso 3  - poucas linhas, coluna grande
    (500,  100),   # Caso 4  - muitas linhas, coluna media
    (1000, 100),   # Caso 5  - alto numero de linhas
    (500,  200),   # Caso 6  - dimensoes equilibradas
    (100,  300),   # Caso 7  - coluna maior que linhas
    (300,  600),   # Caso 8  - matriz de porte elevado
    (800,   80),   # Caso 9  - muitas linhas, coluna pequena
    (1000, 250),   # Caso 10 - maior caso de teste
]

# ===========================================================================
# CONFIGURACOES DO MODO BATCH
# ===========================================================================

# Repeticoes por caso de teste (os tempos sao medias das repeticoes)
REPETICOES = 2

# Semente para reproducibilidade dos dados aleatorios
SEMENTE = 42

# Numero de processos servidores TCP simulados
QUANTIDADE_SERVIDORES = 2

# Processos paralelos no modo "Paralelo local"
WORKERS_LOCAIS = 4

# Processos internos de cada servidor no modo "Distribuido hibrido"
WORKERS_POR_SERVIDOR = 4

# ===========================================================================
# CONTROLE DE SAIDA
# ===========================================================================

# True = executa pytest antes dos experimentos
RODAR_TESTES = False

# True = salva metricas de desempenho em results/resultados.csv
SALVAR_RESULTADOS = True

# True = salva as matrizes A, B e C em CSV em results/matrizes/
SALVAR_MATRIZES = True

# True = abre janela interativa com os graficos ao final
EXIBIR_GRAFICOS = True


# ===========================================================================
# EXECUCAO
# ===========================================================================

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
        modo_interativo=MODO_INTERATIVO,
        salvar_matrizes=SALVAR_MATRIZES,
    )