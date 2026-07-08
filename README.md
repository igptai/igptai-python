# iGPT Python SDK (`igptai`)

Official Python SDK for the iGPT API.

- Website: https://www.igpt.ai
- Documentation: https://docs.igpt.ai
- Playground: https://igpt.ai/hub/playground/

## Requirements

- Python >= 3.8

## Install

```bash
pip install igptai
```

## Authentication

All requests use a Bearer token:

* Header: `Authorization: Bearer <IGPT_API_KEY>`

Store keys in a secret manager or environment variables.




## Quick start

The typical flow when using iGPT is:

1. **Connect datasources** (per user)
2. **Retrieve answers** using the connected context


### Connect a datasource

This example starts an authorization flow to connect a user’s datasource.  
The response includes a **URL** the user must open to complete authorization.

```python
from igptai import IGPT

igpt = IGPT(api_key="IGPT_API_KEY")

res = igpt.connectors.authorize(user="user_123", service="spike", scope="messages")
if res is None:
    print("No response / request failed")
elif res.get("error"):
    print("Connection error:", res)
else:
    print("Open this URL to authorize:", res.get("url"))
```

### Ask with `recall.ask()`

After connecting a datasource, you can retrieve answers scoped to that user.

```python
from igptai import IGPT

igpt = IGPT(api_key="IGPT_API_KEY", user="user_123") # optional default user

res = igpt.recall.ask(input="Summarize key risks, decisions, and next steps from this week's meetings.")
if res is None:
    print("No response / request failed")
elif res.get("error"):
    # No-throw design: handle errors via return value
    print("iGPT error:", res)
else:
    print("iGPT response:", res)
```

---

## Services and routing

Calls map to API routes automatically, for example:

* `igpt.recall.run(...)` → `POST /recall/run`
* `igpt.recall.search(...)` → `POST /recall/search`
* `igpt.recall.ask(...)` → `POST /recall/ask`
* `igpt.datasources.list(...)` → `POST /datasources/list`
* `igpt.datasources.disconnect(...)` → `POST /datasources/disconnect`
* `igpt.connectors.authorize(...)` → `POST /connectors/authorize`


## Connectors

### `connectors.authorize()`

