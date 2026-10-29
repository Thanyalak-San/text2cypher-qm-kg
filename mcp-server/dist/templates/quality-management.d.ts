/**
 * Quality Management Query Templates
 *
 * Cypher queries matching Agent Skill patterns for:
 * - Standards compliance (P1, P2, P4, A6, A7)
 * - Manufacturing processes (P6, P8, P19)
 * - Property testing requirements (A18, A19, A20)
 */
export declare const QUALITY_MANAGEMENT_QUERIES: {
    /**
     * P1: List all standards
     * Expected: 41 standards
     */
    list_all_standards: string;
    /**
     * P2: Cement properties with standards
     * Expected: 11 cement properties
     */
    cement_properties_with_standards: string;
    /**
     * P3: Coarse aggregate properties with standards
     */
    coarse_aggregate_properties_with_standards: string;
    /**
     * P4: Water properties with standards
     * Expected: 11 water properties
     */
    water_properties_with_standards: string;
    /**
     * P6: List all machines with their tasks
     * Expected: 4 machines
     */
    list_all_machines: string;
    /**
     * P8: Required concrete constituents
     * Expected: 3 constituents (Cement, Aggregate, Mixing water)
     */
    list_constituents: string;
    /**
     * P9: Mix parameters affecting fresh concrete properties
     */
    mix_parameters_affecting_fresh_concrete: string;
    /**
     * P12: List fresh concrete properties
     */
    list_fresh_concrete_properties: string;
    /**
     * P13: List hardened concrete properties
     */
    list_hardened_concrete_properties: string;
    /**
     * P18: Hardened concrete properties with standards
     */
    hardened_properties_with_standards: string;
    /**
     * P19: Manufacturing sequence (complete task chain)
     * Expected: 7 tasks in sequence
     */
    manufacturing_sequence: string;
    /**
     * P20: Properties influencing compressive strength
     * Expected: 16 properties
     */
    property_influences: string;
    /**
     * A6: Standards for specific property (e.g., compressive strength)
     */
    standards_for_property: string;
    /**
     * A7: Mix design standards
     */
    mix_design_standards: string;
    /**
     * A18: Test methods for fresh concrete properties
     */
    fresh_concrete_test_methods: string;
    /**
     * A19: Test methods for hardened concrete properties
     */
    hardened_concrete_test_methods: string;
    /**
     * A20: Standards for specific test method
     */
    standards_for_test_method: string;
};
/**
 * Get query template by name
 */
export declare function getQualityManagementQuery(templateName: string): string | undefined;
/**
 * List all available quality management query templates
 */
export declare function listQualityManagementQueries(): string[];
//# sourceMappingURL=quality-management.d.ts.map