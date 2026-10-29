"use strict";
/**
 * MCP Server Configuration and Setup
 *
 * Implements Model Context Protocol server for Neo4j concrete factory knowledge graph.
 * Provides 3 tools: get_schema, execute_cypher_query, validate_cypher
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.createServer = createServer;
exports.startServer = startServer;
const index_js_1 = require("@modelcontextprotocol/sdk/server/index.js");
const stdio_js_1 = require("@modelcontextprotocol/sdk/server/stdio.js");
const types_js_1 = require("@modelcontextprotocol/sdk/types.js");
const neo4j_service_js_1 = require("./services/neo4j.service.js");
const schema_cache_service_js_1 = require("./services/schema-cache.service.js");
const query_executor_service_js_1 = require("./services/query-executor.service.js");
const result_formatter_service_js_1 = require("./services/result-formatter.service.js");
const get_schema_tool_js_1 = require("./tools/get-schema.tool.js");
const execute_cypher_query_tool_js_1 = require("./tools/execute-cypher-query.tool.js");
const validate_cypher_tool_js_1 = require("./tools/validate-cypher.tool.js");
/**
 * Create and configure MCP server
 */
async function createServer() {
    // Initialize services
    console.error('[MCP Server] Initializing services...');
    const neo4jService = await (0, neo4j_service_js_1.initializeNeo4jService)();
    const schemaCacheService = (0, schema_cache_service_js_1.getSchemaCacheService)(neo4jService);
    const resultFormatterService = (0, result_formatter_service_js_1.getResultFormatterService)();
    const queryExecutorService = (0, query_executor_service_js_1.getQueryExecutorService)(neo4jService, resultFormatterService);
    // Initialize tools
    const getSchemaToolHandler = new get_schema_tool_js_1.GetSchemaTool(schemaCacheService);
    const executeCypherToolHandler = new execute_cypher_query_tool_js_1.ExecuteCypherQueryTool(queryExecutorService);
    const validateCypherToolHandler = new validate_cypher_tool_js_1.ValidateCypherTool(queryExecutorService);
    // Create server
    const server = new index_js_1.Server({
        name: process.env.MCP_SERVER_NAME || 'concrete-factory',
        version: '1.0.0',
    }, {
        capabilities: {
            tools: {},
        },
    });
    // List tools handler
    server.setRequestHandler(types_js_1.ListToolsRequestSchema, async () => {
        return {
            tools: [
                get_schema_tool_js_1.GetSchemaTool.getDefinition(),
                execute_cypher_query_tool_js_1.ExecuteCypherQueryTool.getDefinition(),
                validate_cypher_tool_js_1.ValidateCypherTool.getDefinition(),
            ],
        };
    });
    // Call tool handler
    server.setRequestHandler(types_js_1.CallToolRequestSchema, async (request) => {
        const { name, arguments: args } = request.params;
        try {
            switch (name) {
                case 'get_schema': {
                    const forceRefresh = args?.forceRefresh ?? false;
                    const result = await getSchemaToolHandler.execute(forceRefresh);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify(result, null, 2),
                            },
                        ],
                    };
                }
                case 'execute_cypher_query': {
                    const input = args;
                    if (!input?.query) {
                        throw new Error('query parameter is required');
                    }
                    const result = await executeCypherToolHandler.execute(input);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify(result, null, 2),
                            },
                        ],
                    };
                }
                case 'validate_cypher': {
                    const input = args;
                    if (!input?.query) {
                        throw new Error('query parameter is required');
                    }
                    const result = await validateCypherToolHandler.execute(input);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify(result, null, 2),
                            },
                        ],
                    };
                }
                default:
                    throw new Error(`Unknown tool: ${name}`);
            }
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.error(`[MCP Server] Tool execution error (${name}):`, errorMessage);
            return {
                content: [
                    {
                        type: 'text',
                        text: JSON.stringify({
                            error: errorMessage,
                            tool: name,
                        }, null, 2),
                    },
                ],
                isError: true,
            };
        }
    });
    console.error('[MCP Server] Server configured successfully');
    return server;
}
/**
 * Start MCP server with STDIO transport
 */
async function startServer() {
    try {
        const server = await createServer();
        const transport = new stdio_js_1.StdioServerTransport();
        // Setup graceful shutdown
        const cleanup = async () => {
            console.error('[MCP Server] Shutting down...');
            const neo4jService = (0, neo4j_service_js_1.getNeo4jService)();
            await neo4jService.close();
            process.exit(0);
        };
        process.on('SIGINT', cleanup);
        process.on('SIGTERM', cleanup);
        // Connect server to transport
        await server.connect(transport);
        console.error('[MCP Server] Concrete Factory MCP Server running on stdio');
    }
    catch (error) {
        console.error('[MCP Server] Failed to start server:', error);
        process.exit(1);
    }
}
//# sourceMappingURL=server.js.map