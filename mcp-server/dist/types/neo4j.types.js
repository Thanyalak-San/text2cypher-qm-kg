"use strict";
/**
 * Type definitions for Neo4j integration
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.isNeo4jNode = isNeo4jNode;
exports.isNeo4jRelationship = isNeo4jRelationship;
exports.neo4jIntToNumber = neo4jIntToNumber;
/**
 * Type guard for Neo4j Node
 */
function isNeo4jNode(value) {
    return value && typeof value === 'object' && 'labels' in value && 'properties' in value;
}
/**
 * Type guard for Neo4j Relationship
 */
function isNeo4jRelationship(value) {
    return value && typeof value === 'object' && 'type' in value && 'start' in value && 'end' in value;
}
/**
 * Convert Neo4j Integer to JavaScript number
 */
function neo4jIntToNumber(value) {
    if (value && typeof value === 'object' && 'toNumber' in value) {
        return value.toNumber();
    }
    return Number(value);
}
//# sourceMappingURL=neo4j.types.js.map