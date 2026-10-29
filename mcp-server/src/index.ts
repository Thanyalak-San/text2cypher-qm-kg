#!/usr/bin/env node

/**
 * MCP Server Entry Point
 *
 * Concrete Factory Knowledge Graph MCP Server
 * Provides natural language query interface to Neo4j knowledge graph via MCP protocol.
 */

import { readFileSync } from 'fs';
import { resolve } from 'path';
import { startServer } from './server.js';

// Load environment variables manually to avoid any stdout pollution
// MCP requires ONLY JSON-RPC on stdout
try {
  const envPath = resolve(process.cwd(), '.env');
  const envContent = readFileSync(envPath, 'utf-8');
  envContent.split('\n').forEach(line => {
    const match = line.match(/^([^=:#]+)=(.*)$/);
    if (match) {
      const [, key, value] = match;
      process.env[key.trim()] = value.trim();
    }
  });
} catch (error) {
  // .env file not required if environment variables are set via config
  console.error('[MCP Server] Note: .env file not found, using environment variables from config');
}

// Validate required environment variables
const requiredEnvVars = ['NEO4J_PASSWORD'];
const missingVars = requiredEnvVars.filter(varName => !process.env[varName]);

if (missingVars.length > 0) {
  console.error('✗ Missing required environment variables:', missingVars.join(', '));
  console.error('  Create a .env file with:');
  console.error('    NEO4J_URI=bolt://localhost:7687');
  console.error('    NEO4J_USER=neo4j');
  console.error('    NEO4J_PASSWORD=your_password');
  console.error('    NEO4J_DATABASE=neo4j');
  process.exit(1);
}

// Start server (logs go to stderr for MCP protocol)
console.error('='.repeat(70));
console.error('Concrete Factory MCP Server');
console.error('='.repeat(70));
console.error(`Neo4j URI: ${process.env.NEO4J_URI || 'bolt://localhost:7687'}`);
console.error(`Database: ${process.env.NEO4J_DATABASE || 'neo4j'}`);
console.error(`Result Limit: ${process.env.RESULT_LIMIT || 50}`);
console.error(`Query Timeout: ${process.env.QUERY_TIMEOUT_MS || 30000}ms`);
console.error('='.repeat(70));
console.error();

startServer().catch(error => {
  console.error('✗ Fatal error:', error);
  process.exit(1);
});
