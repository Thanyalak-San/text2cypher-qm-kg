/**
 * MCP Server Configuration and Setup
 *
 * Implements Model Context Protocol server for Neo4j concrete factory knowledge graph.
 * Provides 3 tools: get_schema, execute_cypher_query, validate_cypher
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
/**
 * Create and configure MCP server
 */
export declare function createServer(): Promise<Server>;
/**
 * Start MCP server with STDIO transport
 */
export declare function startServer(): Promise<void>;
//# sourceMappingURL=server.d.ts.map