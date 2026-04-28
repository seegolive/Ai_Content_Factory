 ---
name: postgresql-optimization
description: 'PostgreSQL-specific development assistant focusing on unique PostgreSQL features, advanced data types, and PostgreSQL-exclusive capabilities. Covers JSONB operations, array types, custom types, range/geometric types, full-text search, window functions, and PostgreSQL extensions ecosystem.'
---

# PostgreSQL Development Assistant

Expert PostgreSQL guidance focusing on PostgreSQL-specific features, optimization patterns, and advanced capabilities.

## PostgreSQL-Specific Features

### JSONB Operations
```sql
-- GIN index for JSONB performance
CREATE INDEX idx_events_data_gin ON events USING gin(data);

-- JSONB containment and path queries
SELECT * FROM events 
WHERE data @> '{"type": "login"}'
  AND data #>> '{user,role}' = 'admin';
```

### Array Operations
```sql
SELECT * FROM posts WHERE 'postgresql' = ANY(tags);
SELECT * FROM posts WHERE tags && ARRAY['database', 'sql'];
```

### Window Functions & Analytics
```sql
SELECT 
    product_id,
    SUM(amount) OVER (PARTITION BY product_id ORDER BY sale_date) as running_total,
    AVG(amount) OVER (PARTITION BY product_id ORDER BY sale_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as moving_avg,
    LAG(amount, 1) OVER (PARTITION BY product_id ORDER BY sale_date) as prev_amount
FROM sales;
```

### Full-Text Search
```sql
CREATE INDEX idx_documents_search ON documents USING gin(search_vector);

SELECT *, ts_rank(search_vector, plainto_tsquery('postgresql')) as rank
FROM documents 
WHERE search_vector @@ plainto_tsquery('postgresql')
ORDER BY rank DESC;
```

## Performance Tuning

### Query Optimization
```sql
-- EXPLAIN ANALYZE for performance analysis
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) 
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'::date
GROUP BY u.id, u.name;

-- Identify slow queries from pg_stat_statements
SELECT query, calls, total_time, mean_time, rows,
       100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
```

### Index Strategies
```sql
-- Composite indexes for multi-column queries
CREATE INDEX idx_orders_user_date ON orders(user_id, order_date);

-- Partial indexes for filtered queries
CREATE INDEX idx_active_users ON users(created_at) WHERE status = 'active';

-- Expression indexes for computed values
CREATE INDEX idx_users_lower_email ON users(lower(email));

-- Covering indexes to avoid table lookups
CREATE INDEX idx_orders_covering ON orders(user_id, status) INCLUDE (total, created_at);
```

## Common Query Patterns

### Pagination (use cursor-based, not OFFSET)
```sql
-- ❌ BAD: OFFSET for large datasets
SELECT * FROM products ORDER BY id OFFSET 10000 LIMIT 20;

-- ✅ GOOD: Cursor-based pagination
SELECT * FROM products 
WHERE id > $last_id 
ORDER BY id 
LIMIT 20;
```

### JSONB Queries
```sql
-- ❌ BAD: Inefficient JSON querying
SELECT * FROM users WHERE data::text LIKE '%admin%';

-- ✅ GOOD: JSONB operators and GIN index
SELECT * FROM users WHERE data @> '{"role": "admin"}';
```

## Optimization Checklist

- [ ] Run EXPLAIN ANALYZE for expensive queries
- [ ] Check for sequential scans on large tables
- [ ] Create indexes for frequently queried columns
- [ ] Use composite indexes for multi-column searches
- [ ] Consider partial indexes for filtered queries
- [ ] Remove unused or duplicate indexes
- [ ] Use parameterized queries exclusively
- [ ] Implement proper access controls
- [ ] Enable row-level security where needed
- [ ] Set up query performance monitoring with pg_stat_statements

## PostgreSQL-Specific Optimization Tips
- Use `EXPLAIN (ANALYZE, BUFFERS)` for detailed query analysis
- Configure `postgresql.conf` for your workload (OLTP vs OLAP)
- Use connection pooling (pgbouncer) for high-concurrency applications
- Regular VACUUM and ANALYZE for optimal performance
- Partition large tables using PostgreSQL 10+ declarative partitioning
