import { cn } from "@/lib/utils";
import type { Deploy } from "@/types";

type Props = {
  deploys: Deploy[];
  selectedId: string | null;
  isLoading: boolean;
  onSelect: (id: string) => void;
  onRetry: (id: string) => void;
};

const STATUS_STYLES: Record<Deploy["status"], string> = {
  succeeded: "bg-emerald-50 text-emerald-800",
  failed: "bg-red-50 text-red-800",
  running: "bg-slate-100 text-slate-700",
};

export function DeployTable({ deploys, selectedId, isLoading, onSelect, onRetry }: Props) {
  if (isLoading) {
    return (
      <p role="status" className="px-3 py-6 text-sm text-slate-500">
        Loading deploys…
      </p>
    );
  }

  return (
    <table className="w-full border-collapse text-sm tabular-nums">
      <thead>
        <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500">
          <th scope="col" className="px-3 py-2">Service</th>
          <th scope="col" className="px-3 py-2">Status</th>
          <th scope="col" className="px-3 py-2">Started</th>
          <th scope="col" className="px-3 py-2 text-right">Actions</th>
        </tr>
      </thead>
      <tbody>
        {deploys.map((deploy) => (
          <tr
            key={deploy.id}
            className={cn(
              "border-b border-slate-200 transition-colors duration-150 hover:bg-slate-50",
              deploy.id === selectedId && "bg-slate-100",
              deploy.status === "failed" && "border-l-2 border-l-red-600"
            )}
          >
            <td className="px-3 py-2.5">
              <button
                type="button"
                onClick={() => onSelect(deploy.id)}
                className="rounded font-medium text-slate-900 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-700"
              >
                {deploy.service}
              </button>
            </td>
            <td className="px-3 py-2.5">
              <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs", STATUS_STYLES[deploy.status])}>
                {deploy.status}
              </span>
            </td>
            <td className="px-3 py-2.5 text-slate-600">{deploy.startedAt}</td>
            <td className="px-3 py-2.5 text-right">
              <button
                type="button"
                disabled={deploy.status !== "failed"}
                onClick={() => onRetry(deploy.id)}
                className="rounded border border-slate-300 px-2 py-1 text-xs transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 disabled:opacity-50"
              >
                Retry
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
