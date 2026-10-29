/**
 * execute_cypher_query MCP Tool
 *
 * Executes read-only Cypher queries against the Neo4j database with safety guards:
 * - Write operations blocked (CREATE, SET, DELETE, MERGE, etc.)
 * - Result truncation (default 50 records)
 * - Timeout enforcement (default 30 seconds)
 * - Internal property sanitization
 */
import { QueryExecutorService } from '../services/query-executor.service.js';
import { ExecuteCypherQueryInput, ExecuteCypherQueryResult } from '../types/mcp.types.js';
export declare class ExecuteCypherQueryTool {
    private queryExecutor;
    constructor(queryExecutor: QueryExecutorService);
    /**
     * Execute Cypher query
     */
    execute(input: ExecuteCypherQueryInput): Promise<ExecuteCypherQueryResult>;
    /**
     * Get tool definition for MCP server
     */
    static getDefinition(): {
        name: string;
        description: string;
        inputSchema: {
            type: string;
            properties: {
                query: {
                    type: string;
                    description: string;
                };
                parameters: {
                    type: string;
                    description: string;
                    additionalProperties: boolean;
                };
                limit: {
                    type: string;
                    description: string;
                    minimum: number;
                    maximum: number;
                };
            };
            required: string[];
        };
    };
}
//# sourceMappingURL=execute-cypher-query.tool.d.ts.map