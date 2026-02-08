# SSE Streaming Guide

## Overview

The MGX platform uses Server-Sent Events (SSE) for real-time agent streaming. This allows clients to receive incremental updates as the agent processes tasks, providing a responsive user experience.

## Architecture

```
Client → FastAPI SSE Endpoint → Event Table (MongoDB) ← Agent Runtime (Celery)
                 ↓
            Langfuse Trace
```

## API Endpoints

### 1. POST `/api/apps/{session_id}/agent/generate`

Start a new agent task and stream events.

**Request:**
```json
{
  "prompt": "Create a simple hello world API endpoint"
}
```

**Response:** SSE stream

**Headers:**
- `Authorization: Bearer {token}`
- `Content-Type: application/json`

**Example (JavaScript):**
```javascript
const eventSource = new EventSource(
  `/api/apps/${sessionId}/agent/generate?token=${token}`,
  {
    method: 'POST',
    body: JSON.stringify({ prompt: userPrompt })
  }
);

eventSource.addEventListener('delta', (e) => {
  const data = JSON.parse(e.data);
  console.log('Token:', data.delta);
});

eventSource.addEventListener('message', (e) => {
  const data = JSON.parse(e.data);
  console.log('Complete message:', data.content);
});

eventSource.addEventListener('finish', (e) => {
  console.log('Task completed');
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  const data = JSON.parse(e.data);
  console.error('Error:', data.error);
  eventSource.close();
});
```

### 2. GET `/api/apps/{session_id}/agent/stream-continue`

Resume streaming from a specific timestamp (for reconnection).

**Query Parameters:**
- `since_timestamp`: Unix timestamp to resume from; omit for all events

**Response:** SSE stream

**Example (JavaScript):**
```javascript
const eventSource = new EventSource(
  `/api/apps/${sessionId}/agent/stream-continue?since_timestamp=${lastEventTimestamp}&token=${token}`
);

// Same event handlers as above
```

## Event Types

### Delta Event (`delta`)

Incremental LLM token output.

```json
{
  "event": "delta",
  "id": "evt_123abc",
  "data": {
    "event_type": "message_delta",
    "delta": "Hello",
    "content_type": "text",
    "trace_id": "trace_langfuse_123",
    "run_id": "run_456"
  }
}
```

### Message Event (`message`)

Complete message (e.g., after tool execution).

```json
{
  "event": "message",
  "id": "evt_456def",
  "data": {
    "event_type": "message_complete",
    "message_id": "msg_789ghi",
    "content": "It's sunny in San Francisco",
    "trace_id": "trace_langfuse_123"
  }
}
```

### Status Event (`status`)

Agent status updates (start, end, tool calls).

```json
{
  "event": "status",
  "id": "evt_789ghi",
  "data": {
    "event_type": "agent_start",
    "prompt": "User prompt here",
    "framework": "fastapi-vite"
  }
}
```

### Error Event (`error`)

Error notification.

```json
{
  "event": "error",
  "id": "evt_error123",
  "data": {
    "event_type": "agent_error",
    "error": "Failed to execute tool",
    "error_type": "ToolExecutionError"
  }
}
```

### Finish Event (`finish`)

Task completion (terminal event).

```json
{
  "event": "finish",
  "id": "evt_finish123",
  "data": {
    "event_type": "finish",
    "status": "success"
  }
}
```

## Client Implementation

### React Example

```typescript
import { useEffect, useState } from 'react';

interface SSEEvent {
  type: string;
  id: string;
  data: any;
}

function useAgentStream(sessionId: string, prompt: string) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!prompt) return;

    setIsStreaming(true);
    setError(null);

    const eventSource = new EventSource(
      `/api/apps/${sessionId}/agent/generate?prompt=${encodeURIComponent(prompt)}`
    );

    eventSource.onmessage = (e) => {
      const event: SSEEvent = {
        type: e.type,
        id: e.lastEventId,  // event_id from SSE
        data: JSON.parse(e.data)
      };
      setEvents(prev => [...prev, event]);
    };

    eventSource.addEventListener('finish', () => {
      setIsStreaming(false);
      eventSource.close();
    });

    eventSource.onerror = (e) => {
      setError('Stream connection error');
      setIsStreaming(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [sessionId, prompt]);

  return { events, isStreaming, error };
}
```

### Python Example

```python
import httpx

async def stream_agent_events(session_id: str, prompt: str):
    """Stream agent events."""
    url = f"http://localhost:8000/api/apps/{session_id}/agent/generate"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"prompt": prompt}
    
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, headers=headers, json=data) as response:
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("id:"):
                    event_id = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    event_data = json.loads(line.split(":", 1)[1].strip())
                    
                    # Process event
                    if event_type == "delta":
                        print(event_data["delta"], end="", flush=True)
                    elif event_type == "finish":
                        print("\nTask completed!")
                        break
```

## Reconnection Strategy

### Best Practices

