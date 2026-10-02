/**
 * RoleCraft AI - Clean PDF / Print Export Helper
 * Lou Adler & Emil Kowalski Print Engineering
 */

export function triggerCleanPdfExport(roleTitle?: string): void {
  if (typeof window === 'undefined') return;

  const originalTitle = document.title;
  if (roleTitle) {
    document.title = `${roleTitle} — RoleCraft Enterprise Specification`;
  }

  // Trigger browser print dialog (which uses @media print styles)
  window.print();

  // Restore title after print dialog closes
  if (roleTitle) {
    setTimeout(() => {
      document.title = originalTitle;
    }, 1000);
  }
}
