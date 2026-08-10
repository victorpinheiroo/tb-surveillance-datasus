# Vigilância de Tuberculose no Brasil — SINAN × SIM × IBGE

Pipeline de engenharia de dados de ponta a ponta sobre dados públicos de saúde do Brasil, construído como prova técnica para vagas internacionais de Data Engineering — não como estudo epidemiológico.

**[→ Dashboard interativo](https://victorpinheiroo.github.io/tb-surveillance-datasus/)**

## Por que este projeto existe

A maioria dos portfólios de engenharia de dados usa datasets de tutorial (Titanic, Iris) — dado limpo, sem ambiguidade, sem decisão real a tomar. Este projeto usa o oposto deliberadamente: dados reais de vigilância epidemiológica brasileira, com toda a sujeira, inconsistência e subnotificação que isso implica.

O foco é **engenharia**: ingestão, tratamento de dado inconsistente entre fontes, qualidade e governança. Não há modelagem preditiva ou Ciência de Dados aqui — decisão deliberada, para não reivindicar competência que ainda não foi construída formalmente. A camada analítica final usa apenas estatística descritiva.

## O que o pipeline responde

1. **Incidência de tuberculose** por 100 mil habitantes, por município/UF/ano (SINAN-TB × população IBGE).
2. **Taxa de abandono de tratamento**, por UF/ano — indicador clínico sério, associado a agravamento e resistência bacteriana.
3. **Subnotificação estimada**, cruzando óbitos por TB notificados no SINAN contra óbitos por TB registrados no SIM — duas fontes independentes do mesmo evento.

## Arquitetura

Medallion (bronze / silver / gold), com decisões documentadas em [ADRs](docs/adrs/):

```
Fontes (PySUS, API SIDRA/IBGE)
        ↓
    BRONZE   — cópia fiel da fonte, imutável, com metadado de proveniência
        ↓
    SILVER   — tipado, deduplicado, decodificado, com dimensão SCD2 de município
        ↓
    GOLD     — agregados: incidência, abandono, reconciliação SINAN×SIM
        ↓
  GitHub Pages (dashboard, DuckDB-WASM lendo Parquet direto do repositório)
```

Orquestração via GitHub Actions (mensal + manual), infraestrutura 100% gratuita — sem cartão de crédito cadastrado em nenhum serviço usado continuamente (ver [ADR-001](docs/adrs/ADR-001-scope-source-infrastructure.md)).

## Fontes de dados

| Fonte | Conteúdo | Janela | Acesso |
|---|---|---|---|
| SINAN-TB | Notificações de tuberculose | 2015–2024 | PySUS |
| SIM | Óbitos (filtrado para CID-10 A15-A19) | 2015–2024, 251/270 combinações UF×ano | PySUS |
| IBGE/SIDRA | População residente por município | 2015–2024 | API SIDRA |

## Decisões de engenharia — não é volume, é julgamento

Cinco ADRs documentam decisões com contexto, alternativas consideradas e trade-offs — não só "o que foi feito", mas por quê e o que foi descartado:

- **[ADR-001](docs/adrs/ADR-001-scope-source-infrastructure.md)** — escolha de fonte, right-censoring validado empiricamente (dado de 2024 ainda em consolidação), cobertura irregular do SIM (7% de gaps, sem padrão único), SCD2 mantida por design mesmo sem uso observado na janela atual.
- **[ADR-002](docs/adrs/ADR-002-case-identity-deduplication.md)** — o SINAN-TB não tem identificador único de caso; decisão deliberada de não construir uma chave sintética (colisão de quase-identificador testada e rejeitada por gerar falsos positivos em municípios grandes).
- **[ADR-003](docs/adrs/ADR-003-population-source-ibge.md)** — 2022/2023 sem tabela de estimativa populacional disponível; solução replica a lógica que o próprio IBGE usou publicamente (Censo 2022 como proxy), não uma interpolação inventada.
- **[ADR-004](docs/adrs/ADR-004-orchestration.md)** — orquestração com janela de anos fixa (não estende automaticamente), porque todo ano novo investigado neste projeto trouxe uma particularidade que só apareceu com investigação humana.
- **[ADR-005](docs/adrs/ADR-005-azure-demonstration-scope.md)** — a arquitetura de referência Azure é só código, nunca implantada; um caso documentado de cobrança inesperada do Microsoft Purview durante um PoC de pequena escala tornou até uma única janela curta de "subir, capturar evidência, derrubar" um risco inaceitável frente à restrição de custo zero do projeto.

## Achados de qualidade de dado

O que diferencia este projeto de um dashboard de tutorial:

- **Bug de metadado no catálogo remoto do PySUS**: `TUBEBR16.parquet` existia mas retornava vazio — causa raiz identificada (`group_id` nulo excluindo o arquivo de queries filtradas), documentado em [`docs/known-issues.md`](docs/known-issues.md).
- **Três fontes, três convenções diferentes para "valor ausente"**: SINAN-TB usa `"0"`, IBGE/SIDRA usa `"..."`, SIM usa `UF+0000` — mesma ideia semântica, sintaxes incompatíveis, cada uma identificada e tratada explicitamente.
- **Hipótese testada e parcialmente refutada, documentada como tal**: uma tentativa de explicar 4 casos anômalos na reconciliação SINAN×SIM por atraso de maturidade do SIM não se sustentou nos dados — reportado como está, não forçado para caber numa narrativa limpa.
- **Dicionário de dados oficial (`SITUA_ENCE`) confirmado por leitura direta de PDF do Ministério da Saúde**, depois de duas fontes secundárias divergirem entre si sobre a ordem correta das categorias.

Ver [`docs/known-issues.md`](docs/known-issues.md) para a lista completa.

## Stack

Python 3.13 · pandas/pyarrow · PySUS · sidrapy (API SIDRA) · Parquet (zstd) · GitHub Actions · DuckDB-WASM · Azure (Bicep, demonstração pontual — ver `infra/`)

## Como rodar

```bash
pip install -r requirements.txt
python pipeline/run_pipeline.py --stage all      # bronze -> silver -> gold completo
python pipeline/run_pipeline.py --stage bronze   # só ingestão
```

## Estrutura

```
ingestion/               # extração bronze (SINAN-TB, SIM, IBGE)
transformation/
  bronze_to_silver/      # limpeza, deduplicação, SCD2
  silver_to_gold/        # agregados analíticos
pipeline/                # orquestrador
docs/adrs/                    # Architecture Decision Records
docs/known-issues.md          # achados de qualidade de dado
docs/schema-reference-*.md    # schema real documentado por fonte
quality/logs/             # log estruturado de cada execução
infra/                    # IaC Azure (demonstração pontual)
```

## Limitações conhecidas

- Identidade de caso é por evento de notificação, não por paciente único (ver ADR-002).
- 7% das combinações UF×ano do SIM não têm dado disponível na fonte (não preenchido por fonte alternativa — ver ADR-001).
- Taxa de abandono em nível de município é estatisticamente instável para ~90% dos municípios (amostra pequena); visão de UF é a recomendada.
- 4 casos residuais na reconciliação SINAN×SIM permanecem sem explicação completa.
- `requirements.txt` não fixa versões exatas (só `pysus>=2.0`) — uma lacuna de reprodutibilidade. Se uma versão futura do PySUS mudar o comportamento do metadado do catálogo (como já aconteceu uma vez, ver `docs/known-issues.md`), o pipeline pode funcionar hoje e quebrar silenciosamente pra quem clonar o repo depois. Ainda não fixado; vale fazer via `pip freeze` contra o ambiente validado.
- Não há suite de testes automatizados (ex.: `pytest`). Os logs de qualidade validam o *dado* a cada execução, mas a lógica central — decodificação de `SITUA_ENCE`, regex do sentinela `XX0000`, parser de data — não tem teste unitário. Uma lacuna real pra um projeto de nível sênior, deixada honesta aqui em vez de implícita como coberta.

---

Victor Pinheiro — [linkedin.com/in/victorpinheiroo](https://linkedin.com/in/victorpinheiroo) · [github.com/victorpinheiroo](https://github.com/victorpinheiroo)

---

*[English version](README.md)*
