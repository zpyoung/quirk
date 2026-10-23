import { useId, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useCollection } from "@/lib/mini/store"

import { WorkspacePanes } from "./workspace-panes"
import type { WorkspaceLayout } from "./types"

type Recipe = {
  id: string
  title: string
  servings: number
  ingredients: string[]
  steps: string[]
  created: string
  modified: string
}

type Preview = "live" | "empty" | "loading" | "error"

const LAYOUT_STORE = "workspace-panes-layout"

function recipe(
  id: string,
  title: string,
  servings: number,
  ingredients: string[],
  steps: string[]
): Recipe {
  return {
    id,
    title,
    servings,
    ingredients,
    steps,
    created: "2026-09-02T10:15:00.000Z",
    modified: "2026-10-12T18:40:00.000Z",
  }
}

const seed: Recipe[] = [
  recipe("r-pancakes", "Lemon ricotta pancakes", 4, ["1 cup ricotta", "3 eggs", "3/4 cup flour", "Zest of 1 lemon", "Butter for the pan"], ["Whisk ricotta, eggs and zest.", "Fold in the flour until just combined.", "Cook in butter, about 2 minutes a side."]),
  recipe("r-shakshuka", "Shakshuka", 3, ["1 onion, sliced", "2 peppers, sliced", "1 can crushed tomatoes", "6 eggs", "1 tsp cumin", "1 tsp paprika"], ["Soften the onion and peppers in oil.", "Add spices and tomatoes; simmer 10 minutes.", "Make wells, crack in the eggs, cover until set."]),
  recipe("r-ribs", "Slow-braised short ribs with red wine, shallots, thyme, orange peel and a very long overnight rest before serving", 6, ["2 kg short ribs", "1 bottle red wine", "8 shallots", "Thyme", "1 strip orange peel"], ["Season and sear the ribs.", "Add wine, shallots, thyme and peel.", "Braise at 150 C for 3 hours.", "Rest overnight in the liquid, reheat to serve."]),
  recipe("r-dal", "Red lentil dal", 4, ["1 cup red lentils", "1 onion", "3 garlic cloves", "1 tbsp grated ginger", "1 tsp turmeric", "1 can coconut milk"], ["Sweat onion, garlic and ginger.", "Add lentils, turmeric and 3 cups water.", "Simmer 20 minutes, stir in coconut milk."]),
  recipe("r-focaccia", "Overnight focaccia", 8, ["500 g bread flour", "400 g water", "10 g salt", "2 g yeast", "Olive oil", "Flaky salt"], ["Mix everything except the oil; rest 12 hours.", "Stretch into an oiled tray and dimple.", "Bake at 230 C for 22 minutes."]),
  recipe("r-gazpacho", "Tomato gazpacho", 4, ["1 kg ripe tomatoes", "1 cucumber", "1 pepper", "1 garlic clove", "3 tbsp sherry vinegar", "Olive oil"], ["Blend the vegetables with garlic and vinegar.", "Stream in oil while blending.", "Chill for 2 hours."]),
  recipe("r-tacos", "Crispy fish tacos", 4, ["500 g white fish", "Corn tortillas", "1/4 red cabbage", "2 limes", "Hot sauce", "Mayonnaise"], ["Dredge the fish in seasoned flour and fry.", "Toss the cabbage with lime.", "Fill warm tortillas, finish with sauce."]),
  recipe("r-risotto", "Mushroom risotto", 4, ["300 g arborio rice", "400 g mushrooms", "1 L stock", "1 shallot", "Parmesan", "White wine"], ["Brown the mushrooms and set aside.", "Toast rice with the shallot, add wine.", "Add stock a ladle at a time, 18 minutes.", "Fold in mushrooms and cheese."]),
  recipe("r-granola", "Maple granola", 10, ["4 cups rolled oats", "1 cup nuts", "1/2 cup maple syrup", "1/3 cup oil", "1 tsp cinnamon"], ["Mix everything in a bowl.", "Spread on a tray and bake at 160 C, stirring twice.", "Cool completely before storing."]),
  recipe("r-salmon", "Miso-glazed salmon", 2, ["2 salmon fillets", "2 tbsp white miso", "1 tbsp mirin", "1 tsp soy sauce"], ["Mix miso, mirin and soy.", "Coat the fillets and rest 20 minutes.", "Broil for 8 minutes."]),
  recipe("r-brownies", "Fudgy brownies", 12, ["200 g dark chocolate", "150 g butter", "200 g sugar", "3 eggs", "80 g flour"], ["Melt chocolate and butter together.", "Whisk in sugar, then eggs, then flour.", "Bake at 175 C for 25 minutes."]),
  recipe("r-slaw", "Crunchy peanut slaw", 6, ["1/2 green cabbage", "2 carrots", "1/4 cup peanut butter", "2 tbsp lime juice", "1 tbsp soy sauce"], ["Shred the vegetables.", "Whisk the dressing.", "Toss just before serving."]),
]

