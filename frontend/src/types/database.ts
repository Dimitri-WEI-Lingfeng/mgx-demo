/**
 * Database related types
 */

export interface CollectionInfo {
  name: string;
  document_count: number;
}

export interface CollectionsResponse {
  collections: CollectionInfo[];
}

export interface DatabaseQueryRequest {
  collection: string;
  filter: Record<string, any>;
  limit?: number;
  skip?: number;
}

export interface DatabaseQueryResponse {
  collection: string;
  documents: Array<Record<string, any>>;
  count: number;
  has_more: boolean;
}
