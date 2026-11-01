/** Days until a YYYY-MM-DD due date, from today (negative when past). */
export function daysUntil(due: string, now = new Date()): number {
  const [y, m, d] = due.split("-").map(Number);
  const end = new Date(y, m - 1, d).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((end - today) / 86_400_000);
}
