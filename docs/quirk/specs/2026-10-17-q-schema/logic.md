# Logic spec: `q-schema`, an explorable data model and class diagram element for `writing-html-artifacts`

**Status**: Approved

`q-schema` is a kit element that draws a read-only data model: tables (entities) as cards with their
fields, and the relationships between them as lines with crow's-foot marks. The reader can pan,
zoom, click a table to light it and its neighbours, and open a drawer with every field. Agents today
have no documented way to draw a data model; the routing evals quietly expect Mermaid's static
`erDiagram`, whose cardinality syntax is easy to get wrong and whose picture can't be explored.

With `notation="class"` the same element draws a UML class diagram instead: classes with their
attributes and methods, joined by inheritance, implementation, composition, aggregation, association
and dependency lines. That replaces Mermaid's `classDiagram` on HTML pages too.

It is the fourth of four specs. It reuses the canvas of the element specified in
[the q-flow logic spec](../2026-10-16-q-flow/logic.md) (layout, zoom, toolbar, group panels, drawer,
focus and dim, keyboard, text list), and builds on
[the q-flow shapes logic spec](../2026-10-17-q-flow-shapes/logic.md), which this branch is stacked on.
Everything the q-flow spec says about the canvas holds here unless this spec changes it.

## Conceptual model

A **data model** has five kinds of thing, all written by the agent as data:

| Thing | What it is | What the agent gives it |
|---|---|---|
| entity | a table, collection or record type | an id, a label and its fields; optionally a kind, a group and a detail |
| field | one column of an entity | a name and a type; optionally its keys, whether it can be empty, and a note |
| relationship | one entity's field pointing at another entity's field | the two fields, the cardinality at each end, and optionally a label |
| group | a named box around entities, which can nest | an id and a label; optionally a parent group |
| kind | a category of entity, shown as the accent on its header | a free-text name and one of the eight chart colors |

A field's **keys** are any of PK (primary key), FK (foreign key) and UK (unique key). One field can
carry several, such as a join table's column that is both part of the primary key and a foreign key.

A relationship runs **from** the field that holds the reference (usually an FK) **to** the field it
references. Each end has a **cardinality**, one of `zero-or-one`, `one`, `zero-or-many` and
`one-or-many`. The cardinality at an end says how many rows of that end's entity match one row of
the other end's entity, and the crow's-foot mark for it is drawn at that end. The optional label is a
verb phrase read from the referenced entity to the referencing one, such as "places" in "Each
customer places zero or many orders".

The agent never writes a position. The element lays the model out itself and draws each entity as a
table-like **card**: a header with the label and the kind accent, then one row per shown field. A
relationship line leaves the card at its own field's row and arrives at the referenced field's row.

A card shows the fields that matter to the picture and folds the rest:

1. every field that carries a key, and every field a relationship uses, always
2. then the other fields, in the agent's order, until the card shows 8 fields
3. then a "+N more" row standing for the fields left out

Shown fields keep the agent's order, so a foreign key listed last still sits last on the card.

The reader explores the model through **focus**. Focusing an entity lights it, its relationships and
the entities directly related to it, dims everything else, and opens the entity's **drawer** with
every field and every relationship. Nothing moves or pulses: a data model has no direction of flow.

Every model also renders as a **text list**, a "Data model as a list" disclosure under the canvas. It
lists every entity with all its fields, then every relationship as a sentence. It is the
screen-reader and no-script view, so it always carries everything the canvas does and more.

### Class notation

A `q-schema` with `notation="class"` is a **class diagram**. Everything above about kinds, groups,
focus, the drawer, the canvas and the text list holds, with these changes:

| Thing | In a class diagram | What the agent gives it |
|---|---|---|
| class | an entity drawn as a UML class | an id and a label; optionally a kind, a group, a stereotype, a detail, attributes and methods |
| attribute | a field of a class | a name; optionally a type, a visibility, whether it is static, and a note |
| method | an operation of a class | a free-text signature such as `parse(src: str) -> Ast`; optionally a visibility, whether it is static or abstract, and a note |
| relationship | a line from one class to another | the two classes and a type; optionally a multiplicity at each end and a label |

- **Stereotype** marks a class as `interface`, `abstract` or `enum`, shown as «interface» above the
  label. It is separate from kind, which stays a free color category. An enum's values are written
  as attributes with no type.
- **Visibility** is `public`, `private`, `protected` or `package`, shown before the member as `+`,
  `-`, `#` or `~`. Static members are underlined and abstract methods italic on the card; the drawer
  and the text list say "static" and "abstract" in words.
- **Relationships join classes, not members**, and read from `from` to `to`:

  | Type | Reads as | Drawn as |
  |---|---|---|
  | `inherits` | from inherits from to | solid line, hollow triangle at to |
  | `implements` | from implements to | dashed line, hollow triangle at to |
  | `composition` | from is composed of to | solid line, filled diamond at from |
  | `aggregation` | from aggregates to | solid line, hollow diamond at from |
  | `association` | from is associated with to | solid line, an open arrow at to only when marked `directed` |
  | `dependency` | from depends on to | dashed line, open arrow at to |

- **Multiplicity** at an end is UML's short form: `1`, `0..1`, `*`, `0..*`, `1..*` or `n..m` with
  whole numbers, drawn as text beside that end.
- **Cards** have three compartments: the header (stereotype, label and kind accent), the attributes
  and the methods.
- **Layout** runs top to bottom with parents above children: the target of `inherits` and
  `implements`, and the whole in `composition` and `aggregation`, sits above the other end.
- **Fold:** a card shows up to 8 member rows, attributes first, then methods. When both overflow,
  each gets 4 rows; when one needs fewer, the other takes the spare rows. One "+N more" row counts
  the rest.
- The text list is titled "Class diagram as a list".

## Data flow

