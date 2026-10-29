/**
 * Result Formatter Service
 *
 * Sanitizes and formats Neo4j query results for LLM consumption.
 * Removes internal Neo4j properties and converts complex types.
 */
export declare class ResultFormatterService {
    /**
     * Format query results by removing Neo4j internals
     */
    formatResults(records: Record<string, any>[]): Record<string, any>[];
    /**
     * Format a single record
     */
    private formatRecord;
    /**
     * Format a single value (recursive for nested structures)
     */
    private formatValue;
    /**
     * Format a Neo4j Node (remove internal properties)
     */
    private formatNode;
    /**
     * Format a Neo4j Relationship
     */
    private formatRelationship;
    /**
     * Remove internal Neo4j properties from property object
     */
    private sanitizeProperties;
    /**
     * Truncate results to specified limit
     */
    truncateResults(records: Record<string, any>[], limit: number): {
        records: Record<string, any>[];
        truncated: boolean;
    };
    /**
     * Format error for LLM consumption
     */
    formatError(error: any): {
        error: string;
        code?: string;
        details?: string;
    };
}
/**
 * Get singleton result formatter service instance
 */
export declare function getResultFormatterService(): ResultFormatterService;
//# sourceMappingURL=result-formatter.service.d.ts.map