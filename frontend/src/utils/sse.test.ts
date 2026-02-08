import { describe, it, expect, vi } from 'vitest';
import { normalizeEventType, processSSELine, createSSEProcessLine } from './sse';

describe('normalizeEventType', () => {
  it('returns empty string for undefined', () => {
    expect(normalizeEventType(undefined)).toBe('');
  });

  it('returns empty string for empty string', () => {
    expect(normalizeEventType('')).toBe('');
  });

  it('returns lowercase for plain event type', () => {
    expect(normalizeEventType('llm_stream')).toBe('llm_stream');
    expect(normalizeEventType('LLM_STREAM')).toBe('llm_stream');
    expect(normalizeEventType('message_complete')).toBe('message_complete');
    expect(normalizeEventType('finish')).toBe('finish');
  });

  it('extracts and lowercases for EventType.XXX format', () => {
    expect(normalizeEventType('EventType.LLM_STREAM')).toBe('llm_stream');
    expect(normalizeEventType('EventType.MESSAGE_COMPLETE')).toBe('message_complete');
    expect(normalizeEventType('EventType.NODE_START')).toBe('node_start');
    expect(normalizeEventType('EventType.FINISH')).toBe('finish');
    expect(normalizeEventType('EventType.AGENT_ERROR')).toBe('agent_error');
  });

  it('handles dot-separated multi-part format', () => {
    expect(normalizeEventType('foo.bar.BAZ')).toBe('baz');
  });
});

