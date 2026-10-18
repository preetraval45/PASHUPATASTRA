import { ModeIndicator } from "@/components/chrome";
import { ConsoleFrame } from "@/components/sidebar";
import { getHealth } from "@/lib/api";

/**
 * The console as an app (RP-48): a sidebar and a working area that fills the
 * window. Pages that read like documents sit in `(padded)`, which scrolls and
 * centres them; Ask sits outside it, because a conversation wants the whole
 * height with its input pinned to the bottom.
 */
export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const health = await getHealth();
  return <ConsoleFrame status={<ModeIndicator health={health} />}>{children}</ConsoleFrame>;
}
