## Project Overview

This project implements a **local, AI-assisted configuration management system** that enables safe modification of complex JSON configuration files using natural language.

The core goal is to transform **unstructured user input** into **structured, validated configuration changes**, while preserving strict safety guarantees through **deterministic code** and **JSON Schema validation**.

The system is intentionally designed to balance:
- AI flexibility
- Deterministic correctness
- Schema-enforced safety

---

## System Workflow Overview

The system operates as a **multi-stage pipeline** with clearly separated responsibilities.

### Pipeline Stages

1. **Intent Analysis**
   - A locally hosted LLM (Phi-3 via Ollama) interprets the user’s natural language input.
   - Determines:
     - Target application
     - Intended configuration parameter
     - Desired value

2. **Deterministic Processing**
   - All numeric parsing, normalization, and unit conversion are handled by Python code.
   - No numeric interpretation is delegated to the AI.

3. **Schema Validation**
   - The proposed configuration change is validated against the application’s JSON Schema.

4. **Application**
   - Only schema-approved changes are returned to the caller.

This layered design combines AI interpretation with deterministic execution and schema-level safety.

---

## 1. Initial Goal and First Design

### Scope and Intent
- Accept natural language configuration requests.
- Safely apply changes to application configuration files.
- Eliminate manual JSON editing while preserving strict structural correctness.

### Initial Design
The AI model was initially provided with:
- The full JSON Schema
- The current configuration values

The model was expected to return a fully updated JSON object.

### Observed Problems
- Excessive prompt sizes
- Long inference times
- Frequent HTTP read timeouts

### Design Decision
Responsibilities were redistributed:
- The AI was limited to **intent interpretation**
- All structural logic and mutation were moved into application code

### Outcome and Trade-off
- Faster and more predictable responses
- Reduced AI complexity
- A deliberate shift from creative AI usage toward reliability

---

## 2. LLM Timeout Problem

### Problem Description
Requests such as:
set tournament service memory to 1024mb

frequently resulted in HTTP timeout errors.

### Root Cause Analysis
- JSON Schema and values created very large prompts
- CPU-based inference was slow
- HTTP timeout thresholds were exceeded

### Resolution Strategy
The AI was restricted to producing a minimal structure:

{ "app": "...", "path": "...", "value": "..." }
All JSON manipulation was delegated to deterministic Python code.

Resulting Trade-off
Timeouts were eliminated

Performance improved significantly

System stability was prioritized over AI autonomy

3. Hallucinated JSON Paths
Problem Description
The AI occasionally generated configuration paths that did not exist, causing schema validation failures.

Risk Assessment
The AI inferred structure instead of following schema

Silent configuration corruption was identified as a critical production risk

Mitigation Strategy
A strict validation pipeline was enforced:

Deep-copy the current values JSON

Apply the change via deterministic code

Validate using jsonschema.validate

Reject immediately on failure

Outcome
Invalid configurations cannot be committed

JSON Schema acts as the final authority

4. Service-to-Service Communication
Design Intent
Service communication is documented at the logical level, not the raw HTTP level.

Interaction Model
The Bot Service:

Fetches schemas from the Schema Service

Fetches values from the Values Service

Characteristics:

Communication via simple HTTP GET requests

Application names used as identifiers

No external state mutation

Logical Flow
Fetch schema and values

Apply change on a deep-copied object

Validate against schema

Reject or return the result

Documentation Trade-off
README.md documents HTTP endpoints

INTERN.md documents architectural reasoning and safety guarantees

5. Invalid Path Errors from README Examples
Problem Description
The input:

set GAME_NAME env to toyblast for matchmaking service
initially failed due to an invalid path.

Analysis
The actual configuration path was deeply nested

The AI could not reliably infer this hierarchy

Resolution
Prompts were updated to enforce exact path rules

Code-level normalization was added for common patterns:

env

cpu

memory

Outcome
README examples became stable

Path hallucinations were significantly reduced

6. Missing Debug Tools in Docker
Problem Description
Minimal base images lacked basic debugging tools:

makefile
Kodu kopyala
curl: not found
Resolution
The curl package was explicitly installed in the Bot Service Docker image.

Trade-off
Slightly larger image size

Significantly improved debuggability

7. Ollama Model Availability Issues
Problem Description
Early requests failed with:

404 Not Found

model not found

Root Cause
The Ollama service started before the required model was pulled.

Resolution
Explicit model pull during setup:

ollama pull phi3:latest
Clearer service dependency handling

8. Why Some Logic Is Hard-Coded
Design Intent
Guarantee precise and predictable numeric interpretation.

Examples
%80

1024mb

replicas

Design Decision
A hybrid approach was adopted:

AI identifies intent

Application code performs parsing and normalization

Outcome
Deterministic behavior

Reduced ambiguity

Improved schema compatibility

9. Core Architectural Insight
The system enforces a strict separation of responsibility:

AI → Interpreter

Code → Authority

Schema → Final decision-maker

This separation is essential for building reliable, production-safe systems.

10. Final Result
Summary
The final system balances performance, correctness, and safety using fully local resources.

System Properties
Fully Local
No external API dependencies

Schema-Safe
Invalid data cannot be committed

Deterministic
Critical logic is code-controlled

Debuggable
Every transformation step is traceable

11. Framework Selection: Why FastAPI
Summary
FastAPI was selected to implement small, independent HTTP services with strong validation guarantees and minimal complexity.

Reasons
Strong request/response validation via Pydantic

Clear and explicit API contracts

Minimal boilerplate

Structured error handling

Trade-off
Advanced framework features were intentionally avoided

FastAPI is treated as a thin HTTP layer, not a business logic container

12. Limitations and Assumptions
Limitations
Single-node execution

Updated configurations are not persisted to disk

No authentication or authorization layer

Assumptions
Trusted local execution environment

AI output is never authoritative

JSON Schema is the final validation authority

Deterministic code always overrides AI suggestions

Design Outcome
These constraints simplify the system, improve predictability, and prioritize correctness and safety over feature completeness.
