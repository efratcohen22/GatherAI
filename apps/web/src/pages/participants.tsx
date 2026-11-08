import { zodResolver } from "@hookform/resolvers/zod";
import { Download, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";
import {
  Async, Avatar, Button, Card, Checkbox, ConfirmDialog, Dialog, Drawer, EmptyState, Input, PageHeader, Select, StatusBadge, Table, Tabs, useToast,
} from "@/components/ui";
import { useAction, useEventId, useGet } from "@/hooks/useApi";
import { downloadFile } from "@/lib/api";
import type { Participant, ParticipantPage, RequestItem } from "@/lib/types";

const STATUSES = ["pending", "confirmed", "waitlisted", "cancelled"];
type Filter = "all" | "confirmed" | "pending" | "waitlisted" | "cancelled" | "ride" | "stay";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" }, { value: "confirmed", label: "Confirmed" }, { value: "pending", label: "Pending" },
  { value: "waitlisted", label: "Waitlisted" }, { value: "cancelled", label: "Cancelled" }, { value: "ride", label: "Needs ride" }, { value: "stay", label: "Needs stay" },
];

const schema = z.object({
  name: z.string().min(1, "Enter a name"),
  email: z.union([z.literal(""), z.string().email("Enter a valid email")]),
  phone: z.string(),
  transportation_required: z.boolean(),
  pickup_location: z.string(),
  accommodation_required: z.boolean(),
});

function AddDialog({ open, onClose }: { open: boolean; onClose(): void }) {
  const id = useEventId();
  const add = useAction("Participant added");
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", phone: "", pickup_location: "", transportation_required: false, accommodation_required: false },
  });
  const { errors } = form.formState;
  return (
    <Dialog open={open} onClose={onClose} title="Add participant">
      <form noValidate className="space-y-4" onSubmit={form.handleSubmit((v) => add.mutate(
        { path: `/api/events/${id}/participants`, body: { ...v, email: v.email || null, phone: v.phone || null, pickup_location: v.pickup_location || null } },
        { onSuccess: () => { form.reset(); onClose(); } },
      ))}>
        <Input label="Name" error={errors.name?.message} {...form.register("name")} />
        <Input label="Email" type="email" error={errors.email?.message} {...form.register("email")} />
        <Input label="Phone" {...form.register("phone")} />
        <Checkbox label="Needs a ride" {...form.register("transportation_required")} />
        <Input label="Pickup location" {...form.register("pickup_location")} />
        <Checkbox label="Needs accommodation" {...form.register("accommodation_required")} />
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" loading={add.isPending}>Add</Button></div>
      </form>
    </Dialog>
  );
}

