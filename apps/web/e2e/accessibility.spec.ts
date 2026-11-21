import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Automated WCAG 2.2 A/AA checks. Axe finds roughly a third of accessibility issues;
// keyboard and screen reader passes are still manual (see docs/TEST_PLAN.md).
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function audit(page: Page, label: string) {
  await page.waitForLoadState("networkidle");
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  const summary = violations.map((v) => `${label}: ${v.id} (${v.impact}) x${v.nodes.length}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
  expect(summary, summary.join("\n")).toEqual([]);
}

test("public pages meet automated WCAG AA checks", async ({ page }) => {
  for (const path of ["/", "/features", "/how-it-works", "/login", "/signup", "/privacy", "/terms"]) {
    await page.goto(path);
    await audit(page, path);
  }
});

test("organizer pages meet automated WCAG AA checks", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("demo@gatherai.example");
  await page.getByLabel("Password").fill("demo-organizer-2026");
  await page.getByRole("button", { name: "Log in" }).click();
  await audit(page, "/app");
  await page.getByRole("heading", { name: "Monsey Community Shabbat Weekend" }).click();
  await expect(page.getByText("Needs your attention")).toBeVisible();
  const base = new URL(page.url()).pathname;
  await audit(page, "overview");
  for (const path of ["participants", "transportation", "accommodations", "tasks", "messages", "assistant", "simulator", "settings"]) {
    await page.goto(`${base}/${path}`);
    await audit(page, path);
  }
  for (const path of ["/app/team", "/app/settings"]) {
    await page.goto(path);
    await audit(page, path);
  }
});

test("public registration page meets automated WCAG AA checks", async ({ page, request }) => {
  const login = await request.post("http://localhost:8000/api/auth/local/login", { data: { email: "demo@gatherai.example", password: "demo-organizer-2026" } });
  const token = (await login.json()).access_token;
  const events = await (await request.get("http://localhost:8000/api/events", { headers: { Authorization: `Bearer ${token}` } })).json();
  const items = Array.isArray(events) ? events : events.items;
  const slug = items.find((e: { slug?: string; name: string }) => e.name.startsWith("Monsey")).slug;
  await page.goto(`/e/${slug}`);
  await audit(page, "/e/:slug");
});
