"use client";

/**
 * A dropdown drawn by the page rather than the browser.
 *
 * The native `<select>` was the Ask page's incident picker, and its open list
 * is painted by the operating system: on a dark page it came up white with
 * near-white text (RP-47). `color-scheme` fixes the colours but not the rest —
 * an option cannot carry a badge or a second line, which the model picker
 * needs to say where a model runs. So this is the listbox pattern from the
 * ARIA practices: a button, a `listbox`, `option`s with `aria-selected`, arrow
 * keys, Enter, Escape, and a click outside closes it.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

export type ListboxOption = {
  value: string;
  label: ReactNode;
  hint?: ReactNode;
};

export function Listbox({
  label,
  value,
  options,
  onChange,
  align = "left",
  buttonClassName = "",
  dataAttr,
}: {
  label: string;
  value: string;
  options: ListboxOption[];
  onChange: (value: string) => void;
  align?: "left" | "right";
  buttonClassName?: string;
  dataAttr?: string;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);

  const selectedIndex = Math.max(
    0,
    options.findIndex((option) => option.value === value),
  );
  const selected = options[selectedIndex];

  useEffect(() => {
    if (!open) return;
    setActive(selectedIndex);
    list.current?.focus();
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open, selectedIndex]);

  useEffect(() => {
    if (!open) return;
    list.current
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const choose = (index: number) => {
    const option = options[index];
    if (option) onChange(option.value);
    setOpen(false);
    button.current?.focus();
  };

  return (
    <div ref={root} className="relative min-w-0" {...(dataAttr ? { [dataAttr]: "" } : {})}>
      <button
        ref={button}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-label={label}
        onClick={() => setOpen((was) => !was)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className={`focusable flex min-w-0 max-w-full items-center gap-2 rounded-md border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] px-2.5 py-1.5 text-left text-sm transition hover:bg-[rgb(var(--raised))] ${buttonClassName}`}
      >
        <span className="min-w-0 truncate">{selected?.label ?? "—"}</span>
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-[rgb(var(--faint))]" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <ul
          ref={list}
          id={`${id}-list`}
          role="listbox"
          aria-label={label}
          aria-activedescendant={`${id}-${active}`}
          tabIndex={-1}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActive((at) => Math.min(options.length - 1, at + 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((at) => Math.max(0, at - 1));
            } else if (event.key === "Home") {
              event.preventDefault();
              setActive(0);
            } else if (event.key === "End") {
              event.preventDefault();
              setActive(options.length - 1);
            } else if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              choose(active);
            } else if (event.key === "Escape" || event.key === "Tab") {
              setOpen(false);
              if (event.key === "Escape") button.current?.focus();
            }
          }}
          className={`rise absolute top-full z-50 mt-1.5 max-h-80 w-max min-w-full max-w-[min(26rem,90vw)] overflow-y-auto rounded-lg border border-[rgb(var(--edge-strong))] bg-[rgb(var(--panel))] p-1 shadow-2xl outline-none ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {options.map((option, index) => {
            const isSelected = option.value === value;
            return (
              <li
                key={option.value}
                id={`${id}-${index}`}
                data-index={index}
                role="option"
                aria-selected={isSelected}
                onPointerEnter={() => setActive(index)}
                onClick={() => choose(index)}
                className={`flex cursor-pointer items-start gap-2 rounded-md px-2.5 py-2 text-sm ${
                  index === active ? "bg-[rgb(var(--raised))]" : ""
                }`}
              >
                <span aria-hidden="true" className={`mt-0.5 w-4 shrink-0 text-[rgb(var(--astra))] ${isSelected ? "" : "invisible"}`}>
                  ✓
                </span>
                <span className="min-w-0">
                  <span className="block text-[rgb(var(--ink))]">{option.label}</span>
                  {option.hint && (
                    <span className="mt-0.5 block text-xs text-[rgb(var(--faint))]">{option.hint}</span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