const demoLayout: WorkspaceLayout = {
  id: "layout",
  activeGroupId: "g-left",
  sidebarOpen: true,
  recent: ["r-shakshuka", "r-pancakes"],
  groups: [
    {
      groupId: "g-left",
      activeTabId: "t-left-1",
      tabs: [
        { tabId: "t-left-1", itemId: "r-pancakes", mode: "structured" },
        { tabId: "t-left-2", itemId: "r-shakshuka", mode: "structured" },
      ],
    },
    {
      groupId: "g-right",
      activeTabId: "t-right-1",
      tabs: [{ tabId: "t-right-1", itemId: "r-pancakes", mode: "raw" }],
    },
  ],
}

function toRaw(r: Recipe): string {
  return [
    "---",
    `title: ${r.title}`,
    `servings: ${r.servings}`,
    "---",
    "",
    "## Ingredients",
    "",
    ...r.ingredients.map((line) => `- ${line}`),
    "",
    "## Steps",
    "",
    ...r.steps.map((line, i) => `${i + 1}. ${line}`),
    "",
  ].join("\n")
}

function parseRaw(raw: string, current: Recipe): Recipe {
  const lines = raw.replace(/\r\n/g, "\n").split("\n")
  if (lines[0]?.trim() !== "---") throw new Error('The file must start with a "---" line.')
  const end = lines.findIndex((line, i) => i > 0 && line.trim() === "---")
  if (end === -1) throw new Error('The front matter is missing its closing "---" line.')

  const fields = new Map<string, string>()
  for (const line of lines.slice(1, end)) {
    const match = /^(\w+):\s*(.*)$/.exec(line)
    if (match) fields.set(match[1], match[2])
  }
  const title = fields.get("title")?.trim()
  if (!title) throw new Error("The front matter needs a title.")
  const servings = Number(fields.get("servings"))
  if (!Number.isInteger(servings) || servings < 1) {
    throw new Error("servings must be a whole number, 1 or more.")
  }

  const ingredients: string[] = []
  const steps: string[] = []
  let section: "ingredients" | "steps" | undefined
  const seen = new Set<string>()
  for (const line of lines.slice(end + 1)) {
    const heading = /^##\s+(.*)$/.exec(line)
    if (heading) {
      const name = heading[1].trim().toLowerCase()
      section = name === "ingredients" ? "ingredients" : name === "steps" ? "steps" : undefined
      if (section) seen.add(section)
      continue
    }
    const bullet = /^-\s+(.*\S)\s*$/.exec(line)
    const numbered = /^\d+\.\s+(.*\S)\s*$/.exec(line)
    if (section === "ingredients" && bullet) ingredients.push(bullet[1])
    if (section === "steps" && numbered) steps.push(numbered[1])
  }
  if (!seen.has("ingredients")) throw new Error('Add an "## Ingredients" section.')
  if (!seen.has("steps")) throw new Error('Add a "## Steps" section.')

  return { ...current, title, servings, ingredients, steps }
}

