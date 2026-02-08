import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { eventBus } from '@/utils/eventBus';
import { Tree, Spin, Typography } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { FileTreeNode } from '@/types';
import { listFileTree } from '@/api/client';

interface FileTreePanelProps {
  workspaceId: string;
  onSelectFile?: (path: string) => void;
  selectedPath?: string | null;
}

function pathToTreeKey(path: string) {
  return path || '/';
}

function sortEntries(entries: FileTreeNode[]): FileTreeNode[] {
  return [...entries].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
    return (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' });
  });
}

function flatEntryToDataNode(node: FileTreeNode): DataNode {
  const key = pathToTreeKey(node.path);
  return {
    title: node.name,
    key,
    isLeaf: !node.is_dir,
    ...(node.is_dir && { children: undefined }),
  };
}

function updateNodeChildren(
  nodes: DataNode[],
  targetKey: React.Key,
  children: DataNode[]
): DataNode[] {
  return nodes.map((node) => {
    if (node.key === targetKey) {
      return { ...node, children };
    }
    if (node.children) {
      return {
        ...node,
        children: updateNodeChildren(node.children, targetKey, children),
      };
    }
    return node;
  });
}

/** 合并新根数据与已缓存的懒加载子节点，避免 refetch 时子目录消失（递归处理嵌套目录） */
function mergeWithLoadedChildren(
  nodes: DataNode[],
  loadedChildrenMap: Map<React.Key, DataNode[]>
): DataNode[] {
  return nodes.map((node) => {
    if (node.isLeaf) return node;
    const cached = loadedChildrenMap.get(node.key);
    if (cached) {
      const mergedChildren = mergeWithLoadedChildren(cached, loadedChildrenMap);
      return { ...node, children: mergedChildren };
    }
    return { ...node, children: undefined };
  });
}

export function FileTreePanel({ workspaceId, onSelectFile, selectedPath }: FileTreePanelProps) {
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [treeData, setTreeData] = useState<DataNode[]>([]);
  const loadedChildrenMapRef = useRef<Map<React.Key, DataNode[]>>(new Map());

  const { isLoading: loading, refetch } = useQuery({
    queryKey: ['fileTree', workspaceId],
    queryFn: async () => {
      const result = await listFileTree(workspaceId, '');
      const rootNodes = sortEntries(result.entries || []).map(flatEntryToDataNode);
      const merged = mergeWithLoadedChildren(rootNodes, loadedChildrenMapRef.current);
      setTreeData(merged);
      return merged;
    },
    enabled: !!workspaceId,
  });

  // workspace 切换时清空已加载子节点缓存
  useEffect(() => {
    loadedChildrenMapRef.current = new Map();
  }, [workspaceId]);

  // stream 期间通过 event bus 接收轮询触发，刷新文件树
  useEffect(() => {
    if (!workspaceId) return;
    const onStreamTick = () => refetch();
    eventBus.on('stream-tick', onStreamTick);
    return () => eventBus.off('stream-tick', onStreamTick);
  }, [workspaceId, refetch]);

  const loadData = useCallback(
    async (node: DataNode) => {
      if (node.children) return;
      const dir = String(node.key);
      const result = await listFileTree(workspaceId, dir);
      const children = sortEntries(result.entries || []).map(flatEntryToDataNode);
      loadedChildrenMapRef.current.set(node.key, children);
      setTreeData((prev) => updateNodeChildren(prev, node.key, children));
    },
    [workspaceId]
  );

  const onSelect = (keys: React.Key[]) => {
    const key = keys[0];
    if (!key || key === '/') return;
    const path = String(key) === '/' ? '' : String(key);
    onSelectFile?.(path);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Spin tip="加载文件树..." />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto py-2 px-2">
      <Typography.Text type="secondary" className="px-3 block mb-2 text-xs">
        项目文件
      </Typography.Text>
      <Tree
        showLine
        blockNode
        selectedKeys={selectedPath != null ? [pathToTreeKey(selectedPath)] : []}
        expandedKeys={expandedKeys}
        onExpand={(keys) => setExpandedKeys(keys)}
        treeData={treeData}
        loadData={loadData}
        onSelect={(_, info) => {
          if (info.node.isLeaf) onSelect([info.node.key as string]);
        }}
        fieldNames={{ title: 'title', key: 'key', children: 'children' }}
      />
    </div>
  );
}

export default FileTreePanel;