1. **Choosing.** The agent reaches for `q-schema` for every data model, entity-relationship or class
   diagram on an HTML page, adding `notation="class"` for a class diagram. It keeps Mermaid for
   diagrams inside Markdown.
2. **Authoring.** The agent writes a `<q-schema>` tag with a one-sentence `summary` and the model as
   JSON inside it: `kinds`, `groups`, `entities` with their `fields`, and `relationships` that name
   fields as `entity.field`. A class diagram's entities carry attributes in `fields` and `methods`,
   and its relationships name classes and a type.
3. **Building.** The build sees the tag and inlines the graph library that `q-flow` uses (the layout
   engine, the zoom library and the kit's renderer, with their licenses), once per page however many
   `q-flow` and `q-schema` elements it holds. The kit check runs the rules in SC-3 and SC-4 over a
   data model and those in SC-29 and SC-30 over a class diagram. The no-JS fallback carries the text list.
4. **Loading.** The element measures each card's rows, lays the model out with a port on each shown
   field row, fits it to the view and only then shows it. It writes the text list from the same data.
5. **Reading.** The reader pans, zooms, focuses entities and groups, and opens drawers. The theme
   toggle recolors the model live.
6. **Verifying.** Verify waits until every model on the page has finished laying out, then takes its
   screenshots at 375px and 1280px in both themes.

## Key decisions and rationale

- **A new element on q-flow's canvas, not a mode of `q-flow`.** A data model's nodes are tables with
  rows, its lines attach to rows and carry cardinality, and it has no direction or pulse. Bending
  `q-flow`'s contract to hold all that would complicate it for every graph. Sharing the canvas pieces
  keeps zoom, keyboard, drawer and fallbacks the same in both, so a reader who learnt one knows the
  other.
- **Crow's foot notation.** It keeps attributes inside the box and cardinality at the line ends, and
  it is the notation readers of database diagrams expect.
- **Cardinality as four words, not symbols.** Mermaid's two-character pairs such as `}o--||` mirror on
  each side of the line and are easy to get wrong. Words the check can validate make a wrong mark a
  build failure instead of a quiet mistake.
- **Lines attach to field rows.** A line from `orders.customer_id` to `customers.id` shows which
  column holds the reference, which a line between two boxes can't.
- **Keys and related fields always show.** The relationships are the point of the picture, so
  folding a field away must never hide the end of a line. Folding the rest keeps wide tables from
  swamping the canvas.
- **Badges carry text.** PK, FK and UK are written on the row, so meaning never rests on color.
- **Focus lights direct neighbours only.** A data model is usually connected end to end, so following
  relationships transitively, as `q-flow` does with paths, would light the whole model.
- **Class diagrams are a notation of `q-schema`, chosen by an attribute.** They share the card,
  canvas, focus, drawer and text list, so a second element would repeat all of it. One notation per
  model lets the check apply one rule set: keys and cardinality can't leak into a class diagram, and
  methods and UML line types can't leak into a data model.
- **Methods are free-text signatures.** Parameter and return types vary by language; a structured
  form would be much more for agents to write and get wrong, for no gain on the canvas.
- **Class relationships join classes.** UML draws them between class boxes, not members, and most
  class diagrams have no member to point at.

## Behavior and scenarios

The scenarios share one billing model unless they say otherwise. It has kinds "core" (color 1) and
"billing" (color 2); a group Billing; and four entities:

- **Customer** (core, outside every group): id (PK), email (UK), first name, last name, created at
- **Subscription** (billing, in Billing): id (PK), customer id (FK), product title, status, next
  charge date, interval
- **Charge** (billing, in Billing): 15 fields, id (PK), status, total price, currency, scheduled at,
  processed at, error type, error, retry count, tags, note, created at, updated at, then customer id
  (FK) and subscription id (FK, can be empty) last
- **Line item** (billing, in Billing): id (PK), charge id (FK), title, quantity, price

Entity ids are `customer`, `subscription`, `charge` and `line_item`, and field names are written in
the same style (`customer_id`), so relationships name ends such as `charge.customer_id`. There are
four relationships:

- Subscription's customer id to Customer's id, "has", zero or many subscriptions to one customer
- Charge's customer id to Customer's id, "is billed", zero or many charges to one customer
- Charge's subscription id to Subscription's id, "generates", zero or many charges to zero or one
  subscription
- Line item's charge id to Charge's id, "contains", one or many line items to one charge

### Authoring and building

1. **SC-1**
   - **Given** an agent writing an HTML design write-up about billing tables
   - **When** it writes a `q-schema` with the billing model and builds the page
   - **Then** the build inlines the graph library and its license comments, the kit check passes,
     and the page shows four cards, with Subscription, Charge and Line item inside a tinted Billing
     panel and four relationship lines between field rows
   - **Data before:** **Source**: `<q-schema summary="Customers, their subscriptions, and the charges and line items billing creates.">`
     holding the billing model as JSON
   - **Walkthrough:**
     1. The build finds the `q-schema` tag and inlines the graph library with a license comment for
        each part
     2. The kit check reads the JSON: ids unique, field names unique per entity, every relationship
        end names a real entity and field, every cardinality and key known
     3. In the browser, the element measures each card, lays the model out, fits it to view, then
        shows it
   - **Data after:** **Built page**: ✓ graph library inlined once; ✓ license comments present; ✓ kit
     check passed; **Model on screen**: ✓ Customer outside the Billing panel; ✓ Subscription, Charge
     and Line item inside it; ✓ each card's header carries its kind color; ✓ four lines, each between
     the two field rows its relationship names

2. **SC-2**
   - **Given** a page with one `q-flow` and one `q-schema`
   - **When** it is built
   - **Then** the graph library is inlined exactly once, and a page with neither tag carries none of
     it

3. **SC-3**
   - **Given** a model whose data breaks the contract
   - **When** the page is built
   - **Then** the build fails the kit check and names the element and the problem, for each case in
     the table
   - **Kit check failures:**

     | Model data | Result |
     |---|---|
     | two entities with the id "charge" | ✗ fails: duplicate entity id "charge" |
     | Charge lists the field "status" twice | ✗ fails: duplicate field "status" in "charge" |
     | a relationship to "customers.id", which no entity has | ✗ fails: relationship names unknown entity "customers" |
     | a relationship to "customer.uuid", which Customer doesn't have | ✗ fails: relationship names unknown field "customer.uuid" |
     | a relationship end written "customer" with no field | ✗ fails: relationship ends are written `entity.field` |
     | a cardinality of "many" | ✗ fails: unknown cardinality "many"; use zero-or-one, one, zero-or-many or one-or-many |
     | a key of "PRIMARY" | ✗ fails: unknown key "PRIMARY"; use PK, FK or UK |
     | an entity with `x` and `y` | ✗ fails: positions are not allowed; the element lays the model out |
     | nine kinds declared | ✗ fails: at most eight kinds, one per chart color |
     | an entity of kind "audit" that `kinds` doesn't declare | ✗ fails: undeclared kind "audit" |
     | an entity in group "ledger", which `groups` doesn't declare | ✗ fails: unknown group "ledger" |
     | a group whose parent is itself or its own child | ✗ fails: group nesting loops |
     | a detail containing a script, a form or an external image | ✗ fails: detail may hold only paragraphs, lists, code and links |
     | 85 entities | ✗ fails: more than 80 entities |
     | no `summary` | ✗ fails: summary is required |

4. **SC-4**
   - **Given** a model that is valid but likely to read poorly or hide a mistake
   - **When** the page is built
   - **Then** the kit check passes with a warning for each case in the table
   - **Kit check warnings:**

     | Model data | Result |
     |---|---|
     | 34 entities | ✓ passes with a warning: large models read poorly, split them into groups or several models |
     | an entity with 45 fields | ✓ passes with a warning: "charge" has more than 40 fields |
     | Line item's charge id marked FK, and no relationship uses it | ✓ passes with a warning: FK field "line_item.charge_id" has no relationship |
     | a relationship from Charge's status, which isn't marked FK | ✓ passes with a warning: relationship starts at "charge.status", which isn't marked FK |

5. **SC-5**
   - **Given** a page with two `q-schema` models
   - **When** the reader focuses an entity in the first
   - **Then** only the first model changes; each model keeps its own focus, zoom and drawer

### Reading at rest

6. **SC-6**
   - **Given** the billing model on a long write-up
   - **When** the page loads
   - **Then** the model appears already laid out and fitted, nothing moves, the corner toolbar offers
     zoom in, zoom out, fit and expand, and the wheel, drag, pinch and touch inputs behave as in
     `q-flow` (the wheel scrolls the page; Ctrl or Cmd plus wheel or a pinch zooms)

7. **SC-7**
   - **Given** the billing model
   - **When** the page loads
   - **Then** Charge's card shows 8 fields and a "+7 more" row; customer id and subscription id are
     on it even though they are the last two fields; each row shows its name, its type and its key
     badges as text
   - **Data before:** **Charge**: 15 fields; keys on id (PK), customer id (FK), subscription id (FK);
     customer id and subscription id are fields 14 and 15
   - **Walkthrough:**
     1. The element keeps the three key fields, which are also the three fields relationships use
     2. It adds the other fields in order until the card shows 8: status, total price, currency,
        scheduled at, processed at
     3. It counts the rest: error type, error, retry count, tags, note, created at, updated at
   - **Data after:** **Charge card**: ✓ id PK, status, total price, currency, scheduled at, processed
     at, customer id FK, subscription id FK, in that order; ✓ "+7 more" row last

8. **SC-8**
   - **Given** the billing model
   - **When** the page loads
   - **Then** each relationship line runs between the two field rows it names and carries the
     crow's-foot mark for each end's cardinality at that end, with its label on the line
   - **Crow's-foot marks:**

     | Cardinality at an end | Mark drawn at that end |
     |---|---|
     | `zero-or-one` | ✓ a circle and one bar |
     | `one` | ✓ two bars |
     | `zero-or-many` | ✓ a circle and a crow's foot |
     | `one-or-many` | ✓ one bar and a crow's foot |

   - **Data before:** **Relationship**: Line item's charge id to Charge's id, "contains", one or many
     at the Line item end, one at the Charge end
   - **Walkthrough:**
     1. The element gives the charge id row on Line item's card a port, and the id row on Charge's card
        another
     2. The layout routes the line between the two ports
     3. The element draws a bar and a crow's foot where the line meets Line item, and two bars where
        it meets Charge
   - **Data after:** **Line on screen**: ✓ starts at Line item's charge id row; ✓ ends at Charge's id
     row; ✓ bar and crow's foot at the Line item end; ✓ two bars at the Charge end; ✓ "contains" on
     the line

9. **SC-9**
   - **Given** an Employee entity whose manager id (FK) points at its own id
   - **When** the page loads
   - **Then** the relationship draws as a short loop off the side of the card, from the manager id row
     back to the id row, with both marks and its label
   - **Data before:** **Relationship**: Employee's manager id to Employee's id, "manages", zero or many
     at the manager id end, zero or one at the id end
   - **Data after:** **Employee card**: ✓ one loop from the manager id row to the id row; ✓ circle and
     crow's foot at the manager id end; ✓ circle and bar at the id end; ✓ "manages" beside the loop

10. **SC-10**
    - **Given** the reader toggles the page theme from light to dark
    - **When** the theme changes
    - **Then** the model recolors at once, kind accents, badges and marks included, with no re-layout
      and no flash

11. **SC-11**
    - **Given** the billing model in the page column
    - **When** the reader presses expand
    - **Then** the model fills the screen with the same focus and zoom, and Escape or the button returns
      it to the page

### Focusing

12. **SC-12**
    - **Given** the billing model, nothing focused
    - **When** the reader clicks Subscription
    - **Then** Subscription, its two relationships, Customer and Charge stay lit; Line item, the
      "contains" line and the "is billed" line dim; and the drawer opens with every Subscription field
      and both relationships
    - **Data before:** **Model**: nothing focused; drawer closed
    - **Walkthrough:**
      1. The reader clicks Subscription's card
      2. The element finds its relationships: to Customer ("has") and from Charge ("generates")
      3. It lights those two lines and the entities at their other ends, and dims the rest
    - **Data after:** **Model**: ✓ Subscription, Customer and Charge lit; ✓ the "has" and "generates"
      lines lit; ✓ Line item and the "contains" line dimmed, because Line item is not directly related
      to Subscription; ✓ the "is billed" line between Charge and Customer dimmed, because it isn't one
      of Subscription's relationships; **Drawer**: ✓ open beside the model; ✓ shows "Subscription",
      kind "billing", the detail, all six fields with type, keys and whether each can be empty, and
      two relationship buttons
    - **Drawer contents:**

      | Part | Shown |
      |---|---|
      | fields | ✓ every field with its type, key badges, "can be empty" where it applies, and its note |
      | relationship buttons | ✓ "has: Customer (customer id → id)"; ✓ "generates: Charge (subscription id → id)" |

13. **SC-13**
    - **Given** Subscription focused with its drawer open
    - **When** the reader clicks the "generates: Charge" button
    - **Then** focus moves to Charge: Charge, Customer, Subscription and Line item light, and the drawer
      shows all 15 of Charge's fields

14. **SC-14**
    - **Given** nothing focused
    - **When** the reader clicks the "+7 more" row on Charge's card
    - **Then** Charge is focused and its drawer opens, as clicking the card does, listing all 15 fields

15. **SC-15**
    - **Given** an entity focused
    - **When** the reader presses Escape, clicks empty canvas, or closes the drawer
    - **Then** focus clears, everything returns to full color and the drawer closes

16. **SC-16**
    - **Given** nothing focused
    - **When** the reader clicks the Billing group's header
    - **Then** the view zooms to fit Billing, everything outside it dims, and no drawer opens

### Keyboard, motion and phones

17. **SC-17**
    - **Given** a keyboard user tabbing through the page
    - **When** they tab into the model
    - **Then** focus lands on one entity, and the keys work as in the table
    - **Keyboard:**

      | Key | Result |
      |---|---|
      | Tab | ✓ enters the model on one entity, and a second Tab leaves it |
      | arrow keys | ✓ move to the nearest entity in that direction |
      | Enter | ✓ focuses the entity, as a click does, and announces it, for example "Subscription, billing, 6 fields, 2 relationships" |
      | Escape | ✓ clears focus and closes the drawer |
      | + and - | ✓ zoom in and out |
      | 0 | ✓ fits to view |

18. **SC-18**
    - **Given** the reader has reduced motion turned on
    - **When** they focus an entity, zoom or fit
    - **Then** nothing animates: zooms and fits jump instead of easing, and focus looks the same as with
      motion on

19. **SC-19**
    - **Given** the billing model on a 375px phone
    - **When** the reader taps Charge
    - **Then** Charge and its neighbours light as on desktop, and the drawer opens as a bottom sheet over
      the lower part of the model

### Text list and fallbacks

20. **SC-20**
    - **Given** the billing model
    - **When** the reader opens "Data model as a list"
    - **Then** it lists each group with its entities, each entity with all its fields as name, type,
      keys and whether it can be empty, then each relationship as a sentence; a "many" end uses the
      entity's label made plural by English spelling rules (Subscription to Subscriptions, Category
      to Categories, Address to Addresses), so an odd plural such as Person reads as Persons
    - **Data before:** **Relationship**: Subscription's customer id to Customer's id, "has", zero or
      many at the Subscription end, one at the Customer end
    - **Walkthrough:**
      1. The element starts the sentence at the referenced entity, with its label as written: "Each
         Customer"
      2. It adds the label and the cardinality at the Subscription end, with the label made plural by
         English spelling rules: "has zero or many Subscriptions"
      3. It adds the cardinality at the Customer end, read the other way: "each Subscription has one
         Customer"
      4. It closes with the fields: "(subscription.customer_id → customer.id)"
    - **Data after:** **Text list**: ✓ "Each Customer has zero or many Subscriptions, and each
      Subscription has one Customer (subscription.customer_id → customer.id)"; ✓ a relationship with
      no label uses "has" in its place

