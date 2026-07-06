"use client"

import { Toaster as Sonner, toast } from "sonner"

/**
 * Toaster do design system (sonner por baixo).
 * Montado uma única vez no Shell; dispare com `toast.success(...)`,
 * `toast.error(...)`, `toast.promise(...)` etc.
 */
function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      gap={8}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "flex w-[356px] items-start gap-3 rounded-lg border border-edge-strong bg-surface-3 px-4 py-3 shadow-lg font-sans",
          content: "min-w-0 flex-1",
          title: "text-[13px] font-semibold text-fg",
          description: "mt-0.5 text-[13px] text-fg-muted",
          icon: "mt-0.5 shrink-0 [&_svg]:h-4 [&_svg]:w-4",
          success: "[&_[data-icon]]:text-success",
          error: "[&_[data-icon]]:text-danger",
          warning: "[&_[data-icon]]:text-warning",
          info: "[&_[data-icon]]:text-info",
          loading: "[&_[data-icon]]:text-accent",
          actionButton:
            "ml-auto shrink-0 rounded-md bg-surface-2 border border-edge px-2.5 py-1 text-xs font-medium text-fg hover:bg-surface-1",
          cancelButton:
            "ml-2 shrink-0 rounded-md px-2.5 py-1 text-xs font-medium text-fg-muted hover:text-fg",
        },
      }}
    />
  )
}

export { Toaster, toast }
