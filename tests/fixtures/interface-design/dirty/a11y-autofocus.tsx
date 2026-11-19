export function RenameDialog({ name, onChange }: Props) {
  return (
    <dialog open className="rounded p-4">
      <label htmlFor="rename" className="text-sm">Name</label>
      <input id="rename" value={name} onChange={onChange} autoFocus />{/* expect */}
      <input id="alias" value="" onChange={onChange} autofocus />{/* expect */}
      <input id="owner" value="" onChange={onChange} />
    </dialog>
  );
}
