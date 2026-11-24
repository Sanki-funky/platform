# The microservices

Each service owns one part of Šank. That gives us a clear place for each business rule and lets us deploy a service without releasing the whole app.

| Service | What it does | Database |
| --- | --- | --- |
| `tenant-service` | Companies, locations, memberships and plan limits | `tenant_db` |
| `catalog-service` | Ingredients, menu products, recipes and units | `catalog_db` |
| `sales-service` | Records sales and cancellations | `sales_db` |
| `inventory-service` | Tracks stock movements, counts and low-stock thresholds | `inventory_db` |
| `purchasing-service` | Suppliers, purchase orders and receiving goods | `purchasing_db` |
| `reporting-service` | Builds dashboard data and exposes GraphQL queries | `reporting_db` |

The React app lives in `frontend`. The Python function in `document-fn` generates PDFs and saves them to Blob Storage. It doesn't need a SQL database.

## Why separate databases?

A service can change its tables without breaking another service's SQL queries. Each service has its own database credentials and migrations. They can all use one PostgreSQL server to begin with; separate databases don't require separate servers.

Services ask each other for data through an interface or listen for events. They don't query each other's tables. Reporting keeps its own copies of the data it needs for dashboards.

Keycloak also needs its own database. Its tables belong to Keycloak.

## A sale as an example

When someone sells a cappuccino, sales records it and publishes a `sales.completed` event. Inventory uses the recipe to work out how much coffee and milk were used. If milk drops below its threshold, inventory publishes `stock.low`, and purchasing prepares an order draft.

The manager approves the order. Purchasing asks the document function for a PDF and sends it through the email provider. Receiving the delivery produces another event so inventory can add the stock. Reporting listens to the events and updates the dashboard.

These updates aren't all immediate. The till should still record a sale while inventory is unavailable; inventory catches up when it returns.

## Which connection do we use?

- **REST** handles frontend commands such as creating a product or completing a sale.
- **GraphQL** provides dashboard queries through reporting.
- **gRPC** handles direct internal queries, such as getting a recipe or checking stock.
- **NATS JetStream** carries events that other services can process later.

The frontend goes through the gateway. Keycloak handles login. NATS, Kong and Keycloak are existing tools we configure through platform.

## A few decisions to make early

Use immutable recipe versions. A sale processed tomorrow must use the recipe that applied when it happened, even if someone has since edited the amount of milk.

Give each event an ID and schema version, along with tenant/location scope. Consumers must handle receiving the same event twice. Store the processed-message marker and the resulting database changes in one transaction, then acknowledge the message.

Inventory's stored events are its history. JetStream delivers messages; rebuilding a reporting projection also needs retained events or a backfill source. Decide how long that history is kept.

Order sending needs stable IDs and retry handling too, so processing an event twice doesn't create two orders. A cancelled sale should produce a compensating event rather than erase the original record.
