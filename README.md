# Multiplicação de Matrizes Distribuída

Projeto desenvolvido para a disciplina de **Computação Paralela e Concorrente** (AV3 – 2026.1).

O objetivo é comparar quatro estratégias de multiplicação de matrizes retangulares, variando entre execução serial, paralelismo local com múltiplos processos e computação distribuída simulada via sockets TCP.

---

## Estrutura do Projeto

```
PARALLEL-PROCESSING-DISTRI.../
├── main.py            # Ponto de entrada + parâmetros de configuração
├── operacoes.py       # Geração de matrizes, multiplicação serial e paralela
├── comunicacao.py     # Servidores TCP, protocolo de mensagens, cliente distribuído
├── avaliacao.py       # Orquestração dos experimentos e coleta de métricas
├── graficos.py        # Geração de gráficos com matplotlib
├── requirements.txt   # Dependências Python
└── results/
    ├── resultados.csv         # Métricas de desempenho (gerado ao executar)
    ├── matrizes/
    │   ├── 300x600_rep1_A.csv # Matriz A do caso 300x600, repetição 1
    │   ├── 300x600_rep1_B.csv # Matriz B
    │   └── 300x600_rep1_C.csv # Resultado C = A x B
    └── plots/
        ├── tempo_execucao.png
        ├── speedup.png
        └── eficiencia.png
```

---

## Modos de Operação

O projeto possui dois modos, controlados pela variável `MODO_INTERATIVO` em `main.py`:

### Modo Batch (`MODO_INTERATIVO = False`)
Executa automaticamente os 10 casos de teste pré-definidos com as configurações fixadas no topo de `main.py`. Ideal para rodar todos os experimentos de uma vez e gerar os gráficos.

### Modo Interativo (`MODO_INTERATIVO = True`)
A cada rodada o usuário informa via terminal:
- Dimensões da matriz A (M × N)
- Número de servidores
- Quantidade de workers para paralelismo local
- Quantidade de workers por servidor (modo híbrido)

Permite testar qualquer combinação de tamanho e configuração sem editar código.

**Exemplo de sessão interativa:**
```
--- Rodada #1 ---
  Linhas de A (M)                  : 400
  Colunas de A / Linhas de B (N)   : 300
  Numero de servidores             : 3
  Workers para paralelismo local   : 6
  Workers por servidor (hibrido)   : 4

  Configuracao: A=400x300 | B=300x300 | 3 serv. | 6 workers locais | 4 workers/servidor
```

---

## Modos de Multiplicação Comparados

| Modo                    | Descrição                                                                          |
|-------------------------|------------------------------------------------------------------------------------|
| **Serial**              | Loop Python puro, sem paralelismo — baseline para cálculo de speedup               |
| **Paralelo local**      | Divide as linhas de A entre processos usando `ProcessPoolExecutor`                 |
| **Distribuído serial**  | Envia blocos via socket TCP para servidores que multiplicam serialmente            |
| **Distribuído híbrido** | Cada servidor usa `ProcessPoolExecutor` internamente (distribuído + paralelo)      |

---

## Casos de Teste Pré-definidos

São 10 casos com matrizes retangulares. A matriz **A** tem dimensão **M×N**, a matriz **B** tem dimensão **N×N** (garante multiplicação válida), e o resultado **C = A×B** tem dimensão **M×N**.

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

### 2. Configurar `main.py`

```python
# Escolha o modo de operacao:
MODO_INTERATIVO = False   # False = batch | True = interativo

# Configuracoes do modo batch:
REPETICOES = 2
QUANTIDADE_SERVIDORES = 2
WORKERS_LOCAIS = 4
WORKERS_POR_SERVIDOR = 4

# Saidas:
SALVAR_RESULTADOS = True  # salva results/resultados.csv
SALVAR_MATRIZES   = True  # salva A, B e C em results/matrizes/
EXIBIR_GRAFICOS   = True  # abre janela com graficos ao final
```

### 3. Executar

```bash
python main.py
```

---

## Arquivos Gerados

```
results/
├── resultados.csv              # Métricas de todos os experimentos
├── matrizes/
│   ├── {caso}_{id}_A.csv       # Matriz A de cada execução
│   ├── {caso}_{id}_B.csv       # Matriz B de cada execução
│   └── {caso}_{id}_C.csv       # Resultado C = A x B
└── plots/
    ├── tempo_execucao.png      # Tempo médio (s) por caso e modo
    ├── speedup.png             # Speedup em relação ao serial
    └── eficiencia.png          # Eficiência (speedup / nº servidores)
```

**Nomenclatura dos CSVs de matrizes:**
- Modo batch: `{linhas}x{colunas}_rep{N}_A.csv` — ex: `300x600_rep1_A.csv`
- Modo interativo: `{linhas}x{colunas}_custom_{N}_A.csv` — ex: `400x300_custom_1_A.csv`

---

## Métricas Coletadas

| Métrica      | Descrição                                                        |
|--------------|------------------------------------------------------------------|
| `tempo`      | Tempo de parede (wall time) da operação completa                 |
| `speedup`    | `tempo_serial / tempo` — ganho relativo ao modo serial           |
| `eficiencia` | `speedup / nº_servidores` — aproveitamento dos recursos          |
| `valido`     | Resultado idêntico ao serial? (corretude)                        |

---

## Arquitetura da Computação Distribuída

```
┌──────────────────────────────────────────────────────────┐
│                        main.py                           │
│           (divide A em blocos de linhas)                 │
└─────────────────────┬────────────────────────────────────┘
                      │  ThreadPoolExecutor (envia em paralelo)
           ┌──────────┴──────────┐
           ▼                     ▼
   ┌──────────────┐      ┌──────────────┐
   │  Servidor 1  │      │  Servidor N  │   (processos separados)
   │  TCP :porta1 │      │  TCP :portaN │
   │              │      │              │
   │ recebe bloco │      │ recebe bloco │
   │  multiplica  │      │  multiplica  │
   │  devolve C_i │      │  devolve C_j │
   └──────────────┘      └──────────────┘
           │                     │
           └──────────┬──────────┘
                      ▼
          reunir_blocos() → C final
```

Protocolo: cada mensagem é precedida de 8 bytes (big-endian) com o tamanho do payload JSON.

---

## Conceitos Abordados

- **Computação Distribuída** — simulação de múltiplos nós de processamento via sockets TCP
- **Paralelismo** — divisão do trabalho em blocos de linhas processados concorrentemente
- **Metodologia de Foster (PCAM)** — particionamento → comunicação → aglomeração → mapeamento
- **Speedup e Lei de Amdahl** — o ganho real aparece nas matrizes maiores; matrizes pequenas são dominadas pelo overhead de comunicação
- **Validação de corretude** — todos os resultados são comparados com o serial

---

## Dependências

| Pacote       | Uso                                      |
|--------------|------------------------------------------|
| `matplotlib` | Geração dos gráficos de desempenho       |
| `pytest`     | Suite de testes automatizados (opcional) |

> Bibliotecas padrão: `socket`, `struct`, `json`, `multiprocessing`, `concurrent.futures`, `csv`, `random`, `time`