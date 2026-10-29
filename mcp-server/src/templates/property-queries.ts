/**
 * Property Relationship Query Templates
 *
 * Complex graph traversal queries for:
 * - Property influence chains
 * - Multi-hop relationship tracing
 * - Bidirectional graph exploration
 */

export const PROPERTY_QUERIES = {
  /**
   * Trace relationships from an entity (forward direction)
   */
  trace_relationships_forward: `
    MATCH (start {name: $entityName})
    MATCH path = (start)-[r:$relationshipType*1..$maxHops]->(end)
    RETURN [node in nodes(path) | {
      id: id(node),
      name: node.name,
      labels: labels(node)
    }] as path_nodes,
    [rel in relationships(path) | type(rel)] as relationship_types,
    length(path) as path_length
    ORDER BY path_length
    LIMIT $limit
  `,

  /**
   * Trace relationships from an entity (backward direction)
   */
  trace_relationships_backward: `
    MATCH (start {name: $entityName})
    MATCH path = (start)<-[r:$relationshipType*1..$maxHops]-(end)
    RETURN [node in nodes(path) | {
      id: id(node),
      name: node.name,
      labels: labels(node)
    }] as path_nodes,
    [rel in relationships(path) | type(rel)] as relationship_types,
    length(path) as path_length
    ORDER BY path_length
    LIMIT $limit
  `,

  /**
   * Trace relationships bidirectionally
   */
  trace_relationships_both: `
    MATCH (start {name: $entityName})
    MATCH path = (start)-[r:$relationshipType*1..$maxHops]-(end)
    RETURN [node in nodes(path) | {
      id: id(node),
      name: node.name,
      labels: labels(node)
    }] as path_nodes,
    [rel in relationships(path) | type(rel)] as relationship_types,
    length(path) as path_length
    ORDER BY path_length
    LIMIT $limit
  `,

  /**
   * Find all properties that influence a target property
   */
  find_influencing_properties: `
    MATCH (target {name: $propertyName})<-[:INFLUENCED_BY*1..$depth]-(influencer)
    RETURN DISTINCT influencer.name as property_name,
           labels(influencer) as property_type,
           shortestPath((target)<-[:INFLUENCED_BY*]-(influencer)) as path
    ORDER BY property_name
  `,

  /**
   * Find all properties influenced by a source property
   */
  find_influenced_properties: `
    MATCH (source {name: $propertyName})<-[:INFLUENCED_BY*1..$depth]-(influenced)
    RETURN DISTINCT influenced.name as property_name,
           labels(influenced) as property_type,
           shortestPath((source)-[:INFLUENCED_BY*]->(influenced)) as path
    ORDER BY property_name
  `,

  /**
   * Find shortest path between two entities
   */
  shortest_path: `
    MATCH (start {name: $startEntity}), (end {name: $endEntity})
    MATCH path = shortestPath((start)-[*1..$maxHops]-(end))
    RETURN [node in nodes(path) | {
      id: id(node),
      name: node.name,
      labels: labels(node)
    }] as path_nodes,
    [rel in relationships(path) | {
      type: type(rel),
      properties: properties(rel)
    }] as relationships,
    length(path) as path_length
  `,

  /**
   * Find all paths between two entities (up to max_paths)
   */
  all_paths: `
    MATCH (start {name: $startEntity}), (end {name: $endEntity})
    MATCH path = (start)-[*1..$maxHops]-(end)
    WITH path
    ORDER BY length(path)
    LIMIT $maxPaths
    RETURN [node in nodes(path) | {
      id: id(node),
      name: node.name,
      labels: labels(node)
    }] as path_nodes,
    [rel in relationships(path) | type(rel)] as relationship_types,
    length(path) as path_length
  `,

  /**
   * Get direct neighbors of an entity
   */
  get_neighbors: `
    MATCH (center {name: $entityName})
    OPTIONAL MATCH (center)-[r]->(outgoing)
    OPTIONAL MATCH (center)<-[r2]-(incoming)
    RETURN
      collect(DISTINCT {
        direction: 'outgoing',
        relationship: type(r),
        node: {
          id: id(outgoing),
          name: outgoing.name,
          labels: labels(outgoing)
        }
      }) as outgoing_neighbors,
      collect(DISTINCT {
        direction: 'incoming',
        relationship: type(r2),
        node: {
          id: id(incoming),
          name: incoming.name,
          labels: labels(incoming)
        }
      }) as incoming_neighbors
  `,

  /**
   * Find entities with specific relationship pattern
   */
  pattern_match: `
    MATCH (a {name: $entityName})-[$rel1Type]->(b)-[$rel2Type]->(c)
    RETURN DISTINCT b.name as intermediate_node,
           labels(b) as intermediate_labels,
           c.name as target_node,
           labels(c) as target_labels
    ORDER BY b.name, c.name
  `
};

/**
 * Get property query template by name
 */
export function getPropertyQuery(templateName: string): string | undefined {
  return PROPERTY_QUERIES[templateName as keyof typeof PROPERTY_QUERIES];
}

/**
 * List all available property query templates
 */
export function listPropertyQueries(): string[] {
  return Object.keys(PROPERTY_QUERIES);
}

/**
 * Default parameters for property queries
 */
export const DEFAULT_PROPERTY_QUERY_PARAMS = {
  maxHops: 5,
  limit: 50,
  depth: 3,
  maxPaths: 10
};