21. **SC-21**
    - **Given** a reader whose browser runs no scripts
    - **When** the page loads
    - **Then** the canvas shows a one-line notice and the "Data model as a list" disclosure is open,
      listing every entity, field and relationship

22. **SC-22**
    - **Given** a model the layout engine fails on
    - **When** the page loads
    - **Then** the canvas shows a one-line notice that the model could not be drawn, the text list
      opens, and the rest of the page works

23. **SC-23**
    - **Given** a screen-reader user
    - **When** they reach the model
    - **Then** they hear its summary, can open the text list, and find everything the canvas and the
      drawers show

### Other surfaces

24. **SC-24**
    - **Given** a tier-2 app or a companion screen's `content`
    - **When** it renders a `q-schema` tag
    - **Then** it behaves as on a tier-1 page; the built app inlines the graph library only because a
      `q-flow` or `q-schema` tag is used; a `q-schema` in a companion option's `html` breaks the rule
      against interactive elements in option cards

25. **SC-25**
    - **Given** verify running on a page with a model
    - **When** it takes screenshots
    - **Then** it waits until every model has finished laying out, so no screenshot shows a blank canvas
      or cards piled in one corner

### Class diagrams

These scenarios share one parser class diagram. It has kinds "api" (color 1) and "internals"
(color 3), and these classes:

