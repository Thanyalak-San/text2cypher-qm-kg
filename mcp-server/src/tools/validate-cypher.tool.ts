/**
 * validate_cypher MCP Tool
 *
 * Validates Cypher query syntax without executing it.
 * Uses Neo4j's EXPLAIN to check syntax and query plan.
 */

import { QueryExecutorService } from '../services/query-executor.service.js';
import { ValidateCypherInput, ValidateCypherResult } from '../types/mcp.types.js';

export class ValidateCypherTool {
  constructor(private queryExecutor: QueryExecutorService) {}

  /**
   * Validate Cypher query
   */
  async execute(input: ValidateCypherInput): Promise<ValidateCypherResult> {
    try {
      const result = await this.queryExecutor.validateCypher(input.query);

      if (!result.valid) {
        return {
          valid: false,
          error: result.error,
          suggestions: this.generateSuggestions(result.error)
        };
      }

      return { valid: true };
    } catch (error) {
      return {
        valid: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Generate helpful suggestions based on error message
   */
  private generateSuggestions(error?: string): string[] {
    if (!error) return [];

    const suggestions: string[] = [];
    const lowerError = error.toLowerCase();

    // Common error patterns
    if (lowerError.includes('write operation')) {
      suggestions.push('This tool only supports read queries. Remove CREATE, SET, DELETE, MERGE, or DROP operations.');
      suggestions.push('Use MATCH, RETURN, WHERE, ORDER BY, LIMIT for read queries.');
    }

    if (lowerError.includes('unknown label') || lowerError.includes('label not found')) {
      suggestions.push('Use get_schema tool to see available node labels.');
    }

    if (lowerError.includes('unknown relationship') || lowerError.includes('relationship type')) {
      suggestions.push('Use get_schema tool to see available relationship types.');
    }

    if (lowerError.includes('unknown property')) {
      suggestions.push('Use get_schema tool to see available property keys.');
    }

    if (lowerError.includes('syntax error')) {
      suggestions.push('Check Cypher syntax. Common patterns:');
      suggestions.push('  - MATCH (n:Label) RETURN n');
      suggestions.push('  - MATCH (a)-[r:REL_TYPE]->(b) RETURN a, r, b');
      suggestions.push('  - MATCH (n {name: $name}) RETURN n');
    }

    if (lowerError.includes('parameter')) {
      suggestions.push('Use parameterized queries: MATCH (n {name: $name}) with parameters: {name: "value"}');
    }

    return suggestions;
  }

  /**
   * Get tool definition for MCP server
   */
  static getDefinition() {
    return {
      name: 'validate_cypher',
      description: `Validate Cypher query syntax without executing it.

Uses Neo4j's EXPLAIN to check:
- Query syntax correctness
- Label and relationship type existence
- Property key availability
- Write operation detection

Returns:
- valid: boolean indicating if query is valid
- error: error message if validation failed
- suggestions: helpful tips to fix common errors

Use this tool to test queries before execution to avoid errors.`,
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Cypher query to validate'
          }
        },
        required: ['query']
      }
    };
  }
}
