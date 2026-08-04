---
artifact: adr
version: "1.1"
created: 2026-07-29
status: draft
---

# ADR-001: Escopo do projeto, fonte de dados e infraestrutura de execução

## Status

Accepted (validado empiricamente em 2026-08-02 via spike `00_explore_assumptions.py`)

**Date:** 2026-07-29
**Deciders:** Victor Pinheiro

## Context

O objetivo deste projeto é construir um pipeline de engenharia de dados ponta a ponta, público, usando dado de saúde brasileiro, como prova técnica para vagas remotas internacionais de Data Engineering. O foco declarado é engenharia (ingestão, tratamento de dado sujo/inconsistente, qualidade e governança), não ciência de dados — não há modelagem preditiva neste projeto.

Duas restrições concretas moldaram esta decisão:

1. O dataset não pode ser genérico/didático (tipo Titanic). Precisa ter complexidade real de dado sujo, subnotificação e inconsistência entre fontes, defensável em entrevista técnica.
2. O projeto não pode gerar custo de infraestrutura, nem risco de billing inesperado. Isso exclui qualquer serviço cloud "always-on" com cobrança por capacidade reservada ou por hora ligado, e reduz a tolerância a qualquer configuração que dependa de ficar dentro de cota de free tier sem supervisão constante.

**Nota de revisão (2026-07-29):** a janela temporal originalmente proposta (2014–2023) continha dois problemas não identificados na primeira versão desta ADR:

- **Mudança de schema não tratada**: em 2015 houve a última grande atualização da ficha de notificação/investigação de TB (versão 5.0 do Sinan-Net), que incluiu campos novos (ex.: população privada de liberdade). Incluir 2014 misturaria um schema diferente dos anos seguintes sem que isso fosse uma decisão explícita.
- **Right-censoring em anos recentes**: bases como o SIM têm atraso de consolidação em torno de dois anos em relação ao ano mais atual — dados publicados pelo Datasus referem-se a bases "fechadas" numa data específica, não ao estado corrente. O encerramento de um caso de TB (cura, abandono, óbito) só é conhecido após o acompanhamento do tratamento, que leva meses. Isso significa que anos muito recentes mostram taxas de incidência e de abandono artificialmente baixas — não porque a situação melhorou, mas porque os casos ainda estão em aberto no sistema.

**Nota de validação empírica (2026-08-02):** o spike `00_explore_assumptions.py` rodou contra dado real do PySUS (SINAN-TB, agravo `TUBE`) e testou as suposições acima:

- **Right-censoring confirmado**, com refinamento do limiar: taxa de preenchimento de `DT_ENCERRA` (tratando string vazia como ausente, não só `NaN` — ver Consequências) foi de 95.9% (2015), 97.0% (2019), 95.3% (2023) e **85.9% (2024)**. A queda concentra-se em 2024 (2 anos de idade), enquanto 2023 (3 anos de idade) já está maduro. Isso confirma o padrão de consolidação, com o limiar prático situado entre 2 e 3 anos — dado insuficiente para cravar o valor exato entre esses dois pontos, mas suficiente para validar a janela 2015-2023 como `fechado` e qualquer ano ≥2024 como `provisório`.
- **Anomalia de schema em 2015-2018**: `AGRAVOUTDE`, `EXTRAPUL_O`, `OUTRAS_DES` estão presentes em 2015-2018 e ausentes de 2019 em diante. **Correção (2026-08-03): a afirmação original desta ADR de que essas colunas eram "exclusivas de 2015" estava factualmente errada** — o spike inicial amostrou apenas 2015, 2019 e 2023 (não os anos intermediários 2016-2018), então não detectou que a presença se estendia até 2018. A decisão de descartar as 3 colunas no silver permanece válida (nenhuma delas é necessária às perguntas de negócio do projeto), independente do ano em que aparecem. Achado à parte, não investigado a fundo por desproporção de esforço: o padrão de preenchimento de `OUTRAS_DES` é atípico para um campo de texto livre (quase-vazio em 2015, ~100% preenchido em 2016-2017, 0% em 2018) — mais consistente com valor sentinela/comportamento de sistema do que resposta clínica real, mas isso não muda a decisão de descarte já tomada.
- **Volume real (Parquet comprimido, zstd) é muito menor que a estimativa em memória**: ~2-3 MB por ano, ~25 MB extrapolados para os 9 anos completos (2015-2023) — muito abaixo do limite gratuito de Git LFS (1 GB) ou de um arquivo do GitHub Releases (2 GB). Isso elimina a necessidade dessas ferramentas para este dataset (ver revisão na seção de Decision).

