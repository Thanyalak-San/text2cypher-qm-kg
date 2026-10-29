/**
 * Query Executor Service
 *
 * Executes Cypher queries with safety guards:
 * - Timeout enforcement
 * - Result truncation
 * - Write operation validation
 * - Parameter injection prevention
 */

import { Neo4jService } from './neo4j.service.js';
import { ResultFormatterService } from './result-formatter.service.js';
import { QueryOptions, QueryResult } from '../types/neo4j.types.js';

const FORBIDDEN_OPERATIONS = ['CREATE', 'SET', 'DELETE', 'MERGE', 'REMOVE', 'DROP', 'DETACH'];

export class QueryExecutorService {
  private readonly neo4jService: Neo4jService;
  private readonly resultFormatter: ResultFormatterService;
  private readonly defaultLimit: number;
  private readonly defaultTimeout: number;

  constructor(
    neo4jService: Neo4jService,
    resultFormatter: ResultFormatterService,
    defaultLimit: number = parseInt(process.env.RESULT_LIMIT || '50'),
    defaultTimeout: number = parseInt(process.env.QUERY_TIMEOUT_MS || '30000')
  ) {
    this.neo4jService = neo4jService;
    this.resultFormatter = resultFormatter;
    this.defaultLimit = defaultLimit;
    this.defaultTimeout = defaultTimeout;
  }

  /**
   * Execute a Cypher query with safety guards
   */
  async executeQuery(
    cypher: string,
    options: QueryOptions = {}
  ): Promise<QueryResult> {
    const startTime = Date.now();

    // Validate query (check for write operations)
    this.validateQuery(cypher);

    // Apply limits
    const limit = options.limit ?? this.defaultLimit;
    const timeout = options.timeout ?? this.defaultTimeout;
    const parameters = options.parameters ?? {};

    try {
      // Execute with timeout
      const rawRecords = await this.executeWithTimeout(cypher, parameters, timeout);

      // Format results (remove Neo4j internals)
      const formattedRecords = this.resultFormatter.formatResults(rawRecords);

      // Truncate if needed
      const { records, truncated } = this.resultFormatter.truncateResults(formattedRecords, limit);

      const executionTime = Date.now() - startTime;

      return {
        records,
        metadata: {
          executionTime,
          recordCount: records.length,
          truncated
        }
      };
    } catch (error) {
      const executionTime = Date.now() - startTime;
      console.error('[QueryExecutor] Query failed:', error);

      throw new Error(
        `Query execution failed after ${executionTime}ms: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  /**
   * Validate Cypher query for safety
   */
  private validateQuery(cypher: string): void {
    const upperCypher = cypher.toUpperCase();

    // Check for forbidden write operations
    for (const operation of FORBIDDEN_OPERATIONS) {
      if (upperCypher.includes(operation)) {
        throw new Error(
          `Write operation '${operation}' is not allowed. Only read queries (MATCH, RETURN, WITH, WHERE, ORDER BY, LIMIT) are permitted.`
        );
      }
    }

    // Additional validation: query must not be empty
    if (!cypher.trim()) {
      throw new Error('Query cannot be empty');
    }
  }

  /**
   * Execute query with timeout enforcement
   */
  private async executeWithTimeout(
    cypher: string,
    parameters: Record<string, any>,
    timeoutMs: number
  ): Promise<Record<string, any>[]> {
    return new Promise(async (resolve, reject) => {
      // Set timeout
      const timeoutHandle = setTimeout(() => {
        reject(new Error(`Query timeout after ${timeoutMs}ms`));
      }, timeoutMs);

      try {
        const records = await this.neo4jService.executeRead(cypher, parameters);
        clearTimeout(timeoutHandle);
        resolve(records);
      } catch (error) {
        clearTimeout(timeoutHandle);
        reject(error);
      }
    });
  }

  /**
   * Validate Cypher syntax (without execution)
   */
  async validateCypher(cypher: string): Promise<{ valid: boolean; error?: string }> {
    try {
      // First, check for write operations
      this.validateQuery(cypher);

      // Use Neo4j's EXPLAIN to validate syntax without executing
      await this.neo4jService.executeRead(`EXPLAIN ${cypher}`);

      return { valid: true };
    } catch (error) {
      return {
        valid: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Get executor statistics
   */
  getStats(): { defaultLimit: number; defaultTimeout: number } {
    return {
      defaultLimit: this.defaultLimit,
      defaultTimeout: this.defaultTimeout
    };
  }
}

// Singleton instance
let queryExecutorServiceInstance: QueryExecutorService | null = null;

/**
 * Get singleton query executor service instance
 */
export function getQueryExecutorService(
  neo4jService: Neo4jService,
  resultFormatter: ResultFormatterService
): QueryExecutorService {
  if (!queryExecutorServiceInstance) {
    queryExecutorServiceInstance = new QueryExecutorService(neo4jService, resultFormatter);
  }
  return queryExecutorServiceInstance;
}
