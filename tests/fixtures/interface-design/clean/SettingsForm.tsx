import { useId, useState, type ComponentProps } from "react";
import { cn } from "@/lib/utils";

type FieldProps = ComponentProps<"input"> & { label: string; hint?: string };

function Field({ label, hint, className, ...props }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-slate-900">
        {label}
      </label>
      <input
        id={id}
        aria-describedby={hint ? hintId : undefined}
        className={cn(
          "h-9 rounded-md border border-slate-300 bg-white px-3 text-sm",
          "placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700",
          className
        )}
        {...props}
      />
      {hint ? (
        <p id={hintId} className="text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function SettingsForm({ initialName, onSave }: { initialName: string; onSave: (name: string) => Promise<void> }) {
  const [name, setName] = useState(initialName);
  const [isSaving, setIsSaving] = useState(false);
  const nameChanged = name !== initialName;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setIsSaving(true);
    try {
      await onSave(name);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-md flex-col gap-4 p-6">
      <div className="flex items-center gap-3">
        <img src="/logo-mark.svg" alt="" className="size-8" />
        <h1 className="text-lg font-semibold text-slate-900">Workspace settings</h1>
      </div>
      <Field
        label="Workspace name"
        hint="Shown in the sidebar and in email notifications."
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <Field label="Billing email" type="email" placeholder="billing@example.com" defaultValue="" />
      <div
        role="group"
        aria-label="Danger zone"
        tabIndex={0}
        className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900"
      >
        Deleting a workspace removes every deploy history entry.
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="rounded-md px-3 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!nameChanged || isSaving}
          className="rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2 disabled:opacity-50"
        >
          {isSaving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}
