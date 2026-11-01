/** Conversations grouped as chat apps show them: Today, Yesterday, Previous 7 days, then Older. */
export type Dated = { updated: number; title: string };

const DAY = 86_400_000;

export function historyGroups<T extends Dated>(items: T[], now: number, query = ""): { label: string; items: T[] }[] {
  const q = query.trim().toLowerCase();
  const startOfToday = new Date(now).setHours(0, 0, 0, 0);
  const groups: { label: string; items: T[] }[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];
  for (const item of [...items].sort((a, b) => b.updated - a.updated)) {
    if (q && !item.title.toLowerCase().includes(q)) continue;
    const index =
      item.updated >= startOfToday ? 0 : item.updated >= startOfToday - DAY ? 1 : item.updated >= startOfToday - 7 * DAY ? 2 : 3;
    groups[index].items.push(item);
  }
  return groups.filter((g) => g.items.length > 0);
}
