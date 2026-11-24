# Course requirements

Our proposal describes what we want to build. The course criteria define what gets assessed. Keep the two separate when tracking progress.

The criteria require clean architecture and Kubernetes, cloud deployment, documentation and a GUI. Each service that stores persistent data needs its own database. Stateless services don't need one. Code and the report must also be submitted.

The minimum is two backend services per person, so we're planning for at least four plus the GUI as a two-person team. The proposal has six services.

CI/CD and Helm are optional grading items that we've chosen to implement. To claim them, we need automatic testing and Kubernetes deployment after main changes, plus Helm installations/updates with dev and prod configuration. A build-only workflow isn't the complete CI/CD item.

The proposal also includes event sourcing/CQRS, gRPC, GraphQL, NATS and the PDF function. We'll add those incrementally once the first service runs in the cloud. The criteria require all mandatory items and at least 50% of total requirements; completing optional work doesn't replace mandatory items.

## A numbering correction

The proposal's final requirement numbers differ from the criteria. Use these numbers in the report and evidence checklist:

| Requirement | Number in the criteria |
| --- | --- |
| Intermediate presentation | 21 |
| Project submission | 22 |
| Terraform | 23 |
| API Gateway | 24 |
| Ingress Controller | 25 |
| IAM, OAuth2 and OIDC | 26 |

## References

This documentation is based on the project proposal, `Prijava_projekta_Sank.pdf` (25 October 2026), and the course criteria, `[SLO] Navodila za projekt in kriterij ocenjevanja.pdf` (12 October 2026). The PDFs aren't copied into this repo. Folder layouts and implementation order are our working conventions.

- [Go module layout](https://go.dev/doc/modules/layout)
- [Clean architecture dependency rule](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Data ownership in microservices](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/data-considerations)
- [GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create)
