"use strict";
/**
 * Schema Cache Service
 *
 * Caches Neo4j database schema (labels, relationship types, property keys)
 * to reduce database load and improve response time for get_schema tool.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SchemaCacheService = void 0;
exports.getSchemaCacheService = getSchemaCacheService;
const neo4j_types_js_1 = require("../types/neo4j.types.js");
class SchemaCacheService {
    cache = null;
    lastFetchTime = null;
    ttl;
    neo4jService;
    constructor(neo4jService, ttlMs = parseInt(process.env.SCHEMA_CACHE_TTL_MS || '3600000') // 1 hour default
    ) {
        this.neo4jService = neo4jService;
        this.ttl = ttlMs;
    }
    /**
     * Get schema from cache or fetch from database
     */
    async getSchema(forceRefresh = false) {
        if (!forceRefresh && this.isCacheValid()) {
            console.error('[SchemaCache] Returning cached schema');
            return this.cache;
        }
        console.error('[SchemaCache] Fetching fresh schema from Neo4j');
        this.cache = await this.fetchSchemaFromNeo4j();
        this.lastFetchTime = Date.now();
        return this.cache;
    }
    /**
     * Check if cache is still valid
     */
    isCacheValid() {
        if (!this.cache || !this.lastFetchTime) {
            return false;
        }
        const age = Date.now() - this.lastFetchTime;
        return age < this.ttl;
    }
    /**
     * Invalidate cache (force next getSchema to fetch from database)
     */
    invalidate() {
        this.cache = null;
        this.lastFetchTime = null;
        console.error('[SchemaCache] Cache invalidated');
    }
    /**
     * Fetch schema from Neo4j database
     */
    async fetchSchemaFromNeo4j() {
        try {
            // Fetch all schema information in parallel
            const [labels, relationshipTypes, propertyKeys, counts] = await Promise.all([
                this.fetchLabels(),
                this.fetchRelationshipTypes(),
                this.fetchPropertyKeys(),
                this.fetchCounts()
            ]);
            return {
                labels,
                relationshipTypes,
                propertyKeys,
                nodeCount: counts.nodeCount,
                relationshipCount: counts.relationshipCount
            };
        }
        catch (error) {
            console.error('[SchemaCache] Error fetching schema:', error);
            throw new Error(`Failed to fetch schema: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    /**
     * Fetch all node labels
     */
    async fetchLabels() {
        const result = await this.neo4jService.executeRead('CALL db.labels() YIELD label RETURN label ORDER BY label');
        return result.map(r => r.label);
    }
    /**
     * Fetch all relationship types
     */
    async fetchRelationshipTypes() {
        const result = await this.neo4jService.executeRead('CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType');
        return result.map(r => r.relationshipType);
    }
    /**
     * Fetch all property keys
     */
    async fetchPropertyKeys() {
        const result = await this.neo4jService.executeRead('CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey');
        return result.map(r => r.propertyKey);
    }
    /**
     * Fetch node and relationship counts
     */
    async fetchCounts() {
        const result = await this.neo4jService.executeRead(`MATCH (n)
       WITH count(n) as nodeCount
       MATCH ()-[r]->()
       RETURN nodeCount, count(r) as relationshipCount`);
        if (result.length === 0) {
            return { nodeCount: 0, relationshipCount: 0 };
        }
        return {
            nodeCount: (0, neo4j_types_js_1.neo4jIntToNumber)(result[0].nodeCount),
            relationshipCount: (0, neo4j_types_js_1.neo4jIntToNumber)(result[0].relationshipCount)
        };
    }
    /**
     * Get cache statistics
     */
    getStats() {
        return {
            cached: this.cache !== null,
            age: this.lastFetchTime ? Date.now() - this.lastFetchTime : null,
            ttl: this.ttl
        };
    }
}
exports.SchemaCacheService = SchemaCacheService;
// Singleton instance
let schemaCacheServiceInstance = null;
/**
 * Get singleton schema cache service instance
 */
function getSchemaCacheService(neo4jService) {
    if (!schemaCacheServiceInstance) {
        schemaCacheServiceInstance = new SchemaCacheService(neo4jService);
    }
    return schemaCacheServiceInstance;
}
//# sourceMappingURL=schema-cache.service.js.map