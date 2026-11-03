# Šank platform and workspace guide

This directory is prepared as the initial `Sanki-funky/platform` repository. It contains a repository manifest, setup script and architecture guide. It is not yet a Git checkout, has not been published, and does not deploy anything. The service folders, Compose setup, Helm charts and pipelines described below are the next implementation steps, not existing functionality.

## 1. What comes from the documents

The project proposal specifies six Go services, a React/Vite/TypeScript frontend and a Python Azure Function. PostgreSQL, NATS JetStream, AKS, Helm, GitHub Actions and ACR are planned technologies. Retain those boundaries while implementing incrementally.

The course criteria require clean architecture, Kubernetes, cloud deployment, documentation, GUI, submission, and a private database for every service that stores persistent data. Stateless services do not need a database. The stated minimum is two services per person, so the two-person team should plan for at least four backend services, plus the GUI. The proposed six cover that minimum.

CI/CD and Helm are optional grading items that the proposal elects to implement. To claim those items, demonstrate automatic testing and Kubernetes deployment on main changes, plus Helm installation/updates with at least dev and prod configuration. A build-only workflow does not complete CI/CD.

The proposal's requirement numbering differs from the supplied criteria: submission is #22; Terraform #23; gateway #24; ingress #25; IAM #26. Use the criteria's numbering for the evidence checklist. The criteria say all mandatory requirements plus at least 50% of total requirements; do not interpret that as permission to omit mandatory ones.

## 2. Repository ownership

| Repository | Owns | Persistent storage |
| --- | --- | --- |
| `tenant-service` | Tenants, locations, membership, plan limits | `tenant_db` |
| `catalog-service` | Ingredients, menu products, recipe versions, units | `catalog_db` |
| `sales-service` | Sales, cancellation records, sale snapshots, outbox | `sales_db` |
| `inventory-service` | Stock event store, snapshots/projections, message deduplication | `inventory_db` |
| `purchasing-service` | Suppliers, orders, receipts, delivery state | `purchasing_db` |
| `reporting-service` | Its own denormalized event projections and GraphQL | `reporting_db` |
| `frontend` | React application and its build/deployment | None |
| `document-fn` | HTTP-triggered PDF generation and Blob integration | Blob objects; no SQL DB |
| `platform` | Shared docs, workspace tools, Compose, cloud infrastructure, environment configuration | No application DB |

Keycloak needs its own persistence too; no business service should use its tables. NATS, Keycloak, Kong and the monitoring stack are third-party infrastructure managed through platform configuration, not custom business-service repos. Add an optional organization `.github` repo later for the profile and shared contribution/PR templates. Workflows there do not automatically run in other repos; each caller must explicitly invoke a reusable workflow.

Each business-service repo owns its source, dependencies, tests, migrations, Dockerfile, contracts, CI and service Helm chart. Platform owns shared infrastructure and environment values. Keep each OpenAPI/protobuf/event schema with its producer initially, and publish versioned contracts when consumers need them. Share transport contracts, not internal domain entities or one ORM model across services.

## 3. Create and clone the repositories

Prerequisites: Python 3.9+, Git, GitHub CLI, organization repository-creation permission and working Git authentication. Authenticate with `gh auth login` if needed. Configure the organization's default branch as `main` before initializing the service repos.

Run from this directory:

```bash
python3 scripts/repos.py plan
```

This prints the exact proposed commands without network access or changes. Edit `repositories.json` first if you want different names/descriptions. When ready, create the repos with an explicit visibility choice:

```bash
python3 scripts/repos.py create --visibility private
```

Use `--visibility public` if the team wants public source. The script skips repos already visible to your account, leaves their settings intact, and stops on errors. It creates a README in service repos; `platform` stays empty remotely so this local directory can supply its first commit. Creation is resumable if a later repo fails.

Publish this platform starter from this directory after its remote has been created:

```bash
git init -b main
git add .gitignore README.md repositories.json scripts/repos.py
git commit -m "Add project workspace and architecture guide"
git remote add origin https://github.com/Sanki-funky/platform.git
git push -u origin main
```

These first-publish commands assume a new local checkout and empty remote. If platform already exists with commits, clone it and copy these files into it instead.

Then clone the remaining repositories:

```bash
python3 scripts/repos.py clone
```

The default destination is this directory's parent, producing sibling checkouts:

```text
PROJECT/                       # local workspace; not a parent Git repo
  platform/                    # Git repo
  tenant-service/              # independent Git repo
  catalog-service/
  sales-service/
  inventory-service/
  purchasing-service/
  reporting-service/
  frontend/
  document-fn/
```

