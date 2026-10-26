import { useMemo, useState } from "react"
import { toast } from "sonner"

import { useCollection } from "@/lib/mini/store"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import { matchesText, matchesToken, serializeQuery } from "./query"
import { QueryTokens } from "./query-tokens"
import type { Query, QueryKey } from "./types"

type Recipe = {
  id: string
  name: string
  cuisine: string
  course: string
  diets: string[]
  time: number
  rating: number
  ingredients: string[]
}

type RecentSearch = { id: string; query: string; at: number }

type Preview = "live" | "empty" | "loading" | "error"

const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]
const MAX_RECENT = 8

const SEED: Recipe[] = [
  { id: "r01", name: "Green curry with tofu", cuisine: "thai", course: "main", diets: ["vegan", "vegetarian"], time: 35, rating: 4.5, ingredients: ["tofu", "coconut milk", "basil", "lime"] },
  { id: "r02", name: "Pad see ew", cuisine: "thai", course: "main", diets: [], time: 25, rating: 4, ingredients: ["rice noodles", "garlic", "egg"] },
  { id: "r03", name: "Mango sticky rice", cuisine: "thai", course: "dessert", diets: ["vegetarian", "gluten-free"], time: 40, rating: 4.5, ingredients: ["rice", "coconut milk", "mango"] },
  { id: "r04", name: "Tom kha soup", cuisine: "thai", course: "starter", diets: ["gluten-free"], time: 20, rating: 4, ingredients: ["coconut milk", "lime", "mushroom"] },
  { id: "r05", name: "Margherita flatbread", cuisine: "italian", course: "main", diets: ["vegetarian"], time: 30, rating: 4, ingredients: ["basil", "tomato", "mozzarella"] },
  { id: "r06", name: "Slow lemon risotto", cuisine: "italian", course: "main", diets: ["vegetarian", "gluten-free"], time: 55, rating: 4.5, ingredients: ["rice", "lemon", "parmesan"] },
  { id: "r07", name: "Almond biscotti", cuisine: "italian", course: "snack", diets: ["vegetarian"], time: 75, rating: 3.5, ingredients: ["almond", "egg", "flour"] },
  { id: "r08", name: "White bean bruschetta", cuisine: "italian", course: "starter", diets: ["vegan", "vegetarian"], time: 15, rating: 4, ingredients: ["white beans", "garlic", "basil"] },
  { id: "r09", name: "Black bean tacos", cuisine: "mexican", course: "main", diets: ["vegan", "vegetarian"], time: 25, rating: 4.5, ingredients: ["black beans", "lime", "corn tortillas"] },
  { id: "r10", name: "Chicken tinga bowls", cuisine: "mexican", course: "main", diets: ["gluten-free"], time: 45, rating: 4, ingredients: ["chicken", "chipotle", "rice"] },
  { id: "r11", name: "Churros with chocolate", cuisine: "mexican", course: "dessert", diets: ["vegetarian"], time: 50, rating: 5, ingredients: ["flour", "cinnamon", "chocolate"] },
  { id: "r12", name: "Guacamole and chips", cuisine: "mexican", course: "snack", diets: ["vegan", "vegetarian", "gluten-free"], time: 10, rating: 4.5, ingredients: ["avocado", "lime", "corn tortillas"] },
  { id: "r13", name: "Chana masala", cuisine: "indian", course: "main", diets: ["vegan", "vegetarian", "gluten-free"], time: 40, rating: 4.5, ingredients: ["chickpeas", "tomato", "garlic"] },
  { id: "r14", name: "Palak paneer", cuisine: "indian", course: "main", diets: ["vegetarian", "gluten-free"], time: 35, rating: 4, ingredients: ["spinach", "paneer", "garlic"] },
  { id: "r15", name: "Onion bhaji", cuisine: "indian", course: "starter", diets: ["vegan", "vegetarian"], time: 30, rating: 3.5, ingredients: ["onion", "chickpea flour"] },
  { id: "r16", name: "Cardamom rice pudding", cuisine: "indian", course: "dessert", diets: ["vegetarian", "gluten-free"], time: 70, rating: 4, ingredients: ["rice", "cardamom", "milk"] },
  { id: "r17", name: "Miso soup with greens", cuisine: "japanese", course: "starter", diets: ["vegan", "vegetarian"], time: 12, rating: 4, ingredients: ["miso", "tofu", "spinach"] },
  { id: "r18", name: "Salmon rice bowls", cuisine: "japanese", course: "main", diets: ["gluten-free"], time: 30, rating: 4.5, ingredients: ["salmon", "rice", "cucumber"] },
  { id: "r19", name: "Slow-braised pork belly", cuisine: "japanese", course: "main", diets: [], time: 150, rating: 5, ingredients: ["pork belly", "ginger", "soy sauce"] },
  { id: "r20", name: "Sesame snack balls", cuisine: "japanese", course: "snack", diets: ["vegan", "vegetarian"], time: 20, rating: 3, ingredients: ["sesame", "rice", "sugar"] },
]

const SEED_RECENT: RecentSearch[] = [
  { id: "recent-1", query: "cuisine:thai time:<30", at: 2 },
  { id: "recent-2", query: "course:dessert -diet:vegan", at: 1 },
]

