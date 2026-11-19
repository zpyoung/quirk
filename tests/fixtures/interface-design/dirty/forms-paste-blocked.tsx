export function ConfirmField({ value, onChange }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="confirm" className="text-sm">Confirm email</label>
      <input id="confirm" value={value} onChange={onChange} onPaste={(e) => e.preventDefault()} />{/* expect */}
      <input id="notes" onPaste={handlePaste} />
    </div>
  );
}
