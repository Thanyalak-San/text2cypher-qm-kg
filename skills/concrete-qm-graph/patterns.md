# Query patterns by type of question

Worked queries for each type of question, classified by **query complexity** (how much Cypher structure the
answer needs) and **reasoning depth** (how many inferential steps it needs). Find the type closest to the
question, then adapt the pattern using the labels in `schema_reference.md` and the directions in
`relationship_directions.md`.

| Complexity | Meaning |
|---|---|
| Low | one MATCH pattern with minimal filtering |
| Medium | several MATCH patterns, aggregation, or multi-hop traversal |
| High | compound conditions across several contexts, including temporal logic |

| Reasoning depth | Meaning |
|---|---|
| Low | retrieve one node–relationship–node triple |
| Medium | several steps with conditions and filters |
| High | sequential conditioning, aggregation, comparison and selection |

Each pattern was written for a quality assurance (A), quality control (C) or quality improvement (I) question;
the source question is noted. Most source questions ask about plant records the graph does not hold, so they
were adapted into a question the graph can answer. Where no source question fits a type, the pattern was
written as a question of that QM stage.

---

## 1. Low complexity, low depth: one triple

Source: C19 "Which mixer was used to produce each batch of fresh concrete?", adapted.
Question: In which production stage is each intermediate product used?

```cypher
MATCH (ip:IntermediatedProduct)-[:USED_IN]->(t:PlannedTask)
RETURN ip.name AS Product, t.name AS Stage
```

Technique: a single pattern; return one row per pair.

## 2. Low complexity, medium depth: one pattern with a condition

Source: no matching A, C or I question; written as a quality improvement question to represent this type.
Question: Which aggregate properties influence the consistency of fresh concrete?

```cypher
MATCH (f:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(a:StandardAggregateProperty)
WHERE f.name = 'Consistency'
RETURN collect(DISTINCT a.name) AS AggregateProperties
```

Technique: filter one end of the pattern by name; the affected property is at the start of `INFLUENCED_BY`.

## 3. Medium complexity, low depth: aggregation per group

Source: no matching A, C or I question; written as a quality assurance question to represent this type.
Question: How many cement properties influence each hardened concrete property, and which are they?

```cypher
MATCH (h:StandardHardenedConcreteProperty)-[:INFLUENCED_BY]->(c:StandardCementProperty)
RETURN h.name AS HardenedProperty,
       count(DISTINCT c) AS NumberOfCementProperties,
       collect(DISTINCT c.name) AS CementProperties
ORDER BY NumberOfCementProperties DESC, HardenedProperty
```

Technique: group by the node you return; `count(DISTINCT …)` and `collect(DISTINCT …)` avoid double counting.

## 4. Medium complexity, medium depth: multi-hop with a condition

Source: I4 "Which quality issues were traced back to mix design parameters?", adapted.
Question: Which aggregate properties influence the water absorption of fresh concrete, and which mix design
parameters do those aggregate properties in turn influence?

```cypher
MATCH (f:StandardFreshConcreteProperty {name: 'Water absorption'})-[:INFLUENCED_BY]->(a:StandardAggregateProperty)
OPTIONAL MATCH (m:DesignedMixProportion)-[:INFLUENCED_BY]->(a)
RETURN a.name AS AggregateProperty, collect(DISTINCT m.name) AS InfluencedMixParameters
```

Technique: reuse the variable `a` to chain two patterns; `OPTIONAL MATCH` keeps aggregate properties that
influence no mix parameter. Note that the same name can belong to nodes with different labels, so always
give the label.

## 5. Medium complexity, high depth: aggregation, comparison and selection

Source: no matching A, C or I question; written as a quality improvement question to represent this type.
Question: Which aggregate properties influence the largest number of fresh concrete properties?

```cypher
MATCH (f:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(a:StandardAggregateProperty)
WITH a, count(DISTINCT f) AS freshCount
WITH max(freshCount) AS top, collect({property: a.name, freshCount: freshCount}) AS counts
UNWIND counts AS c
WITH top, c
WHERE c.freshCount = top
RETURN collect(c.property) AS AggregateProperties, top AS NumberOfFreshProperties
```

Technique: count per item, find the maximum, then keep every item with that maximum. This returns all
items in a tie, which `ORDER BY … LIMIT 1` would not.

## 6. High complexity, medium depth: temporal condition

Source: C2 "Which batches experienced deviations in mixing time?", loosely adapted as a quality control question to represent this type.
Question: Which projects are expected to take more than 180 days from the order being placed to the
expected due date?

```cypher
MATCH (p:ProductionProject)
WHERE p.placedOrder_date IS NOT NULL AND p.expectedDue_date IS NOT NULL
  AND duration.inDays(date(p.placedOrder_date), date(p.expectedDue_date)).days > 180
RETURN p.name AS Project,
       duration.inDays(date(p.placedOrder_date), date(p.expectedDue_date)).days AS DaysToDue
```

Technique: the project dates are stored as strings, so convert them with `date(...)` first;
`duration.inDays(...).days` gives the difference in days. Check for missing values before converting.

## 7. High complexity, high depth: compound conditions, aggregation and selection

Source: I6 "Which measurement results supported the identified root causes?", adapted.
Question: Among the fresh concrete properties that are covered by a compliance standard, which one is
influenced by the most aggregate properties, and which standard covers it?

```cypher
MATCH (f:StandardFreshConcreteProperty)-[:COMPLIES_WITH]->(s:ComplianceStandard)
MATCH (f)-[:INFLUENCED_BY]->(a:StandardAggregateProperty)
WITH f, collect(DISTINCT s.name) AS Standards, count(DISTINCT a) AS n
ORDER BY n DESC
LIMIT 1
RETURN f.name AS FreshProperty, Standards, n AS NumberOfAggregateProperties
```

Technique: two MATCH clauses on the same variable act as a compound condition (the property must satisfy
both); aggregate, then order and select. Use the tie-safe form from pattern 5 if several items could share
the top count.
