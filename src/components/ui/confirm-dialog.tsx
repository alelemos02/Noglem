"use client"

import * as React from "react"
import { AlertDialog } from "radix-ui"
import { Button } from "@/components/ui/button"

export interface ConfirmOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: "danger" | "default"
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>

const ConfirmContext = React.createContext<ConfirmFn | null>(null)

/**
 * Substitui o confirm() nativo do browser.
 * Uso: const confirm = useConfirm();
 *      if (await confirm({ title: "Excluir parecer?", variant: "danger" })) { ... }
 */
export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<{
    options: ConfirmOptions
    resolve: (value: boolean) => void
  } | null>(null)

  const confirm = React.useCallback<ConfirmFn>(
    (options) =>
      new Promise<boolean>((resolve) => {
        setState({ options, resolve })
      }),
    []
  )

  const close = (value: boolean) => {
    state?.resolve(value)
    setState(null)
  }

  const options = state?.options

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <AlertDialog.Root
        open={!!state}
        onOpenChange={(open) => {
          if (!open) close(false)
        }}
      >
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 z-(--z-modal-backdrop) bg-overlay animate-fade-in" />
          <AlertDialog.Content className="fixed left-1/2 top-1/2 z-(--z-modal) w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-edge-strong bg-surface-3 p-6 shadow-xl animate-fade-in-up">
            <AlertDialog.Title className="text-[15px] font-semibold text-fg">
              {options?.title}
            </AlertDialog.Title>
            {options?.description && (
              <AlertDialog.Description className="mt-2 text-[13px] leading-relaxed text-fg-muted">
                {options.description}
              </AlertDialog.Description>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <AlertDialog.Cancel asChild>
                <Button variant="ghost" size="sm">
                  {options?.cancelLabel ?? "Cancelar"}
                </Button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <Button
                  variant={options?.variant === "danger" ? "danger" : "primary"}
                  size="sm"
                  onClick={() => close(true)}
                >
                  {options?.confirmLabel ?? "Confirmar"}
                </Button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): ConfirmFn {
  const context = React.useContext(ConfirmContext)
  if (!context) {
    throw new Error("useConfirm deve ser usado dentro de <ConfirmProvider>")
  }
  return context
}
