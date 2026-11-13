const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

/**
 * "YYYY-MM-DD" als lokale Zeit parsen. new Date("YYYY-MM-DD") würde als
 * UTC-Mitternacht interpretiert und getDay() lieferte in UTC<0-Zonen den
 * Vortag — für Datumsangaben ohne Uhrzeit immer so parsen.
 */
export function parseDateOnly(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function weekdayOf(iso: string | null | undefined): string {
  const parsed = parseDateOnly(iso);
  return parsed ? WEEKDAYS[parsed.getDay()] : "";
}

export function formatDateOnly(iso: string | null | undefined): string {
  const parsed = parseDateOnly(iso);
  if (!parsed) return "";
  return parsed.toLocaleDateString("de-DE", { day: "numeric", month: "numeric" });
}
