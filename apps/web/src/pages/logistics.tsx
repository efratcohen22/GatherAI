import { CheckCircle2, Plus, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Async, Badge, Button, Card, Dialog, EmptyState, Input, PageHeader, Select, StatusBadge, Textarea } from "@/components/ui";
import { useAction, useEventId, useGet } from "@/hooks/useApi";
import { formatDate, toIso } from "@/lib/dates";
import type { Accommodations as StayData, ParticipantPage, PersonRef, Transportation as RideData, Waiting } from "@/lib/types";

function Occupants({ people, base, onConfirm }: { people: PersonRef[]; base: string; onConfirm(person: PersonRef): void }) {
  const remove = useAction("Assignment removed");
  if (!people.length) return <p className="mt-3 text-sm text-ink-soft">Nobody assigned yet.</p>;
  return (
    <ul className="mt-3 divide-y divide-line">
      {people.map((p) => (
        <li key={p.assignment_id} className="flex items-center justify-between gap-2 py-1.5 text-sm">
          <span className="flex min-w-0 items-center gap-2"><span className="truncate">{p.name}</span><StatusBadge status={p.status} /></span>
          <span className="flex shrink-0">
            {p.status !== "confirmed" && <Button size="icon" variant="ghost" aria-label={`Record confirmation for ${p.name}`} onClick={() => onConfirm(p)}><CheckCircle2 className="size-4" /></Button>}
            <Button size="icon" variant="ghost" aria-label={`Remove ${p.name}`} onClick={() => remove.mutate({ path: `${base}/${p.assignment_id}`, method: "DELETE" })}><Trash2 className="size-4" /></Button>
          </span>
        </li>
      ))}
    </ul>
  );
}

function ConfirmSource({ person, base, onClose }: { person: PersonRef | null; base: string; onClose(): void }) {
  const confirm = useAction("Confirmation recorded");
  const [source, setSource] = useState("");
  return (
    <Dialog open={!!person} onClose={onClose} title={`Confirm ${person?.name ?? ""}`} description="Only record this once the person has actually confirmed.">
      <form className="space-y-4" onSubmit={(e) => {
        e.preventDefault();
        confirm.mutate({ path: `${base}/${person!.assignment_id}/confirm`, body: { confirmation_source: source } }, { onSuccess: () => { setSource(""); onClose(); } });
      }}>
        <Input label="How was this confirmed?" placeholder="Phone call with participant" minLength={3} required value={source} onChange={(e) => setSource(e.target.value)} />
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" loading={confirm.isPending}>Save</Button></div>
      </form>
    </Dialog>
  );
}

