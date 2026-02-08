import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { createSession } from '../api/client';

interface SessionManagerProps {
  onSessionCreated: (session: any) => void;
}

export function SessionManager({ onSessionCreated }: SessionManagerProps) {
  const [name, setName] = useState('');
  const [framework, setFramework] = useState('fastapi-vite');

  const { mutateAsync: handleCreate, isPending: loading, error } = useMutation({
    mutationFn: () => createSession(name, framework),
    onSuccess: (session) => {
      onSessionCreated(session);
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    handleCreate();
  };

  const errorMessage = error instanceof Error ? error.message : 'Failed to create session';

  return (
    <div style={{ padding: '20px', borderBottom: '1px solid #ccc' }}>
      <h2>Create New App</h2>
      <form onSubmit={onSubmit} style={{ display: 'flex', gap: '10px', alignItems: 'flex-end' }}>
        <div>
          <label>
            App Name:
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-app"
              style={{ padding: '8px', marginLeft: '10px' }}
            />
          </label>
        </div>
        <div>
          <label>
            Framework:
            <select
              value={framework}
              onChange={(e) => setFramework(e.target.value)}
              style={{ padding: '8px', marginLeft: '10px' }}
            >
              <option value="fastapi-vite">FastAPI + React Vite</option>
              <option value="nextjs">Next.js</option>
            </select>
          </label>
        </div>
        <button type="submit" disabled={loading} style={{ padding: '8px 20px' }}>
          {loading ? 'Creating...' : 'Create'}
        </button>
      </form>
      {error && <div style={{ color: 'red', marginTop: '10px' }}>{errorMessage}</div>}
    </div>
  );
}
