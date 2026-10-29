# Relationship directions: concrete production quality management graph

Every relationship in the graph, written as `(:Start)-[:TYPE]->(:End)`.
Each pattern below is the only direction in which that relationship exists; a pattern written the other way round matches nothing.
Node labels and their properties are in `schema_reference.md`.

How to read a pattern:
- `(a)-[:TYPE]->(b)` and `(b)<-[:TYPE]-(a)` are the same pattern; the arrow, not the order in which the nodes are written, gives the direction.
- The same relationship type can connect several pairs of labels. Use the labels on both ends to pick the right one.

20 relationship types, 51 patterns.

## APPROVED_BY

Read as: the project is approved by the person.

```
(:ProductionProject)-[:APPROVED_BY]->(:InternalPersonnel)
```

## ASSIGNED_TO

Read as: the person is assigned to the machine or inspection task.

```
(:InternalPersonnel)-[:ASSIGNED_TO]->(:ProductionMachine)
(:InternalPersonnel)-[:ASSIGNED_TO]->(:QualityInspectionTask)
```

## CLASSIFIED_AS

Read as: the constituent can be classified as the type.

```
(:StandardConcreteConstituent)-[:CLASSIFIED_AS]->(:StandardCementType)
(:StandardConcreteConstituent)-[:CLASSIFIED_AS]->(:StandardMixingWaterType)
```

## COMPLIES_WITH

Read as: the item must comply with the standard; the standard is always at the end.

```
(:FreshConcreteTest)-[:COMPLIES_WITH]->(:ComplianceStandard)
(:StandardAggregateProperty)-[:COMPLIES_WITH]->(:ComplianceStandard)
(:StandardCementProperty)-[:COMPLIES_WITH]->(:ComplianceStandard)
(:StandardFreshConcreteProperty)-[:COMPLIES_WITH]->(:ComplianceStandard)
(:StandardHardenedConcreteProperty)-[:COMPLIES_WITH]->(:ComplianceStandard)
(:StandardMixingWaterProperty)-[:COMPLIES_WITH]->(:ComplianceStandard)
```

## HAS_PROPERTY

Read as: the item has the property; the item is at the start, the property at the end.

```
(:IntermediatedProduct)-[:HAS_PROPERTY]->(:StandardFreshConcreteProperty)
(:IntermediatedProduct)-[:HAS_PROPERTY]->(:StandardHardenedConcreteProperty)
(:StandardCementType)-[:HAS_PROPERTY]->(:StandardCementProperty)
(:StandardConcreteConstituent)-[:HAS_PROPERTY]->(:StandardAggregateProperty)
(:StandardMixingWaterType)-[:HAS_PROPERTY]->(:StandardMixingWaterProperty)
```

## INCLUDES

Read as: the inspection includes a check of the property.

```
(:MixingWaterInspection)-[:INCLUDES]->(:StandardMixingWaterProperty)
```

## INFLUENCED_BY

Read as: the start is influenced by the end: the affected item points to what influences it.

```
(:DesignedMixProportion)-[:INFLUENCED_BY]->(:DesignedMixProportion)
(:DesignedMixProportion)-[:INFLUENCED_BY]->(:StandardAggregateProperty)
(:DesignedMixProportion)-[:INFLUENCED_BY]->(:StandardMixingWaterProperty)
(:StandardCementProperty)-[:INFLUENCED_BY]->(:DesignedMixProportion)
(:StandardCementProperty)-[:INFLUENCED_BY]->(:StandardCementProperty)
(:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(:DesignedMixProportion)
(:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(:StandardAggregateProperty)
(:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(:StandardCementProperty)
(:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(:StandardCuringEnvironment)
(:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(:StandardFreshConcreteProperty)
(:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(:StandardMixingWaterProperty)
(:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(:DesignedMixProportion)
(:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(:StandardAggregateProperty)
(:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(:StandardCementProperty)
(:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(:StandardCuringEnvironment)
(:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(:StandardFreshConcreteProperty)
(:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(:StandardHardenedConcreteProperty)
```

## MEASURED_FROM

Read as: the start property is measured from the end property.

```
(:StandardAggregateProperty)-[:MEASURED_FROM]->(:StandardAggregateProperty)
```

## PERFORMED_AT

Read as: the inspection task is performed at the production stage.

```
(:QualityInspectionTask)-[:PERFORMED_AT]->(:PlannedTask)
```

## PLACES_ORDER

Read as: the client places the order.
Relationship properties: `placedOrder_date` (DATE).

```
(:ExternalClient)-[:PLACES_ORDER]->(:CustomerOrder)
```

## PLANNED_FROM

Read as: the project is planned from the order.

```
(:ProductionProject)-[:PLANNED_FROM]->(:CustomerOrder)
```

## PRECEDES

Read as: the start stage comes before the end stage (earlier to later).

```
(:PlannedTask)-[:PRECEDES]->(:PlannedTask)
```

## PROCESSED_ON

Read as: the production stage is processed on the machine.

```
(:PlannedTask)-[:PROCESSED_ON]->(:ProductionMachine)
```

## PRODUCES

Read as: the production stage produces the product.

```
(:PlannedTask)-[:PRODUCES]->(:IntermediatedProduct)
```

## REQUIRES

Read as: the water type requires the inspection.

```
(:StandardMixingWaterType)-[:REQUIRES]->(:MixingWaterInspection)
```

## SPECIFIES

Read as: the standard specifies the item; the standard is always at the start.

```
(:ComplianceStandard)-[:SPECIFIES]->(:MixingWaterInspection)
(:ComplianceStandard)-[:SPECIFIES]->(:StandardCementType)
(:ComplianceStandard)-[:SPECIFIES]->(:StandardConcreteConstituent)
(:ComplianceStandard)-[:SPECIFIES]->(:StandardMixingWaterType)
```

## STORED_IN

Read as: the constituent is stored in the storage location.

```
(:MonitoredConcreteConstituent)-[:STORED_IN]->(:ConstituentStorage)
```

## SUPERVISES

Read as: the start person supervises the end person.

```
(:InternalPersonnel)-[:SUPERVISES]->(:InternalPersonnel)
```

## TESTED_IN

Read as: the property is tested in the test method.

```
(:StandardFreshConcreteProperty)-[:TESTED_IN]->(:FreshConcreteTest)
```

## USED_IN

Read as: the material or product is used in the production stage.

```
(:IntermediatedProduct)-[:USED_IN]->(:PlannedTask)
(:MonitoredConcreteConstituent)-[:USED_IN]->(:PlannedTask)
```
