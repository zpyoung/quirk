# Mini-app patterns gallery

A Vite app that runs every pattern block next to its reference, so each demo can be tried, read and adapted. The sidebar lists the ten patterns; each page shows the block's `demo.tsx` and the matching `references/patterns/<pattern>.md`.

```bash
pnpm install && pnpm dev
```

## Where things live

- `src/patterns/<pattern>/`: one block. `index.ts` is its public API, `demo.tsx` the worked example, `registry-item.json` its manifest.
- `src/components/mini/`, `src/lib/mini/`, `src/styles/`: the base every block builds on (shell, states, store, tokens).
- `src/gallery/`: the gallery's own chrome. It is not shipped to apps.
- `../registry/r/`: the built items that `shadcn add` installs into an app.

## After editing a block or a base file

Rebuild the registry so the built items match the source:

```bash
python3 ../scripts/build_registry.py
```

`python3 ../scripts/build_registry.py --check` reports whether the built items are stale without writing anything.
