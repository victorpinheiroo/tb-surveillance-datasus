# Azure Infrastructure (Reference Architecture — Code Only)

These Bicep templates describe the Azure reference architecture referenced in the project's [README](../README.md): ADLS Gen2 → Synapse Serverless SQL → Microsoft Purview.

**These templates have never been deployed against a real Azure subscription, and are not intended to be.** See [ADR-005](../docs/adrs/ADR-005-azure-demonstration-scope.md) for the full reasoning: research into Microsoft Purview's pricing model found a documented case of unexpected charges even within a small-scale proof-of-concept scan, which conflicts with this project's zero-cost-exposure constraint (established in ADR-001). The templates exist as a reviewable design artifact, not as an executed deployment.

## Structure

```
main.bicep           # orchestrator, wires the three modules together
modules/
  storage.bicep       # ADLS Gen2 (bronze/silver/gold containers)
  synapse.bicep        # Synapse workspace + serverless SQL pool
  purview.bicep         # Purview account (Data Map only — no scan configured)
```

## How this was validated

Syntax-only, offline, no Azure account required:

```bash
az bicep build --file infra/main.bicep
```

This compiles the Bicep templates to ARM JSON and surfaces syntax errors. It does **not** validate deployment-time concerns (resource name availability, quota, region support) — that would require an actual deployment, which this project deliberately avoids.

## If you wanted to actually deploy this

Not recommended without your own cost review, but for reference:

```bash
az group create --name rg-tb-datasus --location <region>
az deployment group create \
  --resource-group rg-tb-datasus \
  --template-file infra/main.bicep \
  --parameters sqlAdministratorLoginPassword=<secure-value>
```
