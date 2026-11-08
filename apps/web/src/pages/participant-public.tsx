import { useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarDays, CheckCircle2, MapPin } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";
import { Async, Badge, Button, Card, Checkbox, ConfirmDialog, Input, StatusBadge } from "@/components/ui";
import { Logo } from "@/layouts/layouts";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/dates";
import type { ManagedRegistration, PublicEvent } from "@/lib/types";

function Frame({ children }: { children: ReactNode }) {
  return <div className="mx-auto min-h-screen max-w-lg px-4 py-8"><div className="mb-6"><Logo /></div>{children}</div>;
}

const schema = z.object({
  name: z.string().min(1, "Please enter your name"),
  email: z.string().email("Please enter a valid email"),
  phone: z.string().optional(),
  transportation_required: z.boolean(),
  pickup_location: z.string().optional(),
  accommodation_required: z.boolean(),
  dietary_preferences: z.string().optional(),
  consent: z.boolean().refine(Boolean, "Please agree so we can process your registration"),
  website: z.string().optional(),
});

export function Register() {
  const slug = useParams().slug as string;
  const event = useQuery({ queryKey: ["public", slug], queryFn: () => api<PublicEvent>(`/api/public/events/${slug}`), retry: false });
  const [done, setDone] = useState<{ registration_status: string; manage_token: string } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { transportation_required: false, accommodation_required: false, consent: false, website: "" } });
  const { errors, isSubmitting } = form.formState;
  const needsRide = form.watch("transportation_required");

  return (
    <Frame>
      <Async query={event}>
        {(e) => done ? (
          <Card className="p-6 text-center">
            <CheckCircle2 className="mx-auto size-10 text-success" aria-hidden />
            <h1 className="mt-3 text-xl font-semibold">{done.registration_status === "waitlisted" ? "You're on the waitlist" : "Registration received"}</h1>
            <p className="mt-2 text-sm text-ink-soft">An organizer will review it. Rides and accommodation are requests until an organizer confirms them.</p>
            <Link to={`/r/${done.manage_token}`} className="mt-4 inline-block text-sm font-medium text-primary-strong underline">Save this private link to update or cancel</Link>
          </Card>
        ) : (
          <>
            <h1 className="text-2xl font-semibold tracking-tight">{e.name}</h1>
            <p className="mt-2 flex items-center gap-2 text-sm text-ink-soft"><CalendarDays className="size-4" aria-hidden />{formatDate(e.start_at, e.timezone)}</p>
            {e.location && <p className="mt-1 flex items-center gap-2 text-sm text-ink-soft"><MapPin className="size-4" aria-hidden />{e.location}</p>}
            {e.description && <p className="mt-3 text-sm">{e.description}</p>}
            {e.availability === "limited" && <div className="mt-3"><Badge tone="warning">Few places left</Badge></div>}
            {e.availability === "full" && <div className="mt-3"><Badge tone="violet">Full: new registrations join the waitlist</Badge></div>}
            {!e.registration_open ? <Card className="mt-6 p-6 text-center text-sm">Registration is not open right now.</Card> : (
              <Card className="mt-6 p-6">
                <form noValidate className="space-y-4" onSubmit={form.handleSubmit(async (v) => {
                  setFailure(null);
                  try {
                    setDone(await api(`/api/public/events/${slug}/register`, "POST", {
                      ...v, phone: v.phone || null, pickup_location: v.pickup_location || null, dietary_preferences: v.dietary_preferences || null, website: v.website ?? "",
                    }));
                  } catch (err) { setFailure((err as Error).message); }
                })}>
                  <Input label="Full name" autoComplete="name" error={errors.name?.message} {...form.register("name")} />
                  <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...form.register("email")} />
                  <Input label="Phone (optional)" type="tel" autoComplete="tel" {...form.register("phone")} />
                  {e.transportation_enabled && <Checkbox label="I need a ride" {...form.register("transportation_required")} />}
                  {e.transportation_enabled && needsRide && <Input label="Pickup location" {...form.register("pickup_location")} />}
                  {e.accommodation_enabled && <Checkbox label="I need a place to stay" {...form.register("accommodation_required")} />}
                  <Input label="Dietary needs (optional)" {...form.register("dietary_preferences")} />
                  <div aria-hidden className="absolute -start-[9999px]"><label>Website<input tabIndex={-1} autoComplete="off" {...form.register("website")} /></label></div>
                  <Checkbox error={errors.consent?.message} label={<>The organizers may use these details to coordinate this event. See our <Link to="/privacy" className="underline">privacy notice</Link>.</>} {...form.register("consent")} />
                  {failure && <p role="alert" className="text-sm text-danger-strong">{failure}</p>}
                  <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Register</Button>
                </form>
              </Card>
            )}
          </>
        )}
      </Async>
    </Frame>
  );
}

export function ManageRegistration() {
  const token = useParams().token as string;
  const url = `/api/public/registrations/${token}`;
  const query = useQuery({ queryKey: ["manage", token], queryFn: () => api<ManagedRegistration>(url), retry: false });
  const [confirming, setConfirming] = useState(false);
  const [pickup, setPickup] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const update = async (body: object, message: string) => {
    try { await api(url, "PATCH", body); await query.refetch(); setNotice(message); } catch (e) { setNotice((e as Error).message); }
  };
  return (
    <Frame>
      <Async query={query}>
        {(r) => {
          const cancelled = r.registration_status === "cancelled";
          return (
            <Card className="space-y-4 p-6">
              <div><h1 className="text-xl font-semibold">{r.event_name}</h1><p className="text-sm text-ink-soft">{r.name}</p></div>
              <StatusBadge status={r.registration_status} />
              {!cancelled && (
                <>
                  <Checkbox label="I need a ride" checked={r.transportation_required} onChange={(e) => update({ transportation_required: e.target.checked }, "Updated")} />
                  <Input label="Pickup location" value={pickup ?? r.pickup_location ?? ""} onChange={(e) => setPickup(e.target.value)} onBlur={() => pickup !== null && update({ pickup_location: pickup }, "Pickup updated")} />
                  <Checkbox label="I need a place to stay" checked={r.accommodation_required} onChange={(e) => update({ accommodation_required: e.target.checked }, "Updated")} />
                  {notice && <p role="status" className="text-sm text-success">{notice}</p>}
                  <Button variant="ghost" className="text-danger-strong" onClick={() => setConfirming(true)}>Cancel my registration</Button>
                </>
              )}
              <ConfirmDialog open={confirming} onClose={() => setConfirming(false)} danger confirmLabel="Yes, cancel" title="Cancel your registration?" description="Your place, ride and accommodation will be released."
                onConfirm={async () => { await api(`${url}/cancel`, "POST"); await query.refetch(); setConfirming(false); }} />
            </Card>
          );
        }}
      </Async>
    </Frame>
  );
}
