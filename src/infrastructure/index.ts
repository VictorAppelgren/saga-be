export interface InfrastructureConfig {
  region: string;
  environment: 'dev' | 'staging' | 'prod';
  projectName: string;
}

export abstract class BaseInfrastructure {
  protected config: InfrastructureConfig;

  constructor(config: InfrastructureConfig) {
    this.config = config;
  }

  abstract deploy(): Promise<void>;
  abstract destroy(): Promise<void>;
  abstract getOutputs(): Promise<Record<string, string>>;
}

export class AWSInfrastructure extends BaseInfrastructure {
  async deploy(): Promise<void> {
    console.log(`Deploying AWS infrastructure for ${this.config.projectName} in ${this.config.environment}`);
  }

  async destroy(): Promise<void> {
    console.log(`Destroying AWS infrastructure for ${this.config.projectName}`);
  }

  async getOutputs(): Promise<Record<string, string>> {
    return {
      apiEndpoint: `https://api-${this.config.environment}.${this.config.projectName}.com`,
      databaseEndpoint: `neo4j+s://xxx.databases.neo4j.io`
    };
  }
}