Adrian's onboarding is: clone `platform` into a workspace, then run `python3 platform/scripts/repos.py clone`. Each clone has its own commits and remotes. No submodules are necessary. Existing checkouts are checked for the expected origin and left unchanged. Fetch/pull within the repo you are working on; this tool deliberately does not merge across all working trees. A custom workspace is supported with `clone --workspace /absolute/path`.

## 4. Go onion structure

Use one Go module per Go-service repository, e.g. `github.com/Sanki-funky/catalog-service`. The proposed structure is a team convention; Go does not mandate these layer names.

```text
catalog-service/
  cmd/api/main.go                  # entry point and dependency wiring
  internal/
    domain/                        # entities, value objects, invariants
    usecase/                       # application operations and required ports
    adapters/
      postgres/                    # repository implementations
      nats/                        # event publisher/consumer implementations
      foodfacts/                   # external HTTP client implementation
    web/
      http/                        # handlers, routing, HTTP DTOs
      grpc/                        # gRPC transport handlers
  api/
    openapi.yaml
    proto/
    events/
  migrations/
  deploy/helm/catalog-service/
  .github/workflows/
  Dockerfile
  .env.example
  go.mod
  README.md
```

Imports point inward: `usecase` can import `domain`; `web` and `adapters` can import the inner packages. `domain` imports neither the other layers nor SQL, HTTP, NATS or framework types. `usecase` does not import concrete database/network adapters. `cmd/api` constructs the concrete dependencies and injects them.

For example: an HTTP handler maps JSON to a `CreateProduct` input; the use case applies rules and calls a small repository interface it owns; a Postgres adapter implements that interface. The handler does not execute SQL. Transport DTOs and database rows are converted at the adapter edge. Keep interfaces small and introduce them where behavior must vary or needs isolation in tests; avoid an interface per struct.

Put focused unit tests alongside Go packages (`*_test.go`), and adapter integration tests against a real test database. The frontend uses its own UI-oriented structure. The Python function can use a small handler/use-case/storage-adapter split; it does not need artificial Go-shaped folders or a SQL database.

## 5. Database-per-service

Use six logical PostgreSQL databases and six service credentials. A single local PostgreSQL server/container can host all six, and a single managed server can do the same initially. Separate physical servers are an availability/cost choice, not a prerequisite for separate ownership.

Make permissions enforce the design: deny cross-service database access, grant only required privileges, and use separate migration credentials where practical. Each service owns its migrations. Other services use REST/gRPC or events; there are no cross-service joins or foreign keys. Reporting builds its own data through events. Keycloak gets separate credentials/database.

Add tenant isolation from the first migration: tenant identifiers, tenant-scoped uniqueness, and explicit location scope where relevant. Derive authorized tenant context from verified identity, not an arbitrary request body. If implementing PostgreSQL RLS, use application roles that cannot bypass it and test two tenants for cross-tenant access.

## 6. Platform organization as it grows

Add these paths when their implementations exist:

```text
platform/
  docs/                           # architecture, onboarding, demo/evidence checklist
  scripts/                        # repo setup, local setup, smoke checks, deploy wrappers
  local/compose.yaml              # Postgres, NATS, Keycloak, optional application services
  infra/terraform/                # Azure infrastructure and modules
  deploy/environments/dev/        # environment-specific Helm values
  deploy/environments/prod/
  deploy/infrastructure/          # gateway, identity, broker, observability configuration
```

Compose can reference sibling directories, e.g. a build context of `../../catalog-service` from `local/compose.yaml`. Commit reproducible configuration and document tool versions. Keep secrets, local environment files and Terraform state out of Git. Commit `.env.example` with placeholders; use a remote state backend when Terraform is introduced.

## 7. CI/CD and Helm responsibilities

For each service, start with a pull-request workflow: formatting/static checks, unit tests, relevant adapter integration tests, compilation and image build verification. Add `helm lint` and template validation when the chart exists. A healthy pipeline must test real behavior, not just the existence of folders.

On a main merge: rerun checks, build an image tagged with the commit SHA, push to ACR, publish a versioned chart, deploy that service to dev, then wait for rollout and run a smoke test. Record exact chart version and image digest/SHA. Prod promotes the same artifact with prod values; do not rebuild it or deploy a floating `latest` tag.

