# Where things go

We keep the services next to platform so we can work on them independently and still run the whole project locally.

```text
PROJECT/
  platform/
    README.md
    repositories.json
    scripts/
    docs/
  tenant-service/
  catalog-service/
  sales-service/
  inventory-service/
  purchasing-service/
  reporting-service/
  frontend/
  document-fn/
```

Each service folder has its own Git history. The intended setup is for `platform/` to have its own Git checkout too, with `PROJECT/` acting as the workspace. We don't need submodules for this.

If you've initialized the platform Git repo in `PROJECT/` instead, the service checkouts will appear as untracked folders there. Keep them out of platform commits. The repo script doesn't move existing folders or change where Git was initialized.

## What belongs in platform

Shared project docs live in `docs/`. The repository script lives in `scripts/`, with its list of repositories in `repositories.json`.

As we implement the local setup and deployment, we'll add:

| Path | What it's for |
| --- | --- |
| `local/compose.yaml` | Running PostgreSQL, NATS and the app locally |
| `infra/terraform/` | Creating the Azure infrastructure |
| `deploy/environments/dev/` | Helm values for development |
| `deploy/environments/prod/` | Helm values for production |
| `deploy/infrastructure/` | Shared tools such as Keycloak, Kong and monitoring |

Those paths are planned. They don't exist yet. A Compose file in `local/` can use `../../catalog-service` as a build context to reach the catalog checkout.

## What stays with a service

Each service owns its source code, tests and database migrations. Its Dockerfile, Helm chart and GitHub Actions workflows live in that repo too. That keeps a service change and its deployment changes together.

API contracts belong to the service that provides them: OpenAPI for REST, protobuf for gRPC and schemas for events. Consumers use versioned contracts. We don't share database models or internal domain entities between services.

An organization `.github` repo can be added later for a profile and shared templates. Reusable workflows still need to be called explicitly by each repo.
