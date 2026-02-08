/**
 * SSE stream utilities for agent streaming.
 * Pure logic, no React/ChatPanel dependencies. Unit testable.
 */

import type { Message } from '@/types';

/** Normalize event_type (handles both "llm_stream" and "EventType.LLM_STREAM" formats) */
export function normalizeEventType(t: string | undefined): string {
  if (!t) return '';
  const part = t.includes('.') ? t.split('.').pop() : t;
  return (part ?? t).toLowerCase();
}

/** Result of processing one SSE line - pure, no side effects */
export type SSEAction =
  | { type: 'messages'; updater: (prev: Message[]) => Message[]; timestamp?: number }
  | { type: 'node_name'; currentNodeName: string }
  | { type: 'timestamp'; timestamp: number }
  | { type: 'finish' }
  | { type: 'error'; error: string }
  | { type: 'switch_to_dev_tab' };

/** Options for processSSELine (injectable for tests) */
export interface ProcessSSELineOptions {
  sessionId: string;
  currentNodeName: string;
  getNow?: () => number;
}

/**
 * Pure function: parse SSE line and return state update actions.
 * No side effects, no React. Fully unit testable.
 */
export function processSSELine(
  line: string,
  options: ProcessSSELineOptions
): SSEAction | null {
  const { sessionId, currentNodeName, getNow = () => Date.now() / 1000 } = options;

  if (!line.startsWith('data: ')) return null;
  const json = line.slice(6);
  if (json === '[DONE]' || json.trim() === '') return null;

  let data: Record<string, unknown>;
  try {
    data = JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }

  const timestamp = data.timestamp as number | undefined;
  const eventType = normalizeEventType(data.event_type as string);

  if (eventType === 'node_start') {
    const nodeName = (data.node_name as string) ?? '';
    return { type: 'node_name', currentNodeName: nodeName };
  }

  if (eventType === 'llm_stream') {
    const delta = (data.delta as string) ?? '';
    const contentType = (data.content_type as string) ?? 'text';
    // tool_call 增量暂不追加到消息文本，由 MESSAGE_COMPLETE 时 tool_calls 展示
    if (contentType === 'tool_call' || !delta) return null;

    const agentName =
      currentNodeName ||
      ((data.namespace as string[])?.[0]?.split(':')[0]) ||
      'Agent';
    const ts = timestamp ?? getNow();
    const backendMessageId = data.message_id as string | undefined;

    return {
      type: 'messages',
      updater: (prev) => {
        const lastMsg = prev[prev.length - 1];
        // 仅当 message_id 一致时才追加，否则创建新消息（避免多节点消息合并）
        const shouldAppend =
          lastMsg &&
          lastMsg.role === 'assistant' &&
          (!backendMessageId || lastMsg.message_id === backendMessageId);
        if (shouldAppend) {
          return [
            ...prev.slice(0, -1),
            {
              ...lastMsg,
              content:
                typeof lastMsg.content === 'string'
                  ? lastMsg.content + delta
                  : delta,
            },
          ];
        }
        return [
          ...prev,
          {
            message_id:
              backendMessageId ?? `stream-${Math.floor(getNow() * 1000)}`,
            session_id: sessionId,
            role: 'assistant',
            agent_name: agentName,
            content: delta,
            tool_calls: [],
            send_to: [],
            timestamp: ts,
            metadata: {},
          },
        ];
      },
    };
  }

  if (eventType === 'message_complete') {
    const messageId = data.message_id as string | undefined;
    if (messageId) {
      return {
        type: 'messages',
        updater: (prev) => {
          // 按 message_id 定位要更新的消息，避免多节点时更新错乱
          const idx = prev.findIndex((m) => m.role === 'assistant' && m.message_id === messageId);
          if (idx >= 0) {
            return prev.map((m, i) => (i === idx ? { ...m, message_id: messageId } : m));
          }
          // 兼容：若未找到（如临时 id），更新最后一条 assistant 消息
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            return [...prev.slice(0, -1), { ...lastMsg, message_id: messageId }];
          }
          return prev;
        },
        ...(timestamp != null && { timestamp }),
      };
    }
    if (timestamp != null) {
      return { type: 'timestamp', timestamp };
    }
    return null;
  }

  if (eventType === 'finish') {
    return { type: 'finish' };
  }

  if (eventType === 'agent_error') {
    return { type: 'error', error: (data.error as string) ?? 'Agent error occurred' };
  }

  if (eventType === 'custom') {
    const customType = data.custom_type as string | undefined;
    if (customType === 'dev_server_started') {
      return { type: 'switch_to_dev_tab' };
    }
  }

  if (timestamp != null) {
    return { type: 'timestamp', timestamp };
  }

  return null;
}

/** Generic callbacks for SSE processing (no React coupling) */
export interface SSEProcessCallbacks {
  onMessages: (updater: (prev: Message[]) => Message[]) => void;
  onError: (error: string) => void;
  onFinish: () => void;
  onTimestamp: (ts: number) => void;
  onStreamContinueRef?: (value: boolean) => void;
  onSwitchToDevTab?: () => void;
}

/**
 * Read SSE stream from ReadableStream, parse data lines and call processLine for each.
 * Handles chunked decoding and incomplete blocks.
 */
export async function readSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  processLine: (line: string) => void
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const block of parts) {
      const line = block.split('\n').find((l) => l.startsWith('data: '));
      if (line) processLine(line);
    }
  }
  if (buffer) {
    const line = buffer.split('\n').find((l) => l.startsWith('data: '));
    if (line) processLine(line);
  }
}

/**
 * Create a line processor that dispatches to callbacks.
 * Callbacks are generic - can be React setState, Zustand, or plain functions.
 */
export function createSSEProcessLine(
  sessionId: string,
  callbacks: SSEProcessCallbacks,
  getNow: () => number = () => Date.now() / 1000
): (line: string) => void {
  let currentNodeName = '';

  return (line: string) => {
    const action = processSSELine(line, {
      sessionId,
      currentNodeName,
      getNow,
    });

    if (!action) return;

    switch (action.type) {
      case 'node_name':
        currentNodeName = action.currentNodeName;
        break;
      case 'messages':
        callbacks.onMessages(action.updater);
        if (action.timestamp != null) callbacks.onTimestamp(action.timestamp);
        break;
      case 'timestamp':
        callbacks.onTimestamp(action.timestamp);
        break;
      case 'finish':
        callbacks.onFinish();
        callbacks.onStreamContinueRef?.(false);
        break;
      case 'error':
        callbacks.onError(action.error);
        callbacks.onStreamContinueRef?.(false);
        break;
      case 'switch_to_dev_tab':
        callbacks.onSwitchToDevTab?.();
        break;
    }
  };
}
