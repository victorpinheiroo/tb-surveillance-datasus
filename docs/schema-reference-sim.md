# Schema Reference — SIM óbitos por TB (bronze)

Levantamento real de schema do SIM (óbitos com causa básica em TB), gerado a
partir de dado já extraído em `bronze/sim_tb_deaths/uf=SP/ano=2022/data.parquet`
— não de hipótese ou documentação de terceiros. Mesmo processo já aplicado ao
SINAN-TB (`docs/schema-reference-sinan-tb.md`), serve de referência para
desenhar a transformação bronze→silver do SIM com nomes de campo confirmados.

**Fonte:** `bronze/sim_tb_deaths/uf=SP/ano=2022/data.parquet`
**Por que SP/2022:** maior volume disponível entre os 251 arquivos do bronze do
SIM (confirmado por tamanho em disco antes de escolher — SP/2022 é o maior;
SP/2023, que seria o ano/UF mais recente, é um dos 19 gaps de cobertura já
documentados no ADR-001, então não existe no bronze).
**Linhas:** 1.283
**Colunas totais:** 90 (87 do schema original da fonte + 3 de proveniência
adicionadas pelo script de ingestão)

**Metodologia de "% nulo":** mesma lógica já usada no SINAN-TB — string vazia
após `strip()` conta como ausente, não só `NaN`. Todo o schema do SIM também é
`dtype=object` (texto).

## Campos-chave identificados

### Município de residência do falecido

**`CODMUNRES`** — 0,00% nulo, 215 valores únicos na amostra. Exemplos:
`354890`, `350710`, `355030`, `353060`, `354630`.

**Atenção — divergência de formato com o SINAN-TB, relevante para a
reconciliação geográfica pedida:** o código aqui tem **6 dígitos**, não 7. Isso
é a convenção clássica do DATASUS de omitir o dígito verificador do código
IBGE (ex.: `355030` = São Paulo, cujo código IBGE completo é `3550308`). O
SINAN-TB (`ID_MN_RESI`) e a população do IBGE (`D1C`, ver
`transform_population.py`) usam os 7 dígitos completos. **Join direto entre
SIM e SINAN-TB/população vai falhar silenciosamente ou dar zero match sem
normalizar isso primeiro** — precisa de uma decisão explícita na transformação
(mais provável: acrescentar o dígito verificador ao `CODMUNRES` do SIM, ou
truncar os códigos das outras fontes para 6 dígitos; a primeira opção é mais
segura, mas exige implementar ou importar o algoritmo do dígito verificador
do IBGE). Isso não é um problema do dado, é uma decisão de transformação a
ser tomada — só está sendo sinalizado aqui, não resolvido.

Existe também `CODMUNOCOR` (0,00% nulo, município de **ocorrência** do óbito
— onde o óbito aconteceu, não onde o falecido residia) e `CODMUNNATU` (4,29%
nulo, município de **naturalidade** — onde nasceu). Só `CODMUNRES` é o campo
relevante para a pergunta de negócio do projeto (mortalidade por município de
residência, comparável à incidência do SINAN-TB por `ID_MN_RESI`).

### Data do óbito

**`DTOBITO`** — 0,00% nulo, 353 valores únicos na amostra. Exemplos:
`16062022`, `06062022`, `19052022`, `24062022`, `31012022`.

**Atenção — formato diferente do SINAN-TB:** aqui o formato é `DDMMAAAA`
(dia-mês-ano), não `AAAAMMDD` (ano-mês-dia) como `DT_NOTIFIC`/`DT_ENCERRA` no
SINAN-TB. Ex.: `16062022` = 16/06/2022, não "1606-02-2" nem ano 1606. Parsing
de data no silver precisa tratar os dois formatos de forma diferente — não dá
para reusar a mesma função de parse do `transform_sinan_tb.py` sem ajuste.

Existe também `DTATESTADO` (0,08% nulo, data em que o atestado de óbito foi
preenchido — quase sempre igual a `DTOBITO`) e `DTCADASTRO`/`DTRECEBIM`/
`DTRECORIGA` (datas de fluxo administrativo do próprio SIM, 0,00% nulo cada,
mesmo formato `DDMMAAAA`).

### Campo de qualidade/duplicidade análogo ao `NDUPLIC_N`

