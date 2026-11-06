export function RowActions({ onOpen, onArchive }: Props) {
  return (
    <div className="flex gap-2">
      <div className="cursor-pointer text-sm" onClick={onOpen}>Open</div>{/* expect */}
      <span className="cursor-pointer text-sm" onClick={onArchive}>Archive</span>{/* expect */}
      <div className="cursor-pointer text-sm" role="button" tabIndex={0} onClick={onOpen}>Retry</div>
      <button className="text-sm" onClick={onOpen}>Details</button>
    </div>
  );
}
