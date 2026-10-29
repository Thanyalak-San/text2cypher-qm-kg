"use strict";
/**
 * Neo4j Database Service
 *
 * Manages Neo4j driver lifecycle, connections, and session management.
 * Provides health checks and graceful shutdown.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.Neo4jService = void 0;
exports.getNeo4jService = getNeo4jService;
exports.initializeNeo4jService = initializeNeo4jService;
const neo4j_driver_1 = __importDefault(require("neo4j-driver"));
class Neo4jService {
    driver = null;
    uri;
    user;
    password;
    database;
    config;
    constructor(uri = process.env.NEO4J_URI || 'bolt://localhost:7687', user = process.env.NEO4J_USER || 'neo4j', password = process.env.NEO4J_PASSWORD || '', database = process.env.NEO4J_DATABASE || 'neo4j') {
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
                    }
                    else if (level === 'warn') {
                        console.warn(`[Neo4j] ${message}`);
                    }
                    else if (process.env.LOG_LEVEL === 'debug') {
                        console.error(`[Neo4j] ${message}`);
                    }
                }
            }
        };
    }
    /**
     * Initialize Neo4j driver and verify connectivity
     */
    async connect() {
        try {
            this.driver = neo4j_driver_1.default.driver(this.uri, neo4j_driver_1.default.auth.basic(this.user, this.password), this.config);
            // Verify connectivity
            await this.driver.verifyConnectivity();
            console.error(`✓ Connected to Neo4j at ${this.uri}`);
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.error(`✗ Failed to connect to Neo4j: ${errorMessage}`);
            throw new Error(`Neo4j connection failed: ${errorMessage}`);
        }
    }
    /**
     * Get a read session
     */
    getReadSession() {
        if (!this.driver) {
            throw new Error('Neo4j driver not initialized. Call connect() first.');
        }
        return this.driver.session({
            database: this.database,
            defaultAccessMode: neo4j_driver_1.default.session.READ
        });
    }
    /**
     * Get a write session
     */
    getWriteSession() {
        if (!this.driver) {
            throw new Error('Neo4j driver not initialized. Call connect() first.');
        }
        return this.driver.session({
            database: this.database,
            defaultAccessMode: neo4j_driver_1.default.session.WRITE
        });
    }
    /**
     * Execute a read query with automatic session management
     */
    async executeRead(cypher, parameters) {
        const session = this.getReadSession();
        try {
            const result = await session.executeRead(tx => tx.run(cypher, parameters));
            return result.records.map(record => record.toObject());
        }
        finally {
            await session.close();
        }
    }
    /**
     * Execute a write query with automatic session management
     */
    async executeWrite(cypher, parameters) {
        const session = this.getWriteSession();
        try {
            const result = await session.executeWrite(tx => tx.run(cypher, parameters));
            return result.records.map(record => record.toObject());
        }
        finally {
            await session.close();
        }
    }
    /**
     * Check connection health
     */
    async healthCheck() {
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
                const version = result.records[0]?.get('version');
                return {
                    connected: true,
                    uri: this.uri,
                    database: this.database,
                    serverVersion: version
                };
            }
            finally {
                await session.close();
            }
        }
        catch (error) {
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
    async close() {
        if (this.driver) {
            await this.driver.close();
            this.driver = null;
            console.error('✓ Neo4j driver closed');
        }
    }
    /**
     * Check if driver is initialized
     */
    isConnected() {
        return this.driver !== null;
    }
}
exports.Neo4jService = Neo4jService;
// Singleton instance
let neo4jServiceInstance = null;
/**
 * Get singleton Neo4j service instance
 */
function getNeo4jService() {
    if (!neo4jServiceInstance) {
        neo4jServiceInstance = new Neo4jService();
    }
    return neo4jServiceInstance;
}
/**
 * Initialize and connect Neo4j service
 */
async function initializeNeo4jService() {
    const service = getNeo4jService();
    if (!service.isConnected()) {
        await service.connect();
    }
    return service;
}
//# sourceMappingURL=neo4j.service.js.map