**Nota de validação empírica — cobertura do SIM (2026-08-02):** a construção do pipeline de ingestão revelou uma segunda dimensão de qualidade de dado não prevista nas notas anteriores: **cobertura irregular por UF×ano na fonte SIM**, distinta do right-censoring por idade do dado.

- Consulta ao catálogo do PySUS (sem download, `list_files`/`query`) para 27 UFs × 2015-2024 (270 combinações) encontrou **19 combinações (7%) sem arquivo disponível**: CE/2021, CE/2022, MT/2016, MG/2015, MG/2023, PE/2018, PE/2020, PE/2022, PE/2024, RJ/2019, RJ/2021, RJ/2023, RJ/2024, RO/2021, SC/2016, SP/2016, SP/2021, SP/2023, SP/2024.
- O padrão está espalhado por 8 estados sem um ano-corte único nem uma UF isolada — descarta a hipótese inicial de que fosse um caso específico de SP (ex.: fonte alternativa via Fundação SEADE); é mais consistente com lacunas irregulares de sincronização do espelho do catálogo remoto do PySUS.
- **Decisão**: os gaps não serão preenchidos por fonte alternativa (decisão explícita de não expandir escopo para cobrir uma limitação de qualidade de dado — a limitação em si é parte do que o projeto demonstra saber lidar). O silver/gold deve carregar uma coluna `status_cobertura_sim` (`disponível` / `ausente`) por UF×ano, e qualquer agregado nacional (ex.: taxa de reconciliação SINAN×SIM) deve declarar explicitamente o percentual de cobertura em que se baseia, em vez de apresentar um número nacional como se tivesse 100% de cobertura.
- Separadamente, foi identificado e documentado um bug de metadado no catálogo remoto do PySUS (arquivo `TUBEBR16.parquet`, do SINAN, com `group_id` nulo, causando retorno vazio silencioso via `sinan()`) — ver `docs/known-issues.md`. Esse é um problema de integridade de metadado da dependência de terceiros, distinto da cobertura irregular do SIM.

## Decision

Vamos usar **Tuberculose no Brasil, via SINAN Net, cruzado com o SIM (Sistema de Informação de Mortalidade)**, no recorte temporal de **2015 a 2023** — início ajustado para começar após a atualização de schema de 2015, garantindo uma única versão de ficha de notificação em toda a janela; fim ajustado para respeitar a margem de consolidação de aproximadamente dois anos antes da data de execução do projeto.

Anos fora dessa janela (2024 em diante) não serão descartados de forma silenciosa: a camada gold incluirá uma coluna `status_maturidade` (`fechado` / `provisório`) por ano, calculada a partir da regra de consolidação acima. Isso permite, no futuro, estender a análise a anos mais recentes com uma flag explícita de que o dado ainda está em consolidação, em vez de tratar o corte temporal como se esses anos simplesmente não existissem.

Perguntas que o pipeline responde:
- Pergunta epidemiológica: qual a incidência de TB e a taxa de abandono de tratamento por município/UF ao longo do tempo?
- Pergunta meta (o diferencial do projeto): qual a diferença entre casos de TB notificados no SINAN e óbitos por TB registrados no SIM, por região — ou seja, uma estimativa de subnotificação por reconciliação entre duas fontes independentes.

Extração via biblioteca `PySUS` (SINAN e SIM).

Infraestrutura de execução será dividida em duas categorias:

