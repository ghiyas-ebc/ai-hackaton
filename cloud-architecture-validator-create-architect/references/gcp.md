# GCP — term mapping and provider-specific behaviour

## Plain language → service_id

Non-technical users rarely name products precisely. Use this as a heuristic, and
**state the assumption** whenever the mapping wasn't explicit in what they said.

| What they might say | service_id | Note |
|---|---|---|
| "backend", "API server", "app server" | `cloud-run` | default for modern stateless APIs |
| "big backend", "needs orchestration" | `gke-autopilot` | offer as an alternative to Cloud Run |
| "small function", "automatic trigger" | `cloud-functions` | |
| "VM", "legacy server", "need full control" | `compute-engine` | |
| "database", "relational database" | `cloud-sql` | ask which engine (MySQL/PostgreSQL/SQL Server) — this matters when translating to Azure |
| "global database" | `spanner` | confirm they really need strong cross-region consistency; Spanner is expensive |
| "NoSQL database", "for a mobile app" | `firestore` | |
| "time-series", "IoT", "high throughput" | `bigtable` | |
| "cache", "session store" | `memorystore` | reachable only from inside the VPC |
| "storage", "bucket", "store files" | `cloud-storage` | |
| "data warehouse", "reporting", "dashboard" | `bigquery` | |
| "queue", "events", "async notifications" | `pubsub` | |
| "data pipeline", "ETL", "streaming" | `dataflow` | |
| "AI", "machine learning", "model" | `vertex-ai` | |
| "load balancer", "public gateway" | `cloud-load-balancing` | |
| "firewall", "web attack protection" | `cloud-armor` | a policy on the LB, not a separate hop |
| "password", "API key", "credentials" | `secret-manager` | |
| "VPC", "private network" | `vpc` | |

## GCP behaviour that drives validation

- **Serverless compute runs outside the customer VPC.** Cloud Run, Cloud
  Functions, and App Engine need Serverless VPC Access to reach private
  resources. This is the single most common cause of an architecture that looks
  right but doesn't work.
- **Cloud SQL has both a public and a private endpoint.** Connecting over the
  public endpoint will not error, but it almost always fails a security review.
  The validator flags this as WARNING at layer 1 and escalates it to ERROR at
  layer 2 when the architecture contains no private connector at all.
- **Memorystore has no public endpoint.** From serverless compute this is a
  genuine ERROR, not merely a weaker security posture.
- **Cloud Load Balancing merges L4 and L7 into one global product.** This is the
  main source of difficulty when translating to Azure, which splits them.
- **A GCP VPC is global**, with per-region subnets. A multi-region architecture
  that needs one VPC on GCP will need several VNets plus peering on Azure.
