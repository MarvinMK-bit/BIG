// The hosted backend sleeps when idle, and the first request after a quiet spell either fails or
// times out at the host's edge while it starts. Shown in place of a generic failure.
export const WAKING_MESSAGE =
  "The server is waking up — this can take up to a minute. Please try again shortly.";

const WAKING_STATUSES = new Set([500, 502, 503, 504]);

// status undefined means the fetch itself failed
export function isWaking(status: number | undefined): boolean {
  return status === undefined || WAKING_STATUSES.has(status);
}
