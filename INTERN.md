## Project Overview

This project implements a **local, AI-assisted configuration management system** that enables safe modification of complex JSON configuration files using natural language.

The core goal is to transform **unstructured user input** into **structured, validated configuration changes**, while preserving strict safety guarantees through **deterministic code** and **JSON Schema validation**.

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

3. **Schema and Values Retrieval**
   - The Bot Service retrieves:
     - The application JSON Schema from the Schema Service
     - The current configuration values from the Values Service
   - These documents are treated as the single source of truth for validation and mutation.

4. **Schema Validation**
   - The proposed configuration change is validated against the application’s JSON Schema.

5. **Application**
   - Only schema-approved changes are returned to the caller.

This layered design combines AI interpretation with deterministic execution and schema-level safety.

---

1. **Initial Goal and First Design**
      Initially, I assumed that the safest approach would be to let the AI fully generate the updated configuration JSON, as long as it was validated against a schema.
   This seemed reasonable at first, because JSON Schema validation appeared to provide a strong safety net.

   - **Scope and Intent**
     - Accept natural language configuration requests.
     - Safely apply changes to application configuration files.
     - Eliminate manual JSON editing while preserving strict structural correctness.

   - **Initial Design**
     - The AI model was initially provided with:
       - The full JSON Schema
       - The current configuration values
     - The model was expected to return a fully updated JSON object.

   - **Observed Problems**
     - Excessive prompt sizes
     - Long inference times
     - Frequent HTTP read timeouts

   - **Design Decision**
     - Responsibilities were redistributed:
       - The AI was limited to **intent interpretation**
       - All structural logic and mutation were moved into application code

   - **Outcome and Trade-off**
     - Faster and more predictable responses
     - Reduced AI complexity
     - A deliberate shift from creative AI usage toward reliability

---

2. **LLM Timeout Problem**
     
   - **Problem Description**
     - Requests such as:
       ```
       set tournament service memory to 1024mb
       ```
       frequently resulted in HTTP timeout errors.

   - **Root Cause Analysis**
     - JSON Schema and values created very large prompts
     - CPU-based inference was slow
     - HTTP timeout thresholds were exceeded

   - **Resolution Strategy**
     - The AI was restricted to producing a minimal structure:
       ```json
       { "app": "...", "path": "...", "value": "..." }
       ```
     - All JSON manipulation was delegated to deterministic Python code.

   - **Resulting Trade-off**
     - Timeouts were eliminated
     - Performance improved significantly
     - System stability was prioritized over AI autonomy

---

3. **Hallucinated JSON Paths**
   -This issue changed how I think about AI reliability: even when an output looks structurally valid, it cannot be trusted unless it is enforced by deterministic code and validation.
   - **Problem Description**
     - The AI occasionally generated configuration paths that did not exist, causing schema validation failures.

   - **Risk Assessment**
     - The AI inferred structure instead of following schema.
     - Silent configuration corruption was identified as a critical production risk.

   - **Mitigation Strategy**
     - A strict validation pipeline was enforced:
       - Deep-copy the current values JSON
       - Apply the change via deterministic code
       - Validate using `jsonschema.validate`
       - Reject immediately on failure

   - **Outcome**
     - Invalid configurations cannot be committed.
     - JSON Schema acts as the final authority.
    
---

4. **Service-to-Service Communication**
   - **Design Intent**
     - Service communication is documented at the logical level, not the raw HTTP level.
     - Schemas and values are separated to reflect real-world systems, where validation contracts and runtime configuration evolve independently.

   - **Interaction Model**
     - The Bot Service:
       - Fetches schemas from the Schema Service
       - Fetches values from the Values Service

   - **Characteristics**
     - Communication via simple HTTP GET requests
     - Application names used as identifiers
     - No external state mutation

   - **Logical Flow**
     - Fetch schema and values
     - Apply change on a deep-copied object
     - Validate against schema
     - Reject or return the result

   - **Documentation Trade-off**
     - README.md documents HTTP endpoints
     - INTERN.md documents architectural reasoning and safety guarantees

---

