import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { Async, EmptyState, ToastProvider, StatusBadge } from "./components/ui";
import { AuthProvider } from "./lib/auth";

function respond(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((path) => url.endsWith(path));
    return key ? new Response(JSON.stringify(routes[key]), { status: 200 }) : new Response(JSON.stringify({ detail: "Authentication required" }), { status: 401 });
  }));
}

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <AuthProvider><ToastProvider><App /></ToastProvider></AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

const config = { "/api/config": { auth_mode: "local", ai_live: false, environment: "development" } };
afterEach(() => vi.unstubAllGlobals());

describe("routing and auth", () => {
  it("renders the landing page", async () => {
    respond(config);
    renderApp("/");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Less organizing");
  });

  it("sends signed-out visitors from the dashboard to login", async () => {
    respond(config);
    renderApp("/app");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("shows validation errors on the login form", async () => {
    respond(config);
    renderApp("/login");
    await userEvent.click(await screen.findByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Enter a valid email")).toBeInTheDocument();
  });
});

describe("registration form", () => {
  const event = {
    "/api/public/events/test": {
      slug: "test", name: "Test Weekend", description: "", event_type: "retreat", location: "Town", timezone: "UTC", start_at: "2031-01-01T10:00:00Z",
      end_at: "2031-01-02T10:00:00Z", registration_open: true, availability: "open", transportation_enabled: true, accommodation_enabled: false,
    },
  };

  it("requires consent and hides disabled logistics", async () => {
    respond({ ...config, ...event });
    renderApp("/e/test");
    await userEvent.click(await screen.findByRole("button", { name: "Register" }));
    expect(await screen.findByText(/Please agree/)).toBeInTheDocument();
    expect(screen.queryByLabelText("I need a place to stay")).not.toBeInTheDocument();
  });

  it("reveals pickup only when a ride is needed", async () => {
    respond({ ...config, ...event });
    renderApp("/e/test");
    await userEvent.click(await screen.findByLabelText("I need a ride"));
    await waitFor(() => expect(screen.getByLabelText("Pickup location")).toBeInTheDocument());
  });
});

describe("shared states", () => {
  function Failing() {
    const query = useQuery({ queryKey: ["x"], queryFn: async (): Promise<string> => { throw new Error("Could not load"); }, retry: false });
    return <Async query={query}>{(data) => <p>{data}</p>}</Async>;
  }

  it("shows an error state with retry", async () => {
    render(<QueryClientProvider client={new QueryClient()}><Failing /></QueryClientProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<EmptyState title="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("states status in text, not color alone", () => {
    render(<StatusBadge status="driver_cancelled" />);
    expect(screen.getByText("Driver cancelled")).toBeInTheDocument();
  });
});
