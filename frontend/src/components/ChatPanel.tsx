import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Input, Button, Alert, Typography } from 'antd';
import { SendOutlined, StopOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { getHistory, getSession, stopAgent } from '../api/client';
import type { Message, ContentPart } from '../types';
import { useAppStore } from '@/stores/appStore';
import { createSSEProcessLine, readSSEStream } from '@/utils/sse';
import { eventBus } from '@/utils/eventBus';

const SESSION_POLL_INTERVAL_MS = 2000;
const FILE_TREE_POLL_INTERVAL_MS = 2500;

interface ChatPanelProps {
  sessionId: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Layer 1: 数据加载层 - 请求 session + history，按顺序展示 loading
// ─────────────────────────────────────────────────────────────────────────────

function ChatPanelLoading({ phase }: { phase: 'session' | 'history' }) {
  const text = phase === 'session' ? '加载会话...' : '加载对话历史...';
  return <div className="p-3 text-gray-500 text-sm">{text}</div>;
}

function ChatPanelError({ message }: { message: string }) {
  return (
    <div className="p-3">
      <Alert type="error" message={message} showIcon />
    </div>
  );
}

interface ChatPanelDataLayerProps {
  sessionId: string;
  children: (props: {
    sessionData: { is_running?: boolean };
    initialMessages: Message[];
    refetchSession: () => void;
  }) => React.ReactNode;
}

function ChatPanelDataLayer({ sessionId, children }: ChatPanelDataLayerProps) {
  const hasInitialPrompt = !!useAppStore((s) => s.initialPrompt?.trim());

  const {
    data: sessionData,
    isLoading: sessionLoading,
    refetch: refetchSession,
  } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: !!sessionId,
  });

  const {
    data: historyData,
    error: historyError,
    isLoading: historyLoading,
  } = useQuery({
    queryKey: ['agent-history', sessionId],
    queryFn: () => getHistory(sessionId),
    enabled: !!sessionId && !hasInitialPrompt,
  });

  // 按先后顺序：先 session，再 history（若存在 initialPrompt 则跳过 history，新 session 无历史）
  if (sessionLoading) {
    return <ChatPanelLoading phase="session" />;
  }
  if (!sessionData) {
    return <ChatPanelLoading phase="session" />;
  }
  if (hasInitialPrompt) {
    return <>{children({ sessionData, initialMessages: [], refetchSession })}</>;
  }
  if (historyError) {
    const message = historyError instanceof Error ? historyError.message : 'Failed to load history';
    return <ChatPanelError message={message} />;
  }
  // 必须等 history 加载完成后再渲染 Content，否则 stream-continue 会先于 history 启动
  if (historyLoading) {
    return <ChatPanelLoading phase="history" />;
  }

  const initialMessages = historyData?.messages ?? [];
  return <>{children({ sessionData, initialMessages, refetchSession })}</>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Layer 2: 内容展示层 - 消息列表、输入框、stream-continue、sendMessage
// ─────────────────────────────────────────────────────────────────────────────

interface ChatPanelContentProps {
  sessionId: string;
  sessionData: { is_running?: boolean };
  initialMessages: Message[];
  refetchSession: () => void;
}

function ChatPanelContent({
  sessionId,
  sessionData,
  initialMessages,
  refetchSession,
}: ChatPanelContentProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastEventTimestampRef = useRef<number | null>(initialMessages[initialMessages.length - 1]?.timestamp ?? null);
  const streamContinueConnectedRef = useRef(false);

  // Session polling when running
  useEffect(() => {
    if (!sessionData?.is_running) return;
    const id = setInterval(() => refetchSession(), SESSION_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [sessionData?.is_running, refetchSession]);

  // stream 期间通过 event bus 触发 file tree 轮询
  useEffect(() => {
    if (!sending) return;
    const id = setInterval(() => eventBus.emit('stream-tick'), FILE_TREE_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [sending]);

  // stream-continue when session is running
  useEffect(() => {
    if (!sessionData?.is_running || streamContinueConnectedRef.current) return;

    streamContinueConnectedRef.current = true;
    setSending(true);

    const sinceTimestamp = lastEventTimestampRef.current ?? undefined;
    const params = new URLSearchParams();
    if (sinceTimestamp != null) params.set('since_timestamp', String(sinceTimestamp));
    const url = `${import.meta.env.VITE_API_BASE || ''}/api/apps/${sessionId}/agent/stream-continue?${params}`;
    const token = localStorage.getItem('access_token');
    const controller = new AbortController();
    abortControllerRef.current = controller;

    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(res.statusText);
        const reader = res.body?.getReader();
        if (!reader) return;
        const processLine = createSSEProcessLine(sessionId, {
          onMessages: (updater) => setMessages(updater),
          onError: setError,
          onFinish: () => setSending(false),
          onTimestamp: (ts) => { lastEventTimestampRef.current = ts; },
          onStreamContinueRef: (val) => { streamContinueConnectedRef.current = val; },
          onSwitchToDevTab: () => eventBus.emit('switch-to-dev-tab'),
        });
        await readSSEStream(reader, processLine);
        setSending(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Stream connection failed');
        setSending(false);
        streamContinueConnectedRef.current = false;
      });

    return () => {
      controller.abort();
      streamContinueConnectedRef.current = false;
    };
  }, [sessionId, sessionData?.is_running]);

  useEffect(() => {
    streamContinueConnectedRef.current = false;
  }, [sessionId]);

  // 当 history 从空变为有数据时同步到本地（仅当本地为空，避免覆盖用户刚发的消息）
  useEffect(() => {
    if (initialMessages.length > 0 && messages.length === 0) {
      setMessages(initialMessages);
      const lastTs = initialMessages[initialMessages.length - 1]?.timestamp;
      if (lastTs != null) lastEventTimestampRef.current = lastTs;
    }
  }, [initialMessages, messages.length]);

  const sendMessage = async (prompt: string, options?: { onFinish?: () => void }) => {
    if (sending) return;

    setSending(true);
    setError('');

    const userMessage: Message = {
      message_id: `temp-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: prompt,
      tool_calls: [],
      send_to: [],
      timestamp: Date.now() / 1000,
      metadata: {},
    };
    setMessages((prev) => [...prev, userMessage]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const API_BASE = import.meta.env.VITE_API_BASE || '';
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/api/apps/${sessionId}/agent/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ prompt }),
        credentials: 'include',
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || response.statusText);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        setError('No response body');
        setSending(false);
        options?.onFinish?.();
        return;
      }

      const processLine = createSSEProcessLine(sessionId, {
        onMessages: (updater) => setMessages(updater),
        onError: setError,
        onFinish: () => {
          setSending(false);
          options?.onFinish?.();
        },
        onTimestamp: (ts) => { lastEventTimestampRef.current = ts; },
        onSwitchToDevTab: () => eventBus.emit('switch-to-dev-tab'),
      });
      await readSSEStream(reader, processLine);
      setSending(false);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setSending(false);
      options?.onFinish?.();
    } finally {
      abortControllerRef.current = null;
    }
  };

  const sendMessageRef = useRef(sendMessage);
  sendMessageRef.current = sendMessage;

  useEffect(() => {
    const promptToSend = useAppStore.getState().initialPrompt?.trim();
    if (promptToSend) {
      sendMessageRef.current(promptToSend, {
        onFinish: () => useAppStore.getState().setInitialPrompt(''),
      });
      return () => abortControllerRef.current?.abort();
    }
    return () => abortControllerRef.current?.abort();
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending) return;
    const prompt = input.trim();
    setInput('');
    sendMessage(prompt);
  };

  const handleStop = async () => {
    if (!sending) return;
    try {
      await stopAgent(sessionId);
      abortControllerRef.current?.abort();
      refetchSession();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop agent');
    } finally {
      setSending(false);
      streamContinueConnectedRef.current = false;
    }
  };

  return (
    <ChatPanelBody
      messages={messages}
      error={error}
      input={input}
      onInputChange={setInput}
      sending={sending}
      onSend={handleSend}
      onStop={handleStop}
      messagesEndRef={messagesEndRef}
      renderMessageContent={renderMessageContent}
    />
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Layer 3: 纯展示层 - 消息列表和输入框 UI
// ─────────────────────────────────────────────────────────────────────────────

/** Build map: tool_call_id -> tool Message for looking up results by ID */
function buildToolCallResultMap(messages: Message[]): Map<string, Message> {
  const map = new Map<string, Message>();
  for (const msg of messages) {
    if (msg.role === 'tool' && msg.tool_call_id) {
      map.set(msg.tool_call_id, msg);
    }
  }
  return map;
}

/** Set of tool_call_ids that are associated with an assistant's tool_calls (consumed, not standalone) */
function buildConsumedToolCallIds(messages: Message[]): Set<string> {
  const ids = new Set<string>();
  for (const msg of messages) {
    if (msg.role === 'assistant' && msg.tool_calls?.length) {
      for (const tc of msg.tool_calls) {
        if (tc.id) ids.add(tc.id);
      }
    }
  }
  return ids;
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

function getToolResultFromMessage(msg: Message): string {
  const c = msg.content;
  if (typeof c === 'string') return c;
  if (Array.isArray(c)) {
    const part = c.find((p) => p.type === 'tool_result' && p.tool_result != null);
    return part ? String(part.tool_result) : '';
  }
  return '';
}

function ToolCallBlock({ name, args }: { name?: string; args?: Record<string, unknown> }) {
  const argsStr = (() => {
    if (!args) return null;
    if ('__raw' in args && typeof args.__raw === 'string') {
      try {
        const parsed = JSON.parse(args.__raw);
        return Object.keys(parsed).length > 0 ? JSON.stringify(parsed, null, 2) : args.__raw || null;
      } catch {
        return args.__raw || null;
      }
    }
    return Object.keys(args).length > 0 ? JSON.stringify(args, null, 2) : null;
  })();
  return (
    <div className="rounded p-2 my-1 bg-gray-100 border-l-2 border-gray-400">
      <div className="font-medium text-xs text-gray-600 mb-0.5">Tool Call: {name ?? '?'}</div>
      {argsStr && (
        <pre className="text-xs overflow-x-auto mt-1 p-1 bg-white rounded">{argsStr}</pre>
      )}
    </div>
  );
}

function ToolResultBlock({ result }: { result: string }) {
  const display = result.length > 500 ? result.slice(0, 500) + '...' : result;
  return (
    <div className="rounded p-2 my-1 bg-green-50 border-l-2 border-green-400">
      <div className="font-medium text-xs text-green-700 mb-0.5">Tool Result</div>
      <pre className="text-xs overflow-x-auto whitespace-pre-wrap break-words">{display}</pre>
    </div>
  );
}

function renderMessageContent(
  content: string | ContentPart[],
  options?: {
    toolResultsByCallId?: Map<string, Message>;
    toolCalls?: Array<{ id: string; name: string; args: Record<string, unknown> }>;
  }
) {
  const { toolResultsByCallId, toolCalls } = options ?? {};

  if (typeof content === 'string') {
    return (
      <div>
        <MarkdownContent content={content} />
        {toolCalls && toolCalls.length > 0 && toolResultsByCallId &&
          toolCalls.map((tc) => {
            const toolMsg = tc.id ? toolResultsByCallId.get(tc.id) : undefined;
            const result = toolMsg ? getToolResultFromMessage(toolMsg) : '';
            return (
              <div key={tc.id ?? tc.name}>
                <ToolCallBlock name={tc.name} args={tc.args} />
                <ToolResultBlock result={result} />
              </div>
            );
          })}
      </div>
    );
  }

  // ContentPart[]: pair tool_call and tool_result by tool_call_id
  const textParts: string[] = [];
  const toolCallParts: Array<{ id?: string; name?: string; args?: Record<string, unknown> }> = [];
  const toolResultParts: Array<{ id?: string; result: unknown }> = [];

  for (const part of content) {
    if (part.type === 'text' && part.text) {
      textParts.push(part.text);
    }
    if (part.type === 'tool_call') {
      toolCallParts.push({
        id: part.tool_call_id,
        name: part.tool_name,
        args: part.tool_args,
      });
    }
    if (part.type === 'tool_result') {
      toolResultParts.push({
        id: part.tool_call_id,
        result: part.tool_result,
      });
    }
  }

  const resultByCallId = new Map<string, unknown>();
  for (const tr of toolResultParts) {
    if (tr.id != null) resultByCallId.set(tr.id, tr.result);
  }

  const paired: Array<{ call: { id?: string; name?: string; args?: Record<string, unknown> }; result?: unknown }> = [];
  const seenIds = new Set<string>();

  for (const call of toolCallParts) {
    const result = call.id ? resultByCallId.get(call.id) : undefined;
    paired.push({ call, result });
    if (call.id) seenIds.add(call.id);
  }
  for (const tr of toolResultParts) {
    if (tr.id && !seenIds.has(tr.id)) {
      paired.push({ call: { id: tr.id, name: undefined, args: undefined }, result: tr.result });
    }
  }

  return (
    <div>
      {textParts.map((t, i) => (
        <MarkdownContent key={`text-${i}`} content={t} />
      ))}
      {paired.map(({ call, result }, i) => (
        <div key={`pair-${i}`}>
          <ToolCallBlock name={call.name} args={call.args} />
          <ToolResultBlock result={result != null ? String(result) : ''} />
        </div>
      ))}
      {toolCallParts.length === 0 && toolCalls && toolCalls.length > 0 && toolResultsByCallId && (
        <>
          {toolCalls.map((tc) => {
            const toolMsg = tc.id ? toolResultsByCallId.get(tc.id) : undefined;
            const result = toolMsg ? getToolResultFromMessage(toolMsg) : '';
            return (
              <div key={tc.id ?? tc.name}>
                <ToolCallBlock name={tc.name} args={tc.args} />
                <ToolResultBlock result={result} />
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

function StreamingIndicator() {
  return (
    <div className="mb-2 p-2 rounded border-l-2 bg-gray-100 border-gray-400">
      <div className="font-medium text-xs text-gray-500 mb-1">Agent</div>
      <div className="text-sm text-gray-600 flex items-center gap-0.5">
        <span>正在生成</span>
        <span className="streaming-dot">.</span>
        <span className="streaming-dot">.</span>
        <span className="streaming-dot">.</span>
      </div>
    </div>
  );
}

interface ChatPanelBodyProps {
  messages: Message[];
  error: string;
  input: string;
  onInputChange: (v: string) => void;
  sending: boolean;
  onSend: (e: React.FormEvent) => void;
  onStop: () => void;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  renderMessageContent: (
    content: string | ContentPart[],
    options?: { toolResultsByCallId?: Map<string, Message>; toolCalls?: Array<{ id: string; name: string; args: Record<string, unknown> }> }
  ) => React.ReactNode;
}

function ChatPanelBody({
  messages,
  error,
  input,
  onInputChange,
  sending,
  onSend,
  onStop,
  messagesEndRef,
  renderMessageContent,
}: ChatPanelBodyProps) {
  const toolResultsByCallId = buildToolCallResultMap(messages);
  const consumedToolCallIds = buildConsumedToolCallIds(messages);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-2 text-sm min-h-0">
        {messages.length === 0 && (
          <Typography.Text type="secondary" className="block text-center py-4">
            暂无消息，与 Agent 开始对话吧
          </Typography.Text>
        )}
        {messages.map((msg) => {
          if (msg.role === 'tool' && msg.tool_call_id && consumedToolCallIds.has(msg.tool_call_id)) {
            return null;
          }
          const isUser = msg.role === 'user';
          const label = isUser ? '你' : msg.agent_name || 'Agent';
          const toolCalls = msg.role === 'assistant' && msg.tool_calls?.length ? msg.tool_calls : undefined;
          return (
            <div
              key={msg.message_id}
              className={`mb-2 p-2 rounded border-l-2 ${isUser ? 'bg-blue-50 border-blue-400' : 'bg-gray-100 border-gray-400'}`}
            >
              <div className="font-medium text-xs text-gray-500 mb-1">{label}</div>
              {msg.role === 'tool' ? (
                <ToolResultBlock result={getToolResultFromMessage(msg)} />
              ) : (
                renderMessageContent(msg.content, {
                  toolResultsByCallId: msg.role === 'assistant' ? toolResultsByCallId : undefined,
                  toolCalls,
                })
              )}
            </div>
          );
        })}
        {sending && <StreamingIndicator />}
        {error && <Alert type="error" message={error} className="mb-2" showIcon />}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={onSend} className="relative flex gap-2 border-t border-gray-100 shrink-0">
        <Input.TextArea
          rows={5}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="输入消息..."
          disabled={sending}
          size="small"
          onPressEnter={onSend}
        />
        {sending ? (
          <Button
            className="absolute! bottom-2 right-2"
            type="default"
            danger
            htmlType="button"
            icon={<StopOutlined />}
            onClick={onStop}
            disabled={!sending}
            size="small"
          />
        ) : (
          <Button
            className="absolute! bottom-2 right-2"
            type="primary"
            htmlType="submit"
            icon={<SendOutlined />}
            loading={sending}
            disabled={!input.trim()}
            size="small"
          />
        )}
      </form>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Root: ChatPanel
// ─────────────────────────────────────────────────────────────────────────────

export function ChatPanel({ sessionId }: ChatPanelProps) {
  if (!sessionId) {
    return <div className="p-3 text-gray-500 text-sm">未选择会话</div>;
  }

  return (
    <ChatPanelDataLayer sessionId={sessionId}>
      {(props) => <ChatPanelContent sessionId={sessionId} {...props} />}
    </ChatPanelDataLayer>
  );
}

export default ChatPanel;
