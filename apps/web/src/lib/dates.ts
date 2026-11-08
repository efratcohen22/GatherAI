export const toIso = (local: string) => new Date(local).toISOString();

export function formatDate(iso: string, timeZone?: string) {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}

/** Formats an ISO instant for a datetime-local input in the browser's zone. */
export function toLocalInput(iso: string) {
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
