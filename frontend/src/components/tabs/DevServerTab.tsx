import { useQuery } from '@tanstack/react-query';
import { getDevStatus, getDevServerLogs } from '../../api/client';
import { useState } from 'react';
interface DevServerTabProps {
  sessionId: string;
  appName: string;
}

export function DevServerTab({ sessionId, appName }: DevServerTabProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);
  const drawerHeight = 200;

  const { data: status, isLoading: loading, error, isFetching } = useQuery({
    queryKey: ['dev-status', sessionId],
    queryFn: async () => {
      const res = await getDevStatus(sessionId);
      return res;
    },
    enabled: !!sessionId,
    refetchInterval: 5000,
  });

  const {
    data: logsData,
    error: logsError,
    refetch: refetchLogs,
    isFetching: logsFetching,
  } = useQuery({
    queryKey: ['dev-server-logs', sessionId],
    queryFn: () => getDevServerLogs(sessionId, 200),
    enabled: drawerOpen && !!sessionId,
    refetchInterval: drawerOpen ? 3000 : false,
  });

  const logs = logsError
    ? `Failed to fetch logs: ${(logsError as Error).message}`
    : logsData?.logs ?? (logsFetching ? '加载中...' : '');

  const errorMessage = error instanceof Error ? error.message : 'Failed to load dev server status';

  if (loading) {
    return <div className="p-5">Loading dev server status...</div>;
  }

  if (error) {
    return (
      <div className="p-5 text-red-500">
        {errorMessage}
      </div>
    );
  }

  if (!status || status.status !== 'running' || !status.dev_url) {
    return (
      <div className="p-5">
        <h3>Dev Server Status</h3>
        <p className={`font-bold ${status?.status === 'running' ? 'text-green-500' : 'text-orange-500'}`}>
          Status: {status?.status || 'unknown'}
        </p>
        {status?.status !== 'running' && (
          <p className="text-gray-500">
            The dev server is not running yet. The agent will start it when generating the app code.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-2 p-2">
      <div className="p-2.5 border-b border-gray-200 bg-gray-100 flex items-center justify-between gap-2.5">
        <p className="m-0 text-sm">
          <strong>Status:</strong> <span className="text-green-500">Running</span>
          {' | '}
          <strong>URL:</strong> <a href={status.dev_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{status.dev_url}</a>
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setDrawerOpen((o) => !o)}
            className={`py-1 px-2.5 text-xs rounded border ${
              drawerOpen ? 'bg-gray-200 border-gray-300' : 'bg-white border-gray-300 hover:bg-gray-50'
            }`}
          >
            {drawerOpen ? '收起日志' : 'Terminal 日志'}
          </button>
          <button
            type="button"
            onClick={() => setIframeKey((k) => k + 1)}
            disabled={isFetching}
            className={`py-1 px-2.5 text-xs rounded border ${isFetching ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'} bg-white border-gray-300 hover:bg-gray-50`}
          >
            {isFetching ? '刷新中...' : '刷新'}
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 flex flex-col gap-2">
        <iframe
          key={iframeKey}
          src={status.dev_url}
          className="flex-1 min-h-0 w-full border border-gray-200 rounded-lg overflow-hidden"
          title={`Dev Server - ${appName}`}
        />
        {drawerOpen && (
          <div
            className="border border-gray-200 rounded-lg overflow-hidden flex flex-col bg-[#1e1e1e] shrink-0"
            style={{ height: drawerHeight }}
          >
            <div className="px-3 py-1.5 bg-[#2d2d2d] border-b border-gray-600 flex items-center justify-between text-xs text-gray-300">
              <span>Terminal — dev server logs</span>
              <button
                type="button"
                onClick={() => refetchLogs()}
                disabled={logsFetching}
                className="px-2 py-0.5 rounded hover:bg-gray-600 disabled:opacity-50"
              >
                {logsFetching ? '刷新中...' : '刷新'}
              </button>
            </div>
            <pre
              className="flex-1 overflow-auto p-3 text-[13px] font-mono text-[#d4d4d4] m-0"
              style={{ lineHeight: 1.5 }}
            >
              {logs}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default DevServerTab;
