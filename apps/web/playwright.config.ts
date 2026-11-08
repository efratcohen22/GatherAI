import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60000,
  use: { baseURL: "http://localhost:5173", screenshot: "only-on-failure" },
});
