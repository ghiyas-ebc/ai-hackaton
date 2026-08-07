# Azure — term mapping and provider-specific behaviour

## Plain language → service_id

| What they might say | service_id | Note |
|---|---|---|
| "backend", "API server" | `azure-container-apps` | default for modern stateless APIs |
| "big backend", "needs orchestration" | `aks` | |
| "small function", "automatic trigger" | `azure-functions` | |
| "VM", "legacy server" | `azure-vm` | |
| "web app", "app hosting" | `azure-app-service` | |
| "database", "relational database" | `azure-sql-database` | **SQL Server engine only.** If they need MySQL/PostgreSQL, the product is Azure Database for MySQL/PostgreSQL — say so explicitly |
| "global database", "NoSQL" | `azure-cosmos-db` | ask which API (Core/SQL, Cassandra, Mongo) |
| "cache" | `azure-cache-redis` | |
| "storage", "bucket" | `azure-blob-storage` | |
| "data warehouse" | `azure-synapse` | |
| "message queue" (must not lose messages) | `azure-service-bus` | |
| "events", "lightweight notifications" | `azure-event-grid` | |
| "batch ETL" | `azure-data-factory` | |
| "streaming" | `azure-stream-analytics` | |
| "AI", "machine learning" | `azure-ml` | |
| "load balancer" (no detail) | `azure-app-gateway` | default to L7; ask if they actually need pure L4 |
| "CDN", "global entry point" | `azure-front-door` | |
| "WAF", "web firewall" | — | not a node; a SKU on App Gateway/Front Door |
| "secret", "certificate" | `azure-key-vault` | |
| "VNet" | `azure-vnet` | |

## Azure behaviour that drives validation

- **L4 and L7 are separate products.** Load Balancer (L4) cannot terminate HTTP
  and cannot host a WAF. If path/host routing or a WAF is needed, the answer is
  Application Gateway (regional) or Front Door (global).
- **WAF is not a standalone service.** It is a policy/SKU on App Gateway or
  Front Door. `azure-waf` is treated as an alias and drawn as a badge, not a
  separate box.
- **Event Grid ≠ Service Bus.** Event Grid distributes lightweight events;
  Service Bus is a queue with delivery and ordering guarantees. When the
  description is ambiguous, ask: can losing a single message be tolerated?
- **Serverless needs VNet Integration** to reach private resources — the
  analogue of Serverless VPC Access on GCP.
- **A VNet is bound to one region**, unlike GCP's global VPC.
- **Azure SQL Database is SQL Server only.** This is where mapping mistakes most
  often occur when translating from Cloud SQL.
