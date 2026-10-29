/**
 * Quality Management Query Templates
 *
 * Cypher queries matching Agent Skill patterns for:
 * - Standards compliance (P1, P2, P4, A6, A7)
 * - Manufacturing processes (P6, P8, P19)
 * - Property testing requirements (A18, A19, A20)
 */

export const QUALITY_MANAGEMENT_QUERIES = {
  /**
   * P1: List all standards
   * Expected: 41 standards
   */
  list_all_standards: `
    MATCH (s:ComplianceStandard)
    RETURN s.name as standard_name
    ORDER BY s.name
  `,

  /**
   * P2: Cement properties with standards
   * Expected: 11 cement properties
   */
  cement_properties_with_standards: `
    MATCH (p:StandardCementProperty)-[:COMPLIES_WITH]->(s:ComplianceStandard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,

  /**
   * P3: Aggregate properties with standards
   */
  coarse_aggregate_properties_with_standards: `
    MATCH (p:StandardAggregateProperty)-[:COMPLIES_WITH]->(s:ComplianceStandard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,

  /**
   * P4: Water properties with standards
   * Expected: 11 water properties
   */
  water_properties_with_standards: `
    MATCH (p:StandardMixingWaterProperty)-[:COMPLIES_WITH]->(s:ComplianceStandard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,

  /**
   * P6: List all machines with their tasks
   * Expected: 4 machines
   */
  list_all_machines: `
    MATCH (m:ProductionMachine)
    OPTIONAL MATCH (t:PlannedTask)-[:PROCESSED_ON]->(m)
    RETURN m.name as machine_name,
           collect(DISTINCT t.name) as tasks
    ORDER BY m.name
  `,

  /**
   * P8: Required concrete constituents
   * Expected: 3 constituents (Cement, Aggregate, Mixing water)
   */
  list_constituents: `
    MATCH (c:StandardConcreteConstituent)
    RETURN c.name as constituent_name
    ORDER BY c.name
  `,

  /**
   * P9: Mix parameters affecting fresh concrete properties
   */
  mix_parameters_affecting_fresh_concrete: `
    MATCH (fcp:StandardFreshConcreteProperty)-[:INFLUENCED_BY]->(mp:DesignedMixProportion)
    RETURN mp.name as mix_parameter,
           collect(DISTINCT fcp.name) as affected_properties
    ORDER BY mp.name
  `,

  /**
   * P12: List fresh concrete properties
   */
  list_fresh_concrete_properties: `
    MATCH (p:StandardFreshConcreteProperty)
    RETURN p.name as property_name
    ORDER BY p.name
  `,

  /**
   * P13: List hardened concrete properties
   */
  list_hardened_concrete_properties: `
    MATCH (p:StandardHardenedConcreteProperty)
    RETURN p.name as property_name
    ORDER BY p.name
  `,

  /**
   * P18: Hardened concrete properties with standards
   */
  hardened_properties_with_standards: `
    MATCH (p:StandardHardenedConcreteProperty)-[:COMPLIES_WITH]->(s:ComplianceStandard)
    RETURN p.name as property_name,
           collect(DISTINCT s.name) as standards
    ORDER BY p.name
  `,

  /**
   * P19: Manufacturing sequence (complete task chain)
   * Expected: 7 tasks in sequence
   */
  manufacturing_sequence: `
    MATCH path = (start:PlannedTask)-[:PRECEDES*]->(end:PlannedTask)
    WHERE NOT EXISTS { MATCH (:PlannedTask)-[:PRECEDES]->(start) }
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
    MATCH (p {name: $propertyName})-[:COMPLIES_WITH]->(s:ComplianceStandard)
    RETURN s.name as standard_name
    ORDER BY s.name
  `,

  /**
   * A7: Mix design standards
   */
  mix_design_standards: `
    MATCH (s:ComplianceStandard)<-[:COMPLIES_WITH]-(mp:DesignedMixProportion)
    RETURN s.name as standard_name,
           collect(DISTINCT mp.name) as mix_parameters
    ORDER BY s.name
  `,

  /**
   * A18: Test methods for fresh concrete properties
   */
  fresh_concrete_test_methods: `
    MATCH (p:StandardFreshConcreteProperty)-[:TESTED_IN]->(tm:FreshConcreteTest)
    RETURN p.name as property_name,
           collect(DISTINCT tm.name) as test_methods
    ORDER BY p.name
  `,

  /**
   * A19: Test methods for hardened concrete properties
   */
  hardened_concrete_test_methods: `
    MATCH (p:StandardHardenedConcreteProperty)-[:TESTED_IN]->(tm:FreshConcreteTest)
    RETURN p.name as property_name,
           collect(DISTINCT tm.name) as test_methods
    ORDER BY p.name
  `,

  /**
   * A20: Standards for specific test method
   */
  standards_for_test_method: `
    MATCH (tm:FreshConcreteTest {name: $testMethodName})-[:COMPLIES_WITH]->(s:ComplianceStandard)
    RETURN s.name as standard_name
    ORDER BY s.name
  `
};

/**
 * Get query template by name
 */
export function getQualityManagementQuery(templateName: string): string | undefined {
  return QUALITY_MANAGEMENT_QUERIES[templateName as keyof typeof QUALITY_MANAGEMENT_QUERIES];
}

/**
 * List all available quality management query templates
 */
export function listQualityManagementQueries(): string[] {
  return Object.keys(QUALITY_MANAGEMENT_QUERIES);
}