**Não encontrado.** Nenhuma das 87 colunas de origem tem "DUPLIC" no nome, e
não há campo equivalente a uma flag de duplicidade de registro já resolvida
pela fonte, como existe no SINAN-TB. Isso é uma diferença real entre as duas
fontes, não uma lacuna de busca — precisa ficar documentado explicitamente se
o projeto decidir reportar mortalidade sem esse tipo de sinal de qualidade.

Dois campos que **não são** isso, para não confundir:
- **`TIPOBITO`** — classificação do tipo de óbito (fetal/não-fetal), não
  duplicidade. Nesta amostra é `2` (não-fetal) em 100% das linhas — esperado,
  já que óbito fetal não tem causa básica atribuível a TB do mesmo jeito.
- **`CONTADOR`** — 0,00% nulo, e **único nas 1.283 linhas desta amostra**
  (1.283 valores distintos para 1.283 linhas). É candidato a identificador de
  registro, mas com ressalva: não foi confirmado se é único *globalmente*
  (entre UFs/anos) ou só um contador sequencial reiniciado por lote/arquivo de
  extração do DATASUS — precisaria checar se há colisão de `CONTADOR` entre
  dois arquivos `uf=X/ano=Y` diferentes antes de tratá-lo como chave. Não
  testado aqui (fora do escopo deste levantamento, que é de um único arquivo).

### `CAUSABAS` — formato do valor

**Confirmado: CID-10 completo (categoria + dígito de subcategoria), não só a
categoria.** Exemplos: `A162`, `A153`, `A150`, `A159`, `A169` — nunca `A15`
"puro" sem o quarto caractere. 0,00% nulo, 30 valores únicos na amostra, todos
dentro do intervalo `A15`-`A19` esperado pelo filtro de extração (confirmado
pela própria coluna de proveniência `_filter_applied`: `"CAUSABAS startswith
('A15', 'A16', 'A17', 'A18', 'A19')"`).

Existe também `CAUSABAS_O` (causa básica "original", antes de eventuais regras
de recodificação; 0,00% nulo, 72 valores únicos) que **às vezes tem só 3
caracteres** (ex.: `J18`, sem dígito de subcategoria) — os dois campos não são
intercambiáveis; `CAUSABAS` é a coluna já usada no filtro de extração e deve
seguir sendo a fonte de verdade para "é óbito por TB", `CAUSABAS_O` é auxiliar/
auditoria.

## Tabela completa — colunas de origem (87)