function DraftField({
  label,
  value,
  onCommit,
  multiline,
}: {
  label: string
  value: string
  onCommit: (next: string) => void
  multiline?: boolean
}) {
  const id = useId()
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    setDraft(value)
  }
  const commit = () => {
    if (draft !== value) onCommit(draft)
  }
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {multiline ? (
        <Textarea
          id={id}
          rows={Math.max(3, draft.split("\n").length)}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          className="text-sm"
        />
      ) : (
        <Input
          id={id}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          className="text-sm"
        />
      )}
    </div>
  )
}

const lines = (text: string) => text.split("\n").map((line) => line.trim()).filter(Boolean)

function RecipeForm({
  recipe: r,
  update,
  onDelete,
}: {
  recipe: Recipe
  update: (patch: Partial<Recipe>) => Promise<void>
  onDelete: () => void
}) {
  const save = (patch: Partial<Recipe>) => void update(patch).catch(() => undefined)
  return (
    <div className="flex flex-col gap-4">
      <DraftField
        label="Title"
        value={r.title}
        onCommit={(title) => save({ title: title.trim() || r.title })}
      />
      <DraftField
        label="Servings"
        value={String(r.servings)}
        onCommit={(next) => {
          const servings = Number(next)
          if (Number.isInteger(servings) && servings > 0) save({ servings })
        }}
      />
      <DraftField
        multiline
        label="Ingredients (one per line)"
        value={r.ingredients.join("\n")}
        onCommit={(next) => save({ ingredients: lines(next) })}
      />
      <DraftField
        multiline
        label="Steps (one per line)"
        value={r.steps.join("\n")}
        onCommit={(next) => save({ steps: lines(next) })}
      />
      <div>
        <Button variant="outline" size="sm" onClick={onDelete}>
          Delete recipe
        </Button>
      </div>
    </div>
  )
}

const formatDate = (iso: string) => new Date(iso).toLocaleDateString()

export default function Demo() {
  useCollection<WorkspaceLayout>(LAYOUT_STORE, [demoLayout])
  const recipes = useCollection<Recipe>("workspace-panes-demo", seed)
  const [preview, setPreview] = useState<Preview>("live")

  async function onChange(next: Recipe) {
    try {
      await recipes.update(next.id, { ...next, modified: new Date().toISOString() })
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Could not save the recipe")
      throw cause
    }
  }

  async function onCreate() {
    const now = new Date().toISOString()
    const id = crypto.randomUUID()
    await recipes.add({
      id,
      title: "Untitled recipe",
      servings: 2,
      ingredients: [],
      steps: [],
      created: now,
      modified: now,
    })
    setPreview("live")
    return id
  }

  const status = preview === "loading" ? "loading" : preview === "error" ? "error" : recipes.status
  const items = preview === "empty" ? [] : recipes.items

  return (
    <div className="flex h-full min-h-[32rem] flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-1.5">
        <span id="workspace-panes-preview" className="text-xs text-muted-foreground">
          Preview state
        </span>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          spacing={0}
          aria-labelledby="workspace-panes-preview"
          value={preview}
          onValueChange={(value) => {
            if (value) setPreview(value as Preview)
          }}
        >
          {(["live", "empty", "loading", "error"] as const).map((name) => (
            <ToggleGroupItem key={name} value={name} className="h-6 px-2 text-xs capitalize">
              {name}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="min-h-0 flex-1">
        <WorkspacePanes
          items={items}
          status={status}
          error={preview === "error" ? new Error("The recipe store could not be read (simulated).") : recipes.error}
          onRetry={() => setPreview("live")}
          renderStructured={(r, { update }) => (
            <RecipeForm recipe={r} update={update} onDelete={() => void recipes.remove(r.id)} />
          )}
          toRaw={toRaw}
          parseRaw={parseRaw}
          onChange={onChange}
          onCreate={onCreate}
          badge={() => "MD"}
          tooltip={(r) => `Created ${formatDate(r.created)}, modified ${formatDate(r.modified)}`}
        />
      </div>
    </div>
  )
}
