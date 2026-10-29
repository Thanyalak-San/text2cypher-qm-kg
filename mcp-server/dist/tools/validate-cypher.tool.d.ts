/**
 * validate_cypher MCP Tool
 *
 * Validates Cypher query syntax without executing it.
 * Uses Neo4j's EXPLAIN to check syntax and query plan.
 */
import { QueryExecutorService } from '../services/query-executor.service.js';
import { ValidateCypherInput, ValidateCypherResult } from '../types/mcp.types.js';
export declare class ValidateCypherTool {
    private queryExecutor;
    constructor(queryExecutor: QueryExecutorService);
    /**
     * Validate Cypher query
     */
    execute(input: ValidateCypherInput): Promise<ValidateCypherResult>;
    /**
     * Generate helpful suggestions based on error message
     */
    private generateSuggestions;
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
            };
            required: string[];
        };
    };
}
//# sourceMappingURL=validate-cypher.tool.d.ts.map