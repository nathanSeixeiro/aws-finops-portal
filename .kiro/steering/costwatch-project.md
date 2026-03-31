# CostWatch — Steering Document

## Visão Geral do Projeto

CostWatch é um dashboard serverless de custos AWS que fornece visibilidade em tempo real e histórica dos gastos AWS para gestores. O sistema usa Python Lambdas, DynamoDB e CDK (Python) para deploy via perfil AWS `gsti-us`.

## Stack Tecnológica

- Python 3.12, Pydantic v2, boto3
- AWS CDK (Python) para infraestrutura
- DynamoDB (2 tabelas: `costwatch-cost-records`, `costwatch-budgets`)
- API Gateway REST com autenticação por API key
- Frontend vanilla JS + Chart.js (sem framework, sem build step)
- Testes com pytest + moto

## Perfil AWS

Sempre usar `--profile gsti-us` para qualquer comando AWS CLI ou CDK.

## Contas AWS

O projeto opera em um ambiente multi-conta. Mapeamento de contas:

| Account ID     | Nome              |
|----------------|-------------------|
| 019361054970   | Backup            |
| 243197391534   | Moodle EAD SESI-SP|
| 282489000805   | Homologation      |
| 365998109386   | Management        |
| 499075731692   | SESISENAI-SP GSTI |
| 566105750844   | Development       |
| 592197479665   | Network           |
| 682120331793   | Innovation Hub    |
| 869697964666   | Security          |
| 941297671692   | Log               |
| 967883358132   | Production        |

## Estrutura do Projeto

```
src/
  handlers/     — Lambda handlers (thin wrappers)
  services/     — Lógica de negócio
  repositories/ — Acesso ao DynamoDB
  models/       — Modelos Pydantic v2
  utils/        — Utilitários (auth, response, dates, aws_client)
cdk/
  stacks/       — 3 CDK stacks (Database, Api, Scheduler)
frontend/       — HTML + CSS + JS (servido localmente)
tests/          — Testes unitários com pytest + moto
```

## Convenções de Código

- Imports dentro de `src/` usam caminhos relativos (sem prefixo `src.`), pois o Lambda empacota `src/` como raiz
- Testes usam `pythonpath = [".", "src"]` no `pyproject.toml`
- Todos os clientes AWS usam injeção de dependência para testabilidade
- Lambda handlers são wrappers finos — toda lógica fica na camada de serviço
- Respostas da API incluem sempre valores em USD e BRL

## Deploy

```bash
make deploy   # Roda: install → lint → unit-testing → synth → deploy
```

Após deploy, atualizar Lambda code manualmente com:
```bash
pip install pydantic requests -t /tmp/lambda-pkg --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 --implementation cp
cp -r src/* /tmp/lambda-pkg/
cd /tmp/lambda-pkg && zip -r /tmp/lambda-pkg.zip . && cd -
# Atualizar cada Lambda com: aws lambda update-function-code --function-name <NAME> --zip-file fileb:///tmp/lambda-pkg.zip --profile gsti-us
```

## Moeda

- Dados são armazenados em USD e BRL simultaneamente
- Taxa de câmbio vem do SSM Parameter Store (`/costwatch/brl-exchange-rate`)
- Fallback rate: 5.05

## Endpoints da API

| Endpoint    | Método | Descrição                          |
|-------------|--------|------------------------------------|
| /summary    | GET    | KPIs: today, MTD, prev month, forecast |
| /services   | GET    | Breakdown por serviço AWS          |
| /trend      | GET    | Tendência de custos por período    |
| /forecast   | GET    | Projeção de custo mensal           |
| /accounts   | GET    | Breakdown por conta AWS            |

Todos requerem header `x-api-key`.

## Frontend

- Servido localmente via live server (porta 5500)
- Tema "Dark Command Center"
- Chart.js para gráficos (CDN)
- Google Fonts: Space Mono + DM Sans
