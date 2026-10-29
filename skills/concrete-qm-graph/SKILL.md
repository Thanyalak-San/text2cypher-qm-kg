---
name: concrete-qm-graph
description: Write Cypher queries for the concrete production quality management knowledge graph (standards and requirements, mix design, production plan, inspections and tests, personnel, customers and orders). Use for any question answered from this graph.
---

# Querying the concrete production quality management graph

The graph holds what the applicable standards specify for concrete production, the plant's mix design and
production plan, its quality inspections and tests, and the people, customers and orders involved. Follow these steps to answer a question with one correct Cypher query.

## Workflow

1. **Identify the QM stage and what the question asks for.** Decide which stage the question belongs to, then which entities it involves, which conditions it sets and what it should return.

   | QM stage | Typical subject | Where to look in `schema_reference.md` |
   |---|---|---|
   | Quality planning | requirements, mix design, production plan, people and orders | Standards and requirements; Mix design and testing; Production plan and resources; People, customers and orders |
   | Quality control | inspections and tests of materials and concrete | Mix design and testing; Production plan and resources |
   | Quality assurance | compliance with standards and test methods | Standards and requirements; Mix design and testing |
   | Quality improvement | which properties or parameters influence others | Standards and requirements; Mix design and testing |

2. **Read the schema files.**
   - Read `schema_reference.md` for the node labels, their properties and property types, and `relationship_directions.md` for every relationship and the only direction in which it exists.
   - Use only labels, relationship types and properties listed there.
   - If the question needs counting, grouping, more than one hop, ranking or dates, also read `patterns.md` and start from the pattern for the closest type of question.

3. **Write the query.**
   - Copy each relationship's direction from `relationship_directions.md`. A relationship written the other way round matches nothing.
   - Give a label to every node you filter or return, and write labels and names with their exact spelling and case.
   - Check property types in `schema_reference.md` before comparing values (for example, dates stored as strings).
   - Return exactly what the question asks for, using `DISTINCT` where the same value could appear more than once.

4. **Check it with `validate.py`.** Run `validate.py` on the query. It checks labels, relationship types and directions against the graph and asks Neo4j to check the query without running it. Fix every problem it reports and run it again until it prints `OK`.

5. **Submit the query.** Submit the checked query once, in the way the task asks.