- **Parser** (api, interface): method `+ parse(src: str) -> Ast`
- **RecursiveDescentParser** (internals): 6 attributes, `+ max_depth: int` (static),
  `- lexer: Lexer`, `- pos: int`, `- depth: int`, `- errors: list`, `- options: dict`; 7 methods,
  `+ parse(src: str) -> Ast`, `- expr() -> Ast`, `- term() -> Ast`, `- factor() -> Ast`,
  `- expect(kind: TokenKind) -> Token`, `- peek() -> Token`, `- error(msg: str)`
- **Lexer** (internals): attributes `- src: str`, `- pos: int`; methods `+ next() -> Token`,
  `+ peek() -> Token`
- **Token** (internals): attributes `+ kind: TokenKind`, `+ text: str`, `+ line: int`
- **TokenKind** (internals, enum): NUMBER, IDENT, PLUS, LPAREN, RPAREN, EOF
- **Ast** (api, abstract): method `+ accept(v: Visitor)` (abstract)
- **BinaryExpr** (api): attributes `+ left: Ast`, `+ op: TokenKind`, `+ right: Ast`

Class ids are the labels in lower case (`parser`, `recursivedescentparser`, `lexer` and so on). The
relationships are:

- RecursiveDescentParser `implements` Parser
- RecursiveDescentParser `composition` Lexer, multiplicity `1` at Lexer
- Lexer `dependency` Token, label "produces"
- Token `association` TokenKind, `directed`
- BinaryExpr `inherits` Ast
- BinaryExpr `aggregation` Ast, multiplicity `2` at Ast, label "operands"
- Parser `dependency` Ast, label "returns"

