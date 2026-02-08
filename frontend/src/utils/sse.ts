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

  console.log('eventType', eventType);
  console.log('data', data);

  if (eventType === 'node_start') {
    const nodeName = (data.node_name as string) ?? '';
    return { type: 'node_name', currentNodeName: nodeName };
  }

  if (eventType === 'llm_stream') {
    const delta = (data.delta as string) ?? '';
    const contentType = (data.content_type as string) ?? 'text';
    const agentName =
      currentNodeName ||
      ((data.namespace as string[])?.[0]?.split(':')[0]) ||
      'Agent';
    const ts = timestamp ?? getNow();
    const backendMessageId = data.message_id as string | undefined;

    // tool_call 流式处理：累积 name、id、args（使用 __raw）
    if (contentType === 'tool_call') {
      const toolCallIndex = (data.tool_call_index as number) ?? 0;
      const toolCallName = (data.tool_call_name as string) ?? '';
      const toolCallId = (data.tool_call_id as string) ?? '';
      const hasUpdate = delta || toolCallName || toolCallId;
      if (!hasUpdate) return null;

      return {
        type: 'messages',
        updater: (prev) => {
          const lastMsg = prev[prev.length - 1];
          const shouldAppend =
            lastMsg &&
            lastMsg.role === 'assistant' &&
            (!backendMessageId || lastMsg.message_id === backendMessageId);

          const updateToolCall = (
            tc: { id: string; name: string; args: Record<string, unknown> }
          ) => {
            const next: { id: string; name: string; args: Record<string, unknown> } = {
              id: toolCallId || tc.id || `stream-tc-${toolCallIndex}-${Date.now()}`,
              name: toolCallName || tc.name,
              args: { ...tc.args },
            };
            // 仅当 delta 为 args（JSON 片段）时追加：以 { 开头，或继续已有 __raw
            const raw = (tc.args?.__raw as string) ?? '';
            const isArgsDelta =
              delta &&
              (delta.trim().startsWith('{') || (raw.length > 0 && raw.trim().startsWith('{')));
            if (isArgsDelta) {
              next.args = { __raw: raw + delta };
            }
            return next;
          };

          if (shouldAppend) {
            const toolCalls = [...(lastMsg.tool_calls ?? [])];
            while (toolCalls.length <= toolCallIndex) {
              toolCalls.push({
                id: toolCallId || `stream-tc-${toolCallIndex}-${Date.now()}`,
                name: '',
                args: {},
              });
            }
            const existing = toolCalls[toolCallIndex];
            toolCalls[toolCallIndex] = updateToolCall(existing);
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, tool_calls: toolCalls },
            ];
          }

          // 创建新消息（仅 tool_call，无文本）
          const isArgsDelta = delta && delta.trim().startsWith('{');
          const toolCalls: Array<{ id: string; name: string; args: Record<string, unknown> }> = [];
          for (let i = 0; i <= toolCallIndex; i++) {
            toolCalls.push({
              id: i === toolCallIndex ? (toolCallId || `stream-tc-${i}-${Math.floor(getNow() * 1000)}`) : '',
              name: i === toolCallIndex ? toolCallName : '',
              args: i === toolCallIndex && isArgsDelta ? { __raw: delta } : {},
            });
          }
          return [
            ...prev,
            {
              message_id:
                backendMessageId ?? `stream-${Math.floor(getNow() * 1000)}`,
              session_id: sessionId,
              role: 'assistant',
              agent_name: agentName,
              content: '',
              tool_calls: toolCalls,
              send_to: [],
              timestamp: ts,
              metadata: {},
            },
          ];
        },
      };
    }

    // text 流式处理
    if (!delta) return null;

    return {
      type: 'messages',
      updater: (prev) => {
        const lastMsg = prev[prev.length - 1];
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
      // 从 event data 提取可覆盖的完整消息字段（不区分 role）
      const overwrite: Partial<Message> = {
        message_id: messageId,
      };
      if (data.content != null) overwrite.content = data.content as string;
      if (data.role != null) overwrite.role = data.role as string;
      if (data.agent_name != null) overwrite.agent_name = data.agent_name as string;
      if (data.tool_call_id != null) overwrite.tool_call_id = data.tool_call_id as string;
      if (data.tool_calls != null) overwrite.tool_calls = data.tool_calls as Message['tool_calls'];
      if (data.parent_id != null) overwrite.parent_id = data.parent_id as string;
      if (data.send_to != null) overwrite.send_to = data.send_to as string[];
      if (data.metadata != null) overwrite.metadata = data.metadata as Record<string, unknown>;
      if (timestamp != null) overwrite.timestamp = timestamp;

      return {
        type: 'messages',
        updater: (prev) => {
          // 按 message_id 定位要更新的消息，用后端完整数据覆盖（不区分 role）
          const idx = prev.findIndex((m) => m.message_id === messageId);
          if (idx >= 0) {
            return prev.map((msg, i) =>
              i === idx ? { ...msg, ...overwrite } : msg
            );
          }
          // 兼容：若未找到 message_id
          const lastMsg = prev[prev.length - 1];
          const isCompletingLastMessage =
            lastMsg &&
            (overwrite.role == null || overwrite.role === lastMsg.role);

          if (isCompletingLastMessage) {
            // 视为完成最后一条流式消息（如临时 id 被替换）
            return [...prev.slice(0, -1), { ...lastMsg, ...overwrite }];
          }

          // 否则：追加新消息（如 tool 消息、或 assistant 在 user 之后）
          const newMessage: Message = {
            message_id: messageId,
            session_id: sessionId,
            parent_id: overwrite.parent_id,
            agent_name: overwrite.agent_name,
            role: overwrite.role ?? 'assistant',
            content: overwrite.content ?? '',
            tool_call_id: overwrite.tool_call_id,
            tool_calls: overwrite.tool_calls ?? [],
            send_to: overwrite.send_to ?? [],
            timestamp: overwrite.timestamp ?? getNow(),
            metadata: overwrite.metadata ?? {},
          };
          return [...prev, newMessage];
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
