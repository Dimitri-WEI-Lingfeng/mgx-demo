/**
 * Message related types
 */

export enum ContentPartType {
  TEXT = 'text',
  IMAGE = 'image',
  AUDIO = 'audio',
  VIDEO = 'video',
  FILE = 'file',
  TOOL_CALL = 'tool_call',
  TOOL_RESULT = 'tool_result',
}

export interface ContentPart {
  type: ContentPartType;
  text?: string;
  image_url?: string;
  file_url?: string;
  tool_call_id?: string;
  tool_name?: string;
  tool_args?: Record<string, any>;
  tool_result?: any;
}

export interface Message {
  message_id: string;
  session_id: string;
  parent_id?: string;
  agent_name?: string;
  role: string;
  content: string | ContentPart[];
  tool_call_id?: string;
  tool_calls: Array<{
    id: string;
    name: string;
    args: Record<string, any>;
  }>;
  cause_by?: string;
  sent_from?: string;
  send_to: string[];
  trace_id?: string;
  timestamp: number;
  metadata: Record<string, any>;
}

export interface HistoryResponse {
  messages: Message[];
}
