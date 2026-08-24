/**
 * Attribution, kept to one line.
 *
 * The first attempt at R57 put a full bill of materials on every page —
 * dependency versions, the test tooling, a list of the manifest paths they were
 * read from. That is the build talking about itself. A visitor came to look at
 * incidents, and the loudest panel on the page was an inventory of the
 * repository.
 *
 * What R57 actually complains about is narrower: the site has no author and no
 * way to reach the source. That is one line, and it belongs where a reader
 * looks *after* the page rather than in front of it.
 *
 * The stack list still exists, still generated from the manifests, but it lives
 * on `/how-it-works` — a page somebody opens because they want to know how it
 * is built.
 */

const REPO = "https://github.com/preetraval45/PASHUPATASTRA";

export function Attribution() {
  return (
    <>
      {/* No separator glyph. The one that was here measured 1.6:1 against the
          page and was invisible at every size — a divider nobody can see is not
          a divider, and the footer already spaces its items. */}
      <span>Built by Preet Raval</span>
      <a
        href={REPO}
        target="_blank"
        rel="noopener noreferrer"
        className="focusable rounded hover:text-[rgb(var(--muted))]"
      >
        Source
      </a>
      <a
        href="https://www.linkedin.com/in/preetraval45"
        target="_blank"
        rel="noopener noreferrer"
        className="focusable rounded hover:text-[rgb(var(--muted))]"
      >
        LinkedIn
      </a>
    </>
  );
}