- **O que roda permanentemente (produção real do portfólio)**: 100% GitHub-nativo. Dados (bronze/silver/gold em Parquet) versionados diretamente no repositório Git — o volume real validado (~25 MB para 9 anos de SINAN-TB) está muito abaixo de qualquer limite que justificasse Git LFS ou GitHub Releases, então essas ferramentas foram descartadas por desnecessárias (não por indisponibilidade). Orquestração via GitHub Actions agendado; dashboard final publicado como site estático via GitHub Pages. Nenhum destes componentes tem custo, e nenhum exige cartão de crédito cadastrado.
- **O que prova competência em cloud (Azure)**: arquitetura de referência (ADLS Gen2 + Synapse Serverless SQL + Microsoft Purview) escrita como Infrastructure as Code (Bicep) e versionada no repositório, mas não mantida no ar de forma contínua. A validação de que o IaC funciona acontece uma única vez — subir os recursos, executar o pipeline apontando para lá, capturar evidência (prints/vídeo curto), e derrubar os recursos (`az group delete`) imediatamente depois. Exposição de custo é única, breve, e sob controle direto — nunca um serviço esquecido rodando.

## Consequences

### Positive

- A escolha de TB + reconciliação SINAN/SIM dá ao projeto um problema de qualidade de dado citável e documentado na literatura de saúde pública brasileira, não uma alegação genérica de "dado sujo".
- A reconciliação entre duas fontes (SINAN e SIM) é um exercício real de MDM/record linkage, alinhado diretamente com a experiência declarada de Victor em MDM e governança — mais forte como prova de competência do que tratar uma fonte única.
- Custo de infraestrutura é zero de forma garantida para o componente que fica permanentemente visível a recrutadores (GitHub), eliminando o risco de billing inesperado.
- A separação entre "o que roda sempre" (GitHub) e "o que prova cloud" (Azure, exposição pontual) permite reivindicar experiência real com Azure sem assumir risco financeiro contínuo.

### Negative

- O recorte 2015–2023 mantém uma anomalia de schema conhecida em 2015 (3 colunas legadas ausentes nos anos seguintes); essas colunas precisam ser explicitamente descartadas e documentadas no silver, não silenciosamente ignoradas.
- A regra de maturidade (`fechado` a partir de ~3 anos de idade, `provisório` antes disso) foi validada empiricamente só com dois pontos de fronteira (2023 maduro, 2024 imaturo); o valor exato do limiar entre 2 e 3 anos não foi determinado com precisão, mas é suficiente para a decisão prática deste projeto.
- Com volume real de ~25 MB, a arquitetura Medallion completa (bronze/silver/gold) é desproporcional ao volume de dado em si; isso precisa ser justificado explicitamente na documentação pública do projeto (a arquitetura demonstra prática de engenharia, não necessidade de escala) para não ser lida como over-engineering por um avaliador técnico.
- A demonstração em Azure não é "always-on": um avaliador não pode acessar a arquitetura em cloud a qualquer momento, apenas ver evidência gravada de que funcionou. Isso é uma prova mais fraca do que um ambiente permanentemente acessível, e precisa ser compensado por documentação e evidência de execução (vídeo/prints) de boa qualidade.
- Git LFS e GitHub Releases têm limites de tamanho (1GB e 2GB por arquivo, respectivamente); se o volume de dado bruto do recorte escolhido ultrapassar isso, será necessário amostrar ou agregar antes de versionar, o que precisa ser decidido e documentado explicitamente (não pode ser um corte silencioso).

### Neutral

- A escolha de excluir modelagem preditiva é mantida; a camada de análise final usa apenas estatística descritiva (taxas por 100 mil habitantes, comparação entre fontes), consistente com a decisão de não reivindicar competência em Ciência de Dados ainda não estudada formalmente.

## Alternatives Considered

### SINAN Dengue/Chikungunya como fonte primária

Considerado inicialmente por ter boa documentação de qualidade de dado e narrativa topical (mudança climática, epidemias recorrentes). Descartado em favor de TB porque o problema de subnotificação em dengue é majoritariamente de completude de campo dentro de uma única fonte, enquanto TB permite reconciliação entre duas fontes independentes (SINAN x SIM) — um problema de engenharia mais rico e mais alinhado ao perfil de MDM de Victor.

