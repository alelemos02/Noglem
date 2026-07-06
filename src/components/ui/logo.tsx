import { cn } from "@/lib/utils"

type LogoVariant = "full" | "compact" | "tagline"
type LogoSize = "sm" | "md" | "lg"

export interface LogoProps {
  variant?: LogoVariant
  size?: LogoSize
  className?: string
}

const sizeStyles: Record<LogoSize, { text: string; tagline: string }> = {
  sm: { text: "text-lg", tagline: "text-[9px]" },
  md: { text: "text-2xl", tagline: "text-[10px]" },
  lg: { text: "text-4xl", tagline: "text-xs" },
}

function Logo({ variant = "full", size = "md", className }: LogoProps) {
  const s = sizeStyles[size]

  if (variant === "compact") {
    return (
      <span
        className={cn(
          "inline-flex items-baseline font-sans font-semibold leading-none tracking-tight select-none",
          s.text,
          className
        )}
      >
        <span className="text-fg">J</span>
        <span
          className="text-accent -mx-[0.05em]"
          style={{ transform: "skewX(-8deg)", display: "inline-block" }}
          aria-hidden="true"
        >
          /
        </span>
      </span>
    )
  }

  return (
    <span
      className={cn(
        "inline-flex flex-col items-start select-none",
        className
      )}
    >
      <span
        className={cn(
          "inline-flex items-baseline font-sans font-semibold leading-none tracking-tight",
          s.text
        )}
      >
        <span className="text-fg">Jul</span>
        <span
          className="text-accent -mx-[0.05em]"
          style={{ transform: "skewX(-8deg)", display: "inline-block" }}
          aria-hidden="true"
        >
          /
        </span>
        <span className="text-fg">IA</span>
      </span>

      {variant === "tagline" && (
        <span
          className={cn(
            "microlabel mt-1.5",
            s.tagline
          )}
        >
          Engineering Intelligence
        </span>
      )}
    </span>
  )
}

Logo.displayName = "Logo"
export { Logo }
