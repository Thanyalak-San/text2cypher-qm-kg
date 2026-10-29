/**
 * Schema Cache Service
 *
 * Caches Neo4j database schema (labels, relationship types, property keys)
 * to reduce database load and improve response time for get_schema tool.
 */
import { Neo4jService } from './neo4j.service.js';
import { Neo4jSchema } from '../types/neo4j.types.js';
export declare class SchemaCacheService {
    private cache;
    private lastFetchTime;
    private readonly ttl;
    private readonly neo4jService;
    constructor(neo4jService: Neo4jService, ttlMs?: number);
    /**
     * Get schema from cache or fetch from database
     */
    getSchema(forceRefresh?: boolean): Promise<Neo4jSchema>;
    /**
     * Check if cache is still valid
     */
    private isCacheValid;
    /**
     * Invalidate cache (force next getSchema to fetch from database)
     */
    invalidate(): void;
    /**
     * Fetch schema from Neo4j database
     */
    private fetchSchemaFromNeo4j;
    /**
     * Fetch all node labels
     */
    private fetchLabels;
    /**
     * Fetch all relationship types
     */
    private fetchRelationshipTypes;
    /**
     * Fetch all property keys
     */
    private fetchPropertyKeys;
    /**
     * Fetch node and relationship counts
     */
    private fetchCounts;
    /**
     * Get cache statistics
     */
    getStats(): {
        cached: boolean;
        age: number | null;
        ttl: number;
    };
}
/**
 * Get singleton schema cache service instance
 */
export declare function getSchemaCacheService(neo4jService: Neo4jService): SchemaCacheService;
//# sourceMappingURL=schema-cache.service.d.ts.map