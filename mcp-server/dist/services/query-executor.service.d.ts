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
export declare class QueryExecutorService {
    private readonly neo4jService;
    private readonly resultFormatter;
    private readonly defaultLimit;
    private readonly defaultTimeout;
    constructor(neo4jService: Neo4jService, resultFormatter: ResultFormatterService, defaultLimit?: number, defaultTimeout?: number);
    /**
     * Execute a Cypher query with safety guards
     */
    executeQuery(cypher: string, options?: QueryOptions): Promise<QueryResult>;
    /**
     * Validate Cypher query for safety
     */
    private validateQuery;
    /**
     * Execute query with timeout enforcement
     */
    private executeWithTimeout;
    /**
     * Validate Cypher syntax (without execution)
     */
    validateCypher(cypher: string): Promise<{
        valid: boolean;
        error?: string;
    }>;
    /**
     * Get executor statistics
     */
    getStats(): {
        defaultLimit: number;
        defaultTimeout: number;
    };
}
/**
 * Get singleton query executor service instance
 */
export declare function getQueryExecutorService(neo4jService: Neo4jService, resultFormatter: ResultFormatterService): QueryExecutorService;
//# sourceMappingURL=query-executor.service.d.ts.map