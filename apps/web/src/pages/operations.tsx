import { ArrowRight, Bot, Plus, Send, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Async, Badge, Button, Card, cn, ConfirmDialog, Dialog, EmptyState, humanize, Input, PageHeader, Select, StatusBadge, Tabs, Textarea, useToast } from "@/components/ui";
import { useAction, useEventId, useGet } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, toIso } from "@/lib/dates";
import type { ChatReply, EventDetail, Message, Proposal, SimConversation, Task } from "@/lib/types";

const TASK_STATUSES = ["todo", "in_progress", "blocked", "completed"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

export function Tasks() {
  const id = useEventId();
  const [filter, setFilter] = useState("open");
  const [adding, setAdding] = useState(false);
  const tasks = useGet<Task[]>(`/api/events/${id}/tasks`);
  const update = useAction();
  const add = useAction("Task added");
  const form = useForm({ defaultValues: { title: "", description: "", priority: "medium", due_at: "" } });
  return (
    <>
      <PageHeader title="Tasks" actions={<Button onClick={() => setAdding(true)}><Plus className="size-4" aria-hidden />New task</Button>} />
      <Card>
        <div className="border-b border-line p-4">
          <Tabs value={filter} onChange={setFilter} options={[{ value: "open", label: "Open" }, ...TASK_STATUSES.map((s) => ({ value: s, label: humanize(s) }))]} />
        </div>
        <Async query={tasks}>
          {(items) => {
            const shown = items.filter((t) => (filter === "open" ? t.status !== "completed" : t.status === filter));
            return shown.length ? (
              <ul className="divide-y divide-line">
                {shown.map((t) => (
                  <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <div className="min-w-48 flex-1">
                      <p className={cn("text-sm font-medium", t.status === "completed" && "text-ink-soft line-through")}>{t.title}</p>
                      {t.due_at && <p className="text-xs text-ink-soft">Due {formatDate(t.due_at)}</p>}
                    </div>
                    <StatusBadge status={t.priority} />
                    <Select aria-label={`Status of ${t.title}`} className="h-8 w-36" value={t.status}
                      onChange={(e) => update.mutate({ path: `/api/events/${id}/tasks/${t.id}`, method: "PATCH", body: { status: e.target.value } })}>
                      {TASK_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
                    </Select>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No tasks here" />;
          }}
        </Async>
      </Card>
      <Dialog open={adding} onClose={() => setAdding(false)} title="New task">
        <form className="space-y-4" onSubmit={form.handleSubmit((v) => add.mutate(
          { path: `/api/events/${id}/tasks`, body: { ...v, due_at: v.due_at ? toIso(v.due_at) : null } },
          { onSuccess: () => { form.reset(); setAdding(false); } },
        ))}>
          <Input label="Title" required {...form.register("title")} />
          <Textarea label="Description" {...form.register("description")} />
          <Select label="Priority" {...form.register("priority")}>{PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}</Select>
          <Input label="Due" type="datetime-local" {...form.register("due_at")} />
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setAdding(false)}>Cancel</Button><Button type="submit" loading={add.isPending}>Add</Button></div>
        </form>
      </Dialog>
    </>
  );
}

function DraftRow({ message }: { message: Message }) {
  const id = useEventId();
  const url = `/api/events/${id}/messages/${message.id}`;
  const send = useAction("Delivered to the simulator. No real message was sent.");
  const remove = useAction("Draft deleted");
  const save = useAction("Draft saved");
  const [text, setText] = useState(message.content);
  return (
    <li className="space-y-2 p-4">
      <p className="text-sm font-medium">To: {message.participant_name ?? "Everyone"}</p>
      <Textarea label="Message" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" loading={send.isPending} onClick={() => send.mutate({ path: `${url}/send` })}><Send className="size-3.5" aria-hidden />Send (simulated)</Button>
        {text !== message.content && <Button size="sm" variant="secondary" onClick={() => save.mutate({ path: url, method: "PATCH", body: { content: text } })}>Save edit</Button>}
        <Button size="sm" variant="ghost" onClick={() => remove.mutate({ path: url, method: "DELETE" })}>Delete</Button>
      </div>
    </li>
  );
}

export function Messages() {
  const id = useEventId();
  const messages = useGet<Message[]>(`/api/events/${id}/messages`);
  const [tab, setTab] = useState<"drafts" | "history">("drafts");
  return (
    <>
      <PageHeader title="Messages" description="Nothing leaves GatherAI yet. Sending delivers to the built-in simulator only." />
      <Card>
        <div className="border-b border-line p-4"><Tabs value={tab} onChange={setTab} options={[{ value: "drafts", label: "Drafts" }, { value: "history", label: "History" }]} /></div>
        <Async query={messages}>
          {(items) => {
            const drafts = items.filter((m) => m.status === "draft");
            const history = items.filter((m) => m.status !== "draft");
            if (tab === "drafts") return drafts.length ? <ul className="divide-y divide-line">{drafts.map((m) => <DraftRow key={m.id} message={m} />)}</ul> : <EmptyState title="No drafts" description="Ask the assistant to draft a reminder." />;
            return history.length ? (
              <ul className="divide-y divide-line">
                {history.map((m) => (
                  <li key={m.id} className="p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{m.direction === "inbound" ? "From" : "To"} {m.participant_name ?? "Everyone"}</span><StatusBadge status={m.status} /></div>
                    <p className="mt-1 text-ink-soft">{m.content}</p>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No history yet" />;
          }}
        </Async>
      </Card>
    </>
  );
}

function ProposalCard({ proposal, canApprove }: { proposal: Proposal; canApprove: boolean }) {
  const id = useEventId();
  const toast = useToast();
  const base = `/api/events/${id}/ai/proposals/${proposal.id}`;
  const act = useAction<Proposal>();
  const [confirming, setConfirming] = useState(false);
  const p = proposal.proposed_payload;
  const pending = proposal.approval_status === "pending";
  const approve = () => act.mutate({ path: `${base}/approve` }, {
    onSuccess: (r) => {
      setConfirming(false);
      if (r.approval_status === "executed") toast("success", "Approved and applied. Message drafts are ready.");
      else toast("error", r.failure_reason ?? `Proposal ${r.approval_status}. Nothing was changed.`);
    },
  });
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium">{proposal.summary}</p>
        <StatusBadge status={proposal.approval_status} label={pending ? "Awaiting approval" : undefined} />
      </div>
      {proposal.rationale && <p className="mt-1 text-xs text-ink-soft">{proposal.rationale}</p>}
      {!!p.assignments?.length && (
        <ul className="mt-3 space-y-1.5 text-sm">
          {p.assignments.map((a) => <li key={a.participant_name} className="flex flex-wrap items-center gap-1.5">{a.participant_name}<ArrowRight className="size-3.5 text-ink-soft rtl:rotate-180" aria-label="to" /><span className="text-ink-soft">{a.resource_label}</span></li>)}
        </ul>
      )}
      {!!p.tasks?.length && <ul className="mt-3 list-disc space-y-1 ps-5 text-sm">{p.tasks.map((t) => <li key={t.title}>{t.title}</li>)}</ul>}
      {!!p.unresolved?.length && (
        <div className="mt-3 rounded-lg bg-danger-soft p-3 text-sm text-danger-strong">
          <p className="font-medium">Not solved by this plan</p>
          <ul className="mt-1 space-y-0.5">{p.unresolved.map((u) => <li key={u.name}>{u.name}: {u.reason}</li>)}</ul>
        </div>
      )}
      {proposal.failure_reason && <p role="alert" className="mt-3 text-sm text-danger-strong">{proposal.failure_reason}</p>}
      {pending && canApprove && (
        <div className="mt-4 flex gap-2">
          <Button size="sm" onClick={() => setConfirming(true)}>Approve</Button>
          <Button size="sm" variant="secondary" loading={act.isPending} onClick={() => act.mutate({ path: `${base}/reject` })}>Reject</Button>
        </div>
      )}
      <ConfirmDialog open={confirming} onClose={() => setConfirming(false)} onConfirm={approve} loading={act.isPending} confirmLabel="Approve and apply"
        title="Apply this change?" description="GatherAI will recheck current data first. If anything has changed, nothing is applied." />
    </div>
  );
}

const PROMPTS = [
  "One of our drivers just cancelled. Can you reorganize the rides?",
  "How many participants still need rides?",
  "Summarize all unresolved issues.",
  "Draft a reminder for participants who have not confirmed.",
];
interface ChatLine { role: "user" | "assistant"; text: string; meta?: ChatReply }

export function Assistant() {
  const id = useEventId();
  const { config } = useAuth();
  const toast = useToast();
  const event = useGet<EventDetail>(`/api/events/${id}`);
  const proposals = useGet<Proposal[]>(`/api/events/${id}/ai/proposals`);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conversation = useRef<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const canApprove = !!event.data?.permissions.includes("approve_proposals");
  const action = useAction();

  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [lines, busy]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setLines((l) => [...l, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await api<ChatReply>(`/api/events/${id}/ai/chat`, "POST", { message: text, conversation_id: conversation.current });
      conversation.current = reply.conversation_id;
      setLines((l) => [...l, { role: "assistant", text: reply.reply.replace(/^\[Demo mode[^\]]*\]\s*/, ""), meta: reply }]);
      action.reset();
      proposals.refetch();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally { setBusy(false); }
  }

  const live = config?.ai_live;
  const inChat = new Set(lines.flatMap((l) => l.meta?.proposals.map((p) => p.id) ?? []));
  const pending = proposals.data?.filter((p) => p.approval_status === "pending" && !inChat.has(p.id)) ?? [];
  const byId = new Map(proposals.data?.map((p) => [p.id, p]));
  return (
    <>
      <PageHeader title="AI Assistant" actions={<Badge tone={live ? "success" : "warning"}>{live ? "Connected to Claude" : "Demo mode: rule-based, no AI model"}</Badge>} />
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Card className="flex h-[calc(100vh-13rem)] min-h-96 flex-col">
          <div role="log" aria-live="polite" className="flex-1 space-y-4 overflow-y-auto p-5">
            {lines.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot className="size-8 text-primary-strong" aria-hidden />
                <p className="mt-3 font-medium">Ask about this event</p>
                <div className="mt-4 flex max-w-lg flex-wrap justify-center gap-2">
                  {PROMPTS.map((p) => <button key={p} type="button" onClick={() => send(p)} className="cursor-pointer rounded-lg border border-line px-3 py-1.5 text-start text-sm hover:bg-muted">{p}</button>)}
                </div>
              </div>
            )}
            {lines.map((line, i) => (
              <div key={i} className={line.role === "user" ? "flex justify-end" : ""}>
                <div className={cn("max-w-[85%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-wrap", line.role === "user" ? "bg-primary-strong text-white" : "bg-muted")}>{line.text}</div>
                {!!line.meta?.tool_calls.length && (
                  <p className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-ink-soft"><Wrench className="size-3" aria-hidden />Checked: {[...new Set(line.meta.tool_calls.map((c) => humanize(c.name)))].join(", ")}</p>
                )}
                {line.meta?.proposals.map((p) => <div key={p.id} className="mt-3 max-w-xl"><ProposalCard proposal={byId.get(p.id) ?? p} canApprove={canApprove} /></div>)}
              </div>
            ))}
            {busy && <p role="status" className="text-sm text-ink-soft">Checking your event data...</p>}
            <div ref={end} />
          </div>
          <form className="flex gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <input aria-label="Message the assistant" placeholder="Ask about rides, hosts, tasks..." value={input} onChange={(e) => setInput(e.target.value)} className="h-10 min-w-0 flex-1 rounded-lg border border-line px-3 text-sm" />
            <Button type="submit" size="icon" className="h-10 w-10" aria-label="Send" disabled={!input.trim() || busy}><Send className="size-4" /></Button>
          </form>
        </Card>
        <section aria-label="Pending proposals" className="space-y-3">
          <h2 className="font-semibold">Earlier proposals awaiting approval ({pending.length})</h2>
          {pending.length === 0 && <p className="text-sm text-ink-soft">Nothing else is waiting.</p>}
          {pending.map((p) => <ProposalCard key={p.id} proposal={p} canApprove={canApprove} />)}
        </section>
      </div>
    </>
  );
}

export function Simulator() {
  const id = useEventId();
  const toast = useToast();
  const [phone, setPhone] = useState("+1-555-0142");
  const [convo, setConvo] = useState<SimConversation | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => { if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; }, [convo, busy]);

  async function run(work: () => Promise<SimConversation>) {
    setBusy(true);
    try { setConvo(await work()); } catch (e) { toast("error", (e as Error).message); } finally { setBusy(false); }
  }
  const start = () => run(() => api("/api/simulator/conversations", "POST", { event_id: id, phone }));
  const send = () => {
    const text = input.trim();
    if (!text || !convo) return;
    setInput("");
    run(() => api(`/api/simulator/conversations/${convo.id}/messages`, "POST", { message: text }));
  };

  return (
    <>
      <PageHeader title="Chat simulator" description="A WhatsApp-style test of the participant experience. No real messages are sent or received." />
      <div className="grid gap-6 md:grid-cols-[1fr_22rem]">
        <div className="order-2 mx-auto flex h-[34rem] w-full max-w-sm flex-col overflow-hidden rounded-2xl border border-line md:order-1">
          <div className="flex items-center justify-between bg-chat-bar px-4 py-3 text-white">
            <span className="text-sm font-medium">{convo?.participant_name ?? convo?.phone ?? "No conversation"}</span>
            <span className="rounded bg-white/20 px-1.5 py-0.5 text-xs">Simulator</span>
          </div>
          <div ref={scroller} role="log" aria-live="polite" className="flex-1 space-y-2 overflow-y-auto bg-chat-bg p-3">
            {convo?.messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : "flex"}>
                <div className={cn("max-w-[80%] rounded-lg px-3 py-1.5 text-sm whitespace-pre-wrap text-ink", m.role === "user" ? "bg-chat-out" : "bg-surface")}>{m.content}</div>
              </div>
            ))}
          </div>
          <form className="flex gap-2 bg-muted p-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input aria-label="Participant message" placeholder={convo ? "Type as the participant" : "Start a conversation first"} disabled={!convo} value={input} onChange={(e) => setInput(e.target.value)} className="h-10 min-w-0 flex-1 rounded-full bg-surface px-4 text-sm" />
            <Button type="submit" size="icon" className="h-10 w-10 rounded-full" aria-label="Send" disabled={!convo || busy || !input.trim()}><Send className="size-4" /></Button>
          </form>
        </div>
        <Card className="order-1 h-fit space-y-3 p-5 md:order-2">
          <Input label="Simulated phone number" hint="A number matching a participant continues as that person. A new number can register." value={phone} onChange={(e) => setPhone(e.target.value)} />
          <Button className="w-full" loading={busy} onClick={start}>Open conversation</Button>
          <p className="text-xs text-ink-soft">Try: "Hi, I would like to register", "I need a ride from Crown Heights", or "I need to cancel".</p>
        </Card>
      </div>
    </>
  );
}
