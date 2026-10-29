/**
 * Neo4j Database Service
 *
 * Manages Neo4j driver lifecycle, connections, and session management.
 * Provides health checks and graceful shutdown.
 */
import { Session } from 'neo4j-driver';
import { ConnectionStatus } from '../types/neo4j.types.js';
export declare class Neo4jService {
    private driver;
    private readonly uri;
    private readonly user;
    private readonly password;
    private readonly database;
    private readonly config;
    constructor(uri?: string, user?: string, password?: string, database?: string);
    /**
     * Initialize Neo4j driver and verify connectivity
     */
    connect(): Promise<void>;
    /**
     * Get a read session
     */
    getReadSession(): Session;
    /**
     * Get a write session
     */
    getWriteSession(): Session;
    /**
     * Execute a read query with automatic session management
     */
    executeRead<T = any>(cypher: string, parameters?: Record<string, any>): Promise<T[]>;
    /**
     * Execute a write query with automatic session management
     */
    executeWrite<T = any>(cypher: string, parameters?: Record<string, any>): Promise<T[]>;
    /**
     * Check connection health
     */
    healthCheck(): Promise<ConnectionStatus>;
    /**
     * Graceful shutdown
     */
    close(): Promise<void>;
    /**
     * Check if driver is initialized
     */
    isConnected(): boolean;
}
/**
 * Get singleton Neo4j service instance
 */
export declare function getNeo4jService(): Neo4jService;
/**
 * Initialize and connect Neo4j service
 */
export declare function initializeNeo4jService(): Promise<Neo4jService>;
//# sourceMappingURL=neo4j.service.d.ts.map