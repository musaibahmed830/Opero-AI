export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 p-10 text-center">
      <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{title}</h2>
      <p className="mt-2 text-sm text-zinc-500 max-w-md mx-auto">{description}</p>
    </div>
  );
}
