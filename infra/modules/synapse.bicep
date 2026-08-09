// Módulo: Azure Synapse Analytics — workspace com Serverless SQL Pool
// Referência: ADR-005 — validado apenas via `az bicep build`, nunca implantado.
//
// O pool SQL serverless é criado automaticamente com todo workspace Synapse
// (não precisa de recurso separado) — cobrança é por dado escaneado por
// query, não por capacidade reservada, o que era a característica que
// tornava esta peça de baixo risco (ainda que não zero-risco, daí a
// decisão em ADR-005 de não implantar mesmo assim).

@description('Nome do workspace Synapse. Deve ser globalmente único.')
param workspaceName string

@description('Região de implantação.')
param location string = resourceGroup().location

@description('Nome do storage account ADLS Gen2 já existente (ver storage.bicep) usado como data lake padrão do workspace.')
param dataLakeStorageAccountName string

@description('Nome do container usado como filesystem padrão do workspace (recomendado: um container dedicado, ex. "synapse", separado de bronze/silver/gold).')
param dataLakeFilesystemName string = 'synapse'

@description('Login do administrador SQL do workspace.')
param sqlAdministratorLogin string

@description('Senha do administrador SQL — em uso real, isto viria de um Key Vault reference, nunca de texto puro no parâmetro. Ver nota abaixo.')
@secure()
param sqlAdministratorLoginPassword string

@description('Tags aplicadas ao recurso.')
param tags object = {
  project: 'tb-surveillance-datasus'
  purpose: 'iac-demonstration-only'
  status: 'never-deployed'
}

// Referência ao storage account já existente (não recriado aqui — este
// módulo assume que storage.bicep já foi "implantado", hipoteticamente).
resource dataLakeStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: dataLakeStorageAccountName
}

resource synapseWorkspace 'Microsoft.Synapse/workspaces@2021-06-01' = {
  name: workspaceName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    defaultDataLakeStorage: {
      accountUrl: dataLakeStorageAccount.properties.primaryEndpoints.dfs
      filesystem: dataLakeFilesystemName
    }
    sqlAdministratorLogin: sqlAdministratorLogin
    sqlAdministratorLoginPassword: sqlAdministratorLoginPassword
    publicNetworkAccess: 'Enabled' // demonstração apenas; em uso real, restringir via private endpoint
  }
}

// Regra de firewall permitindo acesso de serviços Azure — necessária para
// o próprio pipeline (rodando via GitHub Actions, fora da rede Azure)
// conseguir gravar/consultar dado, caso este módulo fosse implantado.
resource firewallRuleAllowAzureServices 'Microsoft.Synapse/workspaces/firewallRules@2021-06-01' = {
  parent: synapseWorkspace
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output workspaceId string = synapseWorkspace.id
output workspaceName string = synapseWorkspace.name
output serverlessSqlEndpoint string = synapseWorkspace.properties.connectivityEndpoints.sqlOnDemand
