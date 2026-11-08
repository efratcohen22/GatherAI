import * as RD from "@radix-ui/react-dialog";
import type { UseQueryResult } from "@tanstack/react-query";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { AlertCircle, CheckCircle2, Inbox, Loader2, X } from "lucide-react";
import {
  createContext, forwardRef, useCallback, useContext, useId, useState,
  type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap cursor-pointer",
  {
    variants: {
      variant: {
        primary: "bg-primary-strong text-white hover:bg-primary",
        secondary: "bg-surface text-ink border border-line hover:bg-muted",
        ghost: "text-ink-soft hover:bg-muted hover:text-ink",
        danger: "bg-danger-strong text-white hover:opacity-90",
      },
      size: { sm: "h-8 px-3", md: "h-10 px-4", lg: "h-12 px-6 text-base", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonStyles> & { loading?: boolean };
export const buttonClass = buttonStyles;
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, loading, children, disabled, ...props }, ref) => (
  <button ref={ref} type="button" className={cn(buttonStyles({ variant, size }), className)} disabled={disabled || loading} {...props}>
    {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
    {children}
  </button>
));

const control = "w-full rounded-lg border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-soft focus:border-primary aria-[invalid=true]:border-danger-strong";

interface FieldProps { label: string; error?: string; hint?: string }
function Field({ id, label, error, hint, children }: FieldProps & { id: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      {children}
      {hint && !error && <p id={`${id}-hint`} className="text-xs text-ink-soft">{hint}</p>}
      {error && <p id={`${id}-error`} role="alert" className="text-xs text-danger-strong">{error}</p>}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & FieldProps>(({ label, error, hint, className, ...props }, ref) => {
  const id = useId();
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <input ref={ref} id={id} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} className={cn(control, "h-10", className)} {...props} />
    </Field>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps>(({ label, error, hint, className, ...props }, ref) => {
  const id = useId();
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <textarea ref={ref} id={id} aria-invalid={!!error} className={cn(control, "py-2 min-h-20", className)} {...props} />
    </Field>
  );
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { label?: string; error?: string }>(({ label, error, className, children, ...props }, ref) => {
  const id = useId();
  const select = <select ref={ref} id={id} className={cn(control, "h-10", className)} {...props}>{children}</select>;
  return label ? <Field id={id} label={label} error={error}>{select}</Field> : select;
});

export const Checkbox = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; error?: string }>(({ label, error, ...props }, ref) => (
  <div>
    <label className="flex items-start gap-2.5 text-sm cursor-pointer">
      <input ref={ref} type="checkbox" className="mt-0.5 size-4 accent-[var(--color-primary-strong)]" {...props} />
      <span>{label}</span>
    </label>
    {error && <p role="alert" className="mt-1 text-xs text-danger-strong">{error}</p>}
  </div>
));

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-xl border border-line bg-surface", className)}>{children}</div>;
}

const tones = {
  neutral: "bg-muted text-ink-soft",
  violet: "bg-lavender text-primary-strong",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning-ink",
  danger: "bg-danger-soft text-danger-strong",
};
export type Tone = keyof typeof tones;
export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone])}>{children}</span>;
}

const STATUS_TONES: Record<string, Tone> = {
  confirmed: "success", executed: "success", completed: "success", simulated_delivered: "success", active: "success", open: "success",
  pending: "warning", waitlisted: "violet", assigned: "violet", in_progress: "violet", draft: "neutral", todo: "neutral",
  needed: "warning", blocked: "danger", cancelled: "danger", failed: "danger", driver_cancelled: "danger", urgent: "danger", high: "warning",
  rejected: "neutral", expired: "neutral", not_needed: "neutral", received: "neutral",
};
export const humanize = (value: string) => {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};
export const StatusBadge = ({ status, label }: { status: string; label?: string }) => <Badge tone={STATUS_TONES[status] ?? "neutral"}>{label ?? humanize(status)}</Badge>;

export function Avatar({ name }: { name: string }) {
  const initials = name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
  return <span aria-hidden className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-lavender text-xs font-semibold text-primary-strong">{initials}</span>;
}

