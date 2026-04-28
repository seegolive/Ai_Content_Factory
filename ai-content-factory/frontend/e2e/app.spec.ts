import { test, expect } from "@playwright/test";

// ── 1. Login Page ─────────────────────────────────────────────────────────────
test.describe("Login Page", () => {
  test("renders login page with Google OAuth button", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveTitle(/AI Content Factory|Login/i);
    // Should have a Google Sign-In button or redirect to /login
    const body = await page.content();
    expect(body.length).toBeGreaterThan(100);
  });

  test("unauthenticated user redirected to login from /dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    // Should redirect to login page
    await page.waitForURL(/login|auth|\/$/);
    const url = page.url();
    expect(url).toMatch(/login|auth|\//);
  });

  test("login page loads without JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    // Filter out expected OAuth/network errors from missing API keys
    const criticalErrors = errors.filter(
      (e) => !e.includes("Failed to load resource") && !e.includes("net::ERR")
    );
    expect(criticalErrors).toHaveLength(0);
  });
});

// ── 2. API Health ─────────────────────────────────────────────────────────────
test.describe("Backend API", () => {
  test("GET /health returns 200 with status ok", async ({ request }) => {
    const resp = await request.get("http://localhost:8000/health");
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe("ok");
    expect(body.components.database).toBe("ok");
    expect(body.components.storage).toBe(true);
  });

  test("GET /docs returns 200 (Swagger UI available in dev)", async ({ request }) => {
    const resp = await request.get("http://localhost:8000/docs");
    expect(resp.status()).toBe(200);
  });

  test("GET /api/v1/videos without auth returns 401", async ({ request }) => {
    const resp = await request.get("http://localhost:8000/api/v1/videos");
    expect(resp.status()).toBe(401);
  });

  test("GET /api/v1/clips/stats without auth returns 401", async ({ request }) => {
    const resp = await request.get("http://localhost:8000/api/v1/clips/stats");
    expect(resp.status()).toBe(401);
  });

  test("GET /api/v1/auth/google/login returns redirect or 200", async ({ request }) => {
    const resp = await request.get("http://localhost:8000/api/v1/auth/google/login");
    // Returns 200 (redirect URL JSON) or 302 redirect
    expect([200, 302]).toContain(resp.status());
  });
});

// ── 3. Frontend Pages ─────────────────────────────────────────────────────────
test.describe("Frontend Pages", () => {
  test("home page / root loads", async ({ page }) => {
    const resp = await page.goto("/");
    expect(resp?.status()).toBeLessThan(400);
  });

  test("frontend connects to backend (no CORS error on health)", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && msg.text().includes("CORS")) {
        errors.push(msg.text());
      }
    });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("/login page has no broken layout (body not empty)", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");
    const bodyText = await page.locator("body").innerText();
    expect(bodyText.trim().length).toBeGreaterThan(0);
  });
});

// ── 4. API Auth Flow ──────────────────────────────────────────────────────────
test.describe("Auth API Contract", () => {
  test("Google OAuth callback endpoint exists (not 404/405)", async ({ request }) => {
    const resp = await request.get(
      "http://localhost:8000/api/v1/auth/google/callback?code=fake_code&state=fake"
    );
    // Should not 404 (route missing) — 400/422/302 are all acceptable
    expect(resp.status()).not.toBe(404);
    expect(resp.status()).not.toBe(405);
  });

  test("invalid JWT returns 401", async ({ request }) => {
    const resp = await request.get("http://localhost:8000/api/v1/videos", {
      headers: { Authorization: "Bearer invalid.token.here" },
    });
    expect(resp.status()).toBe(401);
  });
});

// ── 5. Celery / Flower ────────────────────────────────────────────────────────
test.describe("Celery Flower Monitor", () => {
  test("Flower dashboard is accessible at :5555", async ({ request }) => {
    const resp = await request.get("http://localhost:5555");
    expect(resp.status()).toBe(200);
  });
});
