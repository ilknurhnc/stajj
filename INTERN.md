## Project Overview

This project implements a local, AI-assisted configuration management system that enables secure modification of complex JSON configuration files using natural language commands.

The core objective is to transform unstructured user input into structured, validated, and executable configuration changes while maintaining strict safety guarantees through deterministic code and JSON Schema validation.

---

## System Workflow Overview

The system operates as a multi-stage pipeline with clearly separated responsibilities.

### Pipeline Stages

1. Intent Analysis
   - A locally hosted LLM (Phi-3 via Ollama) interprets the user's natural language input
   - Determines:
     - Target application
     - Intended configuration parameter
     - Desired value

2. Deterministic Processing
   - All numeric parsing, normalization, and unit conversion are handled by predefined Python logic
   - No numeric interpretation is delegated to the AI

3. Schema Validation
   - The proposed configuration change is validated against the application’s JSON Schema

4. Application
   - Only schema-approved changes are committed to the configuration output

This layered design combines AI flexibility with deterministic correctness and schema-enforced safety.

---

## 1. Initial Goal and First Design

### Scope and Intent

- Build a fully local system capable of accepting natural language configuration requests
- Apply changes safely to application configuration files
- Eliminate manual JSON editing while preserving strict structural correctness

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

- The AI was limited to intent interpretation
- Structural logic and mutation were moved into application code

### Outcome and Trade-off

- Faster and more predictable responses
- Reduced AI complexity
- A deliberate shift from creative AI usage toward reliability

---

## 2. LLM Timeout Problem

### Scope and Intent

The Bot Service relies on a local LLM (Phi-3 via Ollama) running on CPU resources.

### Problem Description

Requests such as:

set tournament service memory to 1024mb

Frequently resulted in HTTP timeout errors.

### Root Cause Analysis

- JSON Schema and values created very large prompts
- CPU-based inference was slow
- HTTP timeout thresholds were exceeded

### Resolution Strategy

The AI was restricted to producing a minimal structure:

```json
{ "app": "...", "path": "...", "value": "..." }
All JSON manipulation was delegated to the Python backend.

Resulting Trade-off
Timeouts were eliminated

Performance improved significantly

System stability was prioritized over AI autonomy

---

## 3. Hallucinated JSON Paths

### Scope and Intent

All configuration changes must strictly conform to the defined JSON Schema.

### Problem Description

The AI occasionally generated configuration paths that did not exist, leading to validation failures.

### Risk Assessment

- The AI inferred or guessed structure
- Silent configuration corruption was identified as a critical production risk

### Mitigation Strategy

A strict validation pipeline was enforced:

1. Deep-copy the current values JSON
2. Apply the change via deterministic code
3. Validate using `jsonschema.validate`
4. Reject immediately on failure

### Outcome

- Invalid configurations are impossible to commit
- The JSON Schema acts as the final authority

---

## 4. Service-to-Service Communication

### Scope and Intent

Service-to-service communication is intentionally described at the logical level rather than the raw HTTP level.

This is a conscious documentation choice.

### How Services Communicate

The Bot Service communicates with:

- Schema Service to fetch the JSON Schema of an application
- Values Service to fetch the current configuration values

Characteristics:

- Communication occurs via simple HTTP GET requests
- Application names are used as identifiers
- The Bot Service never mutates external state

### Logical Interaction Flow

1. Fetch schema and values
2. Apply change on a deep-copied values object
3. Validate against schema
4. Reject or commit the result

### Documentation Trade-off

- README.md documents HTTP endpoints and request and response formats
- INTERN.md documents logical responsibilities, validation and safety guarantees, and architectural reasoning

This separation avoids duplication and keeps the intern-level documentation focused on design intent.


## 5. Invalid Path Errors from README Examples

### Scope and Intent

Ensuring that all documented example commands behave reliably.

### Problem Description

The input:

set GAME_NAME env to toyblast for matchmaking service

initially failed due to an invalid path.

### Analysis

- The actual configuration path was deeply nested
- The AI could not infer this reliably from abstraction alone

### Resolution

- System prompts were updated to clarify hierarchy rules
- Code-level normalization was added for common patterns such as:
  - env
  - cpu
  - memory

### Outcome

- README examples became stable
- Path hallucinations were significantly reduced

---

## 6. Missing Debug Tools in Docker

### Scope and Intent

Effective debugging during development and live testing.

### Problem Description

Minimal base images lacked basic debugging tools, resulting in errors such as:

curl: not found

### Resolution

The curl package was explicitly installed in the Bot Service Docker image.

### Trade-off

- Slightly larger image size
- Significantly improved debuggability

---

## 7. Ollama Model Availability Issues

### Scope and Intent

Ensuring reliable startup behavior for the local LLM dependency.

### Problem Description

Early requests failed with 404 or model not found errors.

### Root Cause

The Ollama service started before the required model was pulled locally.

### Resolution

Explicit model pull during setup:

ollama pull phi3:latest
Clearer service dependency handling was added.

---

## 8. Why Some Logic Is Hard-Coded

### Scope and Intent

Guaranteeing precise numeric interpretation.

### Problem Description

Allowing the AI to interpret numeric transformations proved unreliable.

Examples include:

- %80  
- 1024mb

### Design Decision

A hybrid approach was adopted:

- The AI identifies intent
- Application code performs parsing and normalization

### Outcome

- Predictable numeric behavior
- Reduced ambiguity in configuration changes

---

## 9. Core Architectural Insight

### Key Insight

The system follows a strict separation of responsibility:

- AI acts as the interpreter
- Code acts as the authority
- Schema acts as the final decision-maker

---

## 10. Final Result

### Summary

The final system balances performance, correctness, and safety using fully local resources.

### System Properties

- Fully Local  
  No external API dependencies

- Schema-Safe  
  Invalid data cannot be committed

- Deterministic  
  Critical logic is code-controlled

- Debuggable  
  Every transformation step is traceable
