"""
comunicacao.py
--------------
Infraestrutura de comunicacao distribuida via sockets TCP.

Responsabilidades:
    - Protocolo de mensagens length-prefixed JSON sobre TCP
    - Servidor: recebe blocos de linhas, multiplica e devolve resultado
    - Utilitarios de rede: portas livres, aguardar servidor estar pronto
    - Gerenciamento de servidores: subir e encerrar processos
    - Cliente: envia blocos em paralelo e reune respostas

Fluxo de comunicacao:
    cliente -> divide A em blocos -> envia cada bloco a um servidor via TCP
    servidor -> recebe bloco -> multiplica (serial ou paralelo) -> devolve C_i
    cliente -> recebe todos C_i -> reune em C final
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Process
import json
import socket
import struct
import time

from operacoes import reunir_blocos, multiplicar_paralelo, multiplicar_serial, fatiar_em_blocos


# Endereco de loopback usado pelos servidores simulados
ENDERECO_LOCAL = "127.0.0.1"

# Modos de execucao usados no protocolo de mensagens
MODO_SERIAL = "serial"
MODO_PARALELO = "process-pool"


# ---------------------------------------------------------------------------
# Protocolo de mensagens (length-prefixed JSON sobre TCP)
# ---------------------------------------------------------------------------

def _enviar(sock, dados):
    """
    Serializa um dicionario para JSON e envia com prefixo de 8 bytes (tamanho).

    O prefixo permite ao receptor saber exatamente quantos bytes ler.

    Args:
        sock  : socket TCP conectado
        dados : dicionario a enviar
    """
    payload = json.dumps(dados).encode("utf-8")
    sock.sendall(struct.pack("!Q", len(payload)))  # 8 bytes big-endian
    sock.sendall(payload)


def _receber_exato(sock, tamanho):
    """
    Le exatamente `tamanho` bytes do socket, reagrupando fragmentos TCP.

    Args:
        sock    : socket TCP conectado
        tamanho : numero exato de bytes a ler

    Returns:
        Bytes lidos.
    """
    dados = b""
    while len(dados) < tamanho:
        fragmento = sock.recv(tamanho - len(dados))
        if not fragmento:
            raise ConnectionError("Conexao encerrada antes da mensagem estar completa.")
        dados += fragmento
    return dados


def _receber(sock):
    """
    Le e desserializa uma mensagem JSON do socket.

    Le os 8 bytes de prefixo para saber o tamanho, depois le o payload.

    Args:
        sock : socket TCP conectado

    Returns:
        Dicionario com o conteudo da mensagem.
    """
    tamanho = struct.unpack("!Q", _receber_exato(sock, 8))[0]
    return json.loads(_receber_exato(sock, tamanho).decode("utf-8"))


# ---------------------------------------------------------------------------
# Logica do servidor
# ---------------------------------------------------------------------------

def _executar_tarefa(bloco_a, b, modo, num_workers):
    """
    Executa a multiplicacao de um bloco conforme o modo solicitado.

    Args:
        bloco_a    : sub-matriz de linhas de A
        b          : matriz B completa
        modo       : MODO_SERIAL ou MODO_PARALELO
        num_workers: processos paralelos (usado apenas no modo paralelo)

    Returns:
        Bloco resultado da multiplicacao bloco_a x B.
    """
    if modo == MODO_SERIAL:
        return multiplicar_serial(bloco_a, b)
    if modo == MODO_PARALELO:
        return multiplicar_paralelo(bloco_a, b, num_workers)
    raise ValueError(f"Modo de execucao desconhecido: {modo}")


def atender_cliente(conexao, modo_padrao, workers_padrao):
    """
    Processa uma requisicao de multiplicacao recebida pelo servidor.

    Recebe a tarefa, executa a multiplicacao, cronometra o calculo
    e devolve o resultado ao cliente. Em caso de erro, notifica o cliente.

    Args:
        conexao       : socket da conexao aceita
        modo_padrao   : modo de execucao caso o cliente nao especifique
        workers_padrao: workers caso o cliente nao especifique
    """
    with conexao:
        try:
            tarefa = _receber(conexao)
            modo = tarefa.get("modo", modo_padrao)
            num_workers = int(tarefa.get("num_workers", workers_padrao))

            # Cronometra apenas o calculo, excluindo comunicacao
            t_inicio = time.perf_counter()
            bloco_resultado = _executar_tarefa(tarefa["bloco_a"], tarefa["b"], modo, num_workers)
            tempo_calculo = time.perf_counter() - t_inicio

            _enviar(
                conexao,
                {
                    "linha_inicio":  tarefa["linha_inicio"],
                    "linha_fim":     tarefa["linha_fim"],
                    "bloco_c":       bloco_resultado,
                    "tempo_calculo": tempo_calculo,
                },
            )
        except Exception as erro:
            try:
                _enviar(conexao, {"erro": str(erro)})
            except OSError:
                pass


def iniciar_servidor(host=ENDERECO_LOCAL, porta=9001, modo=MODO_SERIAL, num_workers=1, max_tarefas=None):
    """
    Inicia o servidor TCP e aceita requisicoes de multiplicacao em loop.

    Cada conexao e atendida sequencialmente; o paralelismo entre servidores
    e gerenciado pelo cliente via ThreadPoolExecutor.

    Args:
        host        : endereco IP de escuta
        porta       : porta TCP
        modo        : modo de execucao padrao
        num_workers : workers internos (modo hibrido)
        max_tarefas : limite de tarefas antes de encerrar (None = sem limite)
    """
    atendidos = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((host, porta))
        servidor.listen()
        print(f"[Servidor] {host}:{porta} | modo={modo} | workers={num_workers}", flush=True)

        while max_tarefas is None or atendidos < max_tarefas:
            conexao, _ = servidor.accept()
            atender_cliente(conexao, modo, num_workers)
            atendidos += 1


# ---------------------------------------------------------------------------
# Utilitarios de rede
# ---------------------------------------------------------------------------

def porta_livre(host=ENDERECO_LOCAL):
    """
    Solicita ao SO uma porta TCP disponivel e retorna seu numero.

    Args:
        host : endereco IP para buscar a porta

    Returns:
        Numero de porta livre.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def aguardar_servidor(host, porta, timeout=10.0):
    """
    Bloqueia ate o servidor estar pronto para aceitar conexoes.

    Args:
        host    : endereco IP do servidor
        porta   : porta TCP
        timeout : tempo maximo de espera em segundos

    Raises:
        TimeoutError : se o servidor nao responder a tempo.
    """
    prazo = time.perf_counter() + timeout
    while time.perf_counter() < prazo:
        try:
            with socket.create_connection((host, porta), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Servidor {host}:{porta} nao ficou disponivel no tempo esperado.")


# ---------------------------------------------------------------------------
# Gerenciamento dos processos servidores
# ---------------------------------------------------------------------------

def subir_servidores(quantidade, num_workers, host=ENDERECO_LOCAL):
    """
    Sobe `quantidade` processos servidores em portas aleatorias.

    Cada servidor roda em um processo separado, simulando nos independentes.

    Args:
        quantidade  : numero de servidores a iniciar
        num_workers : workers internos de cada servidor (modo hibrido)
        host        : endereco IP dos servidores

    Returns:
        Tupla (endpoints, processos):
            endpoints : lista de (host, porta)
            processos : lista de objetos Process
    """
    endpoints = []
    processos = []

    for _ in range(quantidade):
        porta = porta_livre(host)
        proc = Process(
            target=iniciar_servidor,
            kwargs={"host": host, "porta": porta, "num_workers": num_workers},
        )
        proc.start()
        endpoints.append((host, porta))
        processos.append(proc)

    # Aguarda todos prontos antes de retornar
    for host_ep, porta_ep in endpoints:
        aguardar_servidor(host_ep, porta_ep)

    return endpoints, processos


def encerrar_servidores(processos):
    """
    Encerra todos os processos servidores ordenadamente.

    Args:
        processos : lista de objetos Process a encerrar
    """
    for proc in processos:
        if proc.is_alive():
            proc.terminate()
    for proc in processos:
        proc.join(timeout=5)


# ---------------------------------------------------------------------------
# Cliente distribuido
# ---------------------------------------------------------------------------

def _enviar_tarefa(endpoint, tarefa, timeout):
    """
    Envia um bloco para um servidor e aguarda o resultado.

    Args:
        endpoint : tupla (host, porta) do servidor
        tarefa   : dicionario com bloco_a, b, modo e num_workers
        timeout  : tempo maximo de espera em segundos

    Returns:
        Dicionario com linha_inicio, linha_fim, bloco_c e tempo_calculo.
    """
    host, porta = endpoint
    with socket.create_connection((host, porta), timeout=timeout) as sock:
        sock.settimeout(timeout)
        _enviar(sock, tarefa)
        resposta = _receber(sock)

    if "erro" in resposta:
        raise RuntimeError(f"Erro no servidor {host}:{porta}: {resposta['erro']}")
    return resposta


def multiplicar_distribuido(a, b, servidores, modo=MODO_SERIAL, workers_por_servidor=1, timeout=120.0):
    """
    Distribui A x B entre os servidores disponiveis.

    Divide A em blocos (um por servidor), envia em paralelo via ThreadPoolExecutor
    e reune os resultados em C.

    Args:
        a                   : matriz A com dimensao M x N
        b                   : matriz B com dimensao N x P
        servidores          : lista de (host, porta)
        modo                : MODO_SERIAL ou MODO_PARALELO nos servidores
        workers_por_servidor: processos internos por servidor (modo hibrido)
        timeout             : timeout de comunicacao em segundos

    Returns:
        Dicionario com:
            matriz            : resultado C (M x P)
            tempo_total       : wall time total (comunicacao + calculo)
            tempo_calculo_max : maior tempo de calculo entre os servidores
            tempo_calculo_soma: soma dos tempos de calculo
            overhead          : custo de comunicacao (tempo_total - tempo_calculo_max)
    """
    blocos = fatiar_em_blocos(a, len(servidores))
    tarefas = [
        {
            "linha_inicio": inicio,
            "linha_fim":    fim,
            "bloco_a":      bloco,
            "b":            b,
            "modo":         modo,
            "num_workers":  workers_por_servidor,
        }
        for inicio, fim, bloco in blocos
    ]

    t_inicio = time.perf_counter()
    respostas = []

    # Envia todas as tarefas em paralelo e coleta conforme chegam
    with ThreadPoolExecutor(max_workers=len(tarefas)) as executor:
        futuros = [
            executor.submit(_enviar_tarefa, endpoint, tarefa, timeout)
            for endpoint, tarefa in zip(servidores, tarefas)
        ]
        for futuro in as_completed(futuros):
            respostas.append(futuro.result())

    tempo_total = time.perf_counter() - t_inicio

    # Reconstroi os blocos na ordem correta de linhas
    blocos_resultado = [
        (r["linha_inicio"], r["linha_fim"], r["bloco_c"]) for r in respostas
    ]
    tempos_calculo = [r["tempo_calculo"] for r in respostas]

    return {
        "matriz":             reunir_blocos(blocos_resultado),
        "tempo_total":        tempo_total,
        "tempo_calculo_max":  max(tempos_calculo, default=0.0),
        "tempo_calculo_soma": sum(tempos_calculo),
        # Overhead = tempo gasto em rede, excluindo o calculo puro
        "overhead":           max(0.0, tempo_total - max(tempos_calculo, default=0.0)),
    }