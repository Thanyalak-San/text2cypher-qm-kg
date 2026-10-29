/**
 * Result Formatter Service
 *
 * Sanitizes and formats Neo4j query results for LLM consumption.
 * Removes internal Neo4j properties and converts complex types.
 */

import { Node as Neo4jNode, Relationship as Neo4jRelationship, Integer } from 'neo4j-driver';
import { SanitizedNode, SanitizedRelationship, isNeo4jNode, isNeo4jRelationship, neo4jIntToNumber } from '../types/neo4j.types.js';

export class ResultFormatterService {
  /**
   * Format query results by removing Neo4j internals
   */
  formatResults(records: Record<string, any>[]): Record<string, any>[] {
    return records.map(record => this.formatRecord(record));
  }

  /**
   * Format a single record
   */
  private formatRecord(record: Record<string, any>): Record<string, any> {
    const formatted: Record<string, any> = {};

    for (const [key, value] of Object.entries(record)) {
      formatted[key] = this.formatValue(value);
    }

    return formatted;
  }

  /**
   * Format a single value (recursive for nested structures)
   */
  private formatValue(value: any): any {
    // Handle null/undefined
    if (value === null || value === undefined) {
      return null;
    }

    // Handle Neo4j Node
    if (isNeo4jNode(value)) {
      return this.formatNode(value);
    }

    // Handle Neo4j Relationship
    if (isNeo4jRelationship(value)) {
      return this.formatRelationship(value);
    }

    // Handle Neo4j Integer
    if (value && typeof value === 'object' && 'toNumber' in value) {
      return neo4jIntToNumber(value);
    }

    // Handle arrays
    if (Array.isArray(value)) {
      return value.map(item => this.formatValue(item));
    }

    // Handle plain objects
    if (typeof value === 'object' && value.constructor === Object) {
      const formatted: Record<string, any> = {};
      for (const [k, v] of Object.entries(value)) {
        formatted[k] = this.formatValue(v);
      }
      return formatted;
    }

    // Return primitive values as-is
    return value;
  }

  /**
   * Format a Neo4j Node (remove internal properties)
   */
  private formatNode(node: Neo4jNode): SanitizedNode {
    // Extract identity as string (remove leading/trailing chars if needed)
    const identity = node.identity.toString();

    // Format properties (remove internal Neo4j keys)
    const properties = this.sanitizeProperties(node.properties);

    return {
      id: identity,
      labels: node.labels,
      properties
    };
  }

  /**
   * Format a Neo4j Relationship
   */
  private formatRelationship(rel: Neo4jRelationship): SanitizedRelationship {
    const identity = rel.identity.toString();
    const startNodeId = rel.start.toString();
    const endNodeId = rel.end.toString();

    // Format properties
    const properties = this.sanitizeProperties(rel.properties);

    return {
      id: identity,
      type: rel.type,
      startNodeId,
      endNodeId,
      properties
    };
  }

  /**
   * Remove internal Neo4j properties from property object
   */
  private sanitizeProperties(properties: Record<string, any>): Record<string, any> {
    const sanitized: Record<string, any> = {};
    const internalKeys = ['_id', '_elementId', '_type', '_labels'];

    for (const [key, value] of Object.entries(properties)) {
      // Skip internal properties
      if (internalKeys.includes(key)) {
        continue;
      }

      // Convert Neo4j Integers to numbers
      if (value && typeof value === 'object' && 'toNumber' in value) {
        sanitized[key] = neo4jIntToNumber(value);
      } else {
        sanitized[key] = value;
      }
    }

    return sanitized;
  }

  /**
   * Truncate results to specified limit
   */
  truncateResults(records: Record<string, any>[], limit: number): {
    records: Record<string, any>[];
    truncated: boolean;
  } {
    if (records.length <= limit) {
      return { records, truncated: false };
    }

    return {
      records: records.slice(0, limit),
      truncated: true
    };
  }

  /**
   * Format error for LLM consumption
   */
  formatError(error: any): { error: string; code?: string; details?: string } {
    if (error instanceof Error) {
      return {
        error: error.message,
        code: (error as any).code,
        details: (error as any).details
      };
    }

    return { error: String(error) };
  }
}

// Singleton instance
let resultFormatterServiceInstance: ResultFormatterService | null = null;

/**
 * Get singleton result formatter service instance
 */
export function getResultFormatterService(): ResultFormatterService {
  if (!resultFormatterServiceInstance) {
    resultFormatterServiceInstance = new ResultFormatterService();
  }
  return resultFormatterServiceInstance;
}
