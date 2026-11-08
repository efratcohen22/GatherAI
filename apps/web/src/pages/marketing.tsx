import { ArrowRight, BedDouble, Bot, Car, CheckCircle2, ClipboardList, MessageCircle, ShieldCheck, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Badge, buttonClass, Card } from "@/components/ui";

function ProposalPreview() {
  const moves = [["Dov Klein", "Yoni Sasson, Crown Heights"], ["Michal Peretz", "Dina Halpern, Flatbush"]];
  return (
    <Card className="p-5 shadow-sm">
      <p className="text-xs text-ink-soft">Organizer</p>
      <p className="mt-1 text-sm">One of our drivers just cancelled. Can you reorganize the rides?</p>
      <div className="mt-4 rounded-lg bg-canvas p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium">Reassign rides after Noa cancelled</p>
          <Badge tone="warning">Awaiting approval</Badge>
        </div>
        <ul className="mt-3 space-y-2 text-sm">
          {moves.map(([person, ride]) => (
            <li key={person} className="flex items-center gap-2"><span>{person}</span><ArrowRight className="size-3.5 text-ink-soft" aria-label="to" /><span className="text-ink-soft">{ride}</span></li>
          ))}
          <li className="text-danger-strong">Asher Green: no compatible seat is available.</li>
        </ul>
        <div className="mt-4 flex gap-2" aria-hidden>
          <span className={buttonClass({ size: "sm" })}>Approve</span>
          <span className={buttonClass({ size: "sm", variant: "secondary" })}>Reject</span>
        </div>
      </div>
      <p className="mt-3 text-xs text-ink-soft">Illustration with fictional people.</p>
    </Card>
  );
}

const FEATURES: [typeof Car, string, string][] = [
  [Users, "Registration without accounts", "Share one link. Capacity, waitlists and duplicates are handled for you."],
  [Car, "Rides that add up", "See seats and shortages at a glance. Assignments can never exceed a vehicle's capacity."],
  [BedDouble, "Hosts and beds", "Match guests to hosts, respect restrictions, and keep host details private."],
  [ClipboardList, "Tasks in one place", "Priorities, owners and due dates, next to the logistics they belong to."],
  [Bot, "An assistant that reads your event", "Ask in plain language. Answers come from your live data."],
  [ShieldCheck, "Nothing changes without you", "The AI proposes. You approve. GatherAI checks again, then applies it and logs it."],
];

export function Landing() {
  return (
    <>
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 md:grid-cols-2 md:py-24">
        <div>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight md:text-5xl">Less organizing.<br />More gathering.</h1>
          <p className="mt-5 max-w-md text-lg text-ink-soft">
            GatherAI keeps registrations, rides, hosts and tasks in one place. When plans change, its assistant works out a fix and waits for your approval.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/signup" className={buttonClass({ size: "lg" })}>Create your first event</Link>
            <Link to="/how-it-works" className={buttonClass({ size: "lg", variant: "secondary" })}>See how it works</Link>
          </div>
        </div>
        <ProposalPreview />
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-2xl font-semibold tracking-tight">Replace the group chat and the five spreadsheets</h2>
          <div className="mt-8 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(([Glyph, title, text]) => (
              <div key={title}><Glyph className="size-5 text-primary-strong" aria-hidden /><h3 className="mt-3 font-medium">{title}</h3><p className="mt-1 text-sm text-ink-soft">{text}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-2xl font-semibold tracking-tight">Built for gatherings of 20 to 100 people</h2>
        <p className="mt-3 max-w-xl text-ink-soft">Community weekends, retreats, group trips, workshops, conferences and private events. Turn rides and accommodation on only when you need them.</p>
        <h2 className="mt-14 text-2xl font-semibold tracking-tight">Questions</h2>
        <dl className="mt-6 grid gap-6 md:grid-cols-2">
          {[
            ["Can the AI change my event by itself?", "No. It creates proposals. Rides, hosts and tasks change only after a person on your team approves."],
            ["Do participants need an account?", "No. They register through a link and receive a private link to update or cancel."],
            ["Does it send WhatsApp messages?", "Not yet. Today there is a clearly labeled simulator. Official WhatsApp Business support is planned."],
            ["Can co-organizers help?", "Yes. Invite them to a specific event with only the permissions they need."],
          ].map(([q, a]) => <div key={q}><dt className="font-medium">{q}</dt><dd className="mt-1 text-sm text-ink-soft">{a}</dd></div>)}
        </dl>
      </section>
    </>
  );
}

function Prose({ title, children }: { title: string; children: ReactNode }) {
  return <article className="mx-auto max-w-2xl space-y-4 px-4 py-16 text-ink-soft"><h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>{children}</article>;
}

export function Features() {
  return (
    <Prose title="Features">
      {FEATURES.map(([, title, text]) => <p key={title}><strong className="text-ink">{title}.</strong> {text}</p>)}
      <p><strong className="text-ink"><MessageCircle className="me-1 inline size-4" aria-hidden />Conversational registration.</strong> Participants can register and request rides by chat, shown today in a labeled simulator.</p>
    </Prose>
  );
}

export function HowItWorks() {
  const steps = [
    ["Create your event", "Set dates, capacity, and whether you need rides or accommodation."],
    ["Share the registration link", "Answers go straight into your dashboard."],
    ["Add drivers and hosts", "GatherAI tracks every seat and bed and shows what is missing."],
    ["Ask the assistant", "When something changes, describe it. You get a checked plan and a list of anything it couldn't solve."],
    ["Approve", "GatherAI rechecks current data, applies the change, logs it, and drafts messages for you to review."],
  ];
  return (
    <Prose title="How it works">
      <ol className="space-y-5">
        {steps.map(([title, text], i) => (
          <li key={title} className="flex gap-3"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-primary-strong" aria-hidden /><div><p className="font-medium text-ink">{i + 1}. {title}</p><p className="text-sm">{text}</p></div></li>
        ))}
      </ol>
    </Prose>
  );
}

export function Privacy() {
  return (
    <Prose title="Privacy">
      <p>Draft for the pre-release product; it needs legal review before public launch.</p>
      <p>GatherAI stores what organizers and participants enter to run an event: names, contact details, and logistics preferences. Organizers can permanently delete a participant's record.</p>
      <p>When the AI assistant is enabled, relevant event data is sent to Anthropic to generate responses. Product analytics count actions and contain no personal details.</p>
    </Prose>
  );
}

export function Terms() {
  return (
    <Prose title="Terms">
      <p>Draft for the pre-release product; it needs legal review before public launch.</p>
      <p>Organizers are responsible for having permission to collect participant information and for reviewing AI proposals before approving them.</p>
    </Prose>
  );
}
