import citation from "@/lib/citation.generated.json";
import { SITE } from "@/lib/site";

/**
 * How to cite this work — BibTeX, APA and the permalink, from `CITATION.cff`.
 *
 * Rendered from the JSON `scripts/buildcitation.py` generates out of the one
 * file GitHub reads as "Cite this repository", so the site and the repository
 * cannot offer two citations (R108). The DOI is read from the same file: until
 * Zenodo mints one, the block says so in words rather than carrying a
 * placeholder that looks like a DOI — a citation that leads nowhere is worse
 * than one that says where it will lead. A `<pre>` rather than a copy button:
 * the text is selectable, a button is one more thing to test, and the reader
 * pasting into a `.bib` file knows how to select text.
 */
export function Cite() {
  return (
    <div className="space-y-4 text-sm">
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[auto_1fr]">
        <dt className="label">permalink</dt>
        <dd className="mono break-all">{SITE}</dd>
        <dt className="label">source</dt>
        <dd className="mono break-all">{citation.repository}</dd>
        <dt className="label">DOI</dt>
        <dd className="mono">
          {citation.doi ? (
            <a
              href={`https://doi.org/${citation.doi}`}
              className="focusable underline decoration-dotted"
              rel="noopener noreferrer"
            >
              {citation.doi}
            </a>
          ) : (
            <span className="text-[rgb(var(--faint))]" data-no-doi>
              no DOI yet — one is minted from a tagged release once the repository carries a licence
            </span>
          )}
        </dd>
      </dl>

      <div>
        <p className="label mb-1">BibTeX</p>
        <pre
          data-bibtex
          className="mono overflow-x-auto whitespace-pre rounded-lg border border-[rgb(var(--edge))] bg-[rgb(var(--raised))]/40 p-3 text-[12px] leading-relaxed"
        >
          {citation.bibtex}
        </pre>
      </div>

      <div>
        <p className="label mb-1">APA</p>
        <p data-apa className="break-words leading-relaxed">
          {citation.apa}
        </p>
      </div>
    </div>
  );
}
