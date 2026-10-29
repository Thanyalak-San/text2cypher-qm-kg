/**
 * MCP Server Configuration and Setup
 *
 * Implements Model Context Protocol server for Neo4j concrete factory knowledge graph.
 * Provides 3 tools: get_schema, execute_cypher_query, validate_cypher
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { initializeNeo4jService, getNeo4jService } from './services/neo4j.service.js';
import { getSchemaCacheService } from './services/schema-cache.service.js';
import { getQueryExecutorService } from './services/query-executor.service.js';
import { getResultFormatterService } from './services/result-formatter.service.js';

import { GetSchemaTool } from './tools/get-schema.tool.js';
import { ExecuteCypherQueryTool } from './tools/execute-cypher-query.tool.js';
import { ValidateCypherTool } from './tools/validate-cypher.tool.js';

import { ExecuteCypherQueryInput, ValidateCypherInput } from './types/mcp.types.js';

/**
 * Create and configure MCP server
 */
export async function createServer(): Promise<Server> {
  // Initialize services
  console.error('[MCP Server] Initializing services...');
  const neo4jService = await initializeNeo4jService();
  const schemaCacheService = getSchemaCacheService(neo4jService);
  const resultFormatterService = getResultFormatterService();
  const queryExecutorService = getQueryExecutorService(neo4jService, resultFormatterService);

  // Initialize tools
  const getSchemaToolHandler = new GetSchemaTool(schemaCacheService);
  const executeCypherToolHandler = new ExecuteCypherQueryTool(queryExecutorService);
  const validateCypherToolHandler = new ValidateCypherTool(queryExecutorService);

  // Create server
  const server = new Server(
    {
      name: process.env.MCP_SERVER_NAME || 'concrete-factory',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // List tools handler
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        GetSchemaTool.getDefinition(),
        ExecuteCypherQueryTool.getDefinition(),
        ValidateCypherTool.getDefinition(),
      ],
    };
  });

  // Call tool handler
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case 'get_schema': {
          const forceRefresh = (args?.forceRefresh as boolean) ?? false;
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
          const input = args as unknown as ExecuteCypherQueryInput;
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
          const input = args as unknown as ValidateCypherInput;
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
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[MCP Server] Tool execution error (${name}):`, errorMessage);

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                error: errorMessage,
                tool: name,
              },
              null,
              2
            ),
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
export async function startServer(): Promise<void> {
  try {
    const server = await createServer();
    const transport = new StdioServerTransport();

    // Setup graceful shutdown
    const cleanup = async () => {
      console.error('[MCP Server] Shutting down...');
      const neo4jService = getNeo4jService();
      await neo4jService.close();
      process.exit(0);
    };

    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);

    // Connect server to transport
    await server.connect(transport);
    console.error('[MCP Server] Concrete Factory MCP Server running on stdio');
  } catch (error) {
    console.error('[MCP Server] Failed to start server:', error);
    process.exit(1);
  }
}
