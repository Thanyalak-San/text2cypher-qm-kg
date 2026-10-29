/**
 * Schema Cache Service
 *
 * Caches Neo4j database schema (labels, relationship types, property keys)
 * to reduce database load and improve response time for get_schema tool.
 */

import { Neo4jService } from './neo4j.service.js';
import { Neo4jSchema, neo4jIntToNumber } from '../types/neo4j.types.js';

export class SchemaCacheService {
  private cache: Neo4jSchema | null = null;
  private lastFetchTime: number | null = null;
  private readonly ttl: number;
  private readonly neo4jService: Neo4jService;

  constructor(
    neo4jService: Neo4jService,
    ttlMs: number = parseInt(process.env.SCHEMA_CACHE_TTL_MS || '3600000') // 1 hour default
  ) {
    this.neo4jService = neo4jService;
    this.ttl = ttlMs;
  }

  /**
   * Get schema from cache or fetch from database
   */
  async getSchema(forceRefresh: boolean = false): Promise<Neo4jSchema> {
    if (!forceRefresh && this.isCacheValid()) {
      console.error('[SchemaCache] Returning cached schema');
      return this.cache!;
    }

    console.error('[SchemaCache] Fetching fresh schema from Neo4j');
    this.cache = await this.fetchSchemaFromNeo4j();
    this.lastFetchTime = Date.now();
    return this.cache;
  }

  /**
   * Check if cache is still valid
   */
  private isCacheValid(): boolean {
    if (!this.cache || !this.lastFetchTime) {
      return false;
    }

    const age = Date.now() - this.lastFetchTime;
    return age < this.ttl;
  }

  /**
   * Invalidate cache (force next getSchema to fetch from database)
   */
  invalidate(): void {
    this.cache = null;
    this.lastFetchTime = null;
    console.error('[SchemaCache] Cache invalidated');
  }

  /**
   * Fetch schema from Neo4j database
   */
  private async fetchSchemaFromNeo4j(): Promise<Neo4jSchema> {
    try {
      // Fetch all schema information in parallel
      const [labels, relationshipTypes, propertyKeys, counts] = await Promise.all([
        this.fetchLabels(),
        this.fetchRelationshipTypes(),
        this.fetchPropertyKeys(),
        this.fetchCounts()
      ]);

      return {
        labels,
        relationshipTypes,
        propertyKeys,
        nodeCount: counts.nodeCount,
        relationshipCount: counts.relationshipCount
      };
    } catch (error) {
      console.error('[SchemaCache] Error fetching schema:', error);
      throw new Error(`Failed to fetch schema: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Fetch all node labels
   */
  private async fetchLabels(): Promise<string[]> {
    const result = await this.neo4jService.executeRead<{ label: string }>(
      'CALL db.labels() YIELD label RETURN label ORDER BY label'
    );
    return result.map(r => r.label);
  }

  /**
   * Fetch all relationship types
   */
  private async fetchRelationshipTypes(): Promise<string[]> {
    const result = await this.neo4jService.executeRead<{ relationshipType: string }>(
      'CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType'
    );
    return result.map(r => r.relationshipType);
  }

  /**
   * Fetch all property keys
   */
  private async fetchPropertyKeys(): Promise<string[]> {
    const result = await this.neo4jService.executeRead<{ propertyKey: string }>(
      'CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey'
    );
    return result.map(r => r.propertyKey);
  }

  /**
   * Fetch node and relationship counts
   */
  private async fetchCounts(): Promise<{ nodeCount: number; relationshipCount: number }> {
    const result = await this.neo4jService.executeRead<{ nodeCount: any; relationshipCount: any }>(
      `MATCH (n)
       WITH count(n) as nodeCount
       MATCH ()-[r]->()
       RETURN nodeCount, count(r) as relationshipCount`
    );

    if (result.length === 0) {
      return { nodeCount: 0, relationshipCount: 0 };
    }

    return {
      nodeCount: neo4jIntToNumber(result[0].nodeCount),
      relationshipCount: neo4jIntToNumber(result[0].relationshipCount)
    };
  }

  /**
   * Get cache statistics
   */
  getStats(): { cached: boolean; age: number | null; ttl: number } {
    return {
      cached: this.cache !== null,
      age: this.lastFetchTime ? Date.now() - this.lastFetchTime : null,
      ttl: this.ttl
    };
  }
}

// Singleton instance
let schemaCacheServiceInstance: SchemaCacheService | null = null;

/**
 * Get singleton schema cache service instance
 */
export function getSchemaCacheService(neo4jService: Neo4jService): SchemaCacheService {
  if (!schemaCacheServiceInstance) {
    schemaCacheServiceInstance = new SchemaCacheService(neo4jService);
  }
  return schemaCacheServiceInstance;
}
