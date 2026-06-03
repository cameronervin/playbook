# Agent Rules (LLM Service)

## Model Tiers
| Tier | Purpose | Example |
|------|---------|---------|
| `DEFAULT` | Balanced performance | Standard model |
| `ADVANCED` | Complex reasoning | High-capability model |
| `FAST` | Quick responses | Optimized for speed |

## Methods
| Method | Purpose |
|--------|---------|
| `stream_response()` | Streaming |
| `run_with_tools()` | Tool loop |
| `generate_with_schema()` | Structured |

## Local Tool
```python
ToolRegistry.register(
    name="my_tool",
    description="desc",
    input_schema={"type": "object", "properties": {}},
    handler=fn,
)
```

## MCP Server
```python
MCPRegistry.add_server("name", "http://server/mcp")
```

## Constants
| Enum | Purpose | Values |
|------|---------|--------|
| `ModelTier` | Capability levels | DEFAULT, ADVANCED, FAST |
| `StopReason` | Completion reasons | END_TURN, TOOL_USE, MAX_TOKENS |
| `ContentType` | Message content types | TEXT, TOOL_USE, TOOL_RESULT |

## DO
- Use `ModelTier` enum for capability-based model selection
- Use structured tool definitions with schemas
- Use constants (not magic strings)
- Inject client/service via `Depends()`
- Return structured responses via schemas

## DON'T
- Hardcode model names or provider-specific strings
- Bypass tool registries (use ToolRegistry/MCPRegistry)
- Mix business logic with LLM client code
- Return raw API responses (use domain models)
