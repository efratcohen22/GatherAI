import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";

const SHOTS = process.env.SHOT_DIR;
const shot = async (page: Page, name: string) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); };

function trackErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => { if (m.type() === "error" && !m.text().includes("fonts.g")) errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

test("organizer creates an event, a participant registers, the AI proposes, the organizer approves", async ({ page, browser }) => {
  const errors = trackErrors(page);
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Less organizing");
  await shot(page, "01-landing");

  await page.getByRole("link", { name: "Get started" }).click();
  await page.getByLabel("Your name").fill("E2E Organizer");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("No events yet")).toBeVisible();

  await page.getByRole("link", { name: "Create an event" }).click();
  await page.getByLabel("Event name").fill("E2E Retreat");
  await page.getByLabel("Starts").fill("2031-05-01T10:00");
  await page.getByLabel("Ends").fill("2031-05-02T10:00");
  await page.getByLabel("Capacity").fill("10");
  await page.getByRole("button", { name: "Create event" }).click();
  await expect(page.getByRole("heading", { name: "E2E Retreat" })).toBeVisible();
  const eventPath = new URL(page.url()).pathname;

  await page.goto(`${eventPath}/settings`);
  await page.getByRole("button", { name: "Open registration" }).click();
  await expect(page.getByRole("button", { name: "Close registration" })).toBeVisible();
  const publicLink = await page.locator("a[href*='/e/']").getAttribute("href");

  // Participant registers without an account, in a separate browser context.
  const visitor = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage();
  await visitor.goto(publicLink!);
  await visitor.getByLabel("Full name").fill("Rider Person");
  await visitor.getByLabel("Email").fill("rider@example.com");
  await visitor.getByLabel("I need a ride").check();
  await visitor.getByLabel("Pickup location").fill("North");
  await visitor.getByRole("checkbox", { name: /organizers may use/ }).check();
  await visitor.getByRole("button", { name: "Register" }).click();
  await expect(visitor.getByText("Registration received")).toBeVisible();

  await page.goto(`${eventPath}/participants`);
  await expect(page.getByText("Rider Person")).toBeVisible();

  await page.goto(`${eventPath}/transportation`);
  await page.getByRole("button", { name: "Add vehicle" }).click();
  await page.getByLabel("Pickup location").fill("North");
  await page.getByRole("dialog").getByRole("button", { name: "Add" }).click();
  await expect(page.getByText("3 of 3 seats open")).toBeVisible();

  await page.goto(`${eventPath}/assistant`);
  await page.getByLabel("Message the assistant").fill("Can you assign the waiting people to rides?");
  await page.getByRole("button", { name: "Send" }).click();
  const log = page.getByRole("log");
  await expect(log.getByText("Awaiting approval")).toBeVisible();
  await log.getByRole("button", { name: "Approve" }).click();
  await page.getByRole("button", { name: "Approve and apply" }).click();
  await expect(log.getByText("Executed")).toBeVisible();

  await page.goto(`${eventPath}/transportation`);
  await expect(page.getByText("2 of 3 seats open")).toBeVisible();
  await page.goto(`${eventPath}/messages`);
  await expect(page.getByText("To: Rider Person")).toBeVisible();
  expect(errors).toEqual([]);
});

test("demo walkthrough on the Monsey event", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill("demo@gatherai.example");
  await page.getByLabel("Password").fill("demo-organizer-2026");
  await page.getByRole("button", { name: "Log in" }).click();
  await page.getByRole("heading", { name: "Monsey Community Shabbat Weekend" }).click();
  await expect(page.getByText("Needs your attention")).toBeVisible();
  await expect(page.getByText("1 driver cancelled")).toBeVisible();
  await shot(page, "02-overview");
  const base = new URL(page.url()).pathname;
  for (const [path, heading] of [["participants", "Participants"], ["transportation", "Transportation"], ["accommodations", "Accommodations"], ["tasks", "Tasks"], ["messages", "Messages"], ["simulator", "Chat simulator"], ["settings", "Event settings"]]) {
    await page.goto(`${base}/${path}`);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await shot(page, `03-${path}`);
  }
  await page.goto(`${base}/assistant`);
  await page.getByRole("button", { name: /One of our drivers/ }).click();
  await expect(page.getByRole("log").getByText("Awaiting approval")).toBeVisible();
  await shot(page, "04-assistant");

  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(base);
  await page.waitForLoadState("networkidle");
  await shot(page, "05-mobile-overview");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("link", { name: "Transportation" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.goto(`${base}/participants`);
  await page.waitForLoadState("networkidle");
  await shot(page, "06-mobile-participants");
  expect(errors).toEqual([]);
});