function Detail({ person, onClose }: { person: Participant; onClose(): void }) {
  const id = useEventId();
  const url = `/api/events/${id}/participants/${person.id}`;
  const requests = useGet<RequestItem[]>(`${url}/requests`);
  const update = useAction("Saved");
  const remove = useAction("Record deleted");
  const resolve = useAction("Request resolved");
  const [confirming, setConfirming] = useState(false);
  const facts: [string, string | null][] = [
    ["Email", person.email], ["Phone", person.phone], ["Pickup", person.pickup_location], ["Dietary", person.dietary_preferences], ["Organizer notes", person.notes],
  ];
  return (
    <div className="space-y-5">
      <Select label="Registration status" value={person.registration_status} disabled={update.isPending}
        onChange={(e) => update.mutate({ path: url, method: "PATCH", body: { registration_status: e.target.value } })}>
        {STATUSES.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
      </Select>
      <div className="flex flex-wrap gap-2">
        <StatusBadge status={person.ride_status} label={`Ride: ${person.ride_status.replace("_", " ")}`} />
        <StatusBadge status={person.stay_status} label={`Stay: ${person.stay_status.replace("_", " ")}`} />
      </div>
      <dl className="space-y-3 text-sm">
        {facts.map(([label, value]) => <div key={label}><dt className="text-xs text-ink-soft">{label}</dt><dd>{value || "Not provided"}</dd></div>)}
      </dl>
      <section>
        <h3 className="mb-2 text-sm font-semibold">Requests</h3>
        <Async query={requests}>
          {(items) => items.length ? (
            <ul className="space-y-2">
              {items.map((r) => (
                <li key={r.id} className="rounded-lg bg-muted p-3 text-sm">
                  <div className="flex items-center justify-between gap-2"><span className="font-medium capitalize">{r.request_type}</span><StatusBadge status={r.status} /></div>
                  <p className="mt-1 text-ink-soft">{r.request_details}</p>
                  {r.status === "open" && <Button size="sm" variant="secondary" className="mt-2" onClick={() => resolve.mutate({ path: `${url}/requests/${r.id}/resolve` })}>Mark resolved</Button>}
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-ink-soft">No requests.</p>}
        </Async>
      </section>
      <Button variant="ghost" className="text-danger-strong" onClick={() => setConfirming(true)}>Delete this record</Button>
      <ConfirmDialog open={confirming} onClose={() => setConfirming(false)} danger confirmLabel="Delete permanently" loading={remove.isPending}
        title={`Delete ${person.name}?`} description="This permanently removes their data and assignments. It cannot be undone."
        onConfirm={() => remove.mutate({ path: url, method: "DELETE" }, { onSuccess: onClose })} />
    </div>
  );
}

const outstandingLabel = (n: number) => (n ? `${n} open` : "None");

export function Participants() {
  const id = useEventId();
  const toast = useToast();
  const [params] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [adding, setAdding] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const query = new URLSearchParams({ page_size: "200" });
  if (search) query.set("search", search);
  if (filter === "ride" || filter === "stay") query.set("needs", filter);
  else if (filter !== "all") query.set("status", filter);
  const page = useGet<ParticipantPage>(`/api/events/${id}/participants?${query}`);
  const selected = page.data?.items.find((p) => p.id === selectedId) ?? null;

  return (
    <>
      <PageHeader title="Participants" actions={<>
        <Button variant="secondary" onClick={() => downloadFile(`/api/events/${id}/participants/export.csv`, "participants.csv").catch((e: Error) => toast("error", e.message))}>
          <Download className="size-4" aria-hidden />Export CSV
        </Button>
        <Button onClick={() => setAdding(true)}><Plus className="size-4" aria-hidden />Add</Button>
      </>} />
      <Card>
        <div className="space-y-3 border-b border-line p-4">
          <Tabs value={filter} onChange={setFilter} options={FILTERS} />
          <input aria-label="Filter by name or email" placeholder="Filter by name or email" value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 w-full max-w-xs rounded-lg border border-line px-3 text-sm" />
        </div>
        <Async query={page}>
          {({ items }) => items.length ? (
            <Table headers={["Name", "Registration", "Ride", "Accommodation", "Outstanding", ""]}>
              {items.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-2.5"><span className="flex items-center gap-2.5 whitespace-nowrap"><Avatar name={p.name} />{p.name}</span></td>
                  <td className="px-4 py-2.5"><StatusBadge status={p.registration_status} /></td>
                  <td className="px-4 py-2.5"><StatusBadge status={p.ride_status} /></td>
                  <td className="px-4 py-2.5"><StatusBadge status={p.stay_status} /></td>
                  <td className="px-4 py-2.5 whitespace-nowrap text-ink-soft">{outstandingLabel(p.open_requests)}</td>
                  <td className="px-4 py-2.5 text-end"><Button size="sm" variant="ghost" aria-label={`View ${p.name}`} onClick={() => setSelectedId(p.id)}>View</Button></td>
                </tr>
              ))}
            </Table>
          ) : <EmptyState title="No participants match" description="Share your registration link or add someone manually." />}
        </Async>
      </Card>
      <AddDialog open={adding} onClose={() => setAdding(false)} />
      <Drawer open={!!selected} onClose={() => setSelectedId(null)} title={selected?.name ?? ""}>
        {selected && <Detail key={selected.id} person={selected} onClose={() => setSelectedId(null)} />}
      </Drawer>
    </>
  );
}
