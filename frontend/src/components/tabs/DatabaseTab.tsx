import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { listCollections, queryCollection } from '../../api/client';
import type { CollectionInfo, DatabaseQueryResponse } from '../../types';

interface DatabaseTabProps {
  sessionId: string;
}

export function DatabaseTab({ sessionId }: DatabaseTabProps) {
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [filterInput, setFilterInput] = useState('{}');
  const [parseError, setParseError] = useState('');

  const { data: collectionsData, isLoading: loading, error: collectionsError } = useQuery({
    queryKey: ['collections', sessionId],
    queryFn: () => listCollections(sessionId),
    enabled: !!sessionId,
  });

  const collections = collectionsData?.collections ?? [];

  useEffect(() => {
    if (collections.length > 0 && !selectedCollection) {
      setSelectedCollection(collections[0].name);
    }
  }, [collections, selectedCollection]);

  const { mutateAsync: handleQuery, data: queryResult, isPending: querying, error: queryError } = useMutation({
    mutationFn: async ({ collection, filter }: { collection: string; filter: Record<string, any> }) =>
      queryCollection(sessionId, collection, filter, 10, 0),
    onError: () => {},
  });

  const error = parseError
    ? parseError
    : collectionsError
      ? (collectionsError instanceof Error ? collectionsError.message : 'Failed to load collections')
      : queryError
        ? (queryError instanceof Error ? queryError.message : 'Query failed')
        : '';

  const onQueryClick = () => {
    setParseError('');
    if (!selectedCollection) return;
    let filter = {};
    if (filterInput.trim()) {
      try {
        filter = JSON.parse(filterInput);
      } catch {
        setParseError('Invalid JSON filter');
        return;
      }
    }
    handleQuery({ collection: selectedCollection, filter });
  };

  if (loading) {
    return <div style={{ padding: '20px' }}>Loading collections...</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <h3>Database Query</h3>
      
      {collections.length === 0 ? (
        <p style={{ color: '#666' }}>No collections found. The app database is empty.</p>
      ) : (
        <div>
          {/* Collection selector */}
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Collection:
            </label>
            <select
              value={selectedCollection}
              onChange={(e) => setSelectedCollection(e.target.value)}
              style={{ padding: '8px', fontSize: '14px', width: '100%', maxWidth: '400px' }}
            >
              {collections.map((col) => (
                <option key={col.name} value={col.name}>
                  {col.name} ({col.document_count} documents)
                </option>
              ))}
            </select>
          </div>

          {/* Filter input */}
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Filter (JSON):
            </label>
            <textarea
              value={filterInput}
              onChange={(e) => setFilterInput(e.target.value)}
              placeholder='{"field": "value"}'
              rows={3}
              style={{
                padding: '8px',
                fontSize: '14px',
                width: '100%',
                maxWidth: '600px',
                fontFamily: 'monospace',
              }}
            />
          </div>

          {/* Query button */}
          <button
            onClick={onQueryClick}
            disabled={querying}
            style={{
              padding: '10px 20px',
              fontSize: '14px',
              backgroundColor: querying ? '#ccc' : '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: querying ? 'not-allowed' : 'pointer',
              marginBottom: '15px',
            }}
          >
            {querying ? 'Querying...' : 'Query'}
          </button>

          {/* Error message */}
          {error && (
            <div style={{ padding: '10px', backgroundColor: '#ffebee', color: '#c62828', borderRadius: '4px', marginBottom: '15px' }}>
              {error}
            </div>
          )}

          {/* Query results */}
          {queryResult && (
            <div>
              <h4>
                Results ({queryResult.documents.length} of {queryResult.count})
                {queryResult.has_more && ' - More available'}
              </h4>
              {queryResult.documents.length === 0 ? (
                <p style={{ color: '#666' }}>No documents found matching the filter.</p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <pre style={{
                    backgroundColor: '#f5f5f5',
                    padding: '15px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    maxHeight: '400px',
                    overflowY: 'auto',
                  }}>
                    {JSON.stringify(queryResult.documents, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DatabaseTab;
