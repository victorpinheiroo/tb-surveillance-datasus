# Schema Reference — SINAN-TB (bronze)

Levantamento real de schema do SINAN-TB, gerado a partir de dado já extraído
em `bronze/sinan_tb/ano=2023/data.parquet` — não de hipótese ou documentação
de terceiros. Serve de referência para desenhar a transformação bronze→silver
com nomes de campo confirmados.

**Fonte:** `bronze/sinan_tb/ano=2023/data.parquet`
**Por que 2023:** ano mais recente do lote "fechado" (ver ADR-001 — right-censoring
validado empiricamente), e schema mais estável — evita as 3 colunas legadas
presentes em 2015-2018, ausentes de 2019 em diante (`AGRAVOUTDE`, `EXTRAPUL_O`,
`OUTRAS_DES`; confirmado por inspeção real dos 10 anos de bronze, não só da
amostra 2015/2019/2023 do spike original).
**Linhas:** 109.854
**Colunas totais:** 97 (94 do schema original da fonte + 3 de proveniência
adicionadas pelo script de ingestão)

**Metodologia de "% nulo":** mesma lógica já validada no spike de `DT_ENCERRA`
(ver ADR-001) — string vazia após `strip()` conta como ausente, não só `NaN`.
Todo o schema do SINAN-TB é `dtype=object` (texto), então essa distinção
importa em praticamente todas as colunas, não só nas de data.

## Campos-chave identificados

### Identificador único de notificação/caso

**Não encontrado.** Nenhuma coluna se aproxima de ser única por linha —
com 109.854 registros, a maior cardinalidade entre todas as 94 colunas de
origem é `ID_MN_RESI` (município de residência), com apenas 4.268 valores
distintos. Não há um campo tipo `NU_NOTIFIC` ou similar neste export.
`NDUPLIC_N` (89,87% nulo, valores `0`/`1`/`2`) parece ser uma *flag* de
notificação duplicada, não um identificador.

**Implicação para o silver:** ou (a) gerar uma chave surrogate por linha na
ingestão/bronze→silver, documentando explicitamente que é sintética e não
vem da fonte, ou (b) investigar se o SINAN/DBF original tem um número de
registro interno que o PySUS descarta na conversão para Parquet — precisa
de decisão explícita antes de desenhar joins ou dedupe no silver.

### Município de notificação

**`ID_MUNICIP`** — código IBGE (7 dígitos), 0% nulo, 3.968 valores únicos.
Exemplos: `3509601`, `3505708`, `3513801`, `4118204`, `3515707` (os 2
primeiros dígitos batem com `SG_UF_NOT`: `35`=SP, `41`=PR).

Existe também `ID_MUNIC_A` (0,29% nulo, 3.980 únicos) — mesmo padrão de
código, parece ser o município de notificação "atualizado" (pós-transferência
dentro do próprio registro); e `ID_MUNIC_2` (23,56% nulo) e `MUN_TRANSF`
(95,10% nulo), ligados a fluxos de transferência de caso. Só `ID_MUNICIP` é
necessário para a pergunta de negócio do projeto (incidência por
município/UF); os demais são candidatos a ficar de fora do silver ou a virar
metadado de auditoria, não dado analítico.

### Município de residência do paciente

**`ID_MN_RESI`** — código IBGE (7 dígitos), 0% nulo, 4.268 valores únicos
(mais granular que `ID_MUNICIP`, esperado — mais gente reside fora de onde
notifica do que o contrário). Este é o campo relevante para reconciliação
geográfica SINAN×SIM (óbitos no SIM também são atribuídos ao município de
residência).

### Situação de encerramento do caso

**`SITUA_ENCE`** — 4,30% nulo (amostra 2023), até 10 valores únicos
codificados numericamente ao longo dos 10 anos (2015-2024). É o campo
pareado com `DT_ENCERRA` (já validado no spike): `DT_ENCERRA` diz *quando*
o caso foi encerrado, `SITUA_ENCE` diz *como* (cura, abandono, óbito, etc.).

