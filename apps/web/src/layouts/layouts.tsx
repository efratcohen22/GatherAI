import { BedDouble, Bot, CalendarDays, Car, CheckSquare, LayoutDashboard, LogOut, Mail, Menu, MessageCircle, Search, Settings, Users, UsersRound } from "lucide-react";
import { useState, type ComponentType } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useMatch, useNavigate } from "react-router-dom";
import { Avatar, Button, buttonClass, cn, Drawer, LoadingState, Select } from "@/components/ui";
import { useGet } from "@/hooks/useApi";
import { t } from "@/i18n";
import { useAuth } from "@/lib/auth";
import type { EventDetail, EventItem } from "@/lib/types";

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <span aria-hidden className="flex size-7 items-center justify-center rounded-lg bg-primary-strong">
        <span className="size-2 rounded-full bg-white" /><span className="-ms-0.5 size-2 rounded-full bg-lavender" />
      </span>
      GatherAI
    </Link>
  );
}

export function PublicLayout() {
  const { me } = useAuth();
  const links = [["/features", "Features"], ["/how-it-works", "How it works"]];
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-2 px-4">
          <Logo />
          <div className="flex items-center gap-1 sm:gap-2">
            {links.map(([to, label]) => <NavLink key={to} to={to} className="hidden rounded-lg px-3 py-2 text-sm text-ink-soft hover:text-ink sm:block">{label}</NavLink>)}
            {me ? <Link to="/app" className={buttonClass({ size: "sm" })}>Open app</Link> : (
              <>
                <Link to="/login" className={buttonClass({ variant: "ghost", size: "sm" })}>Log in</Link>
                <Link to="/signup" className={buttonClass({ size: "sm" })}>Get started</Link>
              </>
            )}
          </div>
        </nav>
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-8 text-sm text-ink-soft">
          <span>GatherAI. Less organizing. More gathering.</span>
          <span className="flex gap-4"><Link to="/privacy" className="hover:text-ink">Privacy</Link><Link to="/terms" className="hover:text-ink">Terms</Link></span>
        </div>
      </footer>
    </div>
  );
}

export function RequireAuth() {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="p-8"><LoadingState /></div>;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

type Icon = ComponentType<{ className?: string }>;
function Item({ to, icon: Glyph, label, end, onNavigate }: { to: string; icon: Icon; label: string; end?: boolean; onNavigate?(): void }) {
  return (
    <NavLink to={to} end={end} onClick={onNavigate}
      className={({ isActive }) => cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm", isActive ? "bg-lavender font-medium text-primary-strong" : "text-ink-soft hover:bg-muted hover:text-ink")}>
      <Glyph className="size-4" />{label}
    </NavLink>
  );
}

function Sidebar({ onNavigate }: { onNavigate?(): void }) {
  const match = useMatch("/app/events/:eventId/*");
  const raw = match?.params.eventId;
  const eventId = raw && raw !== "new" ? raw : undefined;
  const navigate = useNavigate();
  const events = useGet<EventItem[]>("/api/events");
  const event = useGet<EventDetail>(`/api/events/${eventId}`, !!eventId);
  const base = `/app/events/${eventId}`;
  return (
    <div className="flex h-full flex-col gap-5">
      <nav aria-label="Workspace" className="space-y-0.5">
        <Item to="/app" end icon={CalendarDays} label={t("events")} onNavigate={onNavigate} />
        <Item to="/app/team" icon={UsersRound} label={t("team")} onNavigate={onNavigate} />
        <Item to="/app/settings" icon={Settings} label={t("settings")} onNavigate={onNavigate} />
      </nav>
      {!!events.data?.length && (
        <div>
          <label htmlFor="event-switcher" className="mb-1.5 block px-1 text-xs font-medium text-ink-soft">Current event</label>
          <SelectEvent value={eventId ?? ""} events={events.data} onChange={(id) => { navigate(id ? `/app/events/${id}` : "/app"); onNavigate?.(); }} />
        </div>
      )}
      {eventId && (
        <nav aria-label="Event" className="space-y-0.5">
          <Item to={base} end icon={LayoutDashboard} label={t("overview")} onNavigate={onNavigate} />
          <Item to={`${base}/participants`} icon={Users} label={t("participants")} onNavigate={onNavigate} />
          {event.data?.transportation_enabled !== false && <Item to={`${base}/transportation`} icon={Car} label={t("transportation")} onNavigate={onNavigate} />}
          {event.data?.accommodation_enabled !== false && <Item to={`${base}/accommodations`} icon={BedDouble} label={t("accommodations")} onNavigate={onNavigate} />}
          <Item to={`${base}/tasks`} icon={CheckSquare} label={t("tasks")} onNavigate={onNavigate} />
          <Item to={`${base}/messages`} icon={Mail} label={t("messages")} onNavigate={onNavigate} />
          <Item to={`${base}/assistant`} icon={Bot} label={t("assistant")} onNavigate={onNavigate} />
          <Item to={`${base}/simulator`} icon={MessageCircle} label={t("simulator")} onNavigate={onNavigate} />
          <Item to={`${base}/settings`} icon={Settings} label={t("event_settings")} onNavigate={onNavigate} />
        </nav>
      )}
    </div>
  );
}

function SelectEvent({ value, events, onChange }: { value: string; events: EventItem[]; onChange(id: string): void }) {
  return (
    <Select id="event-switcher" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Current event">
      <option value="">Choose an event</option>
      {events.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
    </Select>
  );
}

export function AppLayout() {
  const { me, logout, config } = useAuth();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const match = useMatch("/app/events/:eventId/*");
  const eventId = match?.params.eventId && match.params.eventId !== "new" ? match.params.eventId : undefined;

  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col overflow-y-auto border-e border-line bg-surface p-4 md:flex">
        <div className="mb-6 px-1"><Logo /></div>
        <Sidebar />
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-line bg-surface px-4">
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu className="size-5" /></Button>
          {eventId ? (
            <form role="search" className="relative max-w-sm flex-1" onSubmit={(e) => { e.preventDefault(); navigate(`/app/events/${eventId}/participants?search=${encodeURIComponent(query)}`); }}>
              <Search aria-hidden className="absolute start-2.5 top-2.5 size-4 text-ink-soft" />
              <input aria-label="Search participants" placeholder="Search participants" value={query} onChange={(e) => setQuery(e.target.value)} className="h-9 w-full rounded-lg bg-muted ps-8 pe-3 text-sm" />
            </form>
          ) : <div className="flex-1" />}
          <div className="ms-auto flex items-center gap-2">
            {config?.auth_mode === "local" && <span className="hidden rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning-ink sm:inline">Local development</span>}
            <Avatar name={me?.display_name ?? "?"} />
            <span className="hidden text-sm lg:inline">{me?.display_name}</span>
            <Button variant="ghost" size="icon" aria-label="Log out" onClick={() => logout()}><LogOut className="size-4" /></Button>
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-4 md:p-8"><Outlet /></main>
      </div>
      <Drawer open={open} onClose={() => setOpen(false)} title="GatherAI" side="start"><Sidebar onNavigate={() => setOpen(false)} /></Drawer>
    </div>
  );
}
