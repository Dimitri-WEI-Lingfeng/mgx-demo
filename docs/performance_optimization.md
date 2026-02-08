# Performance Optimization Guide

## Database Indexing

### Event Collection Indexes

The following indexes are created for optimal query performance:

1. **Compound Index: (session_id, timestamp)**
   - Purpose: Fast polling for new events in SSE streaming
   - Query pattern: `find({session_id: X, timestamp: {$gt: Y}})`
   - Impact: O(log n) lookup instead of O(n) scan

2. **Unique Index: event_id**
   - Purpose: Fast event lookup by ID
   - Query pattern: `find({event_id: X})`
   - Impact: O(1) lookup

3. **Index: trace_id**
   - Purpose: Fast lookup of events by langfuse trace
   - Query pattern: `find({trace_id: X})`
   - Impact: Support for debugging and trace analysis

4. **TTL Index: timestamp (7 days)**
   - Purpose: Automatic cleanup of old events
   - Impact: Prevents database bloat, maintains performance

### Message Collection Indexes

1. **Compound Index: (session_id, timestamp)**
   - Purpose: Fast retrieval of session messages
   - Query pattern: `find({session_id: X}).sort({timestamp: 1})`

2. **Unique Index: message_id**
   - Purpose: Fast message lookup

3. **Index: parent_id**
   - Purpose: Fast message tree queries
   - Query pattern: `find({parent_id: X})`

4. **Index: trace_id**
   - Purpose: Langfuse integration

## SSE Streaming Optimization

### Polling Interval

Current: 500ms (0.5 seconds)

**Tuning Guidelines:**
- **Lower latency (100-200ms)**: Better user experience, higher database load
- **Balanced (500ms)**: Good trade-off for most use cases
- **Lower load (1000ms)**: Reduce database queries, slightly higher latency

### Batch Size

Current: 100 events per poll

**Tuning Guidelines:**
- Most agent tasks generate < 100 events
- Increase if you have very chatty agents
- Monitor database query performance

### Connection Timeout

Current: 300 seconds (5 minutes)

**Tuning Guidelines:**
- Increase for long-running agent tasks
- Monitor Celery task execution time
- Consider task timeout alignment

## Memory Optimization

### Event Retention

**TTL Index:** 7 days

**Recommendations:**
- Adjust based on compliance requirements
- Consider archiving to cold storage for long-term retention
- Monitor collection size: `db.events.stats()`

### Connection Pooling

**MongoDB:**
- Default motor connection pooling
- Monitor with: `db.serverStatus().connections`

**Redis:**
- Celery uses connection pooling by default
- Configure with `broker_pool_limit`

## Monitoring Metrics

### Key Metrics to Track

1. **Event Creation Rate**
   - Events per second
   - Alert if > 1000/sec

2. **Event Query Latency**
   - p50, p95, p99 latencies
   - Target: < 10ms for p95

3. **SSE Connection Count**
   - Active connections
   - Alert if > 10,000

4. **Database Collection Size**
   - Events collection size
   - Messages collection size
   - Alert if > 10GB

5. **Celery Task Metrics**
   - Task execution time
   - Task failure rate
   - Queue length

### Monitoring Commands

```bash
# Check MongoDB indexes
mongosh --eval "db.events.getIndexes()"

# Check collection stats
mongosh --eval "db.events.stats()"

# Check event count
mongosh --eval "db.events.countDocuments({})"

# Check recent events
mongosh --eval 'db.events.find().sort({timestamp:-1}).limit(10)'
```

## Scaling Strategies

### Horizontal Scaling

1. **Multiple FastAPI Instances**
   - Load balance with nginx/apisix
   - Each instance can serve SSE streams independently
   - No shared state (events in database)

2. **Multiple Celery Workers**
   - Scale agent execution capacity
   - Configure with `--concurrency` flag
   - Monitor queue length

3. **MongoDB Replica Set**
   - Read scaling for event queries
   - High availability
   - Configure read preference

### Vertical Scaling

1. **Database Resources**
   - Increase RAM for index caching
   - Faster disk for write-heavy workloads

2. **API Server Resources**
   - More CPU for concurrent SSE streams
   - More memory for buffering

## Best Practices

### Event Design

1. **Keep event data small**
   - < 1KB per event
   - Use message references instead of embedding

2. **Batch related events**
   - Consider aggregating rapid-fire deltas
   - Balance between granularity and overhead

3. **Use appropriate event types**
   - Don't over-categorize
   - Clear semantic meaning

### Error Handling

1. **Graceful degradation**
   - Continue on non-critical errors
   - Log but don't fail

2. **Retry logic**
   - Exponential backoff for database operations
   - Circuit breaker for external services

3. **Client reconnection**
   - Use stream-continue endpoint
   - Include since_timestamp in client state for reconnection

## Performance Testing

### Load Testing

```bash
# Test SSE endpoint with multiple clients
python scripts/load_test_sse.py --clients 100 --duration 60

# Test event creation rate
python scripts/benchmark_events.py --events 10000
```

### Profiling

```bash
# Profile agent runtime
python -m cProfile -o profile.stats src/agent_scheduler/tasks.py

# Analyze profile
python -m pstats profile.stats
```

## Troubleshooting

### Slow Event Queries

**Symptoms:** High p95 latency, slow SSE streaming

**Solutions:**
1. Check index usage: `explain()` on queries
2. Verify indexes exist: `getIndexes()`
3. Monitor index memory: `db.serverStatus().indexDetails`
4. Consider adding covered queries

### High Database Load

**Symptoms:** High CPU/memory on MongoDB

**Solutions:**
1. Reduce polling frequency
2. Increase batch size (fetch more events per query)
3. Add more read replicas
4. Enable query profiling

### SSE Connection Issues

**Symptoms:** Frequent disconnections, timeout errors

**Solutions:**
1. Check nginx/apisix buffering settings
2. Increase client timeout
3. Verify network stability
4. Check server resource utilization

## Configuration Tuning

### Environment Variables

```bash
# SSE Configuration
SSE_POLL_INTERVAL=0.5  # seconds
SSE_BATCH_SIZE=100     # events per poll
SSE_TIMEOUT=300        # seconds

# Database Configuration
EVENT_RETENTION_DAYS=7
MESSAGE_RETENTION_DAYS=30

# Celery Configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=600  # seconds
```

### Runtime Configuration

See `src/shared/config/settings.py` for all configurable parameters.
