"use strict";
/**
 * Result Formatter Service
 *
 * Sanitizes and formats Neo4j query results for LLM consumption.
 * Removes internal Neo4j properties and converts complex types.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ResultFormatterService = void 0;
exports.getResultFormatterService = getResultFormatterService;
const neo4j_types_js_1 = require("../types/neo4j.types.js");
class ResultFormatterService {
    /**
     * Format query results by removing Neo4j internals
     */
    formatResults(records) {
        return records.map(record => this.formatRecord(record));
    }
    /**
     * Format a single record
     */
    formatRecord(record) {
        const formatted = {};
        for (const [key, value] of Object.entries(record)) {
            formatted[key] = this.formatValue(value);
        }
        return formatted;
    }
    /**
     * Format a single value (recursive for nested structures)
     */
    formatValue(value) {
        // Handle null/undefined
        if (value === null || value === undefined) {
            return null;
        }
        // Handle Neo4j Node
        if ((0, neo4j_types_js_1.isNeo4jNode)(value)) {
            return this.formatNode(value);
        }
        // Handle Neo4j Relationship
        if ((0, neo4j_types_js_1.isNeo4jRelationship)(value)) {
            return this.formatRelationship(value);
        }
        // Handle Neo4j Integer
        if (value && typeof value === 'object' && 'toNumber' in value) {
            return (0, neo4j_types_js_1.neo4jIntToNumber)(value);
        }
        // Handle arrays
        if (Array.isArray(value)) {
            return value.map(item => this.formatValue(item));
        }
        // Handle plain objects
        if (typeof value === 'object' && value.constructor === Object) {
            const formatted = {};
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
    formatNode(node) {
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
    formatRelationship(rel) {
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
    sanitizeProperties(properties) {
        const sanitized = {};
        const internalKeys = ['_id', '_elementId', '_type', '_labels'];
        for (const [key, value] of Object.entries(properties)) {
            // Skip internal properties
            if (internalKeys.includes(key)) {
                continue;
            }
            // Convert Neo4j Integers to numbers
            if (value && typeof value === 'object' && 'toNumber' in value) {
                sanitized[key] = (0, neo4j_types_js_1.neo4jIntToNumber)(value);
            }
            else {
                sanitized[key] = value;
            }
        }
        return sanitized;
    }
    /**
     * Truncate results to specified limit
     */
    truncateResults(records, limit) {
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
    formatError(error) {
        if (error instanceof Error) {
            return {
                error: error.message,
                code: error.code,
                details: error.details
            };
        }
        return { error: String(error) };
    }
}
exports.ResultFormatterService = ResultFormatterService;
// Singleton instance
let resultFormatterServiceInstance = null;
/**
 * Get singleton result formatter service instance
 */
function getResultFormatterService() {
    if (!resultFormatterServiceInstance) {
        resultFormatterServiceInstance = new ResultFormatterService();
    }
    return resultFormatterServiceInstance;
}
//# sourceMappingURL=result-formatter.service.js.map