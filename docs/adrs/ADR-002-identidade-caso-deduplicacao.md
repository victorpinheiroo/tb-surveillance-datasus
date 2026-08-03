---
artifact: adr
version: "1.0"
created: 2026-08-03
status: draft
---

# ADR-002: Identidade de caso e deduplicação no SINAN-TB

## Status

Accepted

**Date:** 2026-08-03
**Deciders:** Victor Pinheiro

## Context

O levantamento de schema real do SINAN-TB (`docs/schema-reference-sinan-tb.md`, gerado a partir de `bronze/sinan_tb/ano=2023/data.parquet`, 109.854 registros) confirmou que **não existe, no export público via PySUS, nenhuma coluna com cardinalidade compatível com identificador único de caso/notificação**. A coluna de maior cardinalidade entre as 94 colunas de origem (`ID_MN_RESI`) tem apenas 4.268 valores distintos para 109.854 linhas — ordens de grandeza abaixo do necessário para unicidade.

A fonte disponibiliza `NDUPLIC_N`, um campo do próprio SINAN que sinaliza notificação suspeita de duplicidade (89,87% nulo — presumivelmente populado só quando o sistema de origem já detectou e marcou uma duplicidade), mas isso não é um identificador de caso, é uma flag de duplicidade já resolvida pela fonte.

Isso exige uma decisão explícita antes de desenhar a transformação bronze→silver: como tratar identidade de caso, e como lidar com a reabertura/atualização de casos ao longo do tempo, quando nenhuma chave nativa e confiável está disponível.

## Decision

Duas linhas de tratamento, deliberadamente separadas:

1. **Contagem de eventos de notificação, não de pacientes únicos.** Cada linha do SINAN-TB é tratada como um evento de notificação. `NDUPLIC_N` é usado para remover duplicidade já confirmada pela própria fonte — nenhuma heurística própria de deduplicação é aplicada para remover linhas.

2. **Uma chave composta (`ID_MN_RESI` + `DT_NOTIFIC` + `ANO_NASC` + `CS_SEXO`) é calculada apenas como métrica de diagnóstico de qualidade, nunca como filtro.** O silver publica o percentual de registros que compartilham essa combinação, como um teto superior estimado de possível duplicidade não capturada por `NDUPLIC_N` — sem descartar, mesclar ou alterar nenhuma linha com base nela.

Não há tentativa de rastrear o mesmo paciente ao longo de múltiplas notificações/anos (record linkage). Isso está fora do escopo do projeto, tanto pela ausência de identificador confiável quanto pela decisão anterior de não empregar técnicas de correspondência probabilística (fora do escopo declarado de "engenharia sem modelagem preditiva").

## Consequences

### Positive

- Evita o principal risco identificado: usar uma chave composta como identificador de fato geraria colisões silenciosas em municípios grandes (dois pacientes distintos, mesmo ano de nascimento, sexo e município, notificados no mesmo dia — estatisticamente comum, não uma exceção rara), subestimando incidência sem qualquer sinal de que isso ocorreu.
- A separação entre "o que é removido" (duplicidade confirmada pela fonte via `NDUPLIC_N`) e "o que é apenas medido" (colisão de quase-identificador) é auditável: qualquer pessoa pode reproduzir o percentual publicado e entender exatamente o que ele significa e o que não significa.
- Mantém consistência com decisões anteriores do projeto (ADR-001): medir e declarar limitação de qualidade de dado explicitamente, em vez de mascará-la com uma correção que parece mais rigorosa do que é.

### Negative

- O projeto não pode responder perguntas que dependessem de identidade de paciente ao longo do tempo (ex.: taxa de reincidência real por indivíduo) — isso precisa ser declarado como fora de escopo na documentação pública, não deixado implícito.
- A métrica de "percentual de colisão de quase-identificador" é um teto superior estimado, não uma medida exata de duplicidade real — precisa ser apresentada com essa ressalva, para não ser lida como uma taxa de duplicidade confirmada.
- `NDUPLIC_N = 0`/branco significa "não avaliado quanto a duplicidade", não "confirmado como não-duplicata" — filtrar só por `= 2` captura duplicatas já confirmadas pela fonte, mas não garante ausência de duplicidade não avaliada. Isso deve ficar explícito em qualquer relatório de qualidade que cite essa deduplicação.

**Nota de validação — decodificação de `NDUPLIC_N` (2026-08-03):** confirmado via dicionário de dados do SINAN (campo de sistema comum a todos os agravos, nome interno `tp_duplicidade`): `0`/branco = "não identificado" (não avaliado), `1` = "não é duplicidade" (avaliado e válido), `2` = "duplicidade (não contar)". **Regra de filtro adotada: descartar apenas linhas com `NDUPLIC_N = 2`** — é a única categoria que representa duplicata confirmada pela própria fonte; `0` e `1` são mantidos.

**Ressalva de proveniência**: essa decodificação vem de texto indexado (busca via Google) de dois PDFs oficiais do portal SINAN, corroborado por um artigo peer-reviewed (SciELO) citando o mesmo uso do campo — o servidor `portalsinan.saude.gov.br` não respondeu no momento da tentativa de leitura direta do PDF. Confiança razoável (duas fontes independentes convergentes + uso documentado na literatura), mas de proveniência mais fraca que a decodificação de `SITUA_ENCE` (essa sim confirmada por leitura direta de PDF oficial). Se o portal voltar a responder, vale confirmar por leitura direta antes de publicar o projeto.

## Alternatives Considered

### Chave composta como identificador de fato (deduplicação por filtro)

Rejeitada. Combina campos com cardinalidade insuficiente em municípios grandes; geraria falsos positivos (pacientes distintos tratados como duplicata) de forma sistemática e silenciosa, distorcendo exatamente a métrica central do projeto (incidência por 100k habitantes).

### Record linkage probabilístico entre notificações (ex.: `recordlinkage`, `splink`)

Rejeitada para este projeto. Tecnicamente resolveria parte do problema de identidade de paciente ao longo do tempo, mas está fora do escopo declarado desde o início ("engenharia sem modelagem preditiva/ML") e adicionaria complexidade desproporcional ao ganho analítico para as perguntas de negócio definidas.

### Ignorar o problema (usar linha = evento, sem métrica de diagnóstico)

Considerada, mas rejeitada por ser menos rigorosa que a decisão adotada: não custa quase nada calcular e publicar a métrica de colisão de quase-identificador como diagnóstico, e isso é exatamente o tipo de transparência sobre limitação de dado que o projeto usa como diferencial.

## References

- `docs/schema-reference-sinan-tb.md` — levantamento de schema que originou esta decisão.
- ADR-001 — precedente de tratamento de limitação de qualidade de dado como decisão documentada, não como correção silenciosa (right-censoring, cobertura irregular do SIM).