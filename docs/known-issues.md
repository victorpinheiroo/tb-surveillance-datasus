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
