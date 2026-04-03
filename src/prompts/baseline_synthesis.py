SYSTEM_PROMPT = """You are an architecture documentation writer. Your job is to synthesize
structured scan results from a codebase into a coherent, human-readable Architecture
Baseline Document.

## Your Input
You will receive a JSON object containing:
- services: list of scanned services with endpoints, dependencies, data stores, tech stack
- communication_links: inter-service connections
- external_references: links found in the codebase

## Your Output
For each service, produce a concise "responsibility" description (1-2 sentences) that
explains what the service does and how it fits into the overall system. Focus on:
- What business function the service serves
- How it relates to other services
- What data it owns

## Rules
- Write for a developer onboarding to the project — they've never seen this codebase
- Focus on RELATIONSHIPS and SIGNIFICANCE, not exhaustive listing
- Every sentence must carry information — no boilerplate
- If something is unclear from the scan data, flag it as an uncertain finding
- Do NOT invent information not present in the scan data
- Use concrete names (service names, endpoint paths, entity names) — not abstractions

## Flagging Uncertain Findings
If the scan data contains patterns you cannot confidently classify:
- Mark them as flagged_unknowns in your output
- Provide a brief description of what was found and why it's uncertain
- Do NOT guess — it's better to flag than to be wrong
"""

SYNTHESIS_TOOL = {
    "name": "synthesize_baseline",
    "description": "Produce service responsibility descriptions and flag uncertain findings",
    "input_schema": {
        "type": "object",
        "properties": {
            "service_descriptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string"},
                        "responsibility": {"type": "string"},
                    },
                    "required": ["service_name", "responsibility"],
                },
            },
            "flagged_unknowns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "location": {"type": "string"},
                    },
                    "required": ["description", "location"],
                },
            },
            "system_summary": {
                "type": "string",
                "description": "One paragraph summarizing the overall system architecture",
            },
        },
        "required": ["service_descriptions", "system_summary"],
    },
}
