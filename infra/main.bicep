// Arquitetura de referência Azure — orquestrador principal
// Referência: ADR-001 (arquitetura), ADR-005 (decisão de nunca implantar)
//
// Este arquivo NUNCA foi executado contra uma assinatura Azure real.
// Validação feita exclusivamente via:
//     az bicep build --file main.bicep
// (compila para ARM JSON e reporta erro de sintaxe — não requer login
// ou assinatura Azure).
//
// Arquitetura: ADLS Gen2 (bronze/silver/gold) -> Synapse Serverless SQL
// (camada de consulta) -> Microsoft Purview (catálogo/governança).
// Mesma lógica de camadas já implementada localmente no pipeline
// (ver transformation/), reproduzida aqui como design de referência cloud.

targetScope = 'resourceGroup'

@description('Prefixo usado para nomear os recursos (deve ser curto, já que storage account tem limite de 24 caracteres).')
@minLength(3)
@maxLength(11)
param namePrefix string = 'tbdatasus'

@description('Região de implantação.')
param location string = resourceGroup().location

@description('Login do administrador SQL do Synapse.')
param sqlAdministratorLogin string = 'tbadmin'

@description('Senha do administrador SQL do Synapse. Em uso real: referência a Key Vault, nunca texto puro.')
@secure()
param sqlAdministratorLoginPassword string

var tags = {
  project: 'tb-surveillance-datasus'
  purpose: 'iac-demonstration-only'
  status: 'never-deployed'
  managedBy: 'bicep'
}

module storage 'modules/storage.bicep' = {
  name: 'storageDeployment'
  params: {
    storageAccountName: '${namePrefix}dl' // "dl" = data lake
    location: location
    tags: tags
  }
}

module synapse 'modules/synapse.bicep' = {
  name: 'synapseDeployment'
  params: {
    workspaceName: '${namePrefix}-synapse'
    location: location
    dataLakeStorageAccountName: storage.outputs.storageAccountName
    sqlAdministratorLogin: sqlAdministratorLogin
    sqlAdministratorLoginPassword: sqlAdministratorLoginPassword
    tags: tags
  }
}

module purview 'modules/purview.bicep' = {
  name: 'purviewDeployment'
  params: {
    purviewAccountName: '${namePrefix}-purview'
    location: location
    tags: tags
  }
}

output storageAccountName string = storage.outputs.storageAccountName
output synapseServerlessSqlEndpoint string = synapse.outputs.serverlessSqlEndpoint
output purviewAccountName string = purview.outputs.purviewAccountName