5. **Invalid Path Errors from README Examples**
   - **Problem Description**
     - The input:
       ```
       set GAME_NAME env to toyblast for matchmaking service
       ```
       initially failed due to an invalid path.

   - **Analysis**
     - The actual configuration path was deeply nested.
     - The AI could not reliably infer this hierarchy.

   - **Resolution**
     - Prompts were updated to enforce exact path rules.
     - Code-level normalization was added for common patterns:
       - env
       - cpu
       - memory

   - **Outcome**
     - README examples became stable.
     - Path hallucinations were significantly reduced.

---

6. **Missing Debug Tools in Docker**
   - **Problem Description**
     - Minimal base images lacked basic debugging tools:
       ```
       curl: not found
       ```

   - **Resolution**
     - The curl package was explicitly installed in the Bot Service Docker image.

   - **Trade-off**
     - Slightly larger image size.
     - Significantly improved debuggability.

---

7. **Ollama Model Availability Issues**
   - **Problem Description**
     - Early requests failed with:
       - `404 Not Found`
       - `model not found`

   - **Root Cause**
     - The Ollama service started before the required model was pulled.

   - **Resolution**
     - Explicit model pull during setup:
       ```
       ollama pull phi3:latest
       ```
     - Clearer service dependency handling.

---

8. **Why Some Logic Is Hard-Coded**
   - **Design Intent**
     - Guarantee precise and predictable numeric interpretation.

   - **Examples**
     - `%80`
     - `1024mb`
     - `replicas`

   - **Design Decision**
     - A hybrid approach was adopted:
       - AI identifies intent.
       - Application code performs parsing and normalization.

   - **Outcome**
     - Deterministic behavior.
     - Reduced ambiguity.
     - Improved schema compatibility.

---

9. **Core Architectural Insight**
   - The system enforces a strict separation of responsibility:
     - AI → Interpreter
     - Code → Authority
     - Schema → Final decision-maker
   - This separation is essential for building reliable, production-safe systems.

---

10. **Final Result**
   - **Summary**
     - The final system balances performance, correctness, and safety using fully local resources.

   - **System Properties**
     - **Fully Local**
       - No external API dependencies
     - **Schema-Safe**
       - Invalid data cannot be committed
     - **Deterministic**
       - Critical logic is code-controlled
     - **Debuggable**
       - Every transformation step is traceable

---

11. **LLM Selection: Why Phi-3 via Ollama**

- **Scope and Intent**
  - The system requires a local language model that can:
    - Run entirely on a developer machine
    - Follow strict instructions
    - Produce short, structured, machine-readable output
    - Avoid creative or verbose responses

- **Model Choice**
  - Phi-3 was selected and deployed via Ollama for the following reasons:

- **Local Execution**
  - Runs fully locally with no external API dependency
  - Fully compliant with project constraints

- **Instruction-Following Reliability**
  - Performs well on short, rule-based prompts
  - Suitable for structured JSON-oriented output

- **CPU-Friendly Performance**
  - Acceptable inference times on CPU-only environments
  - No GPU requirement

- **Predictable Output**
  - Combined with low temperature and strict prompts
  - Output remains concise and deterministic

- **Design Trade-off**
  - Phi-3 is not chosen for creativity or general intelligence
  - It is chosen because:
    - Reliability > Creativity
    - Determinism > Expressiveness
  - This aligns with the system’s safety-first design


12. **Framework Selection: Why FastAPI**
   - **Summary**
     - FastAPI was selected to implement small, independent HTTP services with strong validation guarantees and minimal complexity.

   - **Reasons**
     - Strong request/response validation via Pydantic
     - Clear and explicit API contracts
     - Minimal boilerplate
     - Structured error handling

   - **Trade-off**
     - Advanced framework features were intentionally avoided
     - FastAPI is treated as a thin HTTP layer, not a business logic container

---

13. **Limitations and Assumptions**
   - **Limitations**
     - Single-node execution
     - Updated configurations are not persisted to disk
     - No authentication or authorization layer
     - This choice is intentional to keep the system stateless and focused on safe configuration transformation rather than long-term configuration storage.


   - **Assumptions**
     - Trusted local execution environment
     - AI output is never authoritative
     - JSON Schema is the final validation authority
     - Deterministic code always overrides AI suggestions

   - **Design Outcome**
     - These constraints simplify the system while prioritizing predictability, correctness, and safety.