1. **Store last event timestamp**: Track `event.data.timestamp` from each event for reconnection
2. **Reconnect on disconnect**: Use `stream-continue` endpoint with `since_timestamp` (omit for all events)
3. **Exponential backoff**: Wait 1s, 2s, 4s, 8s between retries
4. **Max retries**: Give up after 5 failed attempts

### Example Implementation

```javascript
class AgentStreamClient {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.lastEventTimestamp = null;  // Unix timestamp from event.data
    this.retryCount = 0;
    this.maxRetries = 5;
  }

  connect(prompt = null) {
    const url = prompt
      ? `/api/apps/${this.sessionId}/agent/generate`
      : `/api/apps/${this.sessionId}/agent/stream-continue?since_timestamp=${this.lastEventTimestamp ?? ''}`;

    const eventSource = new EventSource(url);

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.timestamp) this.lastEventTimestamp = data.timestamp;
      this.retryCount = 0; // Reset on successful event
      // Process event...
    };

    eventSource.onerror = () => {
      eventSource.close();
      this.reconnect();
    };

    return eventSource;
  }

  reconnect() {
    if (this.retryCount >= this.maxRetries) {
      console.error('Max retries exceeded');
      return;
    }

    const delay = Math.pow(2, this.retryCount) * 1000;
    this.retryCount++;

    console.log(`Reconnecting in ${delay}ms (attempt ${this.retryCount})`);
    setTimeout(() => this.connect(), delay);
  }
}
```

## Langfuse Integration

Every event includes optional `trace_id` and `observation_id` fields for Langfuse integration.

### Viewing Traces

```typescript
// Extract trace_id from event
const traceId = event.data.trace_id;

// Build Langfuse URL
const langfuseUrl = `${LANGFUSE_HOST}/trace/${traceId}`;

// Display link to user
<a href={langfuseUrl} target="_blank">
  View Detailed Trace
</a>
```

This allows users to:
1. See real-time agent output in MGX
2. Click link to view detailed trace, performance metrics, and costs in Langfuse

## Error Handling

### Common Errors

1. **Session not found** (404)
   - Ensure session exists before streaming
   - Create session first if needed

2. **Unauthorized** (403)
   - Check authentication token
   - Verify user owns the session

3. **Timeout** (custom timeout event)
   - Task exceeded 5-minute limit
   - Consider breaking into smaller tasks

4. **Connection lost**
   - Network issue or server restart
   - Use reconnection strategy with `stream-continue`

### Error Event Structure

```json
{
  "event": "error",
  "id": "evt_error",
  "data": {
    "event_type": "agent_error",
    "error": "Error message",
    "error_type": "ErrorClass"
  }
}
```

## Performance Considerations

### Client-Side

1. **Buffer events**: Don't update UI for every token
   - Batch delta events (e.g., every 100ms)
   - Improves rendering performance

2. **Cleanup**: Always close EventSource when done
   ```javascript
   useEffect(() => {
     return () => eventSource.close();
   }, []);
   ```

3. **Memory management**: Clear old events periodically
   - Keep only recent N events in state
   - Archive to separate storage if needed

### Server-Side

See [Performance Optimization Guide](./performance_optimization.md) for:
- Database indexing
- Polling interval tuning
- Scaling strategies

## Testing

### Manual Testing

```bash
# Test with curl
curl -N -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"test"}' \
  http://localhost:8000/api/apps/session123/agent/generate

# Test continue endpoint
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/apps/session123/agent/stream-continue?since_timestamp=1704067200"
```

### Automated Testing

```bash
# Run test suite
python scripts/test_sse_stream.py
```

## Troubleshooting

### Events not streaming

1. Check agent task status in Celery
2. Verify events are being written to database
3. Check FastAPI logs for errors

### Slow streaming

1. Check database query performance
2. Verify indexes are created
3. Monitor polling interval

### Connection drops

1. Check nginx/proxy timeout settings
2. Add `X-Accel-Buffering: no` header
3. Verify network stability

## Security Considerations

1. **Authentication**: Always require valid token
2. **Authorization**: Verify user owns session
3. **Rate limiting**: Limit concurrent streams per user
4. **Input validation**: Sanitize prompt input
5. **Output filtering**: Remove sensitive data from events

## Migration from Polling

If migrating from the legacy polling endpoint:

**Before:**
```javascript
// Poll every 2 seconds
const interval = setInterval(async () => {
  const result = await fetch(`/api/apps/${sessionId}/agent/tasks/${taskId}`);
  const data = await result.json();
  if (data.status === 'SUCCESS') {
    clearInterval(interval);
  }
}, 2000);
```

**After:**
```javascript
// Use SSE streaming
const eventSource = new EventSource(`/api/apps/${sessionId}/agent/generate`);
eventSource.onmessage = (e) => {
  // Real-time updates
};
```

Benefits:
- ✅ Real-time updates (no 2s delay)
- ✅ Lower server load (no repeated polling)
- ✅ Better user experience
- ✅ Automatic reconnection support
