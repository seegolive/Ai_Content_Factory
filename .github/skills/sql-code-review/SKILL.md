 ---
name: sql-code-review
description: 'Universal SQL code review assistant that performs comprehensive security, maintainability, and code quality analysis across all SQL databases (MySQL, PostgreSQL, SQL Server, Oracle). Focuses on SQL injection prevention, access control, code standards, and anti-pattern detection.'
---

# SQL Code Review

Perform a thorough SQL code review focusing on security, performance, maintainability, and database best practices.

## Security Analysis

### SQL Injection Prevention
```sql
-- ❌ CRITICAL: SQL Injection vulnerability
query = "SELECT * FROM users WHERE id = " + userInput;

-- ✅ SECURE: Parameterized queries (PostgreSQL/MySQL)
PREPARE stmt FROM 'SELECT * FROM users WHERE id = ?';
EXECUTE stmt USING @user_id;
```

### Access Control & Permissions
- **Principle of Least Privilege**: Grant minimum required permissions
- **Role-Based Access**: Use database roles instead of direct user permissions
- **Data Protection**: Avoid SELECT * on tables with sensitive columns

## Performance Optimization

### Query Structure Analysis
```sql
-- ❌ BAD: Inefficient query patterns
SELECT DISTINCT u.* 
FROM users u, orders o
WHERE YEAR(o.order_date) = 2024;

-- ✅ GOOD: Optimized structure
SELECT u.id, u.name, u.email
FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.order_date >= '2024-01-01' 
  AND o.order_date < '2025-01-01';
```

### Index Strategy Review
- **Missing Indexes**: Identify columns that need indexing
- **Over-Indexing**: Find unused or redundant indexes
- **Composite Indexes**: Multi-column indexes for complex queries

### Common Anti-Patterns

**N+1 Query Problem**
```sql
-- ❌ BAD: N+1 queries in application code
for user in users:
    orders = query("SELECT * FROM orders WHERE user_id = ?", user.id)

-- ✅ GOOD: Single optimized query
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON u.id = o.user_id;
```

**Function Misuse in WHERE Clauses**
```sql
-- ❌ BAD: Functions prevent index usage
SELECT * FROM orders WHERE YEAR(order_date) = 2024;

-- ✅ GOOD: Range conditions use indexes
SELECT * FROM orders 
WHERE order_date >= '2024-01-01' 
  AND order_date < '2025-01-01';
```

## Code Quality & Maintainability

### SQL Style & Formatting
```sql
-- ❌ BAD: Poor formatting
select u.id,u.name from users u left join orders o on u.id=o.user_id;

-- ✅ GOOD: Clean, readable formatting
SELECT u.id,
       u.name
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.status = 'active';
```

### Naming Conventions
- Consistent naming: Tables, columns, constraints follow consistent patterns
- Descriptive names: Clear, meaningful names for database objects
- Avoid reserved words as identifiers

## SQL Review Checklist

### Security
- [ ] All user inputs are parameterized
- [ ] No dynamic SQL construction with string concatenation
- [ ] Appropriate access controls and permissions
- [ ] Sensitive data is properly protected
- [ ] SQL injection attack vectors are eliminated

### Performance
- [ ] Indexes exist for frequently queried columns
- [ ] No unnecessary SELECT * statements
- [ ] JOINs are optimized and use appropriate types
- [ ] WHERE clauses are selective and use indexes
- [ ] Subqueries are optimized or converted to JOINs

### Code Quality
- [ ] Consistent naming conventions
- [ ] Proper formatting and indentation
- [ ] Appropriate data types are used
- [ ] Error handling is implemented

### Schema Design
- [ ] Tables are properly normalized
- [ ] Constraints enforce data integrity
- [ ] Indexes support query patterns
- [ ] Foreign key relationships are defined

## Review Output Format

```
## [PRIORITY] [CATEGORY]: [Brief Description]

**Location**: [Table/View/Procedure name and line number]
**Issue**: [Detailed explanation]
**Security Risk**: [If applicable]
**Performance Impact**: [Query cost, execution time impact]
**Recommendation**: [Specific fix with code example]

**Before**: [Problematic SQL]
**After**: [Improved SQL]
```

### Summary Assessment
- **Security Score**: [1-10]
- **Performance Score**: [1-10]
- **Maintainability Score**: [1-10]
- **Schema Quality Score**: [1-10]
