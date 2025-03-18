# 🔍 FinOps Anomaly Report

Este projeto tem como objetivo analisar os custos da Azure por grupo ou tag, detectando anomalias e gerando alertas para altos custos. Ele permite segmentar os custos por diferentes dimensões e fornece a opção de salvar os resultados em um arquivo.

## 🚀 Funcionalidades

- 📊 **Análise de custos**: Permite análise baseada em agrupamento ou tags.
- 🔔 **Modo de alerta**: Detecta variações anômalas nos custos e emite alertas.
- 📅 **Período configurável**: Defina a data de início e o número de dias para a análise.
- 💾 **Exportação de dados**: Opção para salvar os resultados em um arquivo Excel.
- 🔐 **Autenticação automática**: Obtém tokens de acesso para interagir com a API da Azure.

## 📦 Estrutura do Projeto

```
.
├── anomalyReport.py      # Script principal para análise de custos
├── utils.py              # Funções auxiliares para requisições, logging e manipulação de dados
├── requirements.txt      # Dependências do projeto
└── README.md             # Documentação do projeto
```

## 🛠️ Instalação e Uso

### 1️⃣ Pré-requisitos
- Python 3.8+
- CLI da Azure instalada e configurada (`az login`)
- Dependências do projeto (instaladas via `pip`)

### 2️⃣ Instalação das Dependências
```bash
pip install -r requirements.txt
```

### 3️⃣ Execução do Script
```bash
python anomalyReport.py <subscription_prefix> <analysis_type> <grouping_key> [--alert] [--save] [--date YYYY-MM-DD] [--period N]
```

**Exemplos:**
- Analisar custos agrupados por serviço nos últimos 30 dias:
  ```bash
  python anomalyReport.py "MinhaSub" group ServiceName --period 30
  ```
- Analisar custos por tag de projeto com alertas ativados:
  ```bash
  python anomalyReport.py "MinhaSub" tag Projeto --alert
  ```
- Analisar custos por grupo e salvar o resultado em um arquivo:
  ```bash
  python anomalyReport.py "MinhaSub" group Departamento --save
  ```

## 📌 Parâmetros

| Parâmetro           | Descrição |
|---------------------|-----------|
| `subscription_prefix` | Prefixo da assinatura a ser analisada |
| `analysis_type`     | Tipo de análise: `group` ou `tag` |
| `grouping_key`      | Chave de agrupamento (Ex: `ServiceName`, `Projeto`) |
| `--alert`          | (Opcional) Ativa o modo alerta para variações de custo |
| `--save`           | (Opcional) Salva os resultados em um arquivo Excel |
| `--date YYYY-MM-DD` | (Opcional) Data de início para a análise |
| `--period N`       | (Opcional) Número de dias para análise (padrão: 31) |

## ⚡ Exemplo de Saída

```
+----------------+--------------+-------------------+-------+
| Service Name   | Average Cost | Analysis Date Cost | Alert |
+----------------+--------------+-------------------+-------+
| VM1           | 250.00       | 300.00            | Yes   |
| Storage       | 120.00       | 110.00            | No    |
+----------------+--------------+-------------------+-------+
```

## 📝 Notas

- O script utiliza a CLI da Azure para buscar dados de assinaturas.
- Há um delay entre as requisições para evitar `Too Many Requests`.
- O alerta é gerado quando o custo do dia analisado ultrapassa 10% da média.

---

