/**
 * MCP Tool type definitions
 */

/**
 * Tool input schema for execute_cypher_query
 */
export interface ExecuteCypherQueryInput {
  query: string;
  parameters?: Record<string, any>;
  limit?: number;
}

/**
 * Tool input schema for validate_cypher
 */
export interface ValidateCypherInput {
  query: string;
}

/**
 * Tool result for get_schema
 */
export interface GetSchemaResult {
  labels: string[];
  relationshipTypes: string[];
  propertyKeys: string[];
  nodeCount: number;
  relationshipCount: number;
  cacheInfo?: {
    cached: boolean;
    age: number | null;
    ttl: number;
  };
}

/**
 * Tool result for execute_cypher_query
 */
export interface ExecuteCypherQueryResult {
  success: boolean;
  records?: Record<string, any>[];
  metadata?: {
    executionTime: number;
    recordCount: number;
    truncated: boolean;
  };
  error?: string;
}

/**
 * Tool result for validate_cypher
 */
export interface ValidateCypherResult {
  valid: boolean;
  error?: string;
  suggestions?: string[];
}
