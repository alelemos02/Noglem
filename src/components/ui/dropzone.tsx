"use client"

import * as React from "react"
import { Upload } from "lucide-react"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

export interface DropzoneProps {
  onFiles: (files: File[]) => void
  accept?: string
  multiple?: boolean
  maxSizeMB?: number
  disabled?: boolean
  loading?: boolean
  /** erro externo (ex: falha de processamento) exibido abaixo da zona */
  error?: string
  /** texto principal — default depende de `multiple` */
  label?: string
  hint?: string
  compact?: boolean
  className?: string
}

/**
 * Dropzone única do design system — substitui as implementações por página.
 * Estado de drag padronizado: border-accent + bg-accent-subtle.
 */
function Dropzone({
  onFiles,
  accept,
  multiple = false,
  maxSizeMB,
  disabled = false,
  loading = false,
  error,
  label,
  hint,
  compact = false,
  className,
}: DropzoneProps) {
  const [dragOver, setDragOver] = React.useState(false)
  const [sizeError, setSizeError] = React.useState("")
  const inputRef = React.useRef<HTMLInputElement>(null)

  const inactive = disabled || loading

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return
    let files = Array.from(fileList)
    if (!multiple) files = files.slice(0, 1)

    if (maxSizeMB) {
      const tooBig = files.filter((f) => f.size > maxSizeMB * 1024 * 1024)
      if (tooBig.length > 0) {
        setSizeError(
          tooBig.length === 1
            ? `"${tooBig[0].name}" excede o limite de ${maxSizeMB} MB.`
            : `${tooBig.length} arquivos excedem o limite de ${maxSizeMB} MB.`
        )
        files = files.filter((f) => f.size <= maxSizeMB * 1024 * 1024)
      } else {
        setSizeError("")
      }
    }

    if (files.length > 0) onFiles(files)
  }

  const displayError = error || sizeError
  const resolvedLabel =
    label ??
    (multiple
      ? "Arraste arquivos ou clique para selecionar"
      : "Arraste um arquivo ou clique para selecionar")

  return (
    <div className={className}>
      <button
        type="button"
        disabled={inactive}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (!inactive) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (!inactive) handleFiles(e.dataTransfer.files)
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-center transition-colors",
          compact ? "px-4 py-5" : "px-6 py-10",
          dragOver
            ? "border-accent bg-accent-subtle"
            : "border-edge-strong hover:border-fg-subtle",
          displayError && !dragOver && "border-danger/50",
          inactive && "cursor-default opacity-60",
          !inactive && "cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={inactive}
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ""
          }}
        />
        {loading ? (
          <Spinner size="md" className="text-accent" />
        ) : (
          <Upload
            className={cn(
              "h-5 w-5",
              dragOver ? "text-accent" : "text-fg-subtle"
            )}
            aria-hidden="true"
          />
        )}
        <span className="text-sm font-medium text-fg">
          {loading ? "Enviando..." : resolvedLabel}
        </span>
        {hint && <span className="text-xs text-fg-subtle">{hint}</span>}
      </button>

      {displayError && (
        <p className="mt-2 text-xs text-danger-text" role="alert">
          {displayError}
        </p>
      )}
    </div>
  )
}

export { Dropzone }
