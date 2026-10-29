/**
 * get_schema MCP Tool
 *
 * Retrieves Neo4j database schema information including:
 * - Node labels
 * - Relationship types
 * - Property keys
 * - Node and relationship counts
 */

import { SchemaCacheService } from '../services/schema-cache.service.js';
import { GetSchemaResult } from '../types/mcp.types.js';

export class GetSchemaTool {
  constructor(private schemaCacheService: SchemaCacheService) {}

  /**
   * Get database schema
   */
  async execute(forceRefresh: boolean = false): Promise<GetSchemaResult> {
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
    } catch (error) {
      throw new Error(
        `Failed to retrieve schema: ${error instanceof Error ? error.message : String(error)}`
      );
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
- Relationship types (e.g., INFLUENCED_BY, COMPLIES_WITH, PROCESSED_AT, etc.)
- Property keys available on nodes and relationships
- Total counts of nodes (157) and relationships (359)
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
