# Backend & Pipelines Repository

## Overview
This repository contains all **backend services** and **data processing pipelines** for our "Snapshot of the World" platform.  
It powers the ingestion, validation, storage, and querying of world state data that the frontend interacts with via HTTP APIs.

We enforce **TypeScript** across the entire backend to ensure type safety, maintainability, and consistency.

---

## Modules

### 1. **API Services**
- **Description:** Exposes HTTP endpoints for the frontend and other clients.
- **Responsibilities:**
  - Receive user requests (queries, task scheduling).
  - Translate natural language requests into structured queries.
  - Retrieve and aggregate insights from the graph database.
  - Trigger deeper analysis workflows.
- **Tech stack:**
  - Language: **TypeScript**
  - Framework: Express.js or Fastify
  - Authentication: JWT-based (details TBD)
  - API Documentation: OpenAPI (Swagger)

---

### 2. **Data Ingestion Pipelines**
- **Description:** Pulls and streams data from external sources into our system.
- **Two pipeline types:**
  1. **Real-time ingestion** (scalable event-driven consumers).
  2. **Scheduled ingestion** (cron-based, predictable fetches).
- **Responsibilities:**
  - Connect to external APIs, feeds, and databases.
  - Normalize and enrich incoming data.
  - Push raw data into the validation pipeline via a message bus (Kafka/NATS).
- **Tech stack:**
  - Language: **TypeScript**
  - Runtime: Node.js
  - Messaging: Kafka, RabbitMQ, or AWS Kinesis

---

### 3. **Data Processing & Validation**
- **Description:** Ensures that only unique, high-quality data enters the "snapshot of the world."
- **Responsibilities:**
  - Deduplicate entries.
  - Validate using AI/ML models (run as separate services).
  - Tag data with provenance metadata.
  - Route invalid or suspicious data to cold storage.
- **Tech stack:**
  - Language: **TypeScript**
  - AI/ML inference calls via HTTP or gRPC to model-serving services.

---

### 4. **Storage Integration**
- **Description:** Handles interactions with storage systems.
- **Responsibilities:**
  - Write validated data to the graph database.
  - Maintain versioned snapshots for historical state queries.
  - Archive raw/unvalidated data for future reprocessing.
- **Tech stack:**
  - Language: **TypeScript**
  - Database: Neo4j, AWS Neptune, or other graph DB
  - Object Storage: S3-compatible

---

### 5. **Infrastructure-as-Code (IaC)**
- **Description:** Defines and manages backend cloud/on-prem infrastructure.
- **Responsibilities:**
  - Provision servers, message queues, databases, and networking.
  - Configure CI/CD pipelines for deployments.
- **Tech stack:**
  - Language: **TypeScript**
  - Tool: AWS CDK / Pulumi

---

## Development Guidelines

1. **Language Enforcement**
   - Only **TypeScript** is allowed for all application logic.
   - Strict TypeScript compiler settings enabled in `tsconfig.json`.

2. **Code Style**
   - Use ESLint + Prettier with project-wide configs.
   - Follow functional programming principles where possible.

3. **Folder Structure**
/api # API services
/pipelines # Ingestion pipelines
/validation # Processing & validation logic
/storage # Storage integration layer
/infrastructure # Infrastructure-as-code
/shared # Shared utilities and types

4. **Commit Guidelines**
- Use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.).
- Always include a short description of the change.

5. **Testing**
- Unit tests with Jest.
- Integration tests for API and pipeline flows.

6. **Boilerplate Generation**
- This repo is designed to work with AI-assisted boilerplate generation.
- When generating code:
  - Reference the relevant module section above.
  - Always generate TypeScript.
  - Include inline JSDoc comments for public functions.
  - Follow folder structure strictly.

---

## Example AI Prompt for Boilerplate
