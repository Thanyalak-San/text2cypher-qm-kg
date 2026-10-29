# Schema reference: concrete production quality management graph

Every node label in the graph, what it represents, and its properties.
Relationships and their directions are in `relationship_directions.md`.

Naming conventions:
- Labels starting with **`Standard`** describe what the applicable standards specify (requirements, types, properties). They are reference knowledge, not records from the plant.
- Labels starting with **`Planned`** or **`Production`** describe the plant's own production plan and resources.
- Labels starting with **`Monitored`** describe resources (e.g. constituents) actually being processed or transformed during production.
  *Example: 4 kg of cement is planned to be used (`Planned` labels), but 4.5 kg is actually used (`Monitored` labels).*
- Label names are case-sensitive and must be written exactly as below, including `IntermediatedProduct`.
- Every node has a `name` (STRING). Most also have an `id` (STRING), an internal identifier with no meaning for queries.

## Standards and requirements

| Label | What it represents | Properties |
|---|---|---|
| `ComplianceStandard` | A published standard that specifies requirements or test methods | `name`, `id` |
| `StandardConcreteConstituent` | A constituent of concrete as defined by the standards (the material in general, not a delivered lot) | `name`, `id` |
| `StandardCementType` | A type of cement defined by the standards | `name`, `id` |
| `StandardCementProperty` | A property of cement that the standards specify | `name`, `id` |
| `StandardAggregateProperty` | A property of aggregate that the standards specify | `name`, `id` |
| `StandardMixingWaterType` | A type or source of mixing water defined by the standards | `name`, `id`, `isAllowed` (BOOLEAN: whether the standards permit this water for concrete) |
| `StandardMixingWaterProperty` | A property of mixing water that the standards specify | `name`, `id`, `pHValue` (FLOAT: specified pH limit, where one applies), `unit` (STRING: unit of the specified limit) |
| `StandardFreshConcreteProperty` | A property of fresh (unhardened) concrete | `name`, `id` |
| `StandardHardenedConcreteProperty` | A property of hardened concrete | `name`, `id` |
| `StandardCuringEnvironment` | An environmental condition during curing | `name`, `id` |

## Mix design and testing

| Label | What it represents | Properties |
|---|---|---|
| `DesignedMixProportion` | A mix design parameter used when proportioning the concrete mix | `name`, `id` |
| `FreshConcreteTest` | A test method applied to fresh concrete | `name`, `id` |
| `MixingWaterInspection` | A group of checks carried out on mixing water before use | `name`, `id` |

## Production plan and resources

| Label | What it represents | Properties |
|---|---|---|
| `PlannedTask` | A stage of the planned production process | `name`, `id` |
| `ProductionMachine` | A machine used in production | `name`, `id`, `batchSize` (INTEGER: planned batch size handled by the machine) |
| `IntermediatedProduct` | A product produced by a production stage (an intermediate state of the concrete or block) | `name`, `id` |
| `MonitoredConcreteConstituent` | A constituent material actually being processed during production | `name`, `id`, `type` (STRING: subtype, where one applies; may be null) |
| `ConstituentStorage` | A storage location for constituent materials | `name`, `id` |
| `QualityInspectionTask` | A planned quality inspection | `name`, `inspection_method` (STRING: how the inspection is carried out) |

## People, customers and orders

| Label | What it represents | Properties |
|---|---|---|
| `InternalPersonnel` | A member of the plant's own staff | `name`, `role` (STRING: job role), `shift` (STRING: working shift, where assigned), `access_level` (STRING) |
| `ExternalClient` | A person or organisation outside the plant, such as a customer | `name`, `role` (STRING), `organisation` (STRING), `customer_id` (STRING: only for customers), `access_level` (STRING) |
| `CustomerOrder` | An order placed by a customer | `name`, `order_id` (STRING), `product_type` (STRING), `requestedQuantity` (INTEGER), `requestedDue_date` (DATE) |
| `ProductionProject` | A production project planned to fulfil an order | `name`, `project_id` (STRING), `placedOrder_date` (STRING), `expectedDue_date` (STRING) |

## Property types to watch

- `CustomerOrder.requestedDue_date` and the `PLACES_ORDER` relationship's `placedOrder_date` are **DATE** values.
- `ProductionProject.placedOrder_date` and `ProductionProject.expectedDue_date` are **STRING** values in `YYYY-MM-DD` form, not dates. Convert them with `date(...)` before comparing them with DATE values.
- `StandardMixingWaterType.isAllowed` is a BOOLEAN: compare it with `true` or `false`, not with strings.
- `ProductionMachine.batchSize` and `CustomerOrder.requestedQuantity` are INTEGER values.