26. **SC-26**
    - **Given** an agent writing an HTML technical overview of the parser
    - **When** it writes a `q-schema` with `notation="class"` and the parser diagram, and builds the page
    - **Then** the kit check passes, and the page shows seven class cards with header, attribute and
      method compartments, Parser and Ast above the classes that implement or inherit them, and each
      line carrying its UML marker
    - **Data before:** **Source**: `<q-schema notation="class" summary="The parser's public interface, its recursive descent implementation and the AST it returns.">`
      holding the parser diagram as JSON
    - **Walkthrough:**
      1. The kit check applies the class rules: class ids unique, members unique per class, every
         relationship names a real class, every type, stereotype, visibility and multiplicity known
      2. In the browser, the element lays the diagram out top to bottom with parents above
    - **Data after:** **Diagram on screen**: ✓ Parser's header reads «interface» above "Parser"; ✓ Ast's
      header reads «abstract» and its `accept` method is italic; ✓ TokenKind's header reads «enum» and
      lists its six values; ✓ Parser above RecursiveDescentParser; ✓ Ast above BinaryExpr; ✓
      `max_depth` underlined
    - **UML markers:**

      | Relationship | Drawn as |
      |---|---|
      | RecursiveDescentParser implements Parser | ✓ dashed line, hollow triangle at Parser |
      | BinaryExpr inherits Ast | ✓ solid line, hollow triangle at Ast |
      | RecursiveDescentParser composition Lexer | ✓ filled diamond at RecursiveDescentParser; "1" beside Lexer |
      | BinaryExpr aggregation Ast | ✓ hollow diamond at BinaryExpr; "2" beside Ast; "operands" on the line |
      | Token association TokenKind, directed | ✓ solid line, open arrow at TokenKind |
      | Lexer dependency Token | ✓ dashed line, open arrow at Token; "produces" on the line |

27. **SC-27**
    - **Given** the parser diagram
    - **When** the page loads
    - **Then** RecursiveDescentParser's card shows 4 attributes, 4 methods and a "+5 more" row, and
      Lexer's card shows both attributes and both methods with no "+N more" row
    - **Data before:** **RecursiveDescentParser**: 6 attributes, 7 methods; **Lexer**: 2 attributes,
      2 methods
    - **Walkthrough:**
      1. RecursiveDescentParser has 13 members, more than 8, and both compartments need more than 4
         rows, so each gets 4
      2. It shows `max_depth`, `lexer`, `pos`, `depth`, then `parse`, `expr`, `term`, `factor`
      3. It counts the rest: 2 attributes and 3 methods
    - **Data after:** **RecursiveDescentParser card**: ✓ 4 attribute rows; ✓ 4 method rows; ✓ "+5 more"
      row last; **Lexer card**: ✓ 2 attribute rows; ✓ 2 method rows; ✓ no "+N more" row
    - **Fold examples:**

      | Attributes, methods | Shown | "+N more" |
      |---|---|---|
      | 6, 7 | ✓ 4 attributes, 4 methods | ✓ "+5 more" |
      | 2, 9 | ✓ 2 attributes, 6 methods | ✓ "+3 more" |
      | 11, 1 | ✓ 7 attributes, 1 method | ✓ "+4 more" |
      | 3, 4 | ✓ all 7 | ✓ none |

28. **SC-28**
    - **Given** the parser diagram, nothing focused
    - **When** the reader clicks Lexer
    - **Then** Lexer, RecursiveDescentParser and Token stay lit with the two lines between them, the rest
      dims, and the drawer lists every attribute and method with its visibility in words, "static" and
      "abstract" where they apply, and buttons for the two relationships
    - **Drawer contents:**

      | Part | Shown |
      |---|---|
      | attributes | ✓ "private src: str"; ✓ "private pos: int" |
      | methods | ✓ "public next() -> Token"; ✓ "public peek() -> Token" |
      | relationship buttons | ✓ "part of: RecursiveDescentParser"; ✓ "produces: Token" |

29. **SC-29**
    - **Given** a class diagram whose data breaks the contract
    - **When** the page is built
    - **Then** the build fails the kit check and names the element and the problem, for each case in
      the table, as well as for the coordinates, kinds, groups, detail, size and summary cases in SC-3
    - **Kit check failures:**

      | Class diagram data | Result |
      |---|---|
      | `notation="uml"` | ✗ fails: unknown notation "uml"; use class, or leave it out for a data model |
      | two classes with the id "lexer" | ✗ fails: duplicate class id "lexer" |
      | Lexer lists the attribute "pos" twice, or the method `peek() -> Token` twice | ✗ fails: duplicate member in "lexer" |
      | a relationship to "tokenizer", which no class has | ✗ fails: relationship names unknown class "tokenizer" |
      | a relationship end written "lexer.next" | ✗ fails: class relationships join classes, not members |
      | a relationship type of "extends" | ✗ fails: unknown relationship type "extends"; use inherits, implements, composition, aggregation, association or dependency |
      | a visibility of "internal" | ✗ fails: unknown visibility "internal"; use public, private, protected or package |
      | a stereotype of "mixin" | ✗ fails: unknown stereotype "mixin"; use interface, abstract or enum |
      | a multiplicity of "many" | ✗ fails: unknown multiplicity "many"; use 1, 0..1, *, 0..*, 1..* or n..m |
      | Ast inherits BinaryExpr while BinaryExpr inherits Ast | ✗ fails: inheritance loops |
      | a field with a key, or a relationship with a cardinality | ✗ fails: keys and cardinality belong to data models; this is a class diagram |
      | in a data model, an entity with methods or a stereotype, or a relationship with a type | ✗ fails: methods, stereotypes and relationship types belong to class diagrams; add notation="class" |

30. **SC-30**
    - **Given** a class diagram that is valid but likely to read poorly or hide a mistake
    - **When** the page is built
    - **Then** the kit check passes with a warning for each case in the table
    - **Kit check warnings:**

      | Class diagram data | Result |
      |---|---|
      | 34 classes | ✓ passes with a warning: large diagrams read poorly, split them into groups or several diagrams |
      | a class with 45 members | ✓ passes with a warning: "recursivedescentparser" has more than 40 members |
      | a class implements Lexer, which isn't marked interface | ✓ passes with a warning: "lexer" is implemented but isn't an interface |
      | a class inherits Parser, which is marked interface | ✓ passes with a warning: "parser" is an interface; use implements |

31. **SC-31**
    - **Given** the parser diagram
    - **When** the reader opens "Class diagram as a list"
    - **Then** it lists every class with its stereotype, every attribute and method with visibility,
      static and abstract in words, then each relationship as a sentence, as in the table
    - **Relationship sentences:**

      | Relationship | Sentence |
      |---|---|
      | implements | ✓ "RecursiveDescentParser implements Parser" |
      | inherits | ✓ "BinaryExpr inherits from Ast" |
      | composition, 1 at Lexer | ✓ "RecursiveDescentParser is composed of 1 Lexer" |
      | aggregation, 2 at Ast, "operands" | ✓ "BinaryExpr aggregates 2 Ast (operands)" |
      | association, directed | ✓ "Token is associated with TokenKind" |
      | dependency, "produces" | ✓ "Lexer depends on Token (produces)" |

### Choosing

32. **SC-32**
    - **Given** an agent asked to "add an entity-relationship diagram of the users, subscriptions, and
      charges tables to the HTML design write-up"
    - **When** it writes the page
    - **Then** it writes a `q-schema`, not a Mermaid `erDiagram`; asked for a class diagram of parser
      interfaces in an HTML technical overview it writes a `q-schema` with `notation="class"`, not a
      Mermaid `classDiagram`; asked for either diagram inside a README it writes Mermaid

## Scope and non-goals

In scope:

- the `q-schema` element: authoring contract, layout with a port per field row, entity cards with
  folded fields, key badges, crow's-foot marks, relationship labels, self-relationships, group panels,
  kinds, focus and dim, the drawer, zoom and pan, expand, keyboard, the text list
- the class notation: classes with stereotypes, attributes and methods, the six UML relationship
  types with multiplicities, top-to-bottom layout, and its own check rules in SC-29 and SC-30
- sharing `q-flow`'s canvas pieces by factoring them out, with no change to how `q-flow` behaves
- the kit check rules and warnings in SC-3, SC-4, SC-29 and SC-30
- inlining the graph library once per page for `q-flow` and `q-schema` together
- tier-1 pages, tier-2 apps and companion screen `content`
- verify waiting for layout
- the skill's text: the `q-schema` versus Mermaid rule in SKILL.md, the design reference and the
  report and components template rules; the generated `q-schema` entry in the components reference;
  the element list in SKILL.md; the routing evals for ER and class diagrams
- one example page with the billing model and the parser class diagram

Not in scope:

- stepping through records or showing sample rows per table
- editing the model
- generating the model from SQL DDL or ORM models
- generics, notes attached to classes, and relationships that point at a single member
- many-to-many relationships drawn without a join table
- relationships across several fields at once (composite foreign keys)
- lanes, a `direction` attribute and the pulse, which `q-flow` has and a data model doesn't need
- replacing Mermaid inside Markdown

## Success criteria

- The routing evals show the agent choosing `q-schema` for an ER, data model or class diagram on an
  HTML page (with `notation="class"` for the class diagram), and Mermaid for the same diagrams inside
  Markdown.
- Verify screenshots of the billing example at 375px and 1280px in both themes show four cards in a
  Billing panel layout, lines that end at field rows, a crow's-foot mark at every line end, and a
  "+7 more" row on Charge; screenshots of the parser example show compartmented class cards with a
  stereotype header, a UML marker at each line end, and parents above children.

