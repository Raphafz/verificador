import { cn } from '@/lib/utils'

export interface Column<T> {
  key: string
  header: string
  cell: (row: T) => React.ReactNode
  className?: string
}

interface SimpleTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  keyFn: (row: T) => string | number
  emptyMessage?: string
}

export function SimpleTable<T>({
  columns,
  rows,
  keyFn,
  emptyMessage = 'Nenhum registro encontrado.',
}: SimpleTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="rounded-[16px] border border-border bg-card px-5 py-10 text-center text-sm text-muted-foreground">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-[16px] border border-border bg-card shadow-sm">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn('px-4 py-3 text-xs font-bold uppercase tracking-wider text-muted-foreground', col.className)}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={keyFn(row)} className="border-b border-border/70 last:border-0 hover:bg-muted/30">
              {columns.map((col) => (
                <td key={col.key} className={cn('px-4 py-3', col.className)}>
                  {col.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
