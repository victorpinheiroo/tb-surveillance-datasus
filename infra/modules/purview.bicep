// Módulo: Microsoft Purview — conta de governança de dados
// Referência: ADR-005 — validado apenas via `az bicep build`, NUNCA implantado.
//
// Esta é a peça que motivou a decisão de ADR-005: pesquisa sobre o modelo
// de cobrança do Purview encontrou um relato documentado de cobrança
// mesmo dentro de uso aparentemente coberto por cota gratuita, em um PoC
// de escopo pequeno — inconsistente com a exigência de custo zero
// garantido do projeto. Este módulo existe como prova de design, não
// como algo a ser executado.

@description('Nome da conta Purview. Deve ser globalmente único.')
param purviewAccountName string

@description('Região de implantação.')
param location string = resourceGroup().location

@description('Tags aplicadas ao recurso.')
param tags object = {
  project: 'tb-surveillance-datasus'
  purpose: 'iac-demonstration-only'
  status: 'never-deployed-cost-risk-identified'
}

resource purviewAccount 'Microsoft.Purview/accounts@2021-12-01' = {
  name: purviewAccountName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  // Sem bloco `sku`: não é mais uma propriedade gravável nessa API version
  // (Microsoft.Purview/accounts@2021-12-01) — mantê-lo compila com warning
  // (BCP073) e não teria efeito num deploy real. Capacidade do Data Map
  // deixou de ser configurada por SKU no provisionamento do recurso desde
  // a mudança de modelo de cobrança do Purview em jan/2025 (cobrança
  // passou a ser por consumo real de Data Map/scan, não por capacidade
  // reservada) — consistente com o próprio motivo de ADR-005 existir.
  properties: {
    publicNetworkAccess: 'Enabled' // demonstração apenas
  }
}

// Em uso real, o próximo passo seria registrar o storage account (ver
// storage.bicep) como fonte de dado no Data Map do Purview, e configurar
// um scan agendado — omitido deliberadamente aqui, já que isso é
// exatamente a operação que gera custo de scan (vCore-hours), e este
// módulo nunca é implantado de qualquer forma.

output purviewAccountId string = purviewAccount.id
output purviewAccountName string = purviewAccount.name
