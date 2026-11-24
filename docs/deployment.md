# Deploying Šank

The plan is to run the Go services and frontend on Azure Kubernetes Service. GitHub Actions builds and tests the code, ACR stores the images, and Helm installs them. The document function is deployed separately to Azure Functions.

This is the deployment plan. The charts and pipelines still need to be implemented.

## What happens on a PR?

Run formatting and static checks, then tests and compilation. Check that the Docker image builds. Once a Helm chart exists, lint it and validate its rendered templates too.

## What happens after a merge?

A merge into `main` should build an image tagged with the commit SHA, push it to ACR and deploy the service to dev. Wait for the rollout and run a smoke test, so a successful build doesn't get mistaken for a successful deployment.

Keep a record of the image digest and chart version. Production should use that same built artifact with production values. Avoid a floating `latest` tag.

## Where do the Helm files go?

The service repo owns its chart, including its Deployment, Service and health probes. It also defines resource requests/limits and references to configuration and secrets.

Platform holds the environment values and configuration for shared infrastructure. Dev and prod values can set hostnames, replica counts and image references differently. Helm uses chart templates and values to produce Kubernetes manifests.

Start with service-owned deployment workflows. If a workflow needs files from a private platform repo, give it explicit read access and pin the revision it checks out. A repo's default GitHub token doesn't automatically have access to its private siblings.

## Configuration and access

Use GitHub-to-Azure OIDC for deployment authentication. Scope access to the intended repository and environment, and give each deployment identity only the permissions it needs. Follow the current provider instructions when setting up the trust relationship.

Keep secrets and local `.env` files out of Git. Commit an `.env.example` with placeholders. Terraform state needs a remote backend once we introduce Terraform; local state files stay out of Git too.

Run migrations as a deliberate deployment step. Use backward-compatible changes so old and new instances can overlap during a rollout. Serialize deployments for the same service and environment.

Document each configuration setting and whether changing it requires a restart. Include a runtime-changeable setting for the course configuration requirement.

## Shared tools

Platform will configure the gateway and TLS, Keycloak, NATS, and the monitoring stack. Add structured application logs early; central collection and dashboards can follow once the first deployment works.

- [Helm chart format](https://helm.sh/docs/topics/charts/)
- [GitHub Actions OIDC with Azure](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)
