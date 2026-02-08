/**
 * Agent related types
 */

export interface AgentTaskRequest {
  prompt: string;
}

export interface AgentTaskResponse {
  task_id: string;
  status: string;
}

export enum EventType {
  AGENT_START = 'agent_start',
  MESSAGE_DELTA = 'message_delta',
  MESSAGE_COMPLETE = 'message_complete',
  TOOL_START = 'tool_start',
  TOOL_END = 'tool_end',
  AGENT_ERROR = 'agent_error',
  FINISH = 'finish',
}

export interface SSEEvent {
  event_id: string;
  event_type: EventType;
  data: any;
}
