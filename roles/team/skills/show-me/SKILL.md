---
name: show-me
description: Help the user understand the current topic visually with concise diagrams, code-shape sketches, and focused HTML artifacts.
disable-model-invocation: true
---

Help the user understand the current topic of conversation visually. Skip the preamble and keep prose brief. Pick the smallest view that makes the key point clear.

- Show logic or an algorithm as pseudocode:

```text
on(save)
  if content is unchanged
    return cached result
  write new content
  return fresh result
```

- Show runtime control flow as a call tree:

```text
submitForm
  createSession
    persistPrompt
    launchAgent
  navigateToSession
```

- Show UI structure as a component tree, including state and module boundaries that matter:

```tsx
<SessionPage> (apps/example/src/routes/session.tsx)
  useSessionEvents()
  <SessionToolbar>
    <RunSkillButton> (packages/ui)
```

- Show file responsibility or a broad refactor as a shallow file tree:

```text
src/
├── commands/       # parses user actions
├── sessions/       # owns session state
└── transport/      # sends API requests
```

- Show component interaction, control flow, or data flow as a drawn diagram (boxes and arrows, or a sequence of lanes). Never use Mermaid: neither the Claude Code CLI nor the desktop app renders it, so the user only sees raw source. Draw it the way the "Where to draw" section below says.

- Use `diff` when the point is what changes and the surrounding shape already exists. Match the diff shape to the topic.

For a component change:

```diff
 <SessionPage>
   useSessionEvents()
   <SessionToolbar>
+    <RunSkillButton />
   <SessionTimeline>
+    <SkillResultCard />
```

For a file-layout change:

```diff
 src/
 ├── commands/
+│   └── show-me.ts       # expands the slash command
 ├── sessions/
-└── transport.ts
+└── transport/
+    ├── client.ts
+    └── stream.ts
```

For a call-tree or call-stack change:

```diff
 submitForm
   createSession
     persistPrompt
+    expandSkillMention
     launchAgent
-  navigateToSession
+  navigateToSession
+    subscribeToEvents
```

For a state or control-flow change:

```diff
 on(save)
-  write content
+  if content is unchanged
+    return cached result
+  write new content
+  invalidate cache
```

- Show the whole block when most of it is new, when omitted context would hide ownership or order, or when the user needs a copyable target shape:

```ts
function expandSkill(command: string): string {
  const skillName = command.slice(1)
  return `use the ${skillName} skill`
}
```

- For a visual UI, layout, state comparison, or concept too dense for a text sketch, make one focused visual — a diagram, an infographic, or a short slide deck, whichever fits the point. Match the product's colors, type, spacing, and components; use real labels and data; support desktop and mobile. Draw it the way the "Where to draw" section below says.

### Where to draw

Drawn diagrams and visuals go to the first of these that exists in the session:

1. An inline visual tool that renders SVG or HTML in the chat (for example `show_widget` in the Claude desktop app). Follow its own setup instructions (call its `read_me` first if it has one). Put the explanation in your reply text, not inside the visual.
2. Otherwise (for example the terminal CLI), write one HTML file and open it for the user:

```
Bash(open path/to/show-me-{description}.html)
```

### Text sketches with Chinese or other wide characters

Chinese, Japanese, and Korean characters are not exactly two monospace columns wide in most chat fonts, so anything aligned after them inside a code block drifts out of line. In pseudocode, call trees, component trees, and file trees:

- Only indentation may carry structure. Never line up arrows, `#` comments, or columns after wide-character text.
- If alignment matters (a mapping like "question → view"), use a Markdown table or a drawn visual instead of a code block.

### guidance

Place each visual next to the short text it supports. Keep only the calls, files, props, states, and boundaries needed to answer the user's current question or the options to resolve the current discussion point.

You may use one of these, you may use several, it is unlikely you will use all of them. Use your judgement and don't overwhelm the user.