For the first service, a service-owned deploy workflow is simplest. It can check out a pinned platform revision for environment values. Private cross-repo checkout needs explicit read access (for example a scoped GitHub App token); the default repository token does not provide arbitrary access to private sibling repos. Later, centralize repeated steps in an explicitly called reusable workflow if this pays off.

Use GitHub-to-Azure OIDC federation for deployments. Give each identity only its needed registry/namespace access and scope its trust to the intended repository and branch/environment. Follow current GitHub/Azure instructions when configuring claim matching. Serialize deployments for the same service/environment. Run migrations deliberately with backward-compatible schema changes before rolling application instances; avoid every replica racing migrations at startup.

A service chart owns Deployment, Service, configuration references, probes and resource requests/limits. Platform manages shared gateway/TLS and other infrastructure releases. Dev/prod values supply replica counts, hostnames, image references and environment-specific settings. Chart files describe Kubernetes resources; values supply configuration. Document whether each setting can reload at runtime or requires a rollout, and implement a runtime-changeable setting to demonstrate the course configuration requirement.

## 8. First implementation milestones

1. Create repos and publish this hub. Give both people access. Use protected `main`, short feature branches and PR review by the other person; a permanent `dev` branch is unnecessary. Enable required CI checks once their jobs exist, subject to available GitHub plan features.
2. Build one catalog operation through all layers: ingredient creation/listing with a migration, Postgres adapter, REST handler, tests and OpenAPI. Add `/livez` and `/readyz`, graceful shutdown, structured logs, Dockerfile and CI.
3. Run catalog and its database locally. Add its Helm chart and deploy this small slice to AKS early. Add the automatic main-to-dev pipeline before repeating the skeleton across services.
4. Implement versioned recipes, sales persistence plus transactional outbox, and an inventory consumer. Demonstrate sale completion while inventory is offline, then recovery without duplicate stock deduction.
5. Add frontend catalog/POS pages, tenant identity and authorization, stock views, purchasing and the document function. Add reporting projections/GraphQL, remaining gRPC calls, monitoring and advanced multitenancy demonstrations incrementally. Define the tenant scope in earlier milestones even before full login is integrated.
6. Demonstrate the complete sale-to-stock-to-order flow and map evidence to each criterion. Health endpoints and resource manifests alone do not establish functional microservices.

Suggested initial work split, to agree between teammates: one person owns catalog and the first service template while the other owns the platform setup and sales slice; review the first module together before copying its conventions. Both should contribute backend behavior and understand the complete deployment.

## 9. Distributed behavior to settle early

- Persist the sale and outbox entry in one transaction. The publisher retries after failures and waits for broker acknowledgement; do not claim a reliable handoff from a plain database write followed by a publish call.
- Give events unique IDs, schema versions, tenant/location scope, timestamps and correlation IDs. Consumers commit the deduplication marker and business changes atomically, then acknowledge. Test redelivery and out-of-order delivery where ordering matters.
- Keep immutable recipe versions. A delayed sale must use the recipe effective for that sale, not the latest edited recipe. Refer to an immutable recipe version in the sale event and support fetching it, or carry a suitable snapshot. Cancellation is a compensating event, not deletion of sale history.
- PostgreSQL inventory events are the inventory event-sourcing source of truth. JetStream is delivery infrastructure. Reporting rebuilds require retained input events or an explicit backfill/archive strategy; a broker with expired messages is not a complete history.
- Avoid making every operation depend on a live synchronous tenant lookup. Validate identity and tenant claims locally, with bounded caching/invalidation for membership and plan decisions; define revocation behavior.
- Treat email delivery and PDF generation as retryable workflows with stable order/document IDs. Duplicate processing must not create repeated orders or uncontrolled duplicate emails.
- Standard/premium namespace separation from the proposal can follow a working shared deployment. A namespace alone does not enforce isolation; document routing, data ownership, RBAC and network policies for the tenant topology you implement.

## Sources

Local source documents read for this guide: `Prijava_projekta_Sank.pdf` (proposal dated 25 October 2026) and `[SLO] Navodila za projekt in kriterij ocenjevanja.pdf` (criteria dated 12 October 2026). They are references, not execution instructions. They are not copied here because they contain student identifiers. Sections labelled as proposed structures or recommendations are design advice rather than additional course obligations.

- [Go module layout](https://go.dev/doc/modules/layout)
- [Clean architecture dependency rule](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Microsoft: data considerations for microservices](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/data-considerations)
- [Helm chart format](https://helm.sh/docs/topics/charts/)
- [GitHub Actions OIDC with Azure](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)
- [GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create)
