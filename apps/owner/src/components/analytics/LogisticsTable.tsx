import { LogisticsRow } from "@/lib/api";
import { StatusSelect } from "./StatusSelect";

const AVATAR_TINTS = [
  "bg-secondary-container text-on-secondary-container",
  "bg-tertiary-container text-on-tertiary-container",
  "bg-primary-container text-on-primary-container",
  "bg-surface-container-high text-on-surface",
];

export function LogisticsTable({ rows }: { rows: LogisticsRow[] }) {
  return (
    <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-surface-container-low/50">
            <th className="py-4 px-6 font-label text-xs uppercase tracking-widest text-on-surface-variant font-medium">User</th>
            <th className="py-4 px-6 font-label text-xs uppercase tracking-widest text-on-surface-variant font-medium">Product</th>
            <th className="py-4 px-6 font-label text-xs uppercase tracking-widest text-on-surface-variant font-medium">Purchased Qty</th>
            <th className="py-4 px-6 font-label text-xs uppercase tracking-widest text-on-surface-variant font-medium">Revenue (Rs)</th>
            <th className="py-4 px-6 font-label text-xs uppercase tracking-widest text-on-surface-variant font-medium text-right">Delivery Status</th>
          </tr>
        </thead>
        <tbody className="font-body text-sm divide-y divide-outline-variant/10">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-10 px-6 text-center text-on-surface-variant font-label text-xs uppercase tracking-widest">
                No active orders
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={row.order_id} className="hover:bg-surface-container-low/30 transition-colors">
                <td className="py-5 px-6">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-label text-xs font-bold ${AVATAR_TINTS[i % AVATAR_TINTS.length]}`}>
                      {row.user_initials}
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-on-background truncate">{row.user_name}</div>
                      {row.user_email ? (
                        <div className="text-[11px] text-on-surface-variant truncate">{row.user_email}</div>
                      ) : null}
                    </div>
                  </div>
                </td>
                <td className="py-5 px-6 text-on-surface-variant truncate max-w-[240px]">{row.product_name}</td>
                <td className="py-5 px-6 text-on-surface-variant">{row.quantity} units</td>
                <td className="py-5 px-6 text-on-background font-medium">{row.revenue.toLocaleString()}</td>
                <td className="py-5 px-6 text-right">
                  <StatusSelect orderId={row.order_id} initialStatus={row.status} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
