# Known Issues

Problemas conhecidos de dependências/fontes de terceiros usados neste projeto,
documentados aqui em vez de ficarem implícitos em comentários de código
espalhados. Ver também `docs/adrs/` para decisões derivadas destes problemas.

## PySUS: `sinan()` retorna DataFrame vazio para `TUBEBR16.parquet` (SINAN-TB, ano 2016)

**Status:** contornado em `ingestion/extract_sinan_tb.py`.

### Sintoma

`sinan(disease="tube", year=2016, as_dataframe=True)` retorna um
`pandas.DataFrame` vazio (`shape == (0, 0)`), sem levantar exceção — o mesmo
padrão silencioso já visto antes para o gap de cobertura do SIM (ver ADR-001),
mas com uma causa completamente diferente: aqui o arquivo **existe e tem dado
íntegro** no catálogo remoto do PySUS; o problema é só no metadado usado para
filtrá-lo.

### Causa raiz investigada

O arquivo `TUBEBR16.parquet` (SINAN, agravo `TUBE`, ano 2016) está presente no
catálogo remoto do PySUS, mas com o campo de `group_id` nulo nos metadados
daquele registro específico. A chamada `sinan(disease="tube", year=2016)`
internamente faz `PySUS.query(dataset="sinan", group="TUBE", year=2016)`, que
filtra por `group` — como o `group_id` desse arquivo está nulo no catálogo, o
filtro exclui o arquivo da lista de resultados antes mesmo de tentar baixá-lo.
O resultado é um `DataFrame` vazio, indistinguível à primeira vista de "não
há dado para esse ano" (que é uma situação real e esperada em outros casos,
ex.: gaps de cobertura do SIM).

Todos os outros anos do SINAN-TB (2015, 2017–2024) têm `group_id` presente e
correto no catálogo; 2016 é um caso isolado.

### Contorno aplicado

Em `ingestion/extract_sinan_tb.py`, a função `extract_year()` detecta quando
`sinan()` retorna um DataFrame vazio e, nesse caso, chama
`_fetch_without_group_filter()` como fallback: essa função consulta o
catálogo via `PySUS.query(dataset="sinan")` **sem** o filtro de `group`,
filtra os resultados no lado do cliente pelo nome do arquivo (prefixo
`TUBEBR16`), baixa e lê o(s) arquivo(s) encontrado(s) diretamente.

Se mesmo assim nada for encontrado, a função levanta `RuntimeError`
explícito — o mesmo princípio já aplicado ao gap de cobertura do SIM em
`extract_sim_tb_deaths.py`: DataFrame vazio nunca é tratado como "sem dado"
por padrão, só depois de confirmar que não há mesmo nenhum arquivo, com ou
sem o filtro de metadado.

O `_metadata.txt` gerado para o bronze de 2016 registra
`extraction_method=fallback_no_group_filter`, para que o uso do contorno
fique rastreável na trilha de proveniência, não escondido no código.

Resultado após o fix: `bronze/sinan_tb/ano=2016/` com 86.210 linhas e 100
colunas — mesma ordem de grandeza dos anos vizinhos (85.462 em 2015, 90.295
em 2017), confirmando que o dado do ano estava íntegro o tempo todo; só o
metadado de filtro é que estava quebrado.

## Dicionário de dados oficial do SINAN Net (TB) — difícil de acessar diretamente

**Status:** referência registrada, para não repetir o esforço de busca.

Confirmar campos codificados do SINAN-TB (`NDUPLIC_N`, `SITUA_ENCE`) contra a
fonte primária (não texto indexado/resumo de busca) se mostrou repetidamente
difícil neste projeto: tentativas de `WebFetch` direto em
`portalsinan.saude.gov.br`, `sitetb.saude.gov.br` e um mirror da UFSC
falharam (timeout, conexão recusada, ou PDF escaneado/binário sem texto
extraível) em pelo menos 3 ocasiões distintas.

O documento que finalmente permitiu confirmação direta (campo 62, domínio
completo de `SITUA_ENCE` com os 10 códigos) foi:

- **`DICI_DADOS_NET_Tuberculose_23_07_2020.pdf`** — dicionário de dados do
  SINAN Net, versão da ficha 5.0, Ministério da Saúde.
