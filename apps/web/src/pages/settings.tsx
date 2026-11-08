import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { Async, Avatar, Badge, Button, Card, ConfirmDialog, EmptyState, humanize, Input, PageHeader, Select, Textarea } from "@/components/ui";
import { useAction, useEventId, useGet } from "@/hooks/useApi";
import { applyLang, getLang, type Lang } from "@/i18n";
import { useAuth } from "@/lib/auth";
import { toIso, toLocalInput } from "@/lib/dates";
import type { EventDetail, Member } from "@/lib/types";
import { EVENT_TYPES } from "./events";

const EVENT_STATUSES = ["draft", "registration_open", "registration_closed", "in_progress", "completed", "cancelled"];

function EventForm({ event }: { event: EventDetail }) {
  const save = useAction("Event saved");
  const form = useForm({
    defaultValues: {
      name: event.name, description: event.description, event_type: event.event_type, location: event.location, timezone: event.timezone,
      start_at: toLocalInput(event.start_at), end_at: toLocalInput(event.end_at), capacity: event.capacity?.toString() ?? "",
    },
  });
  return (
    <form className="space-y-4" onSubmit={form.handleSubmit((v) => save.mutate({
      path: `/api/events/${event.id}`, method: "PATCH", body: { ...v, start_at: toIso(v.start_at), end_at: toIso(v.end_at), capacity: v.capacity ? Number(v.capacity) : null },
    }))}>
      <Input label="Name" required {...form.register("name")} />
      <Select label="Type" {...form.register("event_type")}>{EVENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>
      <Textarea label="Description" {...form.register("description")} />
      <Input label="Location" {...form.register("location")} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Starts" type="datetime-local" required {...form.register("start_at")} />
        <Input label="Ends" type="datetime-local" required {...form.register("end_at")} />
        <Input label="Time zone" {...form.register("timezone")} />
        <Input label="Capacity" type="number" min={1} {...form.register("capacity")} />
      </div>
      <Button type="submit" loading={save.isPending}>Save changes</Button>
    </form>
  );
}

export function EventSettings() {
  const id = useEventId();
  const navigate = useNavigate();
  const event = useGet<EventDetail>(`/api/events/${id}`);
  const members = useGet<Member[]>(`/api/events/${id}/members`);
  const update = useAction("Updated");
  const invite = useAction("Co-organizer added");
  const remove = useAction("Access removed");
  const archive = useAction("Event archived");
  const [email, setEmail] = useState("");
  const [archiving, setArchiving] = useState(false);
  const patch = (body: object) => update.mutate({ path: `/api/events/${id}`, method: "PATCH", body });
  return (
    <Async query={event}>
      {(e) => {
        const link = `${window.location.origin}/e/${e.slug}`;
        const open = e.registration_status === "open";
        return (
          <div className="max-w-2xl space-y-6">
            <PageHeader title="Event settings" />
            <Card className="space-y-3 p-6">
              <h2 className="font-semibold">Registration</h2>
              <p className="text-sm break-all text-ink-soft">Public link: <a className="text-primary-strong underline" href={link}>{link}</a></p>
              <Button variant={open ? "secondary" : "primary"} loading={update.isPending}
                onClick={() => patch(open ? { registration_status: "closed", event_status: "registration_closed" } : { registration_status: "open", event_status: "registration_open" })}>
                {open ? "Close registration" : "Open registration"}
              </Button>
              <Select label="Event status" value={e.event_status} onChange={(ev) => patch({ event_status: ev.target.value })}>
                {EVENT_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
              </Select>
            </Card>
            <Card className="p-6"><h2 className="mb-4 font-semibold">Details</h2><EventForm key={e.id} event={e} /></Card>
            <Card className="p-6">
              <h2 className="font-semibold">Co-organizers</h2>
              <p className="mt-1 text-sm text-ink-soft">They need a GatherAI account. They can view this event, manage logistics, tasks and messages, and use the assistant. Only you can approve proposals.</p>
              <Async query={members}>
                {(rows) => rows.length ? (
                  <ul className="mt-4 divide-y divide-line">
                    {rows.map((m) => (
                      <li key={m.user_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                        <span className="flex items-center gap-2"><Avatar name={m.display_name} />{m.display_name}</span>
                        <Button size="sm" variant="ghost" onClick={() => remove.mutate({ path: `/api/events/${id}/members/${m.user_id}`, method: "DELETE" })}>Remove</Button>
                      </li>
                    ))}
                  </ul>
                ) : <EmptyState title="No co-organizers yet" />}
              </Async>
              <form className="mt-4 flex items-end gap-2" onSubmit={(ev) => { ev.preventDefault(); invite.mutate({ path: `/api/events/${id}/members`, body: { email } }, { onSuccess: () => setEmail("") }); }}>
                <div className="flex-1"><Input label="Add by email" type="email" required value={email} onChange={(ev) => setEmail(ev.target.value)} /></div>
                <Button type="submit" loading={invite.isPending}>Add</Button>
              </form>
            </Card>
            <Card className="p-6">
              <h2 className="font-semibold">Archive</h2>
              <p className="mt-1 text-sm text-ink-soft">Removes this event from your list and takes its public page offline.</p>
              <Button variant="secondary" className="mt-3" onClick={() => setArchiving(true)}>Archive event</Button>
            </Card>
            <ConfirmDialog open={archiving} onClose={() => setArchiving(false)} title="Archive this event?" description="Its public registration page will stop working." confirmLabel="Archive" danger
              onConfirm={() => archive.mutate({ path: `/api/events/${id}/archive` }, { onSuccess: () => navigate("/app") })} />
          </div>
        );
      }}
    </Async>
  );
}

export function Team() {
  const { me } = useAuth();
  const org = me?.organizations[0];
  const members = useGet<Member[]>(`/api/organizations/${org?.id}/members`, !!org);
  const add = useAction("Member added");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("organizer");
  return (
    <div className="max-w-2xl">
      <PageHeader title="Team" description={org?.name} />
      <Card className="p-6">
        <Async query={members}>
          {(rows) => (
            <ul className="divide-y divide-line">
              {rows.map((m) => (
                <li key={m.user_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="flex min-w-0 items-center gap-2"><Avatar name={m.display_name} /><span className="truncate">{m.display_name}</span></span>
                  <Badge>{humanize(m.role)}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Async>
        {org?.role === "organization_owner" && (
          <form className="mt-5 grid gap-3 sm:grid-cols-[1fr_10rem_auto] sm:items-end" onSubmit={(e) => { e.preventDefault(); add.mutate({ path: `/api/organizations/${org.id}/members`, body: { email, role } }, { onSuccess: () => setEmail("") }); }}>
            <Input label="Email of an existing account" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select label="Role" value={role} onChange={(e) => setRole(e.target.value)}><option value="organizer">Organizer</option><option value="co_organizer">Co-organizer</option></Select>
            <Button type="submit" loading={add.isPending}>Add</Button>
          </form>
        )}
      </Card>
    </div>
  );
}

export function AppSettings() {
  const { me, config } = useAuth();
  const [lang, setLang] = useState<Lang>(getLang());
  return (
    <div className="max-w-xl space-y-6">
      <PageHeader title="Settings" />
      <Card className="space-y-1 p-6 text-sm">
        <h2 className="mb-2 font-semibold">Account</h2>
        <p>{me?.display_name}</p>
        <p className="text-ink-soft">{me?.email}</p>
      </Card>
      <Card className="p-6">
        <h2 className="mb-3 font-semibold">Language</h2>
        <Select label="Display language" value={lang} onChange={(e) => { const next = e.target.value as Lang; setLang(next); applyLang(next); window.location.reload(); }}>
          <option value="en">English</option>
          <option value="he">עברית (navigation only, more coming)</option>
        </Select>
      </Card>
      <Card className="space-y-2 p-6 text-sm">
        <h2 className="font-semibold">Connections</h2>
        <p>Authentication: {config?.auth_mode === "local" ? "Local development" : "Supabase"}</p>
        <p>AI assistant: {config?.ai_live ? "Claude connected" : "Demo mode (no API key)"}</p>
        <p>WhatsApp: Simulator only</p>
      </Card>
    </div>
  );
}
