/**
 * Workspace related types
 */

export interface DirectoryEntry {
  name: string;
  type: 'file' | 'directory';
  size?: number;
  modified_at?: number;
}

export interface DirectoryResponse {
  path: string;
  entries: DirectoryEntry[];
}

export interface FileTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  size?: number;
  children?: FileTreeNode[];
}

export interface FileTreeResponse {
  entries: FileTreeNode[];
}

export interface FileResponse {
  path: string;
  content: string;
  size: number;
}

export interface FileContent {
  content: string;
}