| Coluna | Tipo (dtype) | % Nulo | Valores únicos (amostra) |
|---|---|---|---|
| `ORIGEM` | object | 0.00% | `1` |
| `TIPOBITO` | object | 0.00% | `2` |
| `DTOBITO` | object | 0.00% | `16062022`, `06062022`, `19052022`, `24062022`, `31012022` |
| `HORAOBITO` | object | 4.99% | `2316`, `1510`, `2124`, `1300`, `2055` |
| `NATURAL` | object | 2.10% | `829`, `850`, `835`, `826`, `825` |
| `CODMUNNATU` | object | 4.29% | `291480`, `500620`, `355250`, `355080`, `260540` |
| `DTNASC` | object | 0.62% | `10091967`, `29061981`, `23031959`, `22061994`, `27061940` |
| `IDADE` | object | 0.00% | `454`, `440`, `463`, `428`, `481` |
| `SEXO` | object | 0.00% | `1`, `2` |
| `RACACOR` | object | 0.94% | `1`, `2`, `4`, `3`, `5` |
| `ESTCIV` | object | 2.03% | `9`, `1`, `2`, `3`, `4` |
| `ESC` | object | 3.04% | `9`, `4`, `1`, `3`, `2` |
| `ESC2010` | object | 3.04% | `9`, `3`, `0`, `1`, `2` |
| `SERIESCFAL` | object | 60.41% | `1`, `4`, `3`, `8`, `5` |
| `OCUP` | object | 14.58% | `998999`, `514210`, `521125`, `999993`, `782510` |
| `CODMUNRES` | object | 0.00% | `354890`, `350710`, `355030`, `353060`, `354630` |
| `LOCOCOR` | object | 0.00% | `1`, `5`, `2`, `3`, `4` |
| `CODESTAB` | object | 14.19% | `2080931`, `2081407`, `4050169`, `2080052`, `2080745` |
| `ESTABDESCR` | object | 100.00% | *(sem valores — 100% nulo)* |
| `CODMUNOCOR` | object | 0.00% | `354890`, `352520`, `355030`, `353060`, `354630` |
| `IDADEMAE` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ESCMAE` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ESCMAE2010` | object | 100.00% | *(sem valores — 100% nulo)* |
| `SERIESCMAE` | object | 100.00% | *(sem valores — 100% nulo)* |
| `OCUPMAE` | object | 100.00% | *(sem valores — 100% nulo)* |
| `QTDFILVIVO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `QTDFILMORT` | object | 100.00% | *(sem valores — 100% nulo)* |
| `GRAVIDEZ` | object | 100.00% | *(sem valores — 100% nulo)* |
| `SEMAGESTAC` | object | 100.00% | *(sem valores — 100% nulo)* |
| `GESTACAO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `PARTO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `OBITOPARTO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `PESO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `TPMORTEOCO` | object | 92.28% | `8`, `9`, `5` |
| `OBITOGRAV` | object | 92.28% | `2`, `9` |
| `OBITOPUERP` | object | 92.28% | `3`, `9`, `2` |
| `ASSISTMED` | object | 33.52% | `1`, `2`, `9` |
| `EXAME` | object | 100.00% | *(sem valores — 100% nulo)* |
| `CIRURGIA` | object | 100.00% | *(sem valores — 100% nulo)* |
| `NECROPSIA` | object | 30.24% | `1`, `2`, `9` |
| `LINHAA` | object | 1.64% | `*A419`, `*J969`, `*R688`, `*J960`, `*J189` |
| `LINHAB` | object | 19.10% | `*A162`, `*J180`, `*J690`, `*A150`, `*J189` |
| `LINHAC` | object | 48.56% | `*J449`, `*J159`, `*A169`, `*A159`, `*A162` |
| `LINHAD` | object | 80.28% | `*A150`, `*F172`, `*J189`, `*A198`, `*A159` |
| `LINHAII` | object | 53.78% | `*R64X*F199`, `*K746*A153`, `*A162*K746`, `*E149*A162`, `*J449` |
| `CAUSABAS` | object | 0.00% | `A162`, `A153`, `A150`, `A159`, `A169` |
| `CB_PRE` | object | 100.00% | *(sem valores — 100% nulo)* |
| `COMUNSVOIM` | object | 75.68% | `354140`, `351880`, `355280`, `355030`, `353440` |
| `DTATESTADO` | object | 0.08% | `16062022`, `07062022`, `19052022`, `24062022`, `31012022` |
| `CIRCOBITO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ACIDTRAB` | object | 100.00% | *(sem valores — 100% nulo)* |
| `FONTE` | object | 100.00% | *(sem valores — 100% nulo)* |
| `NUMEROLOTE` | object | 0.00% | `20220043`, `20220039`, `20220228`, `20220129`, `20220003` |
| `TPPOS` | object | 43.96% | `N`, `S` |
| `DTINVESTIG` | object | 80.20% | `19082022`, `07022022`, `05042022`, `13072022`, `29072022` |
| `CAUSABAS_O` | object | 0.00% | `A162`, `A153`, `J18`, `A159`, `A169` |
| `DTCADASTRO` | object | 0.00% | `24062022`, `14062022`, `29062022`, `30062022`, `07022022` |
| `ATESTANTE` | object | 7.87% | `2`, `5`, `4`, `1`, `3` |
| `STCODIFICA` | object | 0.00% | `S` |
| `CODIFICADO` | object | 0.00% | `S` |
| `VERSAOSIST` | object | 0.00% | `3.2.30`, `3.2.00`, `3.2.02` |
| `VERSAOSCB` | object | 0.31% | `3.4`, `3.2`, `3.3` |
| `FONTEINV` | object | 80.12% | `3`, `8`, `1`, `7`, `6` |
| `DTRECEBIM` | object | 0.00% | `03082022`, `15062022`, `01122022`, `24082022`, `12022022` |
| `ATESTADO` | object | 0.00% | `A419/A162*R64 F199`, `A419/J180*K746 A153`, `J969/J690*A162 K746`, `J969/A150`, `A419/J189/J449/A150` |
| `DTRECORIGA` | object | 0.00% | `29062022`, `15062022`, `01122022`, `01072022`, `12022022` |
| `CAUSAMAT` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ESCMAEAGR1` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ESCFALAGR1` | object | 3.04% | `09`, `05`, `00`, `12`, `02` |
| `STDOEPIDEM` | object | 0.00% | `0` |
| `STDONOVA` | object | 0.00% | `1` |
| `DIFDATA` | object | 0.00% | `048`, `009`, `196`, `061`, `012` |
| `NUDIASOBCO` | object | 93.06% | `64`, `128`, `95`, `68`, `56` |
| `NUDIASOBIN` | object | 100.00% | *(sem valores — 100% nulo)* |
| `DTCADINV` | object | 92.91% | `19072022`, `07092022`, `27062022`, `06012023`, `31052022` |
| `TPOBITOCOR` | object | 92.91% | `9`, `6`, `8` |
| `DTCONINV` | object | 93.06% | `13072022`, `07092022`, `27062022`, `01062022`, `31052022` |
| `FONTES` | object | 100.00% | *(sem valores — 100% nulo)* |
| `TPRESGINFO` | object | 99.84% | `1`, `2` |
| `TPNIVELINV` | object | 92.91% | `M`, `R` |
| `NUDIASINF` | object | 100.00% | *(sem valores — 100% nulo)* |
| `DTCADINF` | object | 100.00% | *(sem valores — 100% nulo)* |
| `MORTEPARTO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `DTCONCASO` | object | 100.00% | *(sem valores — 100% nulo)* |
| `FONTESINF` | object | 100.00% | *(sem valores — 100% nulo)* |
| `ALTCAUSA` | object | 100.00% | *(sem valores — 100% nulo)* |
| `CONTADOR` | object | 0.00% | `727`, `953`, `1437`, `1630`, `2820` |

## Colunas de proveniência (adicionadas pela ingestão, não fazem parte do schema da fonte)

| Coluna | Tipo (dtype) | % Nulo | Valores únicos (amostra) |
|---|---|---|---|
| `_source_dataset` | object | 0.00% | `SIM-SP-2022` |
| `_ingested_at` | object | 0.00% | `2026-08-03T01:48:41.647585+00:00` |
| `_filter_applied` | object | 0.00% | `CAUSABAS startswith ('A15', 'A16', 'A17', 'A18', 'A19')` |

## Observações gerais

- **Todo o schema é `dtype=object`** (texto), mesmo padrão do SINAN-TB —
  conversão de tipo é responsabilidade do silver.
- Grande volume de colunas 100% nulas nesta amostra (`ESTABDESCR`,
  `IDADEMAE`, `ESCMAE*`, `SERIESCMAE`, `OCUPMAE`, `QTDFIL*`, `GRAVIDEZ`,
  `SEMAGESTAC`, `GESTACAO`, `PARTO`, `OBITOPARTO`, `PESO`, `EXAME`,
  `CIRURGIA`, `CB_PRE`, `CIRCOBITO`, `ACIDTRAB`, `FONTE`, `CAUSAMAT`,
  `ESCMAEAGR1`, `NUDIASOBIN`, `FONTES`, `NUDIASINF`, `DTCADINF`,
  `MORTEPARTO`, `DTCONCASO`, `FONTESINF`, `ALTCAUSA`) — a maioria é campo de
  óbito fetal/materno (`*MAE*`, `GRAVIDEZ`, `PARTO`, `PESO`, `CAUSAMAT`,
  `MORTEPARTO`), esperado ser irrelevante para óbitos de adulto por TB;
  candidatas a descarte no silver, decisão não tomada aqui.
- Vários campos de investigação epidemiológica (`DTINVESTIG`, `FONTEINV`,
  `DTCADINV`, `TPOBITOCOR`, `DTCONINV`, `TPRESGINFO`, `TPNIVELINV`) têm
  80-99% nulo — parecem populados só quando o óbito passou por investigação
  formal, não em todo registro.
- `LINHAA`-`LINHAD` e `LINHAII` são as linhas do atestado de óbito (Bloco I:
  causa direta → causa básica; Bloco II: causas contribuintes) — insumo bruto
  de onde `CAUSABAS` é derivado pelas regras de seleção de causa básica do
  CID-10, não usado diretamente na pergunta de negócio do projeto.
- Nenhum campo `TPCASO`/`SITUA_ENCE`-like: o SIM não tem conceito de
  encerramento de caso como o SINAN — cada linha já é, por definição, um
  óbito (evento terminal), não um caso em acompanhamento.
