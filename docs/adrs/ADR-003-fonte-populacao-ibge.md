---
artifact: adr
version: "1.0"
created: 2026-08-03
status: draft
---

# ADR-003: Fonte de população para normalização de incidência (IBGE)

## Status

Accepted

**Date:** 2026-08-03
**Deciders:** Victor Pinheiro

## Context

O cálculo de incidência por 100 mil habitantes exige uma fonte de população por município/ano. A tabela 6579 do SIDRA (Estimativas de população residente para os municípios) foi escolhida como fonte primária, mas a validação empírica (teste real de download por ano, não só leitura de metadados declarados) encontrou dois anos sem dado dentro da janela do projeto (2015-2024):

- **2022**: ano de Censo Demográfico — o IBGE retirou as Estimativas de 2022 do calendário do SIDRA, substituindo-as pelos resultados do Censo (tabela 4714).
- **2023**: sem tabela SIDRA equivalente. O próprio IBGE publicou a população de referência de 2023 usando os resultados do Censo 2022, atualizados apenas por mudança de limite territorial até 30/04/2023, via Diário Oficial da União — não como uma tabela SIDRA anual separada.

Isso não apareceu na leitura inicial dos metadados declarados da tabela (que indicavam range nominal 2001-2025); só apareceu ao testar download real por ano — reforça o padrão já estabelecido no projeto (ADR-001, ADR-002) de nunca confiar em cobertura declarada sem teste empírico.

## Decision

Para 2022 e 2023, usar o valor do **Censo 2022** (tabela 4714, variável 93) como fonte de população — para os dois anos, com o mesmo valor. Isso replica a lógica que o próprio IBGE aplicou publicamente para 2023 (Censo 2022 como base, sem nova estimativa demográfica), em vez de o projeto construir sua própria interpolação ou extrapolação.

Cada registro de população carrega uma coluna `_status_fonte_populacao` (`estimativa_direta` / `proxy_censo_2022`), permitindo que qualquer análise posterior saiba, por ano, se o denominador populacional veio da série de estimativas anuais ou do proxy censitário.

Rejeitado explicitamente: buscar a publicação específica do Diário Oficial da União com a correção de limite territorial para 2023. O ganho de precisão (diferença entre o Censo puro e a versão corrigida por limite territorial) é marginal para uma taxa por 100 mil habitantes, e o custo de engenharia (parsing de publicação de diário oficial, fonte não estruturada, sem API) é desproporcional ao ganho — mesmo padrão de decisão já aplicado ao gap de cobertura do SIM (não perseguir fonte alternativa para fechar uma lacuna pequena).

Rejeitado também: qualquer interpolação/extrapolação própria de população para 2023 (ex.: projetar tendência de crescimento entre 2021 e 2024). Isso constituiria o projeto inventando um valor que a fonte não forneceu, contrariando a decisão declarada desde o início de não empregar estimativa/modelagem própria.

**Nota de validação — divergência de 1 município entre fontes (2026-08-03):** a contagem de municípios difere em 1 entre a série de estimativas (5.571 municípios em 2021) e o Censo 2022 (5.570 municípios). Investigação confirmou a causa: **Boa Esperança do Norte (MT), código IBGE `5101837`**, tem criação legal de 2000 mas emancipação só confirmada pelo STF em outubro/2023, com instalação formal em janeiro/2025 — durante a coleta do Censo 2022 (ago/2022-mai/2023) ainda não existia como entidade separada (população contabilizada dentro de Sorriso/Nova Ubiratã). O IBGE já reservava o código na base territorial de estimativas, mas não no Censo. **Implicação para o silver**: a dimensão de município (SCD2) deve tratar `5101837` como válido a partir de 2021 (ou do ano em que passa a aparecer na base de estimativas) e ausente no proxy censitário de 2022/2023 — sem isso, um join direto entre população e notificação/óbito para esse município específico falharia silenciosamente nos anos 2022-2023.

## Consequences

### Positive

- A decisão replica exatamente a lógica pública do IBGE para 2023, em vez de substituí-la por um critério próprio — defensável em qualquer questionamento sobre a escolha.
- `_status_fonte_populacao` torna a limitação auditável por qualquer pessoa que consumir o gold layer, sem precisar ler esta ADR para descobrir que 2022 e 2023 compartilham a mesma base populacional.
- Consistente com o padrão já estabelecido no projeto: medir e declarar limitação de fonte, não mascará-la com refinamento desproporcional.

### Negative

- Qualquer crescimento populacional real ocorrido entre 2022 e 2023 (ainda que pequeno, dado o intervalo curto) não é capturado — a taxa de incidência por 100k para 2023 usa um denominador que é, na prática, o de 2022.
- Se a precisão exata da correção de limite territorial de 2023 se tornar relevante no futuro (ex.: para um município que teve alteração de limite nesse período específico), a decisão precisará ser revisitada — não foi investigada a fundo, foi conscientemente descartada por desproporção de esforço.

## Alternatives Considered

### Buscar a publicação do Diário Oficial da União com a população de 2023 corrigida por limite territorial

Rejeitada por desproporção entre esforço de engenharia (scraping de fonte não estruturada) e ganho de precisão (diferença marginal para a métrica do projeto).

### Interpolação/extrapolação própria de população para 2023

Rejeitada por contrariar a decisão declarada desde o início do projeto de não empregar estimativa ou modelagem própria — o projeto usa dado oficial como está disponível, não substitui a fonte por inferência própria.

### Excluir 2022 e 2023 das métricas normalizadas por população

Considerada, mas rejeitada: 2022 e 2023 estão dentro do lote `fechado` (ADR-001, right-censoring validado), com dado de notificação maduro — excluir a normalização populacional desses dois anos descartaria informação madura e relevante em vez de tratá-la com uma limitação declarada.

## References

- Tabela 6579 (SIDRA/IBGE) — Estimativas de população residente para os municípios.
- Tabela 4714 (SIDRA/IBGE) — Censo Demográfico 2022, população residente por município.
- ADR-001, ADR-002 — precedentes de tratamento de limitação de fonte como decisão documentada.

## Adendo — gap de 1 município entre estimativa e Censo (2026-08-03)

Validação da contagem de municípios entre as duas fontes encontrou uma diferença de exatamente 1 código: **`5101837` (Boa Esperança do Norte, MT)** aparece na base de estimativas (5.571 municípios) mas não no Censo 2022 (5.570 municípios). Causa raiz confirmada: emancipação legal de 2000, mas confirmação pelo STF só em out/2023 e instalação formal em jan/2025 — durante a coleta do Censo 2022 (ago/2022-mai/2023) o município ainda não existia como entidade separada (população contabilizada em Sorriso/Nova Ubiratã); o IBGE já reserva o código na base territorial, usado pelas estimativas, mas o Censo não o contou separadamente.

**Decisão**: não construir tratamento especial (ex.: herdar população proporcional dos municípios de origem) para este único caso — mesmo critério de desproporção já aplicado à correção de limite territorial do DOU. No silver, o join entre notificações SINAN-TB e população deve tratar a ausência de `5101837` em 2022/2023 como população nula e explicitamente sinalizada (não como zero, não descartando a linha de notificação correspondente se houver alguma) — consistente com o princípio já estabelecido no projeto de nunca deixar ausência de dado passar silenciosamente.