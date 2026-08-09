// Módulo: Azure Data Lake Storage Gen2
// Referência: ADR-005 — este template é validado apenas via `az bicep build`
// (compilação para ARM JSON, checagem de sintaxe), NUNCA implantado contra
// uma assinatura Azure real. Ver ADR-005 para o motivo da decisão.
//
// Estrutura: um storage account com hierarchical namespace habilitado
// (isHnsEnabled = true, o que efetivamente o torna ADLS Gen2 em vez de
// Blob Storage padrão), com três containers refletindo as camadas
// Medallion já usadas no pipeline local (bronze/silver/gold).

@description('Nome do storage account. Deve ser globalmente único, 3-24 caracteres, apenas letras minúsculas e números.')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Região de implantação.')
param location string = resourceGroup().location

@description('Tags aplicadas ao recurso, para rastreabilidade de custo/propósito.')
param tags object = {
  project: 'tb-surveillance-datasus'
  purpose: 'iac-demonstration-only'
  status: 'never-deployed'
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS' // redundância local — suficiente para demonstração, não produção real
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true // habilita namespace hierárquico = ADLS Gen2, não Blob Storage padrão
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource bronzeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'bronze'
  properties: {
    publicAccess: 'None'
  }
}

resource silverContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'silver'
  properties: {
    publicAccess: 'None'
  }
}

resource goldContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'gold'
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output primaryDfsEndpoint string = storageAccount.properties.primaryEndpoints.dfs
