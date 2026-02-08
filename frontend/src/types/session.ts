/**
 * Session related types
 */

export interface Session {
  session_id: string;
  name: string;
  framework: string;
  workspace_id: string;
  workspace_path: string;
  creator: string;
  created_at: number;
  updated_at: number;
  is_running?: boolean;
}

export interface SessionCreate {
  name: string;
  framework: string;
}

export interface SessionResponse extends Session {}
