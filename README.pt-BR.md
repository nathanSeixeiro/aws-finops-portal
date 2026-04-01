# CostWatch — Dashboard de Custos AWS

Dashboard serverless que dá visibilidade em tempo real dos gastos AWS em múltiplas contas. Construído com Python Lambdas, DynamoDB, API Gateway e CDK.

![Dashboard](https://img.shields.io/badge/stack-serverless-green) ![Python](https://img.shields.io/badge/python-3.12-blue) ![CDK](https://img.shields.io/badge/aws--cdk-v2-orange)

## Como Funciona

```
EventBridge (cron) → Lambda de Ingestão → Cost Explorer API → DynamoDB
                                                                 ↓
                                                       Snapshot do Dashboard
                                                                 ↓
                        Frontend (browser) → API Gateway → Lambda Dashboard → DynamoDB (GetItem)
```

Os dados de custo são buscados da API do AWS Cost Explorer por agendamento, convertidos para BRL e armazenados no DynamoDB. Um snapshot pré-computado do dashboard é gerado após cada ingestão, então o frontend carrega instantaneamente com uma única chamada de API.

## Estrutura do Projeto

```
src/
  handlers/
    ingest_costs.py              # Lambda: busca custos do Cost Explorer, salva no DynamoDB
    get_dashboard.py             # Lambda: retorna snapshot pré-computado (um único GetItem)
  services/
    cost_ingestion_service.py    # Lógica de busca no Cost Explorer + escrita no DynamoDB
    dashboard_snapshot_service.py # Pré-computa todos os dados do dashboard em um item DynamoDB
    currency_service.py          # Conversão USD→BRL via SSM Parameter Store
  repositories/
    cost_record_repository.py    # Queries DynamoDB para registros de custo
  models/
    cost_record.py               # Modelo Pydantic v2 para registros de custo
    budget.py                    # Modelo Pydantic v2 para orçamentos
  utils/
    auth.py                      # Validação de API key
    aws_client.py                # Factory de clientes boto3 com injeção de dependência
    date_utils.py                # Helpers de cálculo de datas/períodos
    response.py                  # Builder de resposta do API Gateway
cdk/
  app.py                         # Entry point do CDK
  stacks/
    database_stack.py            # Tabelas DynamoDB + GSIs
    api_stack.py                 # API Gateway + funções Lambda
    scheduler_stack.py           # Regras cron do EventBridge
frontend/
  index.html                     # Interface do dashboard
  app.js                         # Uma chamada /dashboard, renderiza tudo no client-side
  styles.css                     # Tema escuro ("Command Center")
tests/                           # Testes unitários com pytest + moto
```

## Pré-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (gerenciador de pacotes Python)
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html) (`npm install -g aws-cdk`)
- AWS CLI configurado com um perfil nomeado
- Uma conta AWS com Cost Explorer habilitado

## Configuração

### 1. Clone e instale as dependências

```bash
git clone <repo-url> && cd costwatch
make install
```

### 2. Configure seu perfil AWS

O Makefile usa `--profile gsti-us` por padrão. Para usar seu próprio perfil, atualize o nome no `Makefile`:

```bash
sed -i '' 's/gsti-us/seu-perfil/g' Makefile
```

### 3. Defina a taxa de câmbio BRL (opcional)

```bash
aws ssm put-parameter \
  --name "/costwatch/brl-exchange-rate" \
  --value "5.34" \
  --type String \
  --profile seu-perfil
```

Se não definido, usa o fallback de 5.05.

### 4. Bootstrap do CDK (apenas na primeira vez)

```bash
make bootstrap
```

### 5. Deploy

```bash
make deploy
```

Executa: install → lint → test → synth → deploy. Três stacks CloudFormation são criadas:

| Stack | Recursos |
|-------|----------|
| CostWatchDatabaseStack | Tabelas DynamoDB (cost-records, budgets) + GSIs |
| CostWatchApiStack | API Gateway, 2 Lambdas (ingestão + dashboard), roles IAM |
| CostWatchSchedulerStack | Regras EventBridge (diário 2h, semanal seg 3h, mensal dia 1 4h UTC) |

### 6. Carregar dados históricos

Após o primeiro deploy, não há dados ainda. Faça o backfill:

