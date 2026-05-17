"""Geracao de graficos de desempenho com matplotlib."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt


def _rotulo_modo(registro: dict) -> str:
    """Gera o rotulo legivel para cada modo de execucao."""
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


def _media_por_caso_e_modo(resultados: list[dict]) -> list[dict]:
    """Agrupa os registros por caso de teste e modo, retornando medias."""
    grupos = defaultdict(list)
    for reg in resultados:
        chave = (reg["caso"], _rotulo_modo(reg))
        grupos[chave].append(reg)

    agregados = []
    for (caso, rotulo), regs in sorted(grupos.items()):
        agregados.append(
            {
                "caso": caso,
                "rotulo": rotulo,
                "tempo": mean(r["tempo"] for r in regs),
                "speedup": mean(r["speedup"] for r in regs),
                "eficiencia": mean(r["eficiencia"] for r in regs),
            }
        )
    return agregados


def plotar_resultados(
    resultados: list[dict],
    diretorio_saida: str = "results/plots",
    exibir: bool = True,
) -> None:
    """Gera e salva os graficos de tempo, speedup e eficiencia."""
    agregados = _media_por_caso_e_modo(resultados)
    pasta_saida = Path(diretorio_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    metricas = [
        ("tempo", "Tempo medio (s)", "Tempo Medio de Execucao por Caso de Teste", "tempo_execucao.png"),
        ("speedup", "Speedup medio", "Speedup Medio por Caso de Teste", "speedup.png"),
        ("eficiencia", "Eficiencia media", "Eficiencia Media por Caso de Teste", "eficiencia.png"),
    ]

    for metrica, rotulo_y, titulo, nome_arquivo in metricas:
        fig, ax = plt.subplots(figsize=(13, 6))
        rotulos_unicos = sorted({reg["rotulo"] for reg in agregados})
        casos_unicos = sorted({reg["caso"] for reg in agregados})

        for rotulo in rotulos_unicos:
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
