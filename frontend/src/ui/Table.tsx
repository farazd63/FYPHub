import type { HTMLAttributes, ReactNode, TableHTMLAttributes } from "react";

type TableProps = TableHTMLAttributes<HTMLTableElement> & {
  children: ReactNode;
  stickyHeader?: boolean;
};

export function Table({
  children,
  className,
  stickyHeader = true,
  ...rest
}: TableProps) {
  return (
    <div
      className={[
        "fy-table-scroll",
        stickyHeader && "fy-table-scroll--sticky",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <table className="fy-table" {...rest}>
        {children}
      </table>
    </div>
  );
}

export function TableHead({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={["fy-table__head", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </thead>
  );
}

export function TableBody({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={["fy-table__body", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </tbody>
  );
}

export function TableRow({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={["fy-table__row", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </tr>
  );
}

export function TableHeaderCell({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={["fy-table__th", className].filter(Boolean).join(" ")}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TableCell({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={["fy-table__td", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </td>
  );
}