/**
 * Property Relationship Query Templates
 *
 * Complex graph traversal queries for:
 * - Property influence chains
 * - Multi-hop relationship tracing
 * - Bidirectional graph exploration
 */
export declare const PROPERTY_QUERIES: {
    /**
     * Trace relationships from an entity (forward direction)
     */
    trace_relationships_forward: string;
    /**
     * Trace relationships from an entity (backward direction)
     */
    trace_relationships_backward: string;
    /**
     * Trace relationships bidirectionally
     */
    trace_relationships_both: string;
    /**
     * Find all properties that influence a target property
     */
    find_influencing_properties: string;
    /**
     * Find all properties influenced by a source property
     */
    find_influenced_properties: string;
    /**
     * Find shortest path between two entities
     */
    shortest_path: string;
    /**
     * Find all paths between two entities (up to max_paths)
     */
    all_paths: string;
    /**
     * Get direct neighbors of an entity
     */
    get_neighbors: string;
    /**
     * Find entities with specific relationship pattern
     */
    pattern_match: string;
};
/**
 * Get property query template by name
 */
export declare function getPropertyQuery(templateName: string): string | undefined;
/**
 * List all available property query templates
 */
export declare function listPropertyQueries(): string[];
/**
 * Default parameters for property queries
 */
export declare const DEFAULT_PROPERTY_QUERY_PARAMS: {
    maxHops: number;
    limit: number;
    depth: number;
    maxPaths: number;
};
//# sourceMappingURL=property-queries.d.ts.map