**Dicionário de domínio confirmado (2026-08-03, leitura direta do PDF oficial
do Ministério da Saúde — dicionário de dados SINAN Net v5.0, campo 62; ver
`docs/known-issues.md` para a referência exata e a dificuldade de acesso):**

| Código | Significado |
|---|---|
| 1 | Cura |
| 2 | Abandono |
| 3 | Óbito por Tuberculose |
| 4 | Óbito por outras causas |
| 5 | Transferência |
| 6 | Mudança de Diagnóstico |
| 7 | TB-DR |
| 8 | Mudança de Esquema |
| 9 | Falência |
| 10 | Abandono Primário |

Valores `03`/`04` observados só em 2018 são zero-padding do mesmo código
`3`/`4`, não categorias novas (normalizado no silver via `lstrip('0')`).
Valor `0` (presente só em 2015-2017, 8.358 registros) não faz parte deste
domínio confirmado e permanece não mapeado — não decodificado de memória.

Dois campos parecidos, mas que **não são** o de encerramento final —
ficam fora desse papel:
- `SITUA_9_M` (99,98% nulo) e `SITUA_12_M` (100,00% nulo, com raríssimas
  exceções) — situação de acompanhamento em pontos fixos do tratamento (9 e
  12 meses), não o desfecho final do caso.
- Não existe coluna `TPCASO` neste schema.

## Tabela completa — colunas de origem (94)