## Decisions Locked

Contract:

- The tag is `<q-schema summary="…">` with a JSON `<script type="application/json">` child, and it
  inlines the same graph library as `q-flow` (the layout engine and the zoom library).
- `kinds` work as in `q-flow`: a name mapped to chart color 1 to 8, used as the entity header accent.
- `groups` are `{id, label, parent?}`, drawn as tinted panels by the same rules as `q-flow` groups.
- `entities` are `{id, label, kind?, group?, detail?, fields}`; each field is
  `{name, type, key?, nullable?, note?}`, where `key` is PK, FK or UK, or a list of them.
- `relationships` are `{from: "entity.field", to: "entity.field", from_card, to_card, label?}`, with
  cardinality one of `zero-or-one`, `one`, `zero-or-many` and `one-or-many`.

Drawing:

- Each entity is a table-like card whose header holds the label and the kind accent.
- A card always shows every key field and every field a relationship uses, then other fields in
  order up to about 8 in total, then a "+N more" row.
- Each field row shows the name, the type and the key badges, which carry text.
- Relationship lines run from the FK field's row to the referenced field's row, using a layout port
  per field row, with crow's-foot marks at each end and the optional label on the line.

Exploring:

- The canvas behaves as in `q-flow`: pan, Ctrl or Cmd plus wheel or a pinch to zoom, the toolbar and
  expand; the wheel scrolls the page.
- Clicking an entity lights it, its relationships and the directly related entities, dims the rest,
  and opens the drawer with every field (type, keys, nullability, note) and its relationships as
  buttons that refocus the other entity.
- Clicking "+N more" opens the drawer.
- Clicking a group zooms to it.
- The keyboard model is the same as `q-flow`'s.
- There is no pulse, and so reduced motion has nothing to stop beyond zoom easing.

Text list and fallback:

- The text list gives every entity with all its fields, as name, type, keys and nullability.
- Each relationship reads as a sentence, for example "Each customer places zero or many orders
  (orders.customer_id → customers.id)".

Kit check:

- Fails: a duplicate entity id, a duplicate field name within an entity, a relationship naming an
  unknown entity or field, an unknown cardinality, an unknown key value, coordinates, more than 8
  kinds, more than about 80 entities, no `summary`.
- Warns: more than about 30 entities, an entity with more than about 40 fields, an FK field no
  relationship uses, a relationship whose `from` field isn't marked FK.
- The JavaScript renderer and the Python kit check stay in step.

Choosing and scope:

- Data model and ER diagrams on HTML pages use `q-schema`; Mermaid keeps diagrams inside Markdown.
- Class diagrams on HTML pages also use `q-schema` (chosen at review over keeping them on Mermaid);
  evals 14 and 16 both move to `q-schema`.

Class notation (chosen at review):

- A `notation="class"` attribute makes a model a class diagram; one model is one notation.
- Methods are `{signature, visibility?, static?, abstract?, note?}` with a free-text signature;
  attributes reuse the field shape as `{name, type?, visibility?, static?, note?}`.
- Relationship types are `inherits`, `implements`, `composition`, `aggregation`, `association` and
  `dependency`, joining class to class, with optional multiplicity at each end.
- A `stereotype` field marks `interface`, `abstract` or `enum`, separate from `kind`; enum values are
  attributes with no type.
- Parents sit above children, and a card folds at 8 rows across attributes and methods with a
  "+N more" row.

Text list (chosen at review):

- A "many" end in a relationship sentence uses the entity label made plural by English spelling
  rules, with no `plural` field.
- The work stays out of step-through, sample rows, editing, generation from DDL or ORM models, and
  many-to-many without a join table.
- `q-schema` lives in its own class and shares `q-flow`'s canvas pieces by factoring them, without
  changing their behavior, so the parallel q-flow traces and `q-sequence` work conflicts as little as
  possible.

Decided in this spec (assumed defaults, open to review):

- The exact fold threshold is 8 shown fields; a card with more than 8 key or related fields shows
  them all and no other fields.
- Shown fields keep the agent's order rather than moving keys to the top.
- The label reads from the referenced entity, and the text-list sentence adds the reverse
  cardinality with "has", as in SC-20; a missing label reads as "has".
- Focus lights direct neighbours only, not the transitive closure.
- Clicking "+N more" also focuses the entity, as clicking anywhere on the card does.
- A self-relationship draws as a loop off the card's side (SC-9).
- Unknown and malformed group, kind and detail data fail as they do in `q-flow` (SC-3).
- `q-schema` has no lanes, no `direction` attribute and no pulse.
- `q-schema` works wherever `q-flow` works: tier-1 pages, tier-2 apps and companion screen content.
- The disclosure is titled "Data model as a list", or "Class diagram as a list" in class notation.
- Visibility is one of four words shown as `+ - # ~`; static is underlined and abstract italic on the
  card, and both are written out in the drawer and the text list.
- Composition and aggregation put the diamond at `from`, the whole; an association draws an arrow
  only when marked `directed`.
- Multiplicity uses UML's short form and is checked.
- When both compartments overflow they get 4 rows each; otherwise one gives its spare rows to the
  other.
- The class check rules in SC-29 and SC-30 mirror the data model rules, plus inheritance cycles and
  the interface warnings.

## Industry Insights

The brainstorm's findings, re-sourced on 2026-10-17 with web search (Brave search was unavailable in
the session). Pages marked "snippet" were seen in search results only, not opened.

