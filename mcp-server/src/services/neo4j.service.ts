/**
 * Neo4j Database Service
 *
 * Manages Neo4j driver lifecycle, connections, and session management.
 * Provides health checks and graceful shutdown.
 */

import neo4j, { Driver, Session, Config } from 'neo4j-driver';
import { ConnectionStatus } from '../types/neo4j.types.js';

export class Neo4jService {
  private driver: Driver | null = null;
  private readonly uri: string;
  private readonly user: string;
  private readonly password: string;
  private readonly database: string;
  private readonly config: Config;

  constructor(
    uri: string = process.env.NEO4J_URI || 'bolt://localhost:7687',
    user: string = process.env.NEO4J_USER || 'neo4j',
    password: string = process.env.NEO4J_PASSWORD || '',
    database: string = process.env.NEO4J_DATABASE || 'neo4j'
  ) {
    this.uri = uri;
    this.user = user;
    this.password = password;
    this.database = database;

    // Configure driver with connection pooling and retry logic
    this.config = {
      maxConnectionPoolSize: 50,
      connectionAcquisitionTimeout: 60000, // 60 seconds
      maxTransactionRetryTime: 30000, // 30 seconds
      logging: {
        level: process.env.LOG_LEVEL === 'debug' ? 'debug' : 'info',
        logger: (level, message) => {
          if (level === 'error') {
            console.error(`[Neo4j] ${message}`);
          } else if (level === 'warn') {
            console.warn(`[Neo4j] ${message}`);
          } else if (process.env.LOG_LEVEL === 'debug') {
            console.error(`[Neo4j] ${message}`);
          }
        }
      }
    };
  }

  /**
   * Initialize Neo4j driver and verify connectivity
   */
  async connect(): Promise<void> {
    try {
      this.driver = neo4j.driver(
        this.uri,
        neo4j.auth.basic(this.user, this.password),
        this.config
      );

      // Verify connectivity
      await this.driver.verifyConnectivity();
      console.error(`✓ Connected to Neo4j at ${this.uri}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`✗ Failed to connect to Neo4j: ${errorMessage}`);
      throw new Error(`Neo4j connection failed: ${errorMessage}`);
    }
  }

  /**
   * Get a read session
   */
  getReadSession(): Session {
    if (!this.driver) {
      throw new Error('Neo4j driver not initialized. Call connect() first.');
    }
    return this.driver.session({
      database: this.database,
      defaultAccessMode: neo4j.session.READ
    });
  }

  /**
   * Get a write session
   */
  getWriteSession(): Session {
    if (!this.driver) {
      throw new Error('Neo4j driver not initialized. Call connect() first.');
    }
    return this.driver.session({
      database: this.database,
      defaultAccessMode: neo4j.session.WRITE
    });
  }

  /**
   * Execute a read query with automatic session management
   */
  async executeRead<T = any>(
    cypher: string,
    parameters?: Record<string, any>
  ): Promise<T[]> {
    const session = this.getReadSession();
    try {
      const result = await session.executeRead(tx =>
        tx.run(cypher, parameters)
      );
      return result.records.map(record => record.toObject() as T);
    } finally {
      await session.close();
    }
  }

  /**
   * Execute a write query with automatic session management
   */
  async executeWrite<T = any>(
    cypher: string,
    parameters?: Record<string, any>
  ): Promise<T[]> {
    const session = this.getWriteSession();
    try {
      const result = await session.executeWrite(tx =>
        tx.run(cypher, parameters)
      );
      return result.records.map(record => record.toObject() as T);
    } finally {
      await session.close();
    }
  }

  /**
   * Check connection health
   */
  async healthCheck(): Promise<ConnectionStatus> {
    if (!this.driver) {
      return {
        connected: false,
        uri: this.uri,
        database: this.database,
        error: 'Driver not initialized'
      };
    }

    try {
      await this.driver.verifyConnectivity();

      // Get server version
      const session = this.getReadSession();
      try {
        const result = await session.run('CALL dbms.components() YIELD versions RETURN versions[0] as version');
        const version = result.records[0]?.get('version') as string;

        return {
          connected: true,
          uri: this.uri,
          database: this.database,
          serverVersion: version
        };
      } finally {
        await session.close();
      }
    } catch (error) {
      return {
        connected: false,
        uri: this.uri,
        database: this.database,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Graceful shutdown
   */
  async close(): Promise<void> {
    if (this.driver) {
      await this.driver.close();
      this.driver = null;
      console.error('✓ Neo4j driver closed');
    }
  }

  /**
   * Check if driver is initialized
   */
  isConnected(): boolean {
    return this.driver !== null;
  }
}

// Singleton instance
let neo4jServiceInstance: Neo4jService | null = null;

/**
 * Get singleton Neo4j service instance
 */
export function getNeo4jService(): Neo4jService {
  if (!neo4jServiceInstance) {
    neo4jServiceInstance = new Neo4jService();
  }
  return neo4jServiceInstance;
}

/**
 * Initialize and connect Neo4j service
 */
export async function initializeNeo4jService(): Promise<Neo4jService> {
  const service = getNeo4jService();
  if (!service.isConnected()) {
    await service.connect();
  }
  return service;
}
