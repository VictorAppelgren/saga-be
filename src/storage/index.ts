import neo4j, { Driver, Session } from 'neo4j-driver';

export interface Neo4jConfig {
  uri: string;
  username: string;
  password: string;
}

export class Neo4jStorage {
  private driver: Driver;
  private config: Neo4jConfig;

  constructor(config: Neo4jConfig) {
    this.config = config;
    this.driver = neo4j.driver(
      config.uri,
      neo4j.auth.basic(config.username, config.password)
    );
  }

  async connect(): Promise<void> {
    try {
      await this.driver.verifyConnectivity();
      console.log('Connected to Neo4j Aura');
    } catch (error) {
      console.error('Failed to connect to Neo4j:', error);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    await this.driver.close();
    console.log('Disconnected from Neo4j');
  }

  getSession(): Session {
    return this.driver.session();
  }

  async executeQuery(query: string, parameters: Record<string, any> = {}): Promise<any[]> {
    const session = this.getSession();
    try {
      const result = await session.run(query, parameters);
      return result.records.map(record => record.toObject());
    } finally {
      await session.close();
    }
  }

  async createNode(label: string, properties: Record<string, any>): Promise<void> {
    const query = `CREATE (n:${label} $properties)`;
    await this.executeQuery(query, { properties });
  }

  async findNodes(label: string, properties: Record<string, any> = {}): Promise<any[]> {
    const whereClause = Object.keys(properties).length > 0 
      ? `WHERE ${Object.keys(properties).map(key => `n.${key} = $${key}`).join(' AND ')}`
      : '';
    
    const query = `MATCH (n:${label}) ${whereClause} RETURN n`;
    return this.executeQuery(query, properties);
  }
}