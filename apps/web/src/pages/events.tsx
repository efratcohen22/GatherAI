import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, ArrowRight, CalendarDays, Info, MapPin, Plus, Siren } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Async, Button, buttonClass, Card, Checkbox, EmptyState, Input, PageHeader, Select, StatusBadge, Textarea, humanize } from "@/components/ui";
import { useAction, useEventId, useGet } from "@/hooks/useApi";
import { formatDate, toIso } from "@/lib/dates";
import type { Activity, Alert, EventDetail, EventItem, Overview, Task } from "@/lib/types";

export const EVENT_TYPES = ["community_gathering", "shabbat_weekend", "retreat", "group_trip", "conference", "workshop", "private_event", "custom"];

export function Home() {
  const events = useGet<EventItem[]>("/api/events");
  return (
    <>
      <PageHeader title="Your events" actions={<Link to="/app/events/new" className={buttonClass()}><Plus className="size-4" aria-hidden />New event</Link>} />
      <Async query={events}>
        {(items) => items.length === 0 ? (
          <Card><EmptyState title="No events yet" description="Create your first event to start collecting registrations." action={<Link to="/app/events/new" className={buttonClass()}>Create an event</Link>} /></Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {items.map((e) => (
              <Link key={e.id} to={`/app/events/${e.id}`} className="block rounded-xl">
                <Card className="p-5 transition-colors hover:border-primary">
                  <div className="flex items-start justify-between gap-3"><h2 className="font-semibold">{e.name}</h2><StatusBadge status={e.event_status} /></div>
                  <p className="mt-3 flex items-center gap-2 text-sm text-ink-soft"><CalendarDays className="size-4" aria-hidden />{formatDate(e.start_at)}</p>
                  {e.location && <p className="mt-1 flex items-center gap-2 text-sm text-ink-soft"><MapPin className="size-4" aria-hidden />{e.location}</p>}
                </Card>
              </Link>
            ))}
          </div>
        )}
      </Async>
    </>
  );
}

const eventSchema = z.object({
  name: z.string().min(1, "Give your event a name"),
  event_type: z.string(),
  description: z.string().optional(),
  location: z.string().optional(),
  timezone: z.string().min(1),
  start_at: z.string().min(1, "Choose a start"),
  end_at: z.string().min(1, "Choose an end"),
  capacity: z.string().regex(/^\d*$/, "Use a whole number").optional(),
  transportation_enabled: z.boolean(),
  accommodation_enabled: z.boolean(),
}).refine((v) => !v.start_at || !v.end_at || v.end_at >= v.start_at, { path: ["end_at"], message: "End must be after start" });

export function NewEvent() {
  const navigate = useNavigate();
  const create = useAction<EventItem>("Event created");
  const form = useForm<z.infer<typeof eventSchema>>({
    resolver: zodResolver(eventSchema),
    defaultValues: { event_type: "community_gathering", timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, transportation_enabled: true, accommodation_enabled: true },
  });
  const { errors } = form.formState;
  return (
    <div className="max-w-xl">
      <PageHeader title="New event" />
      <Card className="p-6">
        <form noValidate className="space-y-4" onSubmit={form.handleSubmit((v) => create.mutate(
          { path: "/api/events", body: { ...v, description: v.description ?? "", location: v.location ?? "", start_at: toIso(v.start_at), end_at: toIso(v.end_at), capacity: v.capacity ? Number(v.capacity) : null } },
          { onSuccess: (event) => navigate(`/app/events/${event.id}`) },
        ))}>
          <Input label="Event name" error={errors.name?.message} {...form.register("name")} />
          <Select label="Event type" {...form.register("event_type")}>{EVENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>
          <Textarea label="Description" {...form.register("description")} />
          <Input label="Location" {...form.register("location")} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Starts" type="datetime-local" error={errors.start_at?.message} {...form.register("start_at")} />
            <Input label="Ends" type="datetime-local" error={errors.end_at?.message} {...form.register("end_at")} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Time zone" {...form.register("timezone")} />
            <Input label="Capacity" inputMode="numeric" hint="Leave empty for no limit" error={errors.capacity?.message} {...form.register("capacity")} />
          </div>
          <Checkbox label="This event coordinates rides" {...form.register("transportation_enabled")} />
          <Checkbox label="This event coordinates accommodation" {...form.register("accommodation_enabled")} />
          <Button type="submit" loading={create.isPending}>Create event</Button>
        </form>
      </Card>
    </div>
  );
}

const ALERT_STYLE = {
  critical: { Icon: Siren, color: "text-danger-strong", label: "Urgent" },
  warning: { Icon: AlertTriangle, color: "text-warning-ink", label: "Needs action" },
  info: { Icon: Info, color: "text-primary-strong", label: "Note" },
};

function AlertRow({ alert }: { alert: Alert }) {
  const { Icon, color, label } = ALERT_STYLE[alert.severity];
  return (
    <li>
      <Link to={alert.link} className="flex items-center gap-3 px-5 py-3 hover:bg-muted">
        <Icon className={`size-4 shrink-0 ${color}`} aria-hidden />
        <span className="flex-1 text-sm"><span className="sr-only">{label}: </span>{alert.title}</span>
        <ArrowRight className="size-4 text-ink-soft rtl:rotate-180" aria-hidden />
      </Link>
    </li>
  );
}

function Stat({ label, value, sub }: { label: string; value: number | string | null; sub?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-ink-soft">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value ?? "No limit"}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-soft">{sub}</p>}
    </Card>
  );
}

