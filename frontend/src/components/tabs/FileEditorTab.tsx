import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Typography, message } from 'antd';
import Editor from '@monaco-editor/react';
import { readFile } from '@/api/client';
import { useAppStore } from '@/stores/appStore';
import FileTreePanel from '../FileTreePanel';

function getLanguageFromPath(path: string | null): string {
  if (!path) return 'plaintext';
  const ext = path.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    js: 'javascript',
    ts: 'typescript',
    jsx: 'javascript',
    tsx: 'typescript',
    json: 'json',
    py: 'python',
    html: 'html',
    css: 'css',
    scss: 'scss',
    md: 'markdown',
    yaml: 'yaml',
    yml: 'yaml',
    sh: 'shell',
    bash: 'shell',
  };
  return map[ext ?? ''] ?? 'plaintext';
}

interface FileEditorTabProps {
  workspaceId: string;
}

export function FileEditorTab({ workspaceId }: FileEditorTabProps) {
  const { selectedFilePath, setSelectedFilePath } = useAppStore();

  const { data: fileData, isLoading: loading, error: fileError } = useQuery({
    queryKey: ['file', workspaceId, selectedFilePath],
    queryFn: () => readFile(workspaceId, selectedFilePath!),
    enabled: !!workspaceId && !!selectedFilePath,
  });

  useEffect(() => {
    if (fileError) {
      message.error('读取文件失败');
    }
  }, [fileError]);

  const content = fileData?.content ?? '';

  return (
    <div className="flex-1 flex w-full h-full">
      <div className="w-64 shrink-0 border-r border-gray-100 flex flex-col overflow-hidden">
        <FileTreePanel
          workspaceId={workspaceId}
          selectedPath={selectedFilePath}
          onSelectFile={setSelectedFilePath}
        />
      </div>

      <div className="grow min-h-0 h-full flex flex-col">
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 shrink-0">
          <Typography.Text className="font-mono text-sm truncate flex-1">{selectedFilePath}</Typography.Text>
        </div>
        <div className="flex-1 min-h-[200px] overflow-hidden">
          <Editor
            language={getLanguageFromPath(selectedFilePath)}
            value={content}
            loading={loading ? '加载中...' : undefined}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              fontSize: 13,
              fontFamily: 'ui-monospace, monospace',
            }}
            className="border-0"
          />
        </div>
      </div>
    </div>
  );
}

export default FileEditorTab;
