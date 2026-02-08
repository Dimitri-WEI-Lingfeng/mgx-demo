import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { buildProd, deployProd, stopProd, getProdStatus, getLogs } from '../api/client';

interface ProdConsoleProps {
  sessionId: string;
  appName: string;
}

export function ProdConsole({ sessionId, appName }: ProdConsoleProps) {
  const queryClient = useQueryClient();

  const { data: status, refetch: checkStatus } = useQuery({
    queryKey: ['prod-status', sessionId],
    queryFn: () => getProdStatus(sessionId),
    enabled: !!sessionId,
  });

  const { data: logsData, refetch: handleRefreshLogs, isFetching: logsFetching, error: logsError } = useQuery({
    queryKey: ['prod-logs', sessionId],
    queryFn: () => getLogs(sessionId, 'prod', 100),
    enabled: false,
  });

  const logs = logsError ? `Failed to fetch logs: ${logsError.message}` : (logsData?.logs ?? (logsFetching ? '加载中...' : ''));

  const { mutateAsync: handleBuild, data: buildResult, isPending: buildPending } = useMutation({
    mutationFn: () => buildProd(sessionId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['prod-status', sessionId] });
      if (result.status === 'success') {
        alert('Build successful!');
      } else {
        alert(`Build failed: ${result.error || 'Unknown error'}`);
      }
    },
    onError: (err: Error) => alert(`Build failed: ${err.message}`),
  });

  const { mutateAsync: handleDeploy, isPending: deployPending } = useMutation({
    mutationFn: () => deployProd(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prod-status', sessionId] });
      alert('Deployed!');
    },
    onError: (err: Error) => alert(`Deploy failed: ${err.message}`),
  });

  const { mutateAsync: handleStop, isPending: stopPending } = useMutation({
    mutationFn: () => stopProd(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prod-status', sessionId] });
      alert('Production stopped!');
    },
    onError: (err: Error) => alert(`Failed to stop: ${err.message}`),
  });

  const loading = buildPending || deployPending || stopPending;

  const prodUrl = status?.prod_url;
  const isRunning = status?.status === 'running';

  return (
    <div style={{ padding: '20px' }}>
      <h3>Production Environment</h3>
      
      <div style={{ marginBottom: '20px' }}>
        <p>Status: <strong>{status?.status || 'not built'}</strong></p>
        {buildResult && (
          <p>Last Build: <strong style={{ color: buildResult.status === 'success' ? 'green' : 'red' }}>
            {buildResult.status}
          </strong></p>
        )}
        <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
          <button onClick={handleBuild} disabled={loading}>
            Build Image
          </button>
          <button onClick={handleDeploy} disabled={loading || !buildResult || buildResult.status !== 'success'}>
            Deploy
          </button>
          <button onClick={handleStop} disabled={loading || !isRunning}>
            Stop
          </button>
          <button onClick={checkStatus}>Refresh Status</button>
          <button onClick={handleRefreshLogs}>Refresh Logs</button>
        </div>
      </div>

      {prodUrl && isRunning && (
        <div style={{ marginBottom: '20px' }}>
          <h4>Production Preview</h4>
          <p>
            Prod URL: <a href={prodUrl} target="_blank" rel="noopener noreferrer">{prodUrl}</a>
            {' '}(Open in new tab)
          </p>
          <iframe
            src={prodUrl}
            style={{ width: '100%', height: '600px', border: '1px solid #ccc' }}
            title="Production Preview"
          />
        </div>
      )}

      {logs && (
        <div style={{ marginTop: '20px' }}>
          <h4>Production Logs</h4>
          <pre style={{
            background: '#000',
            color: '#0f0',
            padding: '10px',
            height: '300px',
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '12px'
          }}>
            {logs}
          </pre>
        </div>
      )}
    </div>
  );
}
