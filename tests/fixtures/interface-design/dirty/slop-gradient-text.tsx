export function PlanHeading() {
  return (
    <div>
      <h2 className="bg-gradient-to-r from-violet-500 to-fuchsia-500 bg-clip-text text-3xl font-semibold text-transparent">Plans</h2>{/* expect */}
      <h3 className="bg-clip-text text-lg font-medium text-slate-900">Usage</h3>
      <div className="bg-gradient-to-b from-slate-50 to-white p-4">Summary</div>
    </div>
  );
}
