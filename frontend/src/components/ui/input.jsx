import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-3.5 py-2 text-[14px] text-[var(--cc-text-primary)] shadow-sm transition-all duration-200 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-[var(--cc-text-primary)] placeholder:text-[var(--cc-text-quaternary)] focus-visible:outline-none focus-visible:ring-1.5 focus-visible:ring-[var(--cc-text-primary)] focus-visible:border-[var(--cc-text-primary)] disabled:cursor-not-allowed disabled:opacity-45",
        className
      )}
      ref={ref}
      {...props} />
  );
})
Input.displayName = "Input"

export { Input }
