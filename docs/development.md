# Working on a service

The Go services use the same basic onion structure. Business rules stay in the middle. Database and transport code sit around them, so we can change those details without rewriting the rules.

## The folders

```text
catalog-service/
  cmd/api/main.go
  internal/
    domain/
    usecase/
    adapters/
      postgres/
      nats/
    web/
      httpapi/
      grpc/
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

| Folder | What belongs there |
| --- | --- |
| `domain` | Entities, value objects and business rules |
| `usecase` | Operations such as creating a product, plus the interfaces they need |
| `adapters` | Implementations that talk to PostgreSQL, NATS or external APIs |
| `web` | HTTP/gRPC handlers and request/response mapping |
| `cmd/api` | Starts the app and connects the implementations to the use cases |

Dependencies point inward. Use cases can import domain code. Adapters and handlers can use the inner packages. Domain code doesn't know about SQL, HTTP or NATS, and use cases don't import concrete adapters.

For example, a handler reads a create-product request and calls a use case. The use case applies the rules and calls its repository interface. The PostgreSQL adapter implements that interface and saves the product. SQL stays in the adapter.

Use small interfaces where we need to swap an implementation or test behavior in isolation. We don't need an interface for every struct. Each service gets its own Go module, such as `github.com/Sanki-funky/catalog-service`.

The frontend has a UI-oriented structure. The Python function can stay small, with a handler, document-generation logic and a storage adapter.

## What to build first

1. Get one catalog operation working with a database migration, tests and a REST endpoint. Ingredient creation and listing are a useful start.
2. Add OpenAPI, health endpoints and Docker. Run it locally, then deploy it with Helm and set up its pipeline.
3. Agree on that first service's conventions before copying the structure into the others.
4. Build sales and inventory together. Test a sale while inventory is offline, then bring it back and check that stock is deducted once.
5. Add the UI and remaining workflows in small pieces. Keep a working demo as we go.

For reliable sale events, save the sale and its outbox entry in one database transaction. A background publisher retries delivery and waits for broker acknowledgement. This covers a crash between saving a sale and publishing it.

## Everyday development

Use short feature branches and ask the other person to review the PR before merging into `main`. Enable required CI checks once those jobs exist. GitHub plan features may affect which protection rules are available.

Keep Go unit tests beside the package as `*_test.go`. Test database adapters against a real test database. Each service README should explain how to run that service and its tests.

Include tenant scope in the first migrations. Resolve the authorized tenant through verified identity and check location access too. If we use PostgreSQL RLS, the app role must not bypass it; test access using two different tenants.

Membership and plan checks need a caching/revocation policy so every operation doesn't require a live call to tenant-service. The proposal's separate namespaces for premium tenants can follow later; routing, network policies and data isolation still need to be designed.