export function EventOverview() {
  const id = useEventId();
  const event = useGet<EventDetail>(`/api/events/${id}`);
  const overview = useGet<Overview>(`/api/events/${id}/overview`);
  const tasks = useGet<Task[]>(`/api/events/${id}/tasks`);
  const activity = useGet<Activity[]>(`/api/events/${id}/activity?limit=6`);
  return (
    <Async query={event}>
      {(e) => (
        <>
          <PageHeader title={e.name} description={`${formatDate(e.start_at)}${e.location ? ` · ${e.location}` : ""}`}
            actions={<><StatusBadge status={e.event_status} /><Link to={`/app/events/${id}/assistant`} className={buttonClass({ size: "sm" })}>Ask the assistant</Link></>} />
          <Async query={overview}>
            {({ metrics: m, alerts }) => (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <Stat label="Total participants" value={m.total_participants} sub={`${m.confirmed} confirmed`} />
                  <Stat label="Pending" value={m.pending} sub={`${m.waitlisted} waitlisted`} />
                  <Stat label="Spots available" value={m.available_capacity} />
                  <Stat label="Pending AI proposals" value={m.pending_proposals} />
                  {e.transportation_enabled && <Stat label="Without rides" value={m.without_rides} sub={`of ${m.requesting_rides} requested`} />}
                  {e.accommodation_enabled && <Stat label="Without accommodation" value={m.without_accommodation} sub={`of ${m.requesting_accommodation} requested`} />}
                  <Stat label="Open tasks" value={m.open_tasks} />
                </div>
                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <h2 className="border-b border-line px-5 py-3 font-semibold">Needs your attention</h2>
                    {alerts.length ? <ul className="divide-y divide-line">{alerts.map((a) => <AlertRow key={a.code} alert={a} />)}</ul> : <EmptyState title="All clear" description="Nothing needs attention right now." />}
                  </Card>
                  <Card>
                    <h2 className="border-b border-line px-5 py-3 font-semibold">Upcoming tasks</h2>
                    <Async query={tasks}>
                      {(items) => {
                        const open = items.filter((t) => t.status !== "completed").slice(0, 5);
                        return open.length ? (
                          <ul className="divide-y divide-line">
                            {open.map((t) => <li key={t.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm"><span>{t.title}</span><StatusBadge status={t.priority} /></li>)}
                          </ul>
                        ) : <EmptyState title="No open tasks" />;
                      }}
                    </Async>
                  </Card>
                </div>
                <Card>
                  <h2 className="border-b border-line px-5 py-3 font-semibold">Recent activity</h2>
                  <Async query={activity}>
                    {(rows) => rows.length ? (
                      <ul className="divide-y divide-line">
                        {rows.map((a) => <li key={a.id} className="flex justify-between gap-3 px-5 py-2.5 text-sm"><span>{humanize(a.action.replace(".", " "))}</span><span className="text-ink-soft">{formatDate(a.created_at)}</span></li>)}
                      </ul>
                    ) : <EmptyState title="No activity yet" />}
                  </Async>
                </Card>
              </div>
            )}
          </Async>
        </>
      )}
    </Async>
  );
}
