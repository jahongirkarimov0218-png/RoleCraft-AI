/**
 * Niche Report visibility guard (intent/spec.md D-05).
 * NOT an access-control mechanism: an enabled page on a public deploy is reachable by anyone with the URL.
 * The page is statically rendered, so the flag is read at build time (`next dev` reads it per request).
 */
export function isNicheReportEnabled(
  env: Record<string, string | undefined> = process.env
): boolean {
  return env.NICHE_REPORT_ENABLED === "true";
}