```bash
# Dados mensais (últimos 12 meses)
aws lambda invoke \
  --function-name <nome-da-IngestCostsFunction> \
  --payload '{"detail":{"granularity":"MONTHLY","backfill_months":12}}' \
  --cli-binary-format raw-in-base64-out \
  --profile seu-perfil \
  /tmp/monthly.json

# Dados diários (5 dias por batch — repita com números maiores)
aws lambda invoke \
  --function-name <nome-da-IngestCostsFunction> \
  --payload '{"detail":{"granularity":"DAILY","backfill_days":5}}' \
  --cli-binary-format raw-in-base64-out \
  --profile seu-perfil \
  /tmp/daily.json
```

O nome da função está no output do CDK deploy ou no console do AWS Lambda.

Após o backfill inicial, o EventBridge atualiza tudo automaticamente:
- **Diário** às 2h UTC — ingere os custos do dia anterior
- **Semanal** às segundas 3h UTC — ingere a semana anterior
- **Mensal** no dia 1 às 4h UTC — ingere o mês anterior

### 7. Atualize o config do frontend

Após o deploy, atualize `frontend/app.js` com a URL do API Gateway e a API key:

```javascript
const CONFIG = {
  apiBase: "https://<seu-api-id>.execute-api.<regiao>.amazonaws.com/prod",
  apiKey: "<sua-api-key>",
};
```

A URL da API está no output do CDK deploy. O valor da API key está definido em `cdk/stacks/api_stack.py`.

### 8. Abra o frontend

Sirva a pasta `frontend/` localmente com qualquer servidor estático:

```bash
# Usando Python
python3 -m http.server 5500 -d frontend

# Ou VS Code Live Server na porta 5500
```

## Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `make install` | Instala dependências Python |
| `make lint` | Executa o linter ruff |
| `make format` | Auto-formata código com ruff |
| `make unit-testing` | Executa pytest com cobertura |
| `make synth` | Sintetiza templates CloudFormation |
| `make diff` | Visualiza mudanças de infraestrutura |
| `make deploy` | Pipeline completo: install → lint → test → synth → deploy |
| `make destroy` | Remove todas as stacks e recursos da AWS |
| `make bootstrap` | Bootstrap do CDK na sua conta AWS (apenas primeira vez) |

## Detalhes da Arquitetura

### Fluxo de Dados

1. **EventBridge** dispara a Lambda de Ingestão por agendamento (diário/semanal/mensal)
2. **Lambda de Ingestão** chama a API do AWS Cost Explorer, converte USD→BRL, grava registros no DynamoDB
3. Após a ingestão, **pré-computa um snapshot do dashboard** (KPIs, tendências, breakdown por serviço, breakdown por conta, heatmap) e armazena como um único item no DynamoDB
4. **Lambda Dashboard** lê esse item na requisição — sem computação, apenas um GetItem
5. **Frontend** faz uma chamada `GET /dashboard` e renderiza tudo no client-side

### Schema do DynamoDB

**Tabela: costwatch-cost-records**
- PK: `ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}`
- SK: `SERVICE#{service_name}`
- GSI `gsi-gran-period`: granularity (PK) + period (SK) — usado para range queries
- GSI `gsi-service-period`: service_name (PK) + period (SK)
- GSI `gsi-account-gran`: account_id (PK) + account_gran_sk (SK)
- Snapshot do dashboard: PK=`SNAPSHOT#DASHBOARD`, SK=`LATEST`

### API

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/dashboard` | GET | Retorna o snapshot completo pré-computado do dashboard |

Requer header `x-api-key`.

## Personalização

### Trocar Perfil AWS

Atualize `gsti-us` no `Makefile` para o nome do seu perfil AWS CLI.

### Trocar Taxa de Câmbio

```bash
aws ssm put-parameter --name "/costwatch/brl-exchange-rate" --value "5.50" --type String --overwrite --profile seu-perfil
```

Depois re-ingira os dados para aplicar a nova taxa a todos os registros.

### Trocar API Key

Atualize o `api_key_value` em `cdk/stacks/api_stack.py` e faça redeploy. Depois atualize `frontend/app.js` para combinar.

### Adicionar Origens CORS

Atualize a lista `allow_origins` em `cdk/stacks/api_stack.py` se servir o frontend de uma origem diferente.
