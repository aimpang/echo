import type { Instrumentation } from "next";

type SentryModule = {
  init: (opts: Record<string, unknown>) => void;
  captureException: (err: unknown, ctx?: Record<string, unknown>) => void;
};

let sentry: SentryModule | null = null;

export async function register() {
  const dsn = process.env.SENTRY_DSN;
  if (!dsn) return;

  try {
    // @ts-expect-error — optional dep; present only in deploys that opt in.
    const mod = (await import("@sentry/nextjs")) as unknown as SentryModule;
    mod.init({
      dsn,
      tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.1"),
      environment: process.env.VERCEL_ENV ?? process.env.NODE_ENV,
    });
    sentry = mod;
  } catch {
    console.warn(
      "[echoes] SENTRY_DSN is set but @sentry/nextjs is not installed — skipping.",
    );
  }
}

export const onRequestError: Instrumentation.onRequestError = async (
  err,
  request,
  context,
) => {
  if (sentry) {
    sentry.captureException(err, { extra: { request, context } });
  } else {
    console.error("[echoes] unhandled server error:", err, { request, context });
  }
};
