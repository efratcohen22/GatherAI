import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button, Card, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";

function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-6 text-center text-2xl font-semibold tracking-tight">{title}</h1>
      <Card className="p-6">{children}</Card>
    </div>
  );
}

const loginSchema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Enter your password") });
const signupSchema = z.object({
  display_name: z.string().min(1, "Enter your name"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Use at least 8 characters"),
});

function ErrorLine({ text }: { text: string | null }) {
  return text ? <p role="alert" className="text-sm text-danger-strong">{text}</p> : null;
}

export function Login() {
  const { login, me, config } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/app";
  const [failure, setFailure] = useState<string | null>(null);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const { errors, isSubmitting } = form.formState;
  if (me) return <Navigate to={from} replace />;
  return (
    <Shell title="Welcome back">
      <form noValidate className="space-y-4" onSubmit={form.handleSubmit(async (v) => {
        setFailure(null);
        try { await login(v.email, v.password); navigate(from, { replace: true }); } catch (e) { setFailure((e as Error).message); }
      })}>
        <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...form.register("email")} />
        <Input label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...form.register("password")} />
        <ErrorLine text={failure} />
        <Button type="submit" className="w-full" loading={isSubmitting}>Log in</Button>
      </form>
      <div className="mt-4 flex justify-between text-sm">
        <Link to="/forgot-password" className="text-primary-strong hover:underline">Forgot password?</Link>
        <Link to="/signup" className="text-primary-strong hover:underline">Create account</Link>
      </div>
      {config?.auth_mode === "local" && (
        <p className="mt-4 rounded-lg bg-warning-soft p-3 text-xs text-warning-ink">
          Local development mode. Fictional demo account: demo@gatherai.example / demo-organizer-2026
        </p>
      )}
    </Shell>
  );
}

export function Signup() {
  const { signup, me } = useAuth();
  const navigate = useNavigate();
  const [failure, setFailure] = useState<string | null>(null);
  const form = useForm<z.infer<typeof signupSchema>>({ resolver: zodResolver(signupSchema) });
  const { errors, isSubmitting } = form.formState;
  if (me) return <Navigate to="/app" replace />;
  return (
    <Shell title="Create your account">
      <form noValidate className="space-y-4" onSubmit={form.handleSubmit(async (v) => {
        setFailure(null);
        try { await signup(v.email, v.password, v.display_name); navigate("/app", { replace: true }); } catch (e) { setFailure((e as Error).message); }
      })}>
        <Input label="Your name" autoComplete="name" error={errors.display_name?.message} {...form.register("display_name")} />
        <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...form.register("email")} />
        <Input label="Password" type="password" autoComplete="new-password" error={errors.password?.message} {...form.register("password")} />
        <ErrorLine text={failure} />
        <Button type="submit" className="w-full" loading={isSubmitting}>Create account</Button>
      </form>
      <p className="mt-4 text-center text-sm"><Link to="/login" className="text-primary-strong hover:underline">I already have an account</Link></p>
    </Shell>
  );
}

export function ForgotPassword() {
  const { resetPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  return (
    <Shell title="Reset your password">
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault();
        try { await resetPassword(email); setResult({ ok: true, text: "If this email has an account, a reset link is on its way." }); }
        catch (err) { setResult({ ok: false, text: (err as Error).message }); }
      }}>
        <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        {result && <p role="status" className={result.ok ? "text-sm text-success" : "text-sm text-danger-strong"}>{result.text}</p>}
        <Button type="submit" className="w-full">Send reset link</Button>
      </form>
    </Shell>
  );
}
