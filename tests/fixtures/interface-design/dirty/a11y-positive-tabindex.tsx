export function Toolbar() {
  return (
    <div role="toolbar" className="flex gap-2">
      <button tabIndex={3} className="px-2">Run</button>{/* expect */}
      <button tabIndex="2" className="px-2">Stop</button>{/* expect */}
      <button tabIndex={0} className="px-2">Pause</button>
      <button tabIndex={-1} className="px-2">Skip</button>
    </div>
  );
}
