"use strict";
/**
 * get_schema MCP Tool
 *
 * Retrieves Neo4j database schema information including:
 * - Node labels
 * - Relationship types
 * - Property keys
 * - Node and relationship counts
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.GetSchemaTool = void 0;
class GetSchemaTool {
    schemaCacheService;
    constructor(schemaCacheService) {
        this.schemaCacheService = schemaCacheService;
    }
    /**
     * Get database schema
     */
    async execute(forceRefresh = false) {
        try {
            const schema = await this.schemaCacheService.getSchema(forceRefresh);
            const cacheStats = this.schemaCacheService.getStats();
            return {
                labels: schema.labels,
                relationshipTypes: schema.relationshipTypes,
                propertyKeys: schema.propertyKeys,
                nodeCount: schema.nodeCount,
                relationshipCount: schema.relationshipCount,
                cacheInfo: {
                    cached: cacheStats.cached,
                    age: cacheStats.age,
                    ttl: cacheStats.ttl
                }
            };
        }
        catch (error) {
            throw new Error(`Failed to retrieve schema: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    /**
     * Get tool definition for MCP server
     */
    static getDefinition() {
        return {
            name: 'get_schema',
            description: `Retrieve the Neo4j database schema for the concrete factory knowledge graph.

Returns:
- Node labels (e.g., Machine, Standard, CementProperty, Task, etc.)
- Relationship types (e.g., INFLUENCED_BY, COMPLY_WITH, PROCESSED_AT, etc.)
- Property keys available on nodes and relationships
- Total counts of nodes (178) and relationships (371)
- Cache information (whether cached, cache age, TTL)

Use this tool to understand the structure of the knowledge graph before constructing Cypher queries.`,
            inputSchema: {
                type: 'object',
                properties: {
                    forceRefresh: {
                        type: 'boolean',
                        description: 'Force refresh schema from database (bypass cache)',
                        default: false
                    }
                }
            }
        };
    }
}
exports.GetSchemaTool = GetSchemaTool;
//# sourceMappingURL=get-schema.tool.js.map