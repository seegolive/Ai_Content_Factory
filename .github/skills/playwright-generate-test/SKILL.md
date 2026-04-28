 ---
name: playwright-generate-test
description: 'Generate a Playwright test based on a scenario using Playwright MCP'
---

# Test Generation with Playwright MCP

Your goal is to generate a Playwright test based on the provided scenario after completing all prescribed steps.

## Specific Instructions

- You are given a scenario, and you need to generate a playwright test for it. If the user does not provide a scenario, you will ask them to provide one.
- DO NOT generate test code prematurely or based solely on the scenario without completing all prescribed steps.
- DO run steps one by one using the tools provided by the Playwright MCP.
- Only after all steps are completed, emit a Playwright TypeScript test that uses `@playwright/test` based on message history.
- Save generated test file in the tests directory.
- Execute the test file and iterate until the test passes.

## Workflow

1. **Understand the scenario** — Ask clarifying questions if the scenario is unclear.
2. **Navigate to the page** — Use Playwright MCP to open the target URL.
3. **Inspect the page** — Take a snapshot to understand the DOM structure.
4. **Identify selectors** — Find reliable selectors for the elements involved in the scenario. Prefer `data-testid`, `role`, or `aria-label` over CSS classes.
5. **Trace the user flow** — Interact with the page step by step, capturing each action.
6. **Generate the test** — Write a clean, readable Playwright test based on your observations.
7. **Run and fix** — Execute the test and iterate until it passes.

## Test Structure

```typescript
import { test, expect } from '@playwright/test';

test('scenario description', async ({ page }) => {
  // Navigate
  await page.goto('http://localhost:3000');
  
  // Interact
  await page.getByRole('button', { name: 'Submit' }).click();
  
  // Assert
  await expect(page.getByText('Success')).toBeVisible();
});
```

## Best Practices

- Use `getByRole`, `getByText`, `getByLabel` over CSS selectors when possible
- Add `await expect(...)` assertions to verify each important state change
- Use `page.waitForURL()` after navigation actions
- Add descriptive test names that explain the user scenario
- Group related tests in `test.describe()` blocks
