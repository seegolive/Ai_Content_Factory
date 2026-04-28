 ---
name: refactor
description: 'Surgical code refactoring to improve maintainability without changing behavior. Covers extracting functions, renaming variables, breaking down god functions, improving type safety, eliminating code smells, and applying design patterns. Less drastic than repo-rebuilder; use for gradual improvements.'
license: MIT
---

# Refactor

## Overview

Improve code structure and readability without changing external behavior. Refactoring is gradual evolution, not revolution.

## When to Use

Use this skill when:

- Code is hard to understand or maintain
- Functions/classes are too large
- Code smells need addressing
- Adding features is difficult due to code structure
- User asks "clean up this code", "refactor this", "improve this"

## Refactoring Principles

1. **Behavior is preserved** — Refactoring doesn't change what the code does, only how
2. **Small steps** — Make tiny changes, test after each
3. **Version control is your friend** — Commit before and after each safe state
4. **Tests are essential** — Without tests, you're not refactoring, you're editing
5. **One thing at a time** — Don't mix refactoring with feature changes

### When NOT to Refactor

- Code that works and won't change again
- Critical production code without tests (add tests first)
- When you're under a tight deadline

## Common Code Smells & Fixes

### 1. Long Method/Function
Extract into smaller focused functions.

### 2. Duplicated Code
Extract common logic into a shared function.

### 3. Large Class/Module
Split into single-responsibility classes.

### 4. Long Parameter List
Group related parameters into an object/interface.

### 5. Magic Numbers/Strings
Replace with named constants.

```diff
- if (user.status === 2) { /* ... */ }
- setTimeout(callback, 86400000);

+ const UserStatus = { ACTIVE: 1, INACTIVE: 2, SUSPENDED: 3 } as const;
+ const ONE_DAY_MS = 24 * 60 * 60 * 1000;
+ if (user.status === UserStatus.INACTIVE) { /* ... */ }
+ setTimeout(callback, ONE_DAY_MS);
```

### 6. Nested Conditionals
Use guard clauses / early returns.

```diff
- function process(order) {
-   if (order) {
-     if (order.user) {
-       if (order.user.isActive) {
-         return processOrder(order);
-       }
-     }
-   }
- }

+ function process(order) {
+   if (!order) return { error: 'No order' };
+   if (!order.user) return { error: 'No user' };
+   if (!order.user.isActive) return { error: 'User inactive' };
+   return processOrder(order);
+ }
```

### 7. Dead Code
Remove unused functions, imports, and commented-out code. Git history has it if needed.

## Refactoring Steps

```
1. PREPARE
   - Ensure tests exist (write them if missing)
   - Commit current state
   - Create feature branch

2. IDENTIFY
   - Find the code smell to address
   - Understand what the code does
   - Plan the refactoring

3. REFACTOR (small steps)
   - Make one small change
   - Run tests
   - Commit if tests pass
   - Repeat

4. VERIFY
   - All tests pass
   - Manual testing if needed
   - Performance unchanged or improved

5. CLEAN UP
   - Update comments
   - Final commit
```

## Refactoring Checklist

### Code Quality
- [ ] Functions are small (< 50 lines)
- [ ] Functions do one thing
- [ ] No duplicated code
- [ ] Descriptive names (variables, functions, classes)
- [ ] No magic numbers/strings
- [ ] Dead code removed

### Structure
- [ ] Related code is together
- [ ] Clear module boundaries
- [ ] Dependencies flow in one direction
- [ ] No circular dependencies

### Type Safety
- [ ] Types defined for all public APIs
- [ ] No `any` types without justification
- [ ] Nullable types explicitly marked

### Testing
- [ ] Refactored code is tested
- [ ] Tests cover edge cases
- [ ] All tests pass
