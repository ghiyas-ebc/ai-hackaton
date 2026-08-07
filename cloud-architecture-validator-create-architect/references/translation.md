# Cross-provider translation

## The correct order

1. **Drop connectors from the source architecture.** Serverless VPC Access,
   Cloud SQL Auth Proxy, Private Service Connect, VNet Integration, Private Link.
2. **Translate only functional nodes.**
3. **Stop at every choice point.** If a node has several equivalents, ask.
4. **Re-validate against the target provider.** Whatever connectors are needed
   will emerge from that provider's own rules.

`scripts/translate.py` already does all of this, including reconnecting
connections that previously ran through a connector (`contracted_paths` in the
output).

## Why connectors are not translated

Connector requirements are a property of the target provider, not of the source
architecture. Translating `cloud-run → serverless-vpc-access → cloud-sql`
node-by-node produces an Azure connector in a position that may well be wrong,
and simultaneously hides the possibility that Azure needs no connector there at
all — or needs one somewhere else. Drop them, and let the target rules decide.

## Equivalence levels

| Level | Meaning | Obligation |
|---|---|---|
| `EXACT` | close to 1:1 | — |
| `CLOSE` | strong match, operational differences exist | surface the caveats |
| `PARTIAL` | one side covers more or less than the other | **must** surface caveats before drawing |

## The traps that catch people most often

- **Spanner → Cosmos DB.** Looks reasonable, is wrong. Spanner is relational
  with strong consistency; Cosmos DB is multi-model NoSQL. The closest relational
  equivalent is Azure SQL Hyperscale, and even that is not a full match.
- **Cloud Load Balancing → Azure Load Balancer.** Wrong whenever the source
  architecture uses L7 features. Three different candidates; you have to ask.
- **Pub/Sub → just one of them.** Pub/Sub merges two patterns that Azure splits.
  Answering with one of them without asking is guessing.
- **Cloud SQL → Azure SQL Database** without checking the engine. If the source
  is PostgreSQL, the equivalent is a different product.
- **Cloud Armor as a separate node on Azure.** It becomes a SKU on the gateway.

## When no equivalent exists

Do not assemble one from general knowledge. State that no equivalent for that
service is recorded in the knowledge graph and that engineering needs to decide
it. A wrong-but-confident equivalent is more dangerous than "no data yet" —
because the first one gets forwarded to the client.
