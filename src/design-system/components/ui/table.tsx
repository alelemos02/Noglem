import { forwardRef, type HTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

/* ---------- Table ---------- */

const Table = forwardRef<HTMLTableElement, HTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, ref) => (
    <div className="w-full overflow-auto">
      <table
        ref={ref}
        className={cn('w-full caption-bottom text-sm', className)}
        {...props}
      />
    </div>
  )
)
Table.displayName = 'Table'

/* ---------- Table Header ---------- */

const TableHeader = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead
    ref={ref}
    className={cn('border-b border-border', className)}
    {...props}
  />
))
TableHeader.displayName = 'TableHeader'

/* ---------- Table Body ---------- */

const TableBody = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props} />
))
TableBody.displayName = 'TableBody'

/* ---------- Table Row ---------- */

const TableRow = forwardRef<
  HTMLTableRowElement,
  HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      'border-b border-border transition-colors duration-fast',
      'hover:bg-surface-hover',
      'data-[state=selected]:bg-accent-muted',
      className
    )}
    {...props}
  />
))
TableRow.displayName = 'TableRow'

/* ---------- Table Head Cell ---------- */

const TableHead = forwardRef<
  HTMLTableCellElement,
  ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      'h-10 px-3 text-left align-middle',
      'font-heading font-semibold text-xs text-text-tertiary uppercase tracking-wider',
      className
    )}
    {...props}
  />
))
TableHead.displayName = 'TableHead'

/* ---------- Table Cell ---------- */

const TableCell = forwardRef<
  HTMLTableCellElement,
  TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn(
      'px-3 py-3 align-middle text-text-primary',
      className
    )}
    {...props}
  />
))
TableCell.displayName = 'TableCell'

/* ---------- Numeric Cell (always mono) ---------- */

const TableCellNumeric = forwardRef<
  HTMLTableCellElement,
  TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn(
      'px-3 py-3 align-middle text-text-primary',
      'font-mono tabular-nums text-right',
      className
    )}
    {...props}
  />
))
TableCellNumeric.displayName = 'TableCellNumeric'

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCellNumeric }
