export function InviteForm() {
  return (
    <form className="flex flex-col gap-3">
      <input type="email" placeholder="Email address" className="h-9 rounded border px-3" />{/* expect */}
      <textarea placeholder="Add a note" className="rounded border p-3" />{/* expect */}
      <input type="text" placeholder="Team name" aria-label="Team name" className="h-9 rounded border px-3" />
      <input type="text" id="role" placeholder="Role" className="h-9 rounded border px-3" />
    </form>
  );
}