| Coluna | Tipo (dtype) | % Nulo | Valores únicos (amostra) |
|---|---|---|---|
| `TP_NOT` | object | 0.00% | `2` |
| `ID_AGRAVO` | object | 0.00% | `A169` |
| `DT_NOTIFIC` | object | 0.00% | `20230516`, `20230317`, `20230619`, `20231208`, `20230807` |
| `NU_ANO` | object | 0.00% | `2023`, `2024`, `2025` |
| `SG_UF_NOT` | object | 0.00% | `35`, `41`, `29`, `15`, `23` |
| `ID_MUNICIP` | object | 0.00% | `3509601`, `3505708`, `3513801`, `4118204`, `3515707` |
| `ID_REGIONA` | object | 40.69% | `135`, `140`, `148`, `152`, `153` |
| `DT_DIAG` | object | 0.00% | `20230512`, `20230316`, `20230619`, `20231206`, `20230804` |
| `ANO_NASC` | object | 0.43% | `1963`, `1965`, `1984`, `1961`, `2001` |
| `NU_IDADE_N` | object | 0.04% | `4059`, `4057`, `4038`, `4062`, `4022` |
| `CS_SEXO` | object | 0.00% | `M`, `F`, `I` |
| `CS_GESTANT` | object | 0.01% | `6`, `5`, `9`, `4`, `1` |
| `CS_RACA` | object | 1.68% | `4`, `1`, `5`, `9`, `2` |
| `CS_ESCOL_N` | object | 7.55% | `9`, `7`, `5`, `1`, `3` |
| `SG_UF` | object | 0.00% | `35`, `41`, `29`, `15`, `23` |
| `ID_MN_RESI` | object | 0.00% | `3509601`, `3505708`, `3513801`, `4118204`, `3515707` |
| `ID_RG_RESI` | object | 41.03% | `135`, `140`, `148`, `152`, `154` |
| `ID_PAIS` | object | 22.72% | `1`, `68`, `138`, `126`, `199` |
| `NDUPLIC_N` | object | 89.87% | `1`, `0`, `2` |
| `IN_VINCULA` | object | 90.31% | `1`, `0` |
| `DT_DIGITA` | object | 22.72% | `20231208`, `20230310`, `20230607`, `20230717`, `20230726` |
| `DT_TRANSUS` | object | 93.88% | `20231208`, `20230820`, `20240110`, `20230523`, `20230927` |
| `DT_TRANSDM` | object | 99.06% | `20240410`, `20230502`, `20230426`, `20240417`, `20240209` |
| `DT_TRANSSM` | object | 43.58% | `20230321`, `20240216`, `20230801`, `20240126`, `20230814` |
| `DT_TRANSRM` | object | 100.00% | *(sem valores — 100% nulo)* |
| `DT_TRANSRS` | object | 98.46% | `20230727`, `20230510`, `20230426`, `20240119`, `20230616` |
| `DT_TRANSSE` | object | 64.38% | `20240520`, `20240822`, `20240815`, `20231027`, `20250604` |
| `CS_FLXRET` | object | 100.00% | *(sem valores — 100% nulo)* |
| `FLXRECEBI` | object | 100.00% | *(sem valores — 100% nulo)* |
| `MIGRADO_W` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ID_OCUPA_N` | object | 100.00% | *(sem valores — 100% nulo)* |
| `TRATAMENTO` | object | 0.00% | `1`, `3`, `5`, `2`, `4` |
| `INSTITUCIO` | object | 99.98% | `9`, `1`, `2` |
| `RAIOX_TORA` | object | 1.88% | `4`, `1`, `3`, `2` |
| `TESTE_TUBE` | object | 99.98% | `4`, `3`, `1`, `2` |
| `FORMA` | object | 0.02% | `1`, `2`, `3` |
| `EXTRAPU1_N` | object | 0.00% | `.`, `1`, `3`, `8`, `4` |
| `EXTRAPU2_N` | object | 99.86% | `6`, `7`, `10`, `5`, `3` |
| `AGRAVAIDS` | object | 1.62% | `2`, `9`, `1` |
| `AGRAVALCOO` | object | 1.61% | `2`, `1`, `9` |
| `AGRAVDIABE` | object | 1.84% | `2`, `9`, `1` |
| `AGRAVDOENC` | object | 2.14% | `2`, `9`, `1` |
| `AGRAVOUTRA` | object | 32.86% | `9`, `2`, `1` |
| `BACILOSC_E` | object | 0.02% | `3`, `2`, `1`, `4` |
| `BACILOS_E2` | object | 99.98% | `2`, `3`, `1` |
| `BACILOSC_O` | object | 77.27% | `3`, `1`, `2` |
| `CULTURA_ES` | object | 0.02% | `4`, `1`, `3`, `2` |
| `CULTURA_OU` | object | 81.20% | `4`, `2`, `1`, `3` |
| `HIV` | object | 0.26% | `2`, `4`, `3`, `1` |
| `HISTOPATOL` | object | 6.97% | `5`, `2`, `1`, `4`, `3` |
| `DT_INIC_TR` | object | 4.59% | `20230516`, `20230316`, `20230619`, `20231208`, `20230807` |
| `RIFAMPICIN` | object | 99.99% | `1`, `2` |
| `ISONIAZIDA` | object | 99.99% | `1`, `2` |
| `ETAMBUTOL` | object | 99.99% | `2`, `1` |
| `ESTREPTOMI` | object | 99.99% | `2` |
| `PIRAZINAMI` | object | 99.99% | `1`, `2` |
| `ETIONAMIDA` | object | 99.99% | `1`, `2` |
| `OUTRAS` | object | 99.99% | `2`, `1` |
| `TRAT_SUPER` | object | 77.25% | `1`, `9`, `2` |
| `NU_CONTATO` | object | 3.52% | `1`, `0`, `3`, `4`, `9` |
| `DOENCA_TRA` | object | 99.98% | `2` |
| `SG_UF_AT` | object | 0.29% | `35`, `41`, `29`, `15`, `23` |
| `ID_MUNIC_A` | object | 0.29% | `3509601`, `3505708`, `3513801`, `4118204`, `3515707` |
| `DT_NOTI_AT` | object | 23.00% | `20231208`, `20230304`, `20230603`, `20230710`, `20230721` |
| `SG_UF_2` | object | 23.31% | `41`, `29`, `15`, `23`, `27` |
| `ID_MUNIC_2` | object | 23.56% | `4118204`, `2902708`, `1502608`, `2306108`, `2703809` |
| `BACILOSC_1` | object | 23.64% | `1`, `2`, `3`, `4` |
| `BACILOSC_2` | object | 28.49% | `1`, `2`, `3`, `4` |
| `BACILOSC_3` | object | 31.79% | `2`, `3`, `4`, `1` |
| `BACILOSC_4` | object | 34.94% | `3`, `2`, `4`, `1` |
| `BACILOSC_5` | object | 37.60% | `3`, `2`, `4`, `1` |
| `BACILOSC_6` | object | 40.55% | `3`, `2`, `4`, `1` |
| `TRATSUP_AT` | object | 21.32% | `2`, `1`, `9` |
| `DT_MUDANCA` | object | ~100.00% | `18991230`, `20231227` *(≈2 valores não-vazios em 109.854 linhas)* |
| `NU_COMU_EX` | object | 16.34% | `1`, `0`, `2`, `4`, `3` |
| `SITUA_9_M` | object | 99.98% | `12`, `2`, `5`, `1`, `3` |
| `SITUA_12_M` | object | ~100.00% | `5`, `11`, `1` |
| `SITUA_ENCE` | object | 4.30% | `1`, `5`, `3`, `7`, `4` |
| `DT_ENCERRA` | object | 4.73% | `20240115`, `20240109`, `20240415`, `20240207`, `20230310` |
| `TPUNINOT` | object | 25.40% | `36`, `5`, `2`, `4`, `39` |
| `POP_LIBER` | object | 1.90% | `2`, `9`, `1` |
| `POP_RUA` | object | 2.20% | `2`, `1`, `9` |
| `POP_SAUDE` | object | 2.25% | `3`, `2`, `9`, `1` |
| `POP_IMIG` | object | 2.44% | `2`, `1`, `9`, `3` |
| `BENEF_GOV` | object | 26.89% | `2`, `9`, `1` |
| `AGRAVDROGA` | object | 2.03% | `2`, `9`, `1` |
| `AGRAVTABAC` | object | 2.12% | `1`, `2`, `9` |
| `TEST_MOLEC` | object | 5.23% | `1`, `5`, `2`, `3`, `4` |
| `TEST_SENSI` | object | 44.71% | `5`, `7`, `3`, `6`, `1` |
| `ANT_RETRO` | object | 75.34% | `2`, `1`, `9` |
| `BAC_APOS_6` | object | 70.12% | `3`, `4`, `2`, `1`, `6` |
| `TRANSF` | object | 91.97% | `3`, `2`, `1`, `9`, `4` |
| `UF_TRANSF` | object | 94.78% | `42`, `29`, `27`, `35`, `43` |
| `MUN_TRANSF` | object | 95.10% | `42`, `29`, `27`, `35`, `43` |

## Colunas de proveniência (adicionadas pela ingestão, não fazem parte do schema da fonte)

| Coluna | Tipo (dtype) | % Nulo | Valores únicos (amostra) |
|---|---|---|---|
| `_source_dataset` | object | 0.00% | `SINAN-TUBE-2023` |
| `_ingested_at` | object | 0.00% | `2026-08-03T00:30:20.345312+00:` |
| `_status_maturidade_estimado` | object | 0.00% | `fechado` |

## Observações gerais

- **Todo o schema é `dtype=object`** (texto) — inclusive campos numéricos e de
  data (`YYYYMMDD` como string). Conversão de tipo é responsabilidade
  explícita do silver, não algo que já vem pronto do bronze.
- Colunas 100% (ou quase 100%) nulas neste ano (`DT_TRANSRM`, `CS_FLXRET`,
  `FLXRECEBI`, `MIGRADO_W`, `ID_OCUPA_N`, `DT_MUDANCA`, `SITUA_12_M`) são
  candidatas a descarte no silver, mas isso não foi decidido aqui — este
  documento é só levantamento, a decisão de quais colunas entram no silver é
  separada (ver ADR-001 para o precedente de descarte documentado, aplicado
  às 3 colunas legadas presentes em 2015-2018 e ausentes de 2019 em diante).
- Vários pares `SG_UF_*` / `ID_MUNIC_*` distintos (`_NOT`, `_AT`, `_2`,
  `_TRANSF`) sugerem que o SINAN rastreia transferência de caso entre
  unidades notificadoras — vale desenhar o silver assumindo que só o par
  "de notificação original" (`ID_MUNICIP`/`SG_UF_NOT`) e o "de residência"
  (`ID_MN_RESI`/`SG_UF`) são necessários às perguntas de negócio do projeto,
  a menos que uma decisão explícita amplie esse escopo.
