 ---
name: webapp-testing
description: Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs.
---

# Web Application Testing

This skill enables comprehensive testing and debugging of local web applications using Playwright automation.

Use the Playwright MCP Server to undertake the work if possible. If the MCP Server is unavailable, you can run the code in a local Node.js environment with Playwright installed.

## When to Use This Skill

Use this skill when you need to:

- Test frontend functionality in a real browser
- Verify UI behavior and interactions
- Debug web application issues
- Capture screenshots for documentation or debugging
- Inspect browser console logs
- Validate form submissions and user flows
- Check responsive design across viewports

## Prerequisites

- Node.js installed on the system
- A locally running web application (or accessible URL)
- Playwright will be installed automatically if not present

## Core Capabilities

### 1. Browser Automation
- Navigate to URLs
- Click buttons and links
- Fill form fields
- Select dropdowns
- Handle dialogs and alerts

### 2. Verification
- Assert element presence
- Verify text content
- Check element visibility
- Validate URLs
- Test responsive behavior

### 3. Debugging
- Capture screenshots
- View console logs
- Inspect network requests
- Debug failed tests

## Usage Examples

```javascript
// Navigate to a page and verify title
await page.goto("http://localhost:3000");
const title = await page.title();
console.log("Page title:", title);

// Fill out and submit a form
await page.fill("#username", "testuser");
await page.fill("#password", "password123");
await page.click('button[type="submit"]');
await page.waitForURL("**/dashboard");

// Capture a screenshot for debugging
await page.screenshot({ path: "debug.png", fullPage: true });
```

## Common Patterns

```javascript
// Wait for Element
await page.waitForSelector("#element-id", { state: "visible" });

// Check if Element Exists
const exists = (await page.locator("#element-id").count()) > 0;

// Get Console Logs
page.on("console", (msg) => console.log("Browser log:", msg.text()));

// Handle Errors
try {
  await page.click("#button");
} catch (error) {
  await page.screenshot({ path: "error.png" });
  throw error;
}
```

## Guidelines

1. **Always verify the app is running** — Check that the local server is accessible before running tests
2. **Use explicit waits** — Wait for elements or navigation to complete before interacting
3. **Capture screenshots on failure** — Take screenshots to help debug issues
4. **Clean up resources** — Always close the browser when done
5. **Use selectors wisely** — Prefer `data-testid` or role-based selectors over CSS classes
6. **Test incrementally** — Start with simple interactions before complex flows