### Fontes já agregadas (OMS, Our World in Data)

Descartadas por deixarem pouco trabalho real de engenharia — o tratamento de sujeira e reconciliação já foi feito por terceiros, o que enfraquece a prova de competência que o projeto pretende demonstrar.

### Infraestrutura cloud always-on (Synapse dedicated pool, Fabric capacity, cluster Spark permanente)

Descartada por gerar custo fixo independente de uso, incompatível com a restrição de custo zero. Também descartada a opção de manter recursos serverless (ex: Synapse Serverless, Blob Storage dentro de free tier) rodando de forma contínua sem supervisão, porque fontes divergem sobre o comportamento de cobrança ao exceder cota de free tier no Azure, e a consequência de errar é financeira — não vale apostar nisso para um projeto de portfólio.

## Adendo — validação empírica da necessidade de SCD Type 2 na dimensão de município (2026-08-03)

A decisão original de usar SCD Type 2 para a dimensão de município (documentada na seção de Decision, camada silver) foi motivada por conhecimento genérico de domínio (códigos IBGE mudam ao longo do tempo), não por evidência observada nos dados do projeto. Validação empírica contra os 10 anos de bronze do SINAN-TB e as duas fontes de população IBGE encontrou **zero casos de mudança de código de município dentro da janela 2015-2024**, além do caso já conhecido e tratado (Boa Esperança do Norte/MT, ADR-003 — criação de município, não recodificação).

**Decisão mantida, com justificativa revisada**: SCD2 continua sendo implementada, não porque a janela observada exija, mas porque o pipeline é projetado para ser re-executado com anos futuros (orquestração via GitHub Actions agendado, já decidido nesta ADR) — mudança de código de município é um fenômeno real e documentado ao longo de décadas no Brasil, apenas não observado nesta amostra específica. A implementação é mantida mínima (sem lógica especulativa além do necessário para registrar corretamente o histórico observado), e este adendo documenta explicitamente que a suposição original não foi confirmada pelos dados — apenas re-justificada por um motivo diferente do que motivou a decisão inicial.

## Adendo — hipótese de maturidade do SIM testada e não confirmada (2026-08-03)

`status_maturidade_sim` foi adicionada (regra conservadora, mesmo critério de ~2 anos já usado para o SINAN-TB) para testar se os 4 casos onde SINAN > SIM na reconciliação (de 251 combinações UF×ano com cobertura) se explicavam por atraso de consolidação do SIM. Resultado: só 1 dos 4 casos (PB/2024) está em ano provisório; os outros 3 (AL/2018, AP/2023, MS/2023) persistem mesmo em anos "fechados" por esse critério — a hipótese de maturidade não explica a maioria dos casos reversos. Magnitude pequena em todos os 4 casos (-2 a -12 óbitos) e sem padrão geográfico ou temporal claro identificado. Tratado como anomalia estatística residual não resolvida, documentada explicitamente — não investigado além disso por desproporção entre esforço adicional e volume envolvido (4 de 251 combinações, 1,6%). `status_maturidade_sim` permanece na tabela gold como informação útil, mesmo não explicando integralmente o achado.

## References

- Pinheiro RS, Andrade VL, Oliveira GP. "Subnotificação da tuberculose no Sistema de Informação de Agravos de Notificação (SINAN)." Cad Saúde Pública 2012; 28:1559-68.
- "Sistema de Informação de Agravos de Notificação (Sinan): principais características da notificação e da análise de dados relacionada à tuberculose." Epidemiol. Serv. Saude, Brasília, 29(1):e2019017, 2020 — referência à atualização de schema (versão 5.0) em 2015.
- Portal de Dados Abertos do Estado de Minas Gerais, conjunto "Dados de Tuberculose" — referência ao atraso de consolidação de ~2 anos no SIM.
- Biblioteca PySUS (AlertaDengue/Fiocruz) — github.com/AlertaDengue/PySUS
- Documentação de free tier Azure (verificar limites vigentes antes de qualquer execução em cloud, dado que os termos mudam com frequência)