- **Crow's foot is the working notation.** Entities are plain rectangles with their attributes inside,
  and cardinality sits at the connector ends; it is the notation most schemas are drawn in and most
  tools render by default
  ([dbschema](https://dbschema.com/blog/design/choosing-an-er-notation-your-team-can-read/),
  [dbdiagram](https://blog.dbdiagram.io/mastering-crows-foot-notation-a-comprehensive-guide-for-database-design/),
  [draw.io](https://www.drawio.com/docs/tutorials/crows-foot-notation/)). These are vendor sources;
  no controlled readability study turned up, and dbschema calls Chen clearer for teaching.
- **Space entities apart and limit crossings.** Put related entities near each other to keep lines
  short and crossings few, don't cram entities together, and split a diagram past about 15 to 20
  entities ([Miro](https://miro.com/diagramming/how-to-draw-an-er-diagram/)). Crossing minimisation
  is NP-hard, so engines use heuristics
  ([Terrastruct](https://terrastruct.com/blog/post/diagram-layout-engines-crossing-minimization/index.html),
  snippet).
- **Lines attach to rows in table diagram tools.** draw.io pins a connector to a single row and keeps
  it attached as the row moves
  ([draw.io ER tables](https://www.drawio.com/docs/diagram-types/entity-relationship-tables/)), and
  DBML declares references column to column ([DBML](https://dbml.dbdiagram.io/docs/), snippet).
- **Mermaid's cardinality syntax is two symbol pairs per line.** `|o`, `||`, `}o` and `}|` (mirrored on
  the other side), outer character the maximum and inner the minimum, with `--` or `..` between
  ([Mermaid ER syntax](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)). Users report
  the symbols as unclear and aliases that break parsing
  ([mermaid #7475](https://github.com/mermaid-js/mermaid/issues/7475),
  [mermaid #7351](https://github.com/mermaid-js/mermaid/issues/7351), snippets), and one
  reimplementation silently drops relationships with an unrecognised cardinality
  ([zombie-mermaid #1747](https://github.com/dfadler/zombie-mermaid/issues/1747)). No public evidence
  of agents specifically getting it wrong turned up; that rests on the brainstorm's observation.
- **One ELK port per field row.** React Flow's ELK example gives each node `FIXED_ORDER` port
  constraints with target ports on the west side and source ports on the east, matching port ids to
  handles ([React Flow elkjs multiple handles](https://reactflow.dev/examples/layout/elkjs-multiple-handles));
  the documented workaround for wrong layouts with several handles is one ELK port per handle
  ([xyflow #4248](https://github.com/xyflow/xyflow/discussions/4248), snippet).
- **Fixed port constraints have open ELK bugs.** An edge between two ports of the same node can route
  outside it ([elkjs #177](https://github.com/kieler/elkjs/issues/177)), which matters for
  self-relationships, and fixed constraints on nested nodes can throw
  ([elk #813](https://github.com/eclipse-elk/elk/issues/813), snippet; see also #1192 in the q-flow
  spec). Groups make every model a nested layout, so test both early.

## Deferred Ideas

Build-only questions for the tech spec:

- `[tech-spec]` Which `q-flow` canvas pieces are factored out (layout call, zoom setup, toolbar, group
  panels, drawer, focus and dim, keyboard, text-list shell, readiness signal) and the shape of the
  shared code, so `q-flow` behaves exactly as before.
- `[tech-spec]` ELK settings for cards with field ports: algorithm, port side and order constraints
  (and the open ELK bug with fixed port constraints in hierarchical layouts), spacing that keeps
  crossings down, and which side of a card a line leaves from.
- `[tech-spec]` How the "+N more" row and folded fields work with ports: folded fields never carry a
  port, because every related field is shown.
- `[tech-spec]` The crow's-foot marker geometry and how marks stay readable at low zoom.
- `[tech-spec]` How the kit check and the renderer share the field-folding and sentence rules so
  they stay in step.
- `[tech-spec]` How the build and the library check detect `q-schema` alongside `q-flow` to inline
  the graph library once.
- `[tech-spec]` UML marker geometry (triangles, diamonds, arrows) and how class notation sets the
  layout direction and reverses `inherits` and `implements` lines so parents land above.

Product ideas left out of this version: stepping through records or sample rows, editing,
generating from SQL DDL or ORM models, generics, notes attached to classes, relationships to a
single class member, many-to-many without a join table, composite
foreign keys, and following relationships beyond direct neighbours on focus.

## Glossary

- **data model**: one `q-schema` element and its data.
- **entity**: one table, collection or record type, drawn as a card.
- **field**: one column of an entity, drawn as a row on its card when shown.
- **key badge**: the PK, FK or UK text on a field row.
- **relationship**: a line from the field that holds a reference to the field it references.
- **cardinality**: how many rows at one end of a relationship match one row at the other end.
- **crow's-foot mark**: the circle, bar and fork drawn at a line end to show its cardinality.
- **fold**: leaving a field off its card, counted in the "+N more" row.
- **kind**: a free-text category of entity with one chart color, declared once per model.
- **group**: a named box around entities; groups can nest.
- **focus**: the state where one entity and its direct neighbours, or one group, are lit and the rest
  dimmed.
- **drawer**: the panel inside the canvas that shows a focused entity's fields and relationships.
- **text list**: the "Data model as a list" disclosure that carries the whole model as text.
- **notation**: whether a `q-schema` is a data model (the default) or a class diagram.
- **class**: an entity in class notation, drawn as a card with attribute and method compartments.
- **attribute**: a field of a class.
- **method**: an operation of a class, written as a free-text signature.
- **stereotype**: the «interface», «abstract» or «enum» mark on a class.
- **visibility**: public, private, protected or package, shown as `+ - # ~`.
- **multiplicity**: UML's count at a class relationship end, such as `1` or `0..*`.

## Status & amendments

**Status**: Approved

**Amendments:**

- 2026-10-17: class diagrams move from Mermaid into `q-schema` as `notation="class"`, and the
  relationship sentence makes labels plural by English spelling rules (both chosen at review,
  before implementation).