export function Table({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line text-start text-xs text-ink-soft">{headers.map((h) => <th key={h} scope="col" className="px-4 py-2.5 text-start font-medium">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

function Overlay() {
  return <RD.Overlay className="fixed inset-0 z-40 bg-overlay" />;
}
interface ModalProps { open: boolean; onClose(): void; title: string; description?: string; children: ReactNode }
export function Dialog({ open, onClose, title, description, children }: ModalProps) {
  return (
    <RD.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <RD.Portal>
        <Overlay />
        <RD.Content aria-describedby={undefined} className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl bg-surface p-6">
          <RD.Title className="text-lg font-semibold">{title}</RD.Title>
          {description && <p className="mt-1 text-sm text-ink-soft">{description}</p>}
          <div className="mt-4">{children}</div>
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}
export function Drawer({ open, onClose, title, children, side = "end" }: ModalProps & { side?: "start" | "end" }) {
  return (
    <RD.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <RD.Portal>
        <Overlay />
        <RD.Content aria-describedby={undefined} className={cn("fixed inset-y-0 z-50 flex w-full max-w-md flex-col bg-surface", side === "end" ? "end-0" : "start-0 max-w-72")}>
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <RD.Title className="font-semibold">{title}</RD.Title>
            <RD.Close asChild><Button variant="ghost" size="icon" aria-label="Close"><X className="size-4" /></Button></RD.Close>
          </div>
          <div className="flex-1 overflow-y-auto p-5">{children}</div>
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}

export function ConfirmDialog({ open, onClose, onConfirm, title, description, confirmLabel = "Confirm", danger, loading }: {
  open: boolean; onClose(): void; onConfirm(): void; title: string; description: string; confirmLabel?: string; danger?: boolean; loading?: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title} description={description}>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Dialog>
  );
}

export function Tabs<T extends string>({ value, onChange, options }: { value: T; onChange(next: NoInfer<T>): void; options: { value: NoInfer<T>; label: string }[] }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto">
      {options.map((o) => (
        <button key={o.value} role="tab" type="button" aria-selected={o.value === value} onClick={() => onChange(o.value)}
          className={cn("rounded-lg px-3 py-1.5 text-sm font-medium whitespace-nowrap cursor-pointer", o.value === value ? "bg-lavender text-primary-strong" : "text-ink-soft hover:bg-muted")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const Skeleton = ({ className }: { className?: string }) => <div className={cn("animate-pulse rounded-lg bg-muted", className)} />;

export function LoadingState() {
  return (
    <div role="status" aria-label="Loading" className="space-y-3">
      <Skeleton className="h-24" /><Skeleton className="h-12" /><Skeleton className="h-12" />
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <Inbox className="size-8 text-ink-soft" aria-hidden />
      <p className="mt-3 font-medium">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-ink-soft">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?(): void }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-14 text-center">
      <AlertCircle className="size-8 text-danger-strong" aria-hidden />
      <p className="mt-3 font-medium">{message}</p>
      {onRetry && <Button variant="secondary" className="mt-4" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Async<T>({ query, children }: { query: UseQueryResult<T>; children(data: T): ReactNode }) {
  if (query.isPending) return <LoadingState />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  return <>{children(query.data)}</>;
}

type ToastItem = { id: number; kind: "success" | "error"; text: string };
const ToastCtx = createContext<(kind: ToastItem["kind"], text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
let toastId = 0;
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((kind: ToastItem["kind"], text: string) => {
    const id = ++toastId;
    setItems((current) => [...current, { id, kind, text }]);
    setTimeout(() => setItems((current) => current.filter((i) => i.id !== id)), 5000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 end-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2">
        {items.map((i) => (
          <div key={i.id} className="flex items-start gap-2 rounded-lg border border-line bg-surface p-3 text-sm shadow-lg">
            {i.kind === "success" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden /> : <AlertCircle className="mt-0.5 size-4 shrink-0 text-danger-strong" aria-hidden />}
            <span>{i.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-soft">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