Authorize, connect, and start indexing a new datasource. [↗](https://docs.igpt.ai/docs/api-reference/connect "API reference")

#### Parameters

* `service` (string, required): Service provider identifier (e.g., `"spike"`).
* `scope` (string, required): Space-delimited scopes (e.g., `"messages"`).
* `user` (string, optional if set in constructor): Unique user identifier.
* `redirect_uri` (string, optional): Redirect URL after authorization completes.
* `state` (string, optional): Application state (returned after redirect).

#### Example: start an authorization flow

```python
res = igpt.connectors.authorize(service="spike", scope="messages", user="user_123", redirect_uri="https://yourapp.com/callback", state="optional_state")
print(res)
```

## Agentic Run

### `recall.run()`

Generate an agentic response based on the provided input and the end-user’s connected context.

A run may perform multiple reasoning turns, call internal tools, retrieve relevant sources, and stream the final response as it is generated.

* `input` (string, required): The prompt or question to process.
* `user` (string, optional if set in constructor): A unique identifier representing your end-user.
* `stream` (boolean, optional, default: `False`): When `True`, returns an async iterable of run events.
* `quality` (string, optional): Context engineering quality (e.g., `"cef-4-high"`).
* `reasoning_effort` (string, optional): Controls the reasoning effort (e.g., `"low"`, `"medium"`, or `"high"`).
* `output_format` (string | object, optional):
  * `"text"` - Plain-text output and the default format.
  * `"json"` - JSON output.
  * `{ schema: <JSON Schema> }` - Structured output that follows a JSON Schema.
* `instructions` (string, optional): Additional instructions controlling the response behavior, style, constraints, or structure.

#### Example: text output

```python
resp = client.recall.run(
    input="Summarize my unread emails from the last 7 days.",
    quality="cef-4-high",
    reasoning_effort="high",
    output_format="text",
    instructions="Be concise and highlight anything that needs a response."
)
print(resp)
```

#### Example: JSON output

```python
resp = client.recall.run(
    input="Summarize my last meeting and return the title and summary.",
    output_format="json"
)
print(resp)
```

#### Example: structured output with JSON Schema

Use a schema to produce a consistent, machine-readable response.

```python
output_format = {
    "type": "json_schema",
    "name": "action_items_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "action_items": {
                "type": "array",
                "description": "List of action items",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short summary of the action item"},
                        "owner": {"type": "string", "description": "Person responsible for the action item"},
                        "due_date": {"type": "string", "description": "Expected completion date, ISO 8601 (YYYY-MM-DD)"}
                    },
                    "required": ["title", "owner", "due_date"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["action_items"],
        "additionalProperties": False
    }
}
resp = client.recall.run(
    input="Extract all action items from yesterday’s board meeting.",
    quality="cef-4-high",
    reasoning_effort="high",
    output_format=output_format
)
print(resp)
```

### Streaming

For streaming responses, set `stream=True`.

The SDK returns an iterable that yields parsed JSON events. Each event represents a step in the run lifecycle.

```python
for chunk in client.recall.run(input="Summarize my unread emails from the last 7 days.", stream=True, quality="cef-1-normal"):
    print(chunk, end="", flush=True)
```

### Stream lifecycle

A streamed run starts with `run.start` and ends with `run.done`.

Everything between these two events belongs to the same run.

A run may contain one or more turns. Each turn may include reasoning, tool calls, or output generation.

```text
run.start

  run.turn.start
    run.reasoning_item.start
    run.reasoning_item.done

    run.tool_call_item
  run.turn.done

  run.tool_call_output_item

  run.turn.start
    run.reasoning_item.start

      run.reasoning_summary_part.start
      run.reasoning_summary_part.done

    run.reasoning_item.done

    run.output_item.start
      run.output_text.delta
      run.output_text.delta
      ...
    run.output_item.done
  run.turn.done

run.done
```
This lifecycle is representative. The exact number of turns, reasoning items, summary parts, tool calls, and output deltas depends on the request.

Important relationships:

- `run.start` opens the complete run.
- `run.done` closes the complete run.
- `seq` defines the exact order of all events in the run.
- `turn` identifies the model turn being processed.
- `callId` connects a tool call with its corresponding tool result.
- `run.output_text.delta` contains partial output text.
- `run.output_item.done` contains the complete assistant message.
- `run.done` contains the final run output, usage, duration, and aggregated source metadata.
- A `run.tool_call_output_item` may appear between the turn that requested the tool and the next turn that processes its result.
- Reasoning summary events are optional and may not appear in every turn.


## Recall

### `recall.ask()`

Generate a response based on the input and related context. [↗](https://docs.igpt.ai/docs/api-reference/ask "API reference")

#### Parameters

* `input` (string, required): The prompt/question to ask.
* `user` (string, optional if set in constructor): Unique user identifier.
* `stream` (boolean, optional, default: `false`): If `true`, returns an async iterable stream.
* `quality` (string, optional): Context engineering quality (default: `"cef-1-normal"`). [Read more](https://docs.igpt.ai/docs/concepts/cef).
* `output_format` (string | object, optional):
  * `"text"` (default)
  * `"json"`
  * `{ schema: <JSON Schema> }` to enforce a structured output

#### Example: text output

```python
res = igpt.recall.ask(input="Summarize my last meeting in 5 bullet points.", quality="cef-1-normal", output_format="text")
print(res)
```

#### Example: JSON output

```python
res = igpt.recall.ask(input="Return a JSON object with { title, summary } for my last meeting.", output_format="json")
print(res)
```

#### Example: Structured output with JSON Schema

Use a schema to get consistent, machine-validated structure.

```python
output_format = {
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "action_items": {
                "type": "array",
                "description": "List of action items",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": { "type": "string", "description": "Short summary of the action item" },
                        "owner": { "type": "string", "description": "Person responsible for the action item" },
                        "due_date": { "type": "string", "format": "date", "description": "Expected completion date" }
                    },
                    "required": ["title", "owner", "due_date"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["action_items"],
        "additionalProperties": False
    }
}
res = igpt.recall.ask(output_format=output_format, input="Extract all action items from yesterday’s board meeting.", quality: "cef-1-normal")
print(res)
```

#### Example response (schema)

```json
{
  "action_items": [
    {
      "title": "Approve revised Q1 budget allocation",
      "owner": "Board of Directors",
      "due_date": "2026-01-15"
    },
    {
      "title": "Approve final FY2026 strategic priorities",
      "owner": "Board of Directors",
      "due_date": "2026-01-31"
    }
  ]
}
```

### Streaming (SSE)

For streaming responses, set `stream=True`. The SDK returns an iterable that yields parsed JSON chunks.

Streaming is designed to be resilient: if the stream breaks due to connectivity, the iterator yields an error chunk and finishes rather than throwing.

#### Parameters (streaming-specific)

* `stream` must be `True`
* Other parameters are the same as `recall.ask`

#### Example: basic streaming

```python
stream = igpt.recall.ask(input="Summarize my last meeting.", stream=True)
for chunk in stream:
    if (isinstance(chunk, dict) and chunk.get("error")):
        print("Stream chunk error:", chunk)
        break
    print("chunk:", chunk)
```

### `recall.search()`

Search in connected datasources. [↗](https://docs.igpt.ai/docs/api-reference/search "API reference")

#### Parameters

* `query` (string, optional): Search query to execute.
* `user` (string, optional if set in constructor): Unique user identifier.
* `date_from` (string, optional): Start date filter (`YYYY-MM-DD`).
* `date_to` (string, optional): End date filter (`YYYY-MM-DD`).
* `max_results` (number, optional): Limit number of results (e.g., `50`).

#### Example: simple search

```python
res = igpt.recall.search(query="board meeting notes")
print(res)
```

#### Example: date-bounded search

```python
res = igpt.recall.search(query="budget allocation", date_from="2026-01-01", date_to="2026-01-31", max_results=25)
print(res)
```



## Datasources

### `datasources.list()`

List datasources and indexing status. [↗](https://docs.igpt.ai/docs/api-reference/list "API reference")

#### Parameters

* `user` (string, optional if set in constructor): Unique user identifier.

#### Example

```python
res = igpt.datasources.list()
print(res)
```

### `datasources.disconnect()`

Disconnect a datasource and remove indexed data. [↗](https://docs.igpt.ai/docs/api-reference/disconnect "API reference")

#### Parameters

* `id` (string, required): Datasource ID to disconnect (e.g., `"service/id/type"`).
* `user` (string, optional if set in constructor): Unique user identifier.

#### Example

```python
resp = igpt.datasources.disconnect(id="service/id/type")
print(resp)
```

## Advanced Configuration

```python
igpt = IGPT(
    api_key="IGPT_API_KEY",             # required
    user="default_user_id",             # optional default user
    base_url="https://api.igpt.ai/v1",  # optional override
    max_retries=3,                      # optional: network retries
    backoff_factor=2,                   # optional: exponential backoff factor
    backoff_base=100                    # optional: initial retry delay (ms)
    )
```

### Constructor options

* `api_key` (string, required): Your iGPT API key.
* `user` (string, optional): Default user identifier. If provided, you can omit `user` in method calls.
* `base_url` (string, optional): Override API base URL (default: `https://api.igpt.ai/v1`).
* `max_retries` (number, optional): Retry attempts (default: `3`).
* `backoff_base` (number, optional): Initial retry delay in milliseconds (default: `100`).
* `backoff_factor` (number, optional): Exponential backoff multiplier (default: `2`).

## Error handling

The SDK does not throw exceptions for request or stream failures.  
Instead, it returns (or yields) **normalized error objects** with a consistent shape:

```python
{ error: string }
```

### Client errors
Errors originating from the client environment:

* `{ error: "network_error" }` - A network-level failure occurred (timeout, DNS issue, offline).
* `{ error: "request_aborted" }` - The request was explicitly aborted by the caller.

### Server errors
Errors returned by the API:

* `{ error: "auth" }` - Authentication failed due to missing, invalid, or expired credentials.
* `{ error: "params" }` - The request parameters were invalid or malformed.

---

## Security & compliance

- Use a secure secret manager for `IGPT_API_KEY` (do not hardcode keys in source control).
- Ensure user identifiers (`user`) align with your internal identity and access model.
- For policy and legal references:
  - Privacy Policy: [https://www.igpt.ai/privacy-policy/](https://www.igpt.ai/privacy-policy)
  - Terms & Conditions: [https://www.igpt.ai/terms-and-conditions/](https://www.igpt.ai/terms-and-conditions)

## Resources

* Docs: [https://docs.igpt.ai](https://docs.igpt.ai)
* Playground: [https://igpt.ai/hub/playground/](https://igpt.ai/hub/playground/)
* Book a demo: [https://www.igpt.ai/contact-sales/](https://www.igpt.ai/contact-sales/)
* Contact: [hello@igpt.ai](mailto:hello@igpt.ai)

## License

MIT
