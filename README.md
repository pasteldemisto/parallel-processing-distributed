# Multiplicação de Matrizes Distribuída

Projeto desenvolvido para a disciplina de **Computação Paralela e Concorrente** (AV3 – 2026.1).  
O objetivo é comparar quatro estratégias de multiplicação de matrizes retangulares, variando entre execução serial, paralelismo local com múltiplos processos e computação distribuída simulada via sockets TCP.

---

## Estrutura do Projeto

```
PARALLEL-PROCESSING-DISTRI.../
├── main.py            # Ponto de entrada + configuração dos parâmetros
├── operacoes.py       # Geração de matrizes, multiplicação serial e paralela
├── comunicacao.py     # Servidores TCP, protocolo de mensagens, cliente distribuído
├── avaliacao.py       # Orquestração dos experimentos e coleta de métricas
├── graficos.py        # Geração de gráficos com matplotlib
├── requirements.txt   # Dependências Python
└── results/
    ├── resultados.csv         # Resultados completos em CSV (gerado ao executar)
    └── plots/
        ├── tempo_execucao.png # Tempo médio por caso de teste
        ├── speedup.png        # Speedup por caso de teste
        └── eficiencia.png     # Eficiência por caso de teste
```

---

## Modos de Execução Comparados

| Modo                    | Descrição                                                                          |
|-------------------------|------------------------------------------------------------------------------------|
| **Serial**              | Multiplicação linha × coluna em loop puro Python, sem paralelismo                  |
| **Paralelo local**      | Divide as linhas de A em blocos e distribui entre processos com `ProcessPoolExecutor` |
| **Distribuído serial**  | Envia blocos via socket TCP para servidores que multiplicam serialmente             |
| **Distribuído híbrido** | Cada servidor usa `ProcessPoolExecutor` internamente (distribuído + paralelo)       |

---

## Casos de Teste

São utilizados **10 casos de teste** com matrizes retangulares **MxN**. Para cada caso, a matriz **A** tem dimensão **M×N** e a matriz **B** tem dimensão **N×N**, garantindo que a multiplicação `A × B` seja válida e produzindo um resultado de dimensão **M×N**.

| Caso | Matriz A (M×N) | Matriz B (N×N) | Resultado C (M×N) |
|:----:|:--------------:|:--------------:|:-----------------:|
|  1   |   50 × 100     |  100 × 100     |    50 × 100       |
|  2   |  200 × 100     |  100 × 100     |   200 × 100       |
|  3   |   50 × 500     |  500 × 500     |    50 × 500       |
|  4   |  500 × 100     |  100 × 100     |   500 × 100       |
|  5   | 1000 × 100     |  100 × 100     |  1000 × 100       |
|  6   |  500 × 200     |  200 × 200     |   500 × 200       |
|  7   |  100 × 300     |  300 × 300     |   100 × 300       |
|  8   |  300 × 600     |  600 × 600     |   300 × 600       |
|  9   |  800 ×  80     |   80 ×  80     |   800 ×  80       |
| 10   | 1000 × 250     |  250 × 250     |  1000 × 250       |

---

## Como Executar

### 1. Criar ambiente virtual e instalar dependências

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# ou: venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 2. Configurar os parâmetros (opcional)

Edite o topo de `main.py` conforme necessário:

```python
CASOS_DE_TESTE = [...]       # lista de (linhas, colunas) da matriz A
REPETICOES = 2               # repetições por caso (para média dos tempos)
QUANTIDADE_SERVIDORES = 2    # nós servidores simulados
WORKERS_LOCAIS = 4           # processos para o modo paralelo local
WORKERS_POR_SERVIDOR = 4     # processos em cada servidor (modo híbrido)
RODAR_TESTES = False         # True para executar pytest antes
SALVAR_RESULTADOS = True     # salva CSV em results/resultados.csv
EXIBIR_GRAFICOS = True       # abre janela com gráficos ao final
```

### 3. Rodar

```bash
python main.py
```

---

## Saídas Geradas

Após a execução, os seguintes arquivos são criados automaticamente:

```
results/
├── resultados.csv           # Tabela completa com tempo, speedup e eficiência por caso
└── plots/
    ├── tempo_execucao.png   # Tempo médio (s) por caso de teste e modo
    ├── speedup.png          # Speedup em relação ao serial
    └── eficiencia.png       # Eficiência (speedup / número de servidores)
```

---

## Métricas Coletadas

Para cada combinação de *caso de teste × modo × repetição*, são registradas:

| Métrica      | Descrição                                                        |
|--------------|------------------------------------------------------------------|
| `tempo`      | Tempo de parede (wall time) da operação completa                 |
| `speedup`    | `tempo_serial / tempo` — ganho relativo ao modo serial           |
| `eficiencia` | `speedup / nº_servidores` — quão bem os recursos são usados      |
| `valido`     | Verifica se o resultado é idêntico ao serial (corretude)         |

---

## Arquitetura da Computação Distribuída

```
┌──────────────────────────────────────────────────────────┐
│                        main.py                           │
│              (divide A em blocos de linhas)              │
└─────────────────────┬────────────────────────────────────┘
                      │  ThreadPoolExecutor (cliente)
           ┌──────────┴──────────┐
           ▼                     ▼
   ┌──────────────┐      ┌──────────────┐
   │  Servidor 1  │      │  Servidor 2  │   (processos separados)
   │  TCP :porta1 │      │  TCP :porta2 │
   │              │      │              │
   │ recebe bloco │      │ recebe bloco │
   │  multiplica  │      │  multiplica  │
   │  devolve C_i │      │  devolve C_j │
   └──────────────┘      └──────────────┘
           │                     │
           └──────────┬──────────┘
                      ▼
          reunir_blocos() → matriz C final
```

A comunicação usa um protocolo simples: cada mensagem é precedida de 8 bytes (big-endian) com o tamanho do payload JSON.

---

## Conceitos Abordados

- **Computação Distribuída**: simulação de múltiplos nós de processamento via sockets TCP
- **Paralelismo**: divisão do trabalho em blocos de linhas processados concorrentemente
- **Metodologia de Foster (PCAM)**: particionamento → comunicação → aglomeração → mapeamento aplicado à multiplicação de matrizes
- **Speedup e Lei de Amdahl**: análise do ganho de desempenho em função do grau de paralelismo
- **Validação de corretude**: todos os resultados paralelos/distribuídos são comparados com o resultado serial

---

## Dependências

| Pacote       | Uso                                      |
|--------------|------------------------------------------|
| `matplotlib` | Geração dos gráficos de desempenho       |
| `pytest`     | Suite de testes automatizados (opcional) |

> Bibliotecas padrão utilizadas: `socket`, `struct`, `json`, `multiprocessing`, `concurrent.futures`, `csv`, `random`, `time`