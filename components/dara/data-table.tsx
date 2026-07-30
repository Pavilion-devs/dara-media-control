import { cn } from "../ui/cn";

export type Cell = string | number | boolean | null;

/** Turn an API column id into a human label without hardcoding a mapping. */
export function humanizeColumn(column: string) {
  const cleaned = column
    .replace(/_usd$/, " (USD)")
    .replace(/_id$/, "")
    .replace(/_/g, " ");
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function isMoney(column: string) {
  return column.endsWith("_usd");
}

function isNumeric(value: Cell) {
  return typeof value === "number" || (typeof value === "string" && /^-?\d*\.?\d+$/.test(value));
}

function formatCell(value: Cell, column: string) {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (isMoney(column)) return `$${value}`;
  return String(value);
}

/**
 * Dense tabular data. The container is rounded to match the design language,
 * but the rows inside stay square and hairline-separated — a table should read
 * as a table.
 */
export function DataTable({
  columns,
  rows,
  /** Column id to draw an inline magnitude bar against. */
  barColumn,
  empty = "No rows.",
}: {
  columns: string[];
  rows: Cell[][];
  barColumn?: string;
  empty?: string;
}) {
  const barIndex = barColumn ? columns.indexOf(barColumn) : -1;
  const max =
    barIndex >= 0
      ? Math.max(
          ...rows.map((row) => {
            const value = row[barIndex];
            return isNumeric(value) ? Number(value) : 0;
          }),
          0,
        )
      : 0;

  if (rows.length === 0) {
    return (
      <div className="px-5 py-10 text-center text-sm text-subtle">{empty}</div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line bg-inset">
            {columns.map((column, index) => (
              <th
                className={cn(
                  "whitespace-nowrap px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-subtle",
                  index === 0 ? "text-left" : "text-right",
                )}
                key={column}
                scope="col"
              >
                {humanizeColumn(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              className="border-b border-line last:border-0 hover:bg-inset"
              key={rowIndex}
            >
              {row.map((value, index) => {
                const column = columns[index] ?? String(index);
                const numeric = isNumeric(value) || value === null;
                return (
                  <td
                    className={cn(
                      "px-4 py-3 align-middle",
                      index === 0 ? "text-left" : "text-right",
                      numeric || index === 0 ? "font-mono" : "",
                      value === null ? "text-faint" : "text-ink",
                    )}
                    key={index}
                  >
                    {formatCell(value, column)}
                    {index === barIndex && max > 0 && isNumeric(value) ? (
                      <span
                        aria-hidden
                        className="mt-1.5 block h-1 w-full overflow-hidden rounded-full bg-line"
                      >
                        <span
                          className="block h-full rounded-full bg-accent"
                          style={{ width: `${(Number(value) / max) * 100}%` }}
                        />
                      </span>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