const KEYS: QueryKey[] = [
  { key: "cuisine", type: "choice", hint: "thai", values: ["thai", "italian", "mexican", "indian", "japanese"] },
  { key: "course", type: "choice", hint: "main", values: ["starter", "main", "dessert", "snack"] },
  { key: "diet", type: "choice", hint: "vegan", values: ["vegan", "vegetarian", "gluten-free"] },
  { key: "time", type: "number", hint: "<30", values: ["<15", "<30", "<60", ">60"] },
  { key: "rating", type: "number", hint: ">=4", values: [">=4", ">=4.5", "<4"] },
  { key: "ingredient", type: "text", hint: "basil", values: ["basil", "coconut milk", "garlic", "lime", "rice", "tofu"] },
]

const FIELDS: Record<string, (recipe: Recipe) => string | number | string[]> = {
  cuisine: (recipe) => recipe.cuisine,
  course: (recipe) => recipe.course,
  diet: (recipe) => recipe.diets,
  time: (recipe) => recipe.time,
  rating: (recipe) => recipe.rating,
  ingredient: (recipe) => recipe.ingredients,
}

const matches = (recipe: Recipe, query: Query) =>
  query.tokens.every((token) => matchesToken(token, FIELDS[token.key]?.(recipe))) &&
  matchesText(query.text, recipe.name, ...recipe.ingredients)

const HINTS = [
  "/ focus the search",
  "type a key, then : for its values",
  "Space or Enter turn key:value into a chip",
  "-key:value excludes, time:<30 compares",
  "Backspace in an empty box selects, then removes the last chip",
  "click a chip to edit it",
  "Esc closes the list",
]

export default function Demo() {
  const recipes = useCollection<Recipe>("query-tokens-demo", SEED)
  const recents = useCollection<RecentSearch>("query-tokens-demo-recent", SEED_RECENT)
  const [preview, setPreview] = useState<Preview>("live")
  const [query, setQuery] = useState<Query | undefined>(undefined)

  const status = preview === "live" ? recipes.status : preview === "empty" ? "ready" : preview
  const items = useMemo(() => (preview === "empty" ? [] : recipes.items), [preview, recipes.items])
  const shown = useMemo(
    () => (query ? items.filter((recipe) => matches(recipe, query)) : items),
    [items, query]
  )

  const recentQueries = useMemo(
    () => [...recents.items].sort((a, b) => b.at - a.at).map((recent) => recent.query),
    [recents.items]
  )

  const record = (submitted: Query) => {
    const serialized = serializeQuery(submitted)
    const existing = recents.items.find((recent) => recent.query === serialized)
    const write = existing
      ? recents.update(existing.id, { at: Date.now() })
      : recents.add({ id: `recent-${Date.now()}`, query: serialized, at: Date.now() })
    const stale = [...recents.items]
      .sort((a, b) => b.at - a.at)
      .slice(MAX_RECENT - 1)
      .filter((recent) => recent.id !== existing?.id)
    write
      .then(() => Promise.all(stale.map((recent) => recents.remove(recent.id))))
      .catch(() => toast.error("Could not save the recent search"))
  }

  const restoreSamples = () => {
    setPreview("live")
    void recipes.replaceAll(SEED)
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">State preview (demo only)</span>
        <div role="group" aria-label="State preview" className="flex gap-1">
          {PREVIEWS.map((name) => (
            <Button
              key={name}
              size="xs"
              variant={preview === name ? "default" : "outline"}
              aria-pressed={preview === name}
              onClick={() => setPreview(name)}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
      </div>

      <QueryTokens
        keys={KEYS}
        urlParam="q"
        aria-label="Search recipes"
        placeholder="Search recipes, or filter with key:value"
        onChange={setQuery}
        onSubmit={record}
        recent={recentQueries}
        status={status}
        error={new Error("Could not read the recipe collection (simulated).")}
        onRetry={() => setPreview("live")}
        resultCount={shown.length}
        emptyTitle="No recipes yet"
        emptyAction={
          <Button size="sm" variant="outline" onClick={restoreSamples}>
            Restore sample recipes
          </Button>
        }
        boxClassName="lg:grow-0 lg:basis-[57%]"
        toolbar={
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {status === "ready" ? `${shown.length} of ${items.length} recipes` : ""}
          </span>
        }
      >
        <ul role="list" className="overflow-hidden rounded-lg border">
          {shown.map((recipe) => (
            <li
              key={recipe.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-3 py-2 text-sm last:border-b-0"
            >
              <span data-mini="title" className="min-w-40 flex-1 font-medium">
                {recipe.name}
              </span>
              <span className="flex flex-wrap gap-1">
                <Badge variant="secondary">{recipe.cuisine}</Badge>
                <Badge variant="outline">{recipe.course}</Badge>
                {recipe.diets.map((diet) => (
                  <Badge key={diet} variant="outline" className="text-muted-foreground">
                    {diet}
                  </Badge>
                ))}
              </span>
              <span
                data-mini="cell"
                className="w-28 shrink-0 text-right text-xs text-muted-foreground tabular-nums"
              >
                {recipe.time} min · {recipe.rating.toFixed(1)}
              </span>
            </li>
          ))}
        </ul>
      </QueryTokens>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
