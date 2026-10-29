/**
 * Type definitions for Neo4j integration
 */

import { Integer, Node as Neo4jNode, Relationship as Neo4jRelationship } from 'neo4j-driver';

/**
 * Schema information from Neo4j database
 */
export interface Neo4jSchema {
  labels: string[];
  relationshipTypes: string[];
  propertyKeys: string[];
  nodeCount: number;
  relationshipCount: number;
}

/**
 * Query execution options
 */
export interface QueryOptions {
  limit?: number;
  timeout?: number;
  parameters?: Record<string, any>;
}

/**
 * Query execution result
 */
export interface QueryResult {
  records: Record<string, any>[];
  metadata: {
    executionTime: number;
    recordCount: number;
    truncated: boolean;
  };
}

/**
 * Sanitized node (Neo4j internal properties removed)
 */
export interface SanitizedNode {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

/**
 * Sanitized relationship
 */
export interface SanitizedRelationship {
  id: string;
  type: string;
  startNodeId: string;
  endNodeId: string;
  properties: Record<string, any>;
}

/**
 * Connection status
 */
export interface ConnectionStatus {
  connected: boolean;
  uri: string;
  database: string;
  serverVersion?: string;
  error?: string;
}

/**
 * Type guard for Neo4j Node
 */
export function isNeo4jNode(value: any): value is Neo4jNode {
  return value && typeof value === 'object' && 'labels' in value && 'properties' in value;
}

/**
 * Type guard for Neo4j Relationship
 */
export function isNeo4jRelationship(value: any): value is Neo4jRelationship {
  return value && typeof value === 'object' && 'type' in value && 'start' in value && 'end' in value;
}

/**
 * Convert Neo4j Integer to JavaScript number
 */
export function neo4jIntToNumber(value: any): number {
  if (value && typeof value === 'object' && 'toNumber' in value) {
    return (value as Integer).toNumber();
  }
  return Number(value);
}