describe('processSSELine', () => {
  const baseOpts = { sessionId: 'sess-1', currentNodeName: '' };
  const getNow = vi.fn(() => 1234567.89);

  it('returns null for non-data lines', () => {
    expect(processSSELine('event: delta', baseOpts)).toBeNull();
    expect(processSSELine('id: abc', baseOpts)).toBeNull();
  });

  it('returns null for [DONE] or empty data', () => {
    expect(processSSELine('data: [DONE]', baseOpts)).toBeNull();
    expect(processSSELine('data: ', baseOpts)).toBeNull();
    expect(processSSELine('data:   ', baseOpts)).toBeNull();
  });

  it('returns null for invalid JSON', () => {
    expect(processSSELine('data: not json', baseOpts)).toBeNull();
  });

  it('handles node_start', () => {
    const line = 'data: {"event_type":"node_start","node_name":"boss","timestamp":1}';
    const r = processSSELine(line, baseOpts);
    expect(r).toEqual({ type: 'node_name', currentNodeName: 'boss' });
  });

  it('handles llm_stream - creates new message when no assistant', () => {
    const line = 'data: {"event_type":"llm_stream","delta":"你好","timestamp":1.5,"namespace":["boss:uuid"]}';
    const r = processSSELine(line, { ...baseOpts, getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater([]);
      expect(next).toHaveLength(1);
      expect(next[0]).toMatchObject({
        role: 'assistant',
        content: '你好',
        agent_name: 'boss',
        session_id: 'sess-1',
      });
      expect(next[0].message_id).toMatch(/^stream-/);
    }
  });

  it('handles llm_stream - appends when last is assistant (no message_id = backward compat)', () => {
    const line = 'data: {"event_type":"llm_stream","delta":"世界","timestamp":2}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: '你好',
        tool_calls: [],
        send_to: [],
        timestamp: 1,
        metadata: {},
      },
    ];
    const r = processSSELine(line, { ...baseOpts, currentNodeName: 'boss', getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next).toHaveLength(1);
      expect(next[0].content).toBe('你好世界');
    }
  });

  it('handles llm_stream - appends when last is assistant and same message_id', () => {
    const line = 'data: {"event_type":"llm_stream","delta":"世界","timestamp":2,"message_id":"m1"}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: '你好',
        tool_calls: [],
        send_to: [],
        timestamp: 1,
        metadata: {},
      },
    ];
    const r = processSSELine(line, { ...baseOpts, currentNodeName: 'boss', getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next).toHaveLength(1);
      expect(next[0].content).toBe('你好世界');
    }
  });

  it('handles llm_stream tool_call - creates new message when no assistant', () => {
    const line =
      'data: {"event_type":"llm_stream","content_type":"tool_call","delta":"workflow_decision","tool_call_name":"workflow_decision","tool_call_id":"call_abc","tool_call_index":0,"message_id":"msg-1","timestamp":1.5,"namespace":["pm:uuid"]}';
    const r = processSSELine(line, { ...baseOpts, getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater([]);
      expect(next).toHaveLength(1);
      expect(next[0]).toMatchObject({
        role: 'assistant',
        content: '',
        agent_name: 'pm',
        session_id: 'sess-1',
      });
      expect(next[0].tool_calls).toHaveLength(1);
      expect(next[0].tool_calls[0]).toMatchObject({
        id: 'call_abc',
        name: 'workflow_decision',
      });
      expect(next[0].tool_calls[0].args).toEqual({});
    }
  });

  it('handles llm_stream tool_call - appends args delta to existing message', () => {
    const line1 =
      'data: {"event_type":"llm_stream","content_type":"tool_call","delta":"workflow_decision","tool_call_name":"workflow_decision","tool_call_id":"call_abc","tool_call_index":0,"message_id":"msg-1","timestamp":1}';
    const line2 =
      'data: {"event_type":"llm_stream","content_type":"tool_call","delta":"{\\"next_action\\": \\"continue","tool_call_index":0,"message_id":"msg-1","timestamp":2}';
    const line3 =
      'data: {"event_type":"llm_stream","content_type":"tool_call","delta":"\\"","tool_call_index":0,"message_id":"msg-1","timestamp":3}';
    const prev: Parameters<NonNullable<ReturnType<typeof processSSELine>>['updater']>[0] = [];
    const r1 = processSSELine(line1, { ...baseOpts, getNow });
    if (r1?.type === 'messages') {
      const next1 = r1.updater(prev);
      expect(next1[0].tool_calls[0].args).toEqual({});
      const r2 = processSSELine(line2, { ...baseOpts, getNow });
      if (r2?.type === 'messages') {
        const next2 = r2.updater(next1);
        expect(next2[0].tool_calls[0].args).toEqual({
          __raw: '{"next_action": "continue',
        });
        const r3 = processSSELine(line3, { ...baseOpts, getNow });
        if (r3?.type === 'messages') {
          const next3 = r3.updater(next2);
          expect(next3[0].tool_calls[0].args).toEqual({
            __raw: '{"next_action": "continue"',
          });
        }
      }
    }
  });

  it('handles llm_stream tool_call - appends to existing assistant message', () => {
    const line =
      'data: {"event_type":"llm_stream","content_type":"tool_call","delta":"search","tool_call_name":"search","tool_call_id":"call_xyz","tool_call_index":0,"message_id":"m1","timestamp":2}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'Thinking...',
        tool_calls: [],
        send_to: [],
        timestamp: 1,
        metadata: {},
      },
    ];
    const r = processSSELine(line, { ...baseOpts, getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next).toHaveLength(1);
      expect(next[0].content).toBe('Thinking...');
      expect(next[0].tool_calls).toHaveLength(1);
      expect(next[0].tool_calls[0]).toMatchObject({
        id: 'call_xyz',
        name: 'search',
      });
      expect(next[0].tool_calls[0].args).toEqual({});
    }
  });

  it('handles message_complete - overwrites streaming __raw with final tool_calls', () => {
    const line =
      'data: {"event_type":"message_complete","message_id":"m1","content":"done","tool_calls":[{"id":"tc1","name":"search","args":{"query":"foo"}}],"timestamp":6}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'partial',
        tool_calls: [{ id: 'tc1', name: 'search', args: { __raw: '{"query":"fo' } }],
        send_to: [],
        timestamp: 2,
        metadata: {},
      },
    ];
    const r = processSSELine(line, baseOpts);
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next[0].tool_calls).toEqual([{ id: 'tc1', name: 'search', args: { query: 'foo' } }]);
    }
  });

  it('handles llm_stream - creates new message when message_id differs (multi-node)', () => {
    const line = 'data: {"event_type":"llm_stream","delta":"PM says","timestamp":2,"message_id":"m2"}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'Boss says hello',
        agent_name: 'boss',
        tool_calls: [],
        send_to: [],
        timestamp: 1,
        metadata: {},
      },
    ];
    const r = processSSELine(line, { ...baseOpts, currentNodeName: 'product_manager', getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next).toHaveLength(2);
      expect(next[0].content).toBe('Boss says hello');
      expect(next[0].message_id).toBe('m1');
      expect(next[1].content).toBe('PM says');
      expect(next[1].message_id).toBe('m2');
      expect(next[1].agent_name).toBe('product_manager');
    }
  });

  it('handles message_complete - overwrites message with same id', () => {
    const line =
      'data: {"event_type":"message_complete","message_id":"real-id","content":"complete content from backend","timestamp":3}';
    const prev = [
      {
        message_id: 'stream-123',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'partial stream',
        tool_calls: [],
        send_to: [],
        timestamp: 2,
        metadata: {},
      },
    ];
    const r = processSSELine(line, baseOpts);
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next[0].message_id).toBe('real-id');
      expect(next[0].content).toBe('complete content from backend');
      expect(r.timestamp).toBe(3);
    }
  });

  it('handles message_complete - finds by message_id and overwrites', () => {
    const line =
      'data: {"event_type":"message_complete","message_id":"m1","content":"final content","timestamp":5}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'streaming...',
        tool_calls: [],
        send_to: [],
        timestamp: 2,
        metadata: {},
      },
    ];
    const r = processSSELine(line, baseOpts);
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next[0].message_id).toBe('m1');
      expect(next[0].content).toBe('final content');
    }
  });

  it('handles message_complete - overwrites tool_calls and tool_call_id', () => {
    const line =
      'data: {"event_type":"message_complete","message_id":"m1","content":"done","tool_calls":[{"id":"tc1","name":"search","args":{}}],"tool_call_id":"tc1","timestamp":6}';
    const prev = [
      {
        message_id: 'm1',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'partial',
        tool_calls: [],
        send_to: [],
        timestamp: 2,
        metadata: {},
      },
    ];
    const r = processSSELine(line, baseOpts);
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next[0].content).toBe('done');
      expect(next[0].tool_calls).toEqual([{ id: 'tc1', name: 'search', args: {} }]);
      expect(next[0].tool_call_id).toBe('tc1');
    }
  });

  it('handles message_complete - appends when role differs (tool after assistant)', () => {
    const line =
      'data: {"event_type":"message_complete","message_id":"tool-123","content":"成功写入","role":"tool","tool_call_id":"call_abc","timestamp":7}';
    const prev = [
      {
        message_id: 'lc_run--assistant-id',
        session_id: 'sess-1',
        role: 'assistant',
        content: '将创建需求文档',
        tool_calls: [{ id: 'call_abc', name: 'write_file', args: {} }],
        send_to: [],
        timestamp: 6,
        metadata: {},
      },
    ];
    const r = processSSELine(line, { ...baseOpts, getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next).toHaveLength(2);
      expect(next[0].role).toBe('assistant');
      expect(next[0].content).toBe('将创建需求文档');
      expect(next[1].role).toBe('tool');
      expect(next[1].message_id).toBe('tool-123');
      expect(next[1].content).toBe('成功写入');
    }
  });

  it('handles message_complete - overwrites last when same role (completing streamed message)', () => {
    const line =
      'data: {"event_type":"message_complete","message_id":"real-id","content":"complete content","role":"assistant","timestamp":3}';
    const prev = [
      {
        message_id: 'stream-123',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'partial stream',
        tool_calls: [],
        send_to: [],
        timestamp: 2,
        metadata: {},
      },
    ];
    const r = processSSELine(line, baseOpts);
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater(prev);
      expect(next).toHaveLength(1);
      expect(next[0].message_id).toBe('real-id');
      expect(next[0].content).toBe('complete content');
    }
  });

  it('handles finish', () => {
    const line = 'data: {"event_type":"finish","timestamp":4}';
    expect(processSSELine(line, baseOpts)).toEqual({ type: 'finish' });
  });

  it('handles agent_error', () => {
    const line = 'data: {"event_type":"agent_error","error":"Something failed"}';
    expect(processSSELine(line, baseOpts)).toEqual({
      type: 'error',
      error: 'Something failed',
    });
  });

  it('handles EventType. prefix format', () => {
    const line = 'data: {"event_type":"EventType.LLM_STREAM","delta":"hi","timestamp":1}';
    const r = processSSELine(line, { ...baseOpts, getNow });
    expect(r?.type).toBe('messages');
    if (r?.type === 'messages') {
      const next = r.updater([]);
      expect(next[0].content).toBe('hi');
    }
  });
});

describe('createSSEProcessLine', () => {
  it('dispatches to callbacks and tracks node_name across lines', () => {
    const onMessages = vi.fn();
    const onError = vi.fn();
    const onFinish = vi.fn();
    const onTimestamp = vi.fn();
    const onStreamContinueRef = vi.fn();

    const processLine = createSSEProcessLine('sess-1', {
      onMessages,
      onError,
      onFinish,
      onTimestamp,
      onStreamContinueRef,
    });

    processLine('data: {"event_type":"node_start","node_name":"boss"}');
    processLine('data: {"event_type":"llm_stream","delta":"Hello","timestamp":1}');

    expect(onMessages).toHaveBeenCalledTimes(1);
    const updater = onMessages.mock.calls[0][0];
    const msgs = updater([]);
    expect(msgs[0]).toMatchObject({ content: 'Hello', agent_name: 'boss' });

    processLine('data: {"event_type":"finish"}');
    expect(onFinish).toHaveBeenCalledTimes(1);
    expect(onStreamContinueRef).toHaveBeenCalledWith(false);
  });
});
