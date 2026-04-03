# Design Document: ADR Review Agent

## Approach

The agent follows a pipeline architecture: **Fetch → Filter → Classify → Generate → Commit → Feedback**.

Each stage is a standalone service with Pydantic models as contracts between stages. There is no framework — the pipeline is wired together in the CLI orchestration layer (`src/cli.py`).

## Key Architectural Decisions

### 1. Multi-Perspective Classification (instead of single-prompt)

For each MR, three LLM calls run in parallel with different analysis lenses:

- **API Contract analyst**: endpoints, DTOs, versioning
- **Dependency/Coupling analyst**: inter-service calls, transaction boundaries
- **Risk/Security analyst**: security changes, dead code, incomplete integration

**Why**: A single prompt tends to fixate on whichever signal is most obvious in the diff. Three perspectives catch different types of architectural significance. Consensus (2/3 agree) provides natural calibration.

**Trade-off #1**: 3x LLM cost per MR vs. classification accuracy. For 6 sample MRs, this means 18 LLM calls instead of 6. Acceptable for a prototype; in production, the first-pass file filter reduces the diff size sent to each call, and only architecturally relevant files are analyzed.

### 2. No Agent Framework (DIY pipeline vs. LangChain/CrewAI)

The data flow is a linear pipeline with one fan-out step (parallel classification). This is `asyncio.gather()`, not a graph.

**Why**: Agent frameworks solve cyclic agent graphs, tool routing, and conversational memory. This agent has none of those requirements. Adding LangChain would mean: more dependencies, more indirection, harder debugging, and a longer setup time — violating the 30-minute README goal.

**Trade-off #2**: Flexibility vs. simplicity. If the agent needed dynamic tool selection, multi-step reasoning, or agent-to-agent conversation, a framework would pay for itself. For a fan-out/fan-in classification pipeline, raw Python is sufficient.

### 3. Anthropic tool_use for Structured Output

All LLM responses use Anthropic's tool_use feature with JSON schemas. This forces the model to return structured data matching our Pydantic models.

**Why**: Eliminates fragile regex parsing of free-text responses. The classification schema, ADR generation schema, and escalation schema are all defined as tool input schemas. Pydantic validates the output before downstream processing.

### 4. State Persistence in the Architecture-Decisions Repo

Processing state (`.agent-state.json`) is committed alongside ADL/ADR files in the architecture-decisions repo.

**Why**: Makes the agent's memory reproducible and inspectable (Constitution VI). Running the agent from any machine produces consistent behavior because the state travels with the repo.

### 5. Escalation Precedent Lookup (instead of full ML)

Resolved escalation decisions are stored as key-value pairs in the state file. On subsequent runs, the agent checks if a similar pattern was previously resolved and applies that decision.

**Why**: A full feedback loop (fine-tuning, embeddings, RAG) is overkill for a prototype. A simple pattern-hash lookup achieves the goal (don't re-escalate the same type of finding) with minimal complexity.

## Prompt Design

The three analysis prompts (`src/prompts/`) follow a consistent structure:

1. **Role definition**: "You are a [perspective] analyst"
2. **Positive taxonomy**: What IS architecturally significant from this perspective
3. **Negative taxonomy**: What is NOT significant (critical for reducing false positives)
4. **Change type enum**: Fixed categories to ensure consistent labeling across runs
5. **Output instructions**: Use the provided tool, classify with confidence
6. **Context handling**: How to weight resolved vs. unresolved review comments

Key design choice: **temperature=0** for all classification calls. We want determinism, not creativity.

### File Relevance Filter

Before sending diffs to the LLM, we pre-filter to architecturally relevant files using regex patterns (controllers, clients, entities, configs, build files). This reduces token usage and focuses the model on what matters.

## Limitations

- **Git blame**: Provides minimal value on the sample repos (2 commits each). Fully implemented but demonstrates value on mature repos with deeper history.
- **External references**: The agent follows ticket references in MR metadata but does not scrape external systems (Confluence, Jira). It uses what's available in the GitLab API.
- **Pipeline polling**: After committing, the agent polls the pipeline with a 5-minute timeout. Long pipelines may time out.
- **Merge conflicts**: If the architecture-decisions repo has concurrent modifications, the agent's push may fail. This is a known limitation for the prototype.
