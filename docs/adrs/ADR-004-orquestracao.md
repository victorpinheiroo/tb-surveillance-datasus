---
artifact: adr
version: "1.0"
created: 2026-08-03
status: draft
---

# ADR-004: Orquestração do pipeline (GitHub Actions)

## Status

Accepted

**Date:** 2026-08-03
**Deciders:** Victor Pinheiro

## Context

O pipeline (11 scripts, 3 estágios: bronze/silver/gold) até aqui foi executado manualmente, script por script, com validação humana em cada etapa — deliberado, dado que cada fonte e cada ano trouxe particularidades que exigiram investigação (bug de metadado do PySUS em 2016, colunas legadas de 2015, sentinelas de "não identificado" em três fontes diferentes, cobertura irregular do SIM). A ADR-001 já havia decidido GitHub Actions como orquestrador (infraestrutura zero-custo), mas o desenho concreto — o que automatizar, em que frequência, e com que limites — não tinha sido especificado.

## Decision

**Frequência**: mensal (dia 1, 06:00 UTC), mais execução manual sob demanda (`workflow_dispatch`). Dado de vigilância epidemiológica não muda em escala de dias; mensal é suficiente para capturar consolidação de casos sem gastar minutos de execução do GitHub Actions à toa.

**Janela de anos fixa, não dinâmica**: o pipeline automatizado reprocessa a mesma janela já validada (2015-2024), definida como constante em `pipeline/run_pipeline.py` — não calcula "ano atual" e tenta estender sozinho. O valor da execução periódica não é descobrir anos novos automaticamente; é **capturar consolidação de dado que já existe** (casos de 2024 marcados como `provisorio` vão fechando com o tempo; reprocessar a mesma janela periodicamente reflete essa evolução sem intervenção manual). Estender a janela para incluir anos novos (2025+) é uma decisão manual deliberada, sujeita à mesma investigação aplicada a cada ano novo até aqui — não algo que o cron faz sozinho.

**Commit automático dos artefatos**: o workflow commita `bronze/`, `silver/`, `gold/` e `quality/logs/` de volta ao repositório ao final de cada execução bem-sucedida, usando a identidade `github-actions[bot]` (não a identidade pessoal do autor) — mantém o repositório como fonte única de verdade dos dados, consistente com a decisão da ADR-001 de armazenar Parquet diretamente no Git (volume validado em ~66 MB total, bem abaixo de qualquer limite).

**Fail-fast entre estágios**: `pipeline/run_pipeline.py` interrompe a execução no primeiro script que falhar, sem tentar rodar estágios seguintes sobre dado incompleto. Um erro em bronze não deve deixar silver/gold rodarem sobre bronze quebrado.

**Sem validação de regressão automática nesta versão**: o workflow não compara contagens de linha entre execuções para detectar quedas anômalas (ex.: um ano que subitamente vem com muito menos registros que o histórico). Considerado, mas adiado — ver Alternativas.

## Consequences

### Positive

- Reprocessamento periódico captura consolidação de dado (`status_maturidade` evoluindo de `provisorio` para `fechado`) sem intervenção manual, o que é genuinamente útil dado o padrão de right-censoring já documentado (ADR-001).
- Janela fixa evita o risco de o pipeline automatizado processar um ano novo com uma particularidade não descoberta (mesmo padrão de todos os anos já investigados) e publicar um resultado silenciosamente incorreto.
- Fail-fast entre estágios é barato de implementar e evita a classe de erro mais cara (silver/gold consumindo bronze corrompido).

### Negative

- Extensão da janela de anos exige ação manual — o projeto não fica "sempre atualizado" com o ano mais recente automaticamente, é uma escolha deliberada de segurança sobre automação completa.
- Sem checagem de regressão automática, uma falha sutil na fonte (ex.: DATASUS publicar um arquivo corrompido para um ano já validado) passaria despercebida até uma inspeção manual dos logs de qualidade.
- Commit automático do bot pode gerar ruído no histórico do repositório (um commit por mês, mesmo quando não há mudança de dado — mitigado pelo `git diff --staged --quiet` que pula o commit se nada mudou).

## Alternatives Considered

### Estender a janela de anos automaticamente (calcular ano atual)

Rejeitada por segurança: cada ano novo investigado neste projeto trouxe uma particularidade que só apareceu com investigação humana. Automatizar a extensão arriscaria publicar dado com problema não detectado, contrariando toda a disciplina de validação aplicada até aqui.

### Validação de regressão automática (comparar contagens entre execuções)

Considerada, mas adiada para uma iteração futura — adicionaria complexidade real (definir limiares de "queda anômala" por fonte, decidir o que fazer quando disparar) sem ela ser estritamente necessária para a primeira versão funcional da orquestração. Pode ser revisitada como melhoria incremental.

### Execução diária ou semanal

Rejeitada por desproporção: dado de vigilância epidemiológica brasileira não é atualizado nessa cadência pela fonte; execução mais frequente gastaria minutos de CI sem ganho de informação.

## References

- ADR-001 — decisão original de usar GitHub Actions como orquestrador zero-custo.
- `pipeline/run_pipeline.py`, `.github/workflows/pipeline.yml`.
