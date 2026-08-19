import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[10px] text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-45 active:scale-[0.985] [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-sm hover:opacity-90",
        destructive:
          "bg-[var(--cc-red-bg)] text-[var(--cc-red-text)] border border-[var(--cc-red-dot)]/20 hover:opacity-90 shadow-sm",
        outline:
          "border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-sm hover:bg-[var(--cc-surface-hover)]",
        secondary:
          "bg-[var(--cc-surface-sunken)] text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)]",
        ghost: "text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)] hover:text-[var(--cc-text-primary)]",
        link: "text-[var(--cc-text-primary)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-[8px] px-3 text-xs",
        lg: "h-11 rounded-[12px] px-6 text-[15px]",
        icon: "h-9 w-9 rounded-[8px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
