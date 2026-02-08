/**
 * Container related types
 */

export interface DevContainerResponse {
  status: 'not_created' | 'created' | 'running' | 'stopped' | 'exited';
  container_id?: string;
  dev_url?: string;
}

export interface DevServerStatus {
  running: boolean;
  port?: number;
  pid?: number;
  uptime?: number;
}

export interface ProdContainerResponse {
  status: 'not_created' | 'created' | 'running' | 'stopped' | 'exited';
  container_id?: string;
  prod_url?: string;
}

export interface ProdBuildResponse {
  success: boolean;
  message: string;
  image_id?: string;
}
