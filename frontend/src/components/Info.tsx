/** A small "ⓘ" with a hover/focus tooltip. Keyboard-accessible. */
export function Info({ tip, className = "" }: { tip: string; className?: string }) {
  return (
    <span className={`group relative inline-flex align-middle ${className}`}>
      <button
        type="button"
        aria-label={tip}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-[10px] font-bold leading-none text-slate-400 hover:border-accent hover:text-accent"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-1.5 hidden w-60 -translate-x-1/2 rounded-md bg-ink px-2.5 py-2 text-xs font-normal normal-case leading-snug tracking-normal text-white shadow-lg group-hover:block group-focus-within:block"
      >
        {tip}
      </span>
    </span>
  );
}
