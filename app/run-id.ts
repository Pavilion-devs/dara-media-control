/** Accept both the original hex job IDs and the ULID-style production IDs. */
export function isRunId(value: string): boolean {
  return /^job_[A-Za-z0-9_-]{8,80}$/.test(value);
}