function WaitingList({ people, options, assignPath, field, noun }: {
  people: Waiting[]; options: { id: string; label: string }[]; assignPath: string; field: string; noun: string;
}) {
  const assign = useAction("Assigned");
  return (
    <Card>
      <h2 className="border-b border-line px-5 py-3 font-semibold">Waiting for a {noun} ({people.length})</h2>
      {people.length ? (
        <ul className="divide-y divide-line">
          {people.map((p) => (
            <li key={p.participant_id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5 text-sm">
              <span>{p.name}{p.detail && <span className="text-ink-soft"> · {p.detail}</span>}{p.registration_status === "pending" && <> <StatusBadge status="pending" /></>}</span>
              <Select aria-label={`Assign ${p.name}`} className="h-8 w-44" value="" disabled={!options.length || assign.isPending}
                onChange={(e) => e.target.value && assign.mutate({ path: assignPath, body: { participant_id: p.participant_id, [field]: e.target.value } })}>
                <option value="">{options.length ? "Assign to..." : `No open ${noun}s`}</option>
                {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </Select>
            </li>
          ))}
        </ul>
      ) : <EmptyState title="Everyone is placed" />}
    </Card>
  );
}

function Summary({ open, label, shortage, waiting }: { open: number; label: string; shortage: number; waiting: number }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      <Badge tone="violet">{open} open {label}</Badge>
      <Badge>{waiting} waiting</Badge>
      {shortage > 0 && <Badge tone="danger">Short by {shortage}</Badge>}
    </div>
  );
}

function ResourceCard({ title, status, children }: { title: string; status: string; children: ReactNode }) {
  return <Card className={status === "active" ? "p-4" : "border-danger p-4"}><div className="flex items-start justify-between gap-2"><h3 className="font-medium">{title}</h3>{status !== "active" && <StatusBadge status={status} />}</div>{children}</Card>;
}

function AddVehicle({ open, onClose }: { open: boolean; onClose(): void }) {
  const id = useEventId();
  const add = useAction("Vehicle added");
  const people = useGet<ParticipantPage>(`/api/events/${id}/participants?page_size=200`, open);
  const form = useForm({ defaultValues: { driver_participant_id: "", available_passenger_seats: "3", departure_location: "", departure_at: "" } });
  return (
    <Dialog open={open} onClose={onClose} title="Add vehicle">
      <form className="space-y-4" onSubmit={form.handleSubmit((v) => add.mutate({ path: `/api/events/${id}/vehicles`, body: {
        driver_participant_id: v.driver_participant_id || null, available_passenger_seats: Number(v.available_passenger_seats),
        departure_location: v.departure_location, departure_at: v.departure_at ? toIso(v.departure_at) : null,
      } }, { onSuccess: () => { form.reset(); onClose(); } }))}>
        <Select label="Driver" {...form.register("driver_participant_id")}>
          <option value="">No driver yet</option>
          {people.data?.items.filter((p) => p.registration_status !== "cancelled").map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>
        <Input label="Passenger seats" type="number" min={0} max={100} required {...form.register("available_passenger_seats")} />
        <Input label="Pickup location" {...form.register("departure_location")} />
        <Input label="Departure" type="datetime-local" {...form.register("departure_at")} />
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" loading={add.isPending}>Add</Button></div>
      </form>
    </Dialog>
  );
}

export function Transportation() {
  const id = useEventId();
  const data = useGet<RideData>(`/api/events/${id}/transportation`);
  const [adding, setAdding] = useState(false);
  const [confirming, setConfirming] = useState<PersonRef | null>(null);
  const base = `/api/events/${id}/ride-assignments`;
  return (
    <>
      <PageHeader title="Transportation" actions={<Button onClick={() => setAdding(true)}><Plus className="size-4" aria-hidden />Add vehicle</Button>} />
      <Async query={data}>
        {(d) => (
          <>
            <Summary open={d.total_open_seats} label="seats" shortage={d.shortage} waiting={d.unassigned.length} />
            <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
              <div className="grid content-start gap-4 sm:grid-cols-2">
                {d.vehicles.length === 0 && <Card className="sm:col-span-2"><EmptyState title="No vehicles yet" description="Add your first driver." /></Card>}
                {d.vehicles.map((v) => (
                  <ResourceCard key={v.id} title={v.driver_name ?? "No driver"} status={v.status}>
                    <p className="mt-1 text-sm text-ink-soft">{v.departure_location || "Pickup not set"}{v.departure_at && ` · ${formatDate(v.departure_at)}`}</p>
                    <p className="mt-2 text-sm font-medium">{v.status === "active" ? `${v.seats_remaining} of ${v.available_passenger_seats} seats open` : "Not available"}</p>
                    {v.notes && <p className="mt-1 text-xs text-ink-soft">{v.notes}</p>}
                    <Occupants people={v.passengers} base={base} onConfirm={setConfirming} />
                  </ResourceCard>
                ))}
              </div>
              <WaitingList people={d.unassigned} assignPath={base} field="vehicle_id" noun="ride"
                options={d.vehicles.filter((v) => v.seats_remaining > 0).map((v) => ({ id: v.id, label: `${v.driver_name ?? "Vehicle"} (${v.seats_remaining})` }))} />
            </div>
          </>
        )}
      </Async>
      <AddVehicle open={adding} onClose={() => setAdding(false)} />
      <ConfirmSource person={confirming} base={base} onClose={() => setConfirming(null)} />
    </>
  );
}

function AddHost({ open, onClose }: { open: boolean; onClose(): void }) {
  const id = useEventId();
  const add = useAction("Host added");
  const form = useForm({ defaultValues: { host_name: "", host_contact: "", location: "", capacity: "2", restrictions: "" } });
  return (
    <Dialog open={open} onClose={onClose} title="Add host">
      <form className="space-y-4" onSubmit={form.handleSubmit((v) => add.mutate({ path: `/api/events/${id}/accommodations`, body: {
        ...v, capacity: Number(v.capacity), host_contact: v.host_contact || null, restrictions: v.restrictions || null,
      } }, { onSuccess: () => { form.reset(); onClose(); } }))}>
        <Input label="Host name" required {...form.register("host_name")} />
        <Input label="Private contact" hint="Visible only to people who manage logistics" {...form.register("host_contact")} />
        <Input label="Location" {...form.register("location")} />
        <Input label="Beds" type="number" min={0} required {...form.register("capacity")} />
        <Textarea label="Restrictions" {...form.register("restrictions")} />
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" loading={add.isPending}>Add</Button></div>
      </form>
    </Dialog>
  );
}

export function Accommodations() {
  const id = useEventId();
  const data = useGet<StayData>(`/api/events/${id}/accommodations`);
  const [adding, setAdding] = useState(false);
  const [confirming, setConfirming] = useState<PersonRef | null>(null);
  const base = `/api/events/${id}/accommodation-assignments`;
  return (
    <>
      <PageHeader title="Accommodations" actions={<Button onClick={() => setAdding(true)}><Plus className="size-4" aria-hidden />Add host</Button>} />
      <Async query={data}>
        {(d) => (
          <>
            <Summary open={d.total_open_beds} label="beds" shortage={d.shortage} waiting={d.unassigned.length} />
            <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
              <div className="grid content-start gap-4 sm:grid-cols-2">
                {d.accommodations.length === 0 && <Card className="sm:col-span-2"><EmptyState title="No hosts yet" /></Card>}
                {d.accommodations.map((a) => (
                  <ResourceCard key={a.id} title={a.host_name} status={a.status}>
                    <p className="mt-1 text-sm text-ink-soft">{a.location || "Location not set"}</p>
                    <p className="mt-2 text-sm font-medium">{a.beds_remaining} of {a.capacity} beds open</p>
                    {a.restrictions && <p className="mt-1 text-xs text-ink-soft">{a.restrictions}</p>}
                    {a.host_contact && <p className="mt-1 text-xs text-ink-soft">Contact: {a.host_contact}</p>}
                    <Occupants people={a.guests} base={base} onConfirm={setConfirming} />
                  </ResourceCard>
                ))}
              </div>
              <WaitingList people={d.unassigned} assignPath={base} field="accommodation_id" noun="host"
                options={d.accommodations.filter((a) => a.beds_remaining > 0).map((a) => ({ id: a.id, label: `${a.host_name} (${a.beds_remaining})` }))} />
            </div>
          </>
        )}
      </Async>
      <AddHost open={adding} onClose={() => setAdding(false)} />
      <ConfirmSource person={confirming} base={base} onClose={() => setConfirming(null)} />
    </>
  );
}
