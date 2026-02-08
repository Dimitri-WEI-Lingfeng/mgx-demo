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

  it('handles message_complete - updates message_id', () => {
    const line = 'data: {"event_type":"message_complete","message_id":"real-id","timestamp":3}';
    const prev = [
      {
        message_id: 'stream-123',
        session_id: 'sess-1',
        role: 'assistant',
        content: 'done',
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
      expect(r.timestamp).toBe(3);
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
