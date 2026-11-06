# Reading surfaces

Use this for docs, guides, help pages, articles and changelogs, on the web or in a native app. The reader came to understand something, so the page is first a document of its kind. Documentation reads as documentation, a guide as a guide, a changelog as a changelog. The design serves the reader's question.

Read `.quirk/design/system.md` first if it exists. Build the direction the usual way in [build.md](../build.md), then apply what follows. The rules here replace the component-density rules there, because prose measure and wayfinding matter more than control density.

## Frame and column

Split the page into two parts and treat them differently.

- **The frame** is the masthead, the navigation rail, the ground, the title and section openers, and the way code, tables and callouts are set. Here the product's palette, type and signature move can commit fully, so the page could belong to no other product.
- **The column** is the reading area inside the frame. Keep it calm: a reading face, real contrast, a real measure, nothing performing behind the text.

The product's world never supplies the reading order and never replaces navigation with something a reader has to learn. Keep the color restrained as everywhere else: one accent, used for links, the current page and state.

Good sources for the frame are publishing traditions: reference books, type specimens, timetables, field guides, technical manuals, a newspaper's wayfinding. A tool or instrument the audience operates comes back as a costume on a page meant for reading. Take only its type, palette, density and one signature move.

## The reader's path

Design the shell before the look. Settle these first:

- Navigation, and where the reader stands in it: a sidebar tree, top tabs or inline contents, with the current page marked.
- The title and an opening that answers or frames the reader's question.
- The reading column.
- The way forward: contents, clear section headings, next and previous.

Then name where the frame owns the world and where the signature lives: a masthead, a colored rail, a running head, a margin system, a numbering scheme, a way of setting code or tables. Use one system where it earns its place, never a frame repeated around every element.

## The reading column

- **Measure.** On the web, about 60–75 characters per line with body text near 16px. In a native app, use the platform's body text style and its readable width.
- **Reading face.** Set body text in a face made for reading, with real contrast against its ground. Monospace is for code, parameters and small labels, never running text or headings by default.
- **Type scale.** A fixed rem scale with a tight ratio (1.125–1.2). Clear heading levels, with obvious steps in size and weight. Balance headings and keep body copy free of orphans.
- **Standard forms.** Code blocks, tables, notes and figures take the shapes readers already know, set in the product's type and palette.
- **Consistency.** The same callout looks the same on every page. The same code-block style, table style and link style hold across the whole set. If two pages show a note differently, one is wrong.

## Test with real material

Build and check with the real title, a real opening paragraph, real section names and the hardest content the surface holds: a long code sample, a wide reference table, a diagram. Placeholder text hides the failures that matter. Check a narrow width too, since wide tables and code need a plan there (scroll inside the block, not the page).

## Self-check

- Can a reader tell where they are and where to go next?
- Can they read the body comfortably at the measure you set?
- Cover the product name. Could this be any other product's documentation? If so, the frame hasn't taken the world yet. Push the masthead, rail, ground and openers further.
- Does the page read as an artifact of the world before it reads as a document? Then the world has reached the column. Pull it back to the frame.

## Check-intent flags on docs

Docs reach for two patterns often, and review flags both at P3 with "justify or change". A callout with a colored left stripe is common, so keep it only if the stripe carries meaning that a tinted background or full border wouldn't. Small uppercase labels above headings are fine when they group navigation and noise when they decorate.

For native documents and help screens, add [ios.md](ios.md) or [android.md](android.md).
