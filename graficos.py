"""
graficos.py
-----------
Geracao de graficos de desempenho com matplotlib.

Responsabilidades:
    - Agregar resultados por caso de teste e modo (media entre repeticoes)
    - Gerar graficos de tempo medio, speedup e eficiencia
    - Salvar os graficos em PNG no diretorio results/plots/
"""

from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Utilitarios de rotulagem e agregacao
# ---------------------------------------------------------------------------

def _rotulo_modo(registro):
    """
    Gera o rotulo legivel para exibicao nas legendas dos graficos.

    Args:
        registro : dicionario com as metricas do experimento

    Returns:
        String formatada com o nome do modo e suas configuracoes.
    """
    modo = registro["modo"]
    if modo == "serial":
        return "Serial"
    if modo == "paralelo":
        return f"Paralelo local ({registro['workers']} proc.)"
    if modo == "distribuido":
        return f"Distribuido serial ({registro['servidores']} serv.)"
    if modo == "hibrido":
        return f"Distribuido hibrido ({registro['servidores']} serv. x {registro['workers']} proc.)"
    return modo


def _media_por_caso_e_modo(resultados):
    """
    Agrupa os registros por caso de teste e modo, calculando a media das metricas.

    Como cada caso e executado multiplas vezes (repeticoes), esta funcao
    consolida os valores em um unico ponto por (caso, modo) para os graficos.

    Args:
        resultados : lista de dicionarios com todas as metricas coletadas

    Returns:
        Lista de dicionarios agregados com medias de tempo, speedup e eficiencia.
    """
    grupos = defaultdict(list)
    for reg in resultados:
        chave = (reg["caso"], _rotulo_modo(reg))
        grupos[chave].append(reg)

    agregados = []
    for (caso, rotulo), regs in sorted(grupos.items()):
        agregados.append(
            {
                "caso":       caso,
                "rotulo":     rotulo,
                "tempo":      mean(r["tempo"] for r in regs),
                "speedup":    mean(r["speedup"] for r in regs),
                "eficiencia": mean(r["eficiencia"] for r in regs),
            }
        )
    return agregados


# ---------------------------------------------------------------------------
# Geracao e salvamento dos graficos
# ---------------------------------------------------------------------------

def plotar_resultados(resultados, diretorio_saida="results/plots", exibir=True):
    """
    Gera e salva os tres graficos de desempenho dos experimentos.

    Graficos gerados:
        - tempo_execucao.png : tempo medio de execucao por caso de teste
        - speedup.png        : speedup medio em relacao ao modo serial
        - eficiencia.png     : eficiencia media (speedup / numero de servidores)

    O eixo X usa os rotulos dos casos de teste (ex: "500x200") e cada linha
    do grafico representa um modo de execucao diferente.

    Args:
        resultados       : lista de dicionarios com as metricas coletadas
        diretorio_saida  : pasta onde os arquivos PNG serao salvos
        exibir           : se True, abre a janela interativa do matplotlib
    """
    agregados = _media_por_caso_e_modo(resultados)
    pasta_saida = Path(diretorio_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # Define as tres metricas a plotar com seus titulos e nomes de arquivo
    metricas = [
        ("tempo",      "Tempo medio (s)",  "Tempo Medio de Execucao por Caso de Teste", "tempo_execucao.png"),
        ("speedup",    "Speedup medio",     "Speedup Medio por Caso de Teste",           "speedup.png"),
        ("eficiencia", "Eficiencia media",  "Eficiencia Media por Caso de Teste",        "eficiencia.png"),
    ]

    # Ordem fixa dos casos no eixo X para manter consistencia entre graficos
    casos_unicos = sorted({reg["caso"] for reg in agregados})

    for metrica, rotulo_y, titulo, nome_arquivo in metricas:
        fig, ax = plt.subplots(figsize=(13, 6))
        rotulos_unicos = sorted({reg["rotulo"] for reg in agregados})

        for rotulo in rotulos_unicos:
            # Filtra e ordena os pontos deste modo na ordem dos casos do eixo X
            pontos = [reg for reg in agregados if reg["rotulo"] == rotulo]
            pontos_ord = sorted(pontos, key=lambda r: casos_unicos.index(r["caso"]))
            x = list(range(len(pontos_ord)))
            y = [p[metrica] for p in pontos_ord]
            ax.plot(x, y, marker="o", linewidth=2, markersize=6, label=rotulo)

        ax.set_title(titulo, fontsize=13)
        ax.set_xlabel("Caso de Teste (MxN)", fontsize=11)
        ax.set_ylabel(rotulo_y, fontsize=11)
        ax.set_xticks(range(len(casos_unicos)))
        ax.set_xticklabels(casos_unicos, rotation=30, ha="right", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)
        fig.tight_layout()
        fig.savefig(pasta_saida / nome_arquivo, dpi=150)
        print(f"[Grafico] Salvo: {pasta_saida / nome_arquivo}")

    if exibir:
        plt.show()
    else:
        plt.close("all")