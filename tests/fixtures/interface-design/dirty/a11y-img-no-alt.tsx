export function Avatar({ user }: { user: User }) {
  return (
    <div className="flex items-center gap-2">
      <img src={user.avatarUrl} className="size-8 rounded-full" />{/* expect */}
      <img src={user.orgLogo} alt="" className="size-4" />
      <img src={user.badge} alt={`${user.name} badge`} className="size-4" />
      <span className="text-sm">{user.name}</span>
    </div>
  );
}
