"use strict";
/**
 * execute_cypher_query MCP Tool
 *
 * Executes read-only Cypher queries against the Neo4j database with safety guards:
 * - Write operations blocked (CREATE, SET, DELETE, MERGE, etc.)
 * - Result truncation (default 50 records)
 * - Timeout enforcement (default 30 seconds)
 * - Internal property sanitization
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ExecuteCypherQueryTool = void 0;
class ExecuteCypherQueryTool {
    queryExecutor;
    constructor(queryExecutor) {
        this.queryExecutor = queryExecutor;
    }
    /**
     * Execute Cypher query
     */
    async execute(input) {
        try {
            const result = await this.queryExecutor.executeQuery(input.query, {
                parameters: input.parameters,
                limit: input.limit
            });
            return {
                success: true,
                records: result.records,
                metadata: result.metadata
            };
        }
        catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : String(error)
            };
        }
    }
    /**
     * Get tool definition for MCP server
     */
    static getDefinition() {
        return {
            name: 'execute_cypher_query',
            description: `Execute read-only Cypher queries against the concrete factory knowledge graph.

Safety Features:
- Write operations (CREATE, SET, DELETE, MERGE, REMOVE, DROP) are blocked
- Results automatically truncated to prevent context overload (default: 50 records)
- Query timeout enforcement (default: 30 seconds)
- Neo4j internal properties (_id, _elementId, _type) removed from results

Common Query Patterns:
- List entities: MATCH (n:Label) RETURN n.name ORDER BY n.name
- Find relationships: MATCH (a)-[r:REL_TYPE]->(b) RETURN a, r, b
- Filter by property: MATCH (n {name: $name}) RETURN n
- Multi-hop traversal: MATCH path = (start)-[*1..3]->(end) RETURN path
- Aggregation: MATCH (n:Label) RETURN count(n) as total

Use get_schema tool first to understand available labels and relationship types.`,
            inputSchema: {
                type: 'object',
                properties: {
                    query: {
                        type: 'string',
                        description: 'Cypher query to execute (read-only)',
                    },
                    parameters: {
                        type: 'object',
                        description: 'Query parameters (e.g., {name: "Compressive strength"})',
                        additionalProperties: true
                    },
                    limit: {
                        type: 'number',
                        description: 'Maximum number of records to return (default: 50)',
                        minimum: 1,
                        maximum: 100
                    }
                },
                required: ['query']
            }
        };
    }
}
exports.ExecuteCypherQueryTool = ExecuteCypherQueryTool;
//# sourceMappingURL=execute-cypher-query.tool.js.map