- Encontrado e lido diretamente pelo usuário do projeto (fora desta sessão);
  a URL exata de onde foi baixado não foi capturada aqui — se disponível,
  vale adicionar a este registro para acesso direto no futuro, em vez de
  depender de busca novamente.

Antes de assumir que um código de campo do SINAN não está documentado ou
tentar decodificá-lo só por busca indexada, vale procurar especificamente
por esse nome de arquivo (`DICI_DADOS_NET_*`) — é o padrão de nomenclatura
oficial dos dicionários de dados por agravo do SINAN Net.

## SIM: sentinela `XX0000` em `CODMUNRES` = município de residência ignorado

**Status:** identificado e tratado explicitamente em `transform_sim.py`, não descartado.

### Contexto

`CODMUNRES` (município de residência do falecido, ver
`docs/schema-reference-sim.md`) usa códigos de 6 dígitos (convenção DATASUS de
omitir o dígito verificador do código IBGE de 7 dígitos). A validação empírica
de correspondência contra `silver/dim_municipio` (`transform_sim.py
--validate-only`, amostra `uf=SP/ano=2022`) encontrou taxa de match de 99,5%
(214 de 215 códigos únicos) — o único código sem correspondência foi
`350000`.

### Causa raiz

`XX0000` (código de UF de 2 dígitos + 4 zeros) é a convenção documentada do
DATASUS/TABMUN para **"município de residência ignorado"**: o óbito é real e a
UF é conhecida, mas o município de residência dentro daquela UF não foi
identificado no preenchimento da Declaração de Óbito. Não é um município real
e nunca vai ter correspondência em `dim_municipio` — isso é esperado, não um
bug de join.

Na amostra `SP/2022`: 9 de 1.283 linhas (0,70%). Em escala nacional
(2015-2024, todas as UFs): **266 de 40.205 linhas (0,66%)** — praticamente a
mesma magnitude da amostra, confirmando que não é um artefato específico de
SP.

### Tratamento aplicado

`normalize_municipio_code()` em `transform_sim.py` detecta o padrão via regex
`^\d{2}0000$` e grava uma coluna explícita `municipio_residencia_ignorado`
(booleana) no silver — **a linha é mantida**, não descartada: é um óbito
verdadeiro, só com geografia de residência não resolvida; descartar
subestimaria a mortalidade real. Qualquer agregação por município deve
decidir explicitamente como tratar essas 266 linhas (ex.: excluir só da
agregação geográfica, mas manter no total nacional), não ignorá-las
silenciosamente.

O log de qualidade (`quality/logs/bronze_to_silver_sim_last_run.json`, passo
`normalize_municipio_code`) publica a contagem e o percentual a cada
execução, para detectar se a magnitude muda em UFs ou anos futuros.

## SINAN-TB: `SG_UF='0'` — hipótese de sentinela, não confirmada (volume imaterial)

**Status:** filtrado explicitamente em `build_fct_taxa_abandono.py`
(`aggregate_abandono_uf`), não investigado a fundo contra fonte primária.

`SG_UF='0'` aparece em 109 registros do SINAN-TB (2015: 50, 2016: 55, 2017: 4;
ausente de 2018 em diante) — sem esse filtro, esses registros formavam uma
28ª "UF" inválida no rollup `gold/fct_taxa_abandono_uf`, sem correspondência
em `gold/dim_uf` (27 UFs reais).

Hipótese: mesmo padrão de sentinela de valor "ignorado/não informado" já
confirmado em outras três fontes deste projeto (`SITUA_ENCE='0'` no SINAN-TB,
`"..."` no IBGE/SIDRA, `CODMUNRES='XX0000'` no SIM). **Não confirmado contra o
dicionário de dados oficial do SINAN** — decisão deliberada de não investigar,
por desproporção entre esforço e ganho: volume é 0,012% do total de casos
encerrados (109 de 911.257), mesmo raciocínio já aplicado para rejeitar a
checagem do DOU de 2023 (ver ADR-003, alternativas rejeitadas). Se o volume
crescer em execuções futuras, vale reabrir a investigação.
