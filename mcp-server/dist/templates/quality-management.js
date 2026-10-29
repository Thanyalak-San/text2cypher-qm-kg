"use strict";
/**
 * Quality Management Query Templates
 *
 * Cypher queries matching Agent Skill patterns for:
 * - Standards compliance (P1, P2, P4, A6, A7)
 * - Manufacturing processes (P6, P8, P19)
 * - Property testing requirements (A18, A19, A20)
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.QUALITY_MANAGEMENT_QUERIES = void 0;
exports.getQualityManagementQuery = getQualityManagementQuery;
exports.listQualityManagementQueries = listQualityManagementQueries;
exports.QUALITY_MANAGEMENT_QUERIES = {
    /**
     * P1: List all standards
     * Expected: 41 standards
     */
    list_all_standards: `
    MATCH (s:Standard)
    RETURN s.name as standard_name
    ORDER BY s.name
  `,
    /**
     * P2: Cement properties with standards
     * Expected: 11 cement properties
     */
    cement_properties_with_standards: `
    MATCH (p:CementProperty)-[:COMPLY_WITH]->(s:Standard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,
    /**
     * P3: Coarse aggregate properties with standards
     */
    coarse_aggregate_properties_with_standards: `
    MATCH (p:CoarseAggProperty)-[:COMPLY_WITH]->(s:Standard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,
    /**
     * P4: Water properties with standards
     * Expected: 11 water properties
     */
    water_properties_with_standards: `
    MATCH (p:WaterProperty)-[:COMPLY_WITH]->(s:Standard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,
    /**
     * P6: List all machines with their tasks
     * Expected: 4 machines
     */
    list_all_machines: `
    MATCH (m:Machine)
    OPTIONAL MATCH (t:Task)-[:PROCESSED_AT]->(m)
    RETURN m.name as machine_name,
           collect(DISTINCT t.name) as tasks
    ORDER BY m.name
  `,
    /**
     * P8: Required concrete constituents
     * Expected: 3 constituents (Cement, Aggregate, Mixing water)
     */
    list_constituents: `
    MATCH (c:ConcreteConstituent)
    RETURN c.name as constituent_name
    ORDER BY c.name
  `,
    /**
     * P9: Mix parameters affecting fresh concrete properties
     */
    mix_parameters_affecting_fresh_concrete: `
    MATCH (mp:MixProportion)-[:INFLUENCED_BY]->(fcp:FreshConcreteProperty)
    RETURN mp.name as mix_parameter,
           collect(DISTINCT fcp.name) as affected_properties
    ORDER BY mp.name
  `,
    /**
     * P12: List fresh concrete properties
     */
    list_fresh_concrete_properties: `
    MATCH (p:FreshConcreteProperty)
    RETURN p.name as property_name
    ORDER BY p.name
  `,
    /**
     * P13: List hardened concrete properties
     */
    list_hardened_concrete_properties: `
    MATCH (p:HardenedConcreteProperty)
    RETURN p.name as property_name
    ORDER BY p.name
  `,
    /**
     * P18: Hardened concrete properties with standards
     */
    hardened_properties_with_standards: `
    MATCH (p:HardenedConcreteProperty)-[:COMPLY_WITH]->(s:Standard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,
    /**
     * P19: Manufacturing sequence (complete task chain)
     * Expected: 7 tasks in sequence
     */
    manufacturing_sequence: `
    MATCH path = (start:Task)-[:PERFORMED_BEFORE*]->(end:Task)
    WHERE NOT (start)<-[:PERFORMED_BEFORE]-()
    WITH path
    ORDER BY length(path) DESC
    LIMIT 1
    RETURN [node in nodes(path) | node.name] as sequence
  `,
    /**
     * P20: Properties influencing compressive strength
     * Expected: 16 properties
     */
    property_influences: `
    MATCH (target {name: $propertyName})<-[:INFLUENCED_BY]-(influencer)
    RETURN influencer.name as influencing_property,
           labels(influencer) as property_type
    ORDER BY influencer.name
  `,
    /**
     * A6: Standards for specific property (e.g., compressive strength)
     */
    standards_for_property: `
    MATCH (p {name: $propertyName})-[:COMPLY_WITH]->(s:Standard)
    RETURN s.name as standard_name
    ORDER BY s.name
  `,
    /**
     * A7: Mix design standards
     */
    mix_design_standards: `
    MATCH (s:Standard)<-[:COMPLY_WITH]-(mp:MixProportion)
    RETURN s.name as standard_name,
           collect(DISTINCT mp.name) as mix_parameters
    ORDER BY s.name
  `,
    /**
     * A18: Test methods for fresh concrete properties
     */
    fresh_concrete_test_methods: `
    MATCH (p:FreshConcreteProperty)-[:TESTED_ACCORDING_TO]->(tm:TestMethod)
    RETURN p.name as property_name,
           collect(DISTINCT tm.name) as test_methods
    ORDER BY p.name
  `,
    /**
     * A19: Test methods for hardened concrete properties
     */
    hardened_concrete_test_methods: `
    MATCH (p:HardenedConcreteProperty)-[:TESTED_ACCORDING_TO]->(tm:TestMethod)
    RETURN p.name as property_name,
           collect(DISTINCT tm.name) as test_methods
    ORDER BY p.name
  `,
    /**
     * A20: Standards for specific test method
     */
    standards_for_test_method: `
    MATCH (tm:TestMethod {name: $testMethodName})-[:COMPLY_WITH]->(s:Standard)
    RETURN s.name as standard_name
    ORDER BY s.name
  `
};
/**
 * Get query template by name
 */
function getQualityManagementQuery(templateName) {
    return exports.QUALITY_MANAGEMENT_QUERIES[templateName];
}
/**
 * List all available quality management query templates
 */
function listQualityManagementQueries() {
    return Object.keys(exports.QUALITY_MANAGEMENT_QUERIES);
}
//# sourceMappingURL=quality-management.js.map