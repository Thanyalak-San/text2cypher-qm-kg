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
export declare class GetSchemaTool {
    private schemaCacheService;
    constructor(schemaCacheService: SchemaCacheService);
    /**
     * Get database schema
     */
    execute(forceRefresh?: boolean): Promise<GetSchemaResult>;
    /**
     * Get tool definition for MCP server
     */
    static getDefinition(): {
        name: string;
        description: string;
        inputSchema: {
            type: string;
            properties: {
                forceRefresh: {
                    type: string;
                    description: string;
                    default: boolean;
                };
            };
        };
    };
}
//# sourceMappingURL=get-schema.tool.d.ts.map