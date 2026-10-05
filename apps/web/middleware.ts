import { after, NextResponse, type NextRequest } from "next/server";

import { recordView } from "@/lib/api";

/**
 * Count one render, on the server, after the response has gone (R107).
 *
 * Three properties, each a clause of the task rather than a preference:
 *
 * **No beacon and no cookie.** The count happens here, in the server that
 * served the page. Nothing is asked of the browser, nothing is stored in it,
 * and a reader who blocks scripts is counted exactly like one who does not —
 * which also means the figure is not a measure of people. It is renders, and
 * `/impact` says so.
 *
 * **It cannot slow a page down.** `after()` runs the work once the response
 * has been sent, so the count is never in front of the reader. A counter that
 * added a round trip to every page would be a worse version of the problem
 * R99 and R100 were about.
 *
 * **It cannot break a page either.** `recordView` is one attempt with a short
 * timeout and no retry, and nothing here reads its result. The store being
 * unreachable must cost a visitor nothing at all.
 *
 * And it is not an audit record: R93 stopped page views reaching the
 * append-only ledger, and this does not undo that. A counter has no actor, no
 * verdict and nothing to approve; it lives beside the heartbeat, not in the
 * trail.
 */
export function middleware(request: NextRequest) {
  const route = request.nextUrl.pathname;
  after(async () => {
    try {
      await recordView(route);
    } catch {
      // Deliberately swallowed. Whether a count was recorded is not a fact a
      // visitor should ever learn about, and `/impact` reports an unreachable
      // store as absent rather than as zero.
    }
  });
  return NextResponse.next();
}

export const config = {
  // Pages only. Static assets, the icons and the manifest are not renders a
  // reader made, and counting them would turn one visit into six.
  matcher: ["/((?!_next/|api/|.*\\.(?:png|ico|svg|webmanifest|xml|txt)$).*)"],
};
