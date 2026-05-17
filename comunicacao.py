"""Infraestrutura de comunicacao distribuida via sockets TCP."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Process
import json
import socket
import struct
import time
from typing import Any

from operacoes import (
    Bloco,
    Matriz,
    reunir_blocos,
    multiplicar_paralelo,
    multiplicar_serial,
    fatiar_em_blocos,
)


ENDERECO_LOCAL = "127.0.0.1"
MODO_SERIAL = "serial"
MODO_PARALELO = "process-pool"

Endpoint = tuple[str, int]


# ---------------------------------------------------------------------------
# Protocolo de mensagens (length-prefixed JSON sobre TCP)
# ---------------------------------------------------------------------------

def _enviar(sock: socket.socket, dados: dict[str, Any]) -> None:
    """Serializa e envia um dicionario JSON com prefixo de tamanho."""
    payload = json.dumps(dados).encode("utf-8")
    sock.sendall(struct.pack("!Q", len(payload)))
    sock.sendall(payload)


def _receber_exato(sock: socket.socket, tamanho: int) -> bytes:
    """Recebe exatamente `tamanho` bytes do socket."""
    dados = b""
    while len(dados) < tamanho:
        fragmento = sock.recv(tamanho - len(dados))
        if not fragmento:
            raise ConnectionError("Conexao encerrada antes da mensagem estar completa.")
        dados += fragmento
    return dados


def _receber(sock: socket.socket) -> dict[str, Any]:
    """Le e desserializa uma mensagem JSON do socket."""
    tamanho = struct.unpack("!Q", _receber_exato(sock, 8))[0]
    return json.loads(_receber_exato(sock, tamanho).decode("utf-8"))


# ---------------------------------------------------------------------------
# Logica do servidor
# ---------------------------------------------------------------------------

def _executar_tarefa(bloco_a: Matriz, b: Matriz, modo: str, num_workers: int) -> Matriz:
    """Executa a multiplicacao de um bloco conforme o modo solicitado."""
    if modo == MODO_SERIAL:
        return multiplicar_serial(bloco_a, b)
    if modo == MODO_PARALELO:
        return multiplicar_paralelo(bloco_a, b, num_workers)
    raise ValueError(f"Modo de execucao desconhecido: {modo}")


def atender_cliente(conexao: socket.socket, modo_padrao: str, workers_padrao: int) -> None:
    """Processa uma requisicao de multiplicacao recebida pelo servidor."""
    with conexao:
        try:
            tarefa = _receber(conexao)
            modo = tarefa.get("modo", modo_padrao)
            num_workers = int(tarefa.get("num_workers", workers_padrao))

            t_inicio = time.perf_counter()
            bloco_resultado = _executar_tarefa(tarefa["bloco_a"], tarefa["b"], modo, num_workers)
            tempo_calculo = time.perf_counter() - t_inicio

            _enviar(
                conexao,
                {
                    "linha_inicio": tarefa["linha_inicio"],
                    "linha_fim": tarefa["linha_fim"],
                    "bloco_c": bloco_resultado,
                    "tempo_calculo": tempo_calculo,
                },
            )
        except Exception as erro:
            try:
                _enviar(conexao, {"erro": str(erro)})
            except OSError:
                pass


def iniciar_servidor(
    host: str = ENDERECO_LOCAL,
    porta: int = 9001,
    modo: str = MODO_SERIAL,
    num_workers: int = 1,
    max_tarefas: int | None = None,
) -> None:
    """Inicia o servidor TCP e aguarda requisicoes de multiplicacao."""
    atendidos = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((host, porta))
        servidor.listen()
        print(f"[Servidor] Ouvindo em {host}:{porta} | modo={modo} | workers={num_workers}", flush=True)

        while max_tarefas is None or atendidos < max_tarefas:
            conexao, _ = servidor.accept()
            atender_cliente(conexao, modo, num_workers)
            atendidos += 1


# ---------------------------------------------------------------------------
# Utilitarios de rede
# ---------------------------------------------------------------------------

def porta_livre(host: str = ENDERECO_LOCAL) -> int:
    """Encontra uma porta TCP livre no sistema operacional."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def aguardar_servidor(host: str, porta: int, timeout: float = 10.0) -> None:
    """Bloqueia ate o servidor estar pronto para aceitar conexoes."""
    prazo = time.perf_counter() + timeout
    while time.perf_counter() < prazo:
        try:
            with socket.create_connection((host, porta), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Servidor {host}:{porta} nao ficou disponivel no tempo esperado.")


def subir_servidores(
    quantidade: int, num_workers: int, host: str = ENDERECO_LOCAL
) -> tuple[list[Endpoint], list[Process]]:
    """Sobe `quantidade` processos servidores em portas aleatorias."""
    endpoints: list[Endpoint] = []
    processos: list[Process] = []

    for _ in range(quantidade):
        porta = porta_livre(host)
        proc = Process(
            target=iniciar_servidor,
            kwargs={"host": host, "porta": porta, "num_workers": num_workers},
        )
        proc.start()
        endpoints.append((host, porta))
        processos.append(proc)

    for host_ep, porta_ep in endpoints:
        aguardar_servidor(host_ep, porta_ep)

    return endpoints, processos


def encerrar_servidores(processos: list[Process]) -> None:
    """Termina todos os processos servidores de forma ordenada."""
    for proc in processos:
        if proc.is_alive():
            proc.terminate()
    for proc in processos:
        proc.join(timeout=5)


# ---------------------------------------------------------------------------
# Cliente distribuido
# ---------------------------------------------------------------------------

def _enviar_tarefa(endpoint: Endpoint, tarefa: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Envia um bloco para um servidor e aguarda o resultado."""
    host, porta = endpoint
    with socket.create_connection((host, porta), timeout=timeout) as sock:
        sock.settimeout(timeout)
        _enviar(sock, tarefa)
        resposta = _receber(sock)

    if "erro" in resposta:
        raise RuntimeError(f"Erro no servidor {host}:{porta}: {resposta['erro']}")
    return resposta


def multiplicar_distribuido(
    a: Matriz,
    b: Matriz,
    servidores: list[Endpoint],
    modo: str = MODO_SERIAL,
    workers_por_servidor: int = 1,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Distribui a multiplicacao A x B entre os servidores disponiveis."""
    blocos = fatiar_em_blocos(a, len(servidores))
    tarefas = [
        {
            "linha_inicio": inicio,
            "linha_fim": fim,
            "bloco_a": bloco,
            "b": b,
            "modo": modo,
            "num_workers": workers_por_servidor,
        }
        for inicio, fim, bloco in blocos
    ]

    t_inicio = time.perf_counter()
    respostas: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(tarefas)) as executor:
        futuros = [
            executor.submit(_enviar_tarefa, endpoint, tarefa, timeout)
            for endpoint, tarefa in zip(servidores, tarefas)
        ]
        for futuro in as_completed(futuros):
            respostas.append(futuro.result())

    tempo_total = time.perf_counter() - t_inicio
    blocos_resultado: list[Bloco] = [
        (r["linha_inicio"], r["linha_fim"], r["bloco_c"]) for r in respostas
    ]
    tempos_calculo = [r["tempo_calculo"] for r in respostas]

    return {
        "matriz": reunir_blocos(blocos_resultado),
        "tempo_total": tempo_total,
        "tempo_calculo_max": max(tempos_calculo, default=0.0),
        "tempo_calculo_soma": sum(tempos_calculo),
        "overhead": max(0.0, tempo_total - max(tempos_calculo, default=0.0)),
    }
