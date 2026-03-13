Create an architecture explainer image for "Supex" — a hand-drawn technical diagram.

IMAGE: Technical architecture diagram, sketched with fine-tip pens
CANVAS: 3200×1800px, 16:9, plain white background

STYLE:
Draw this as if sketched quickly with Centropen fine-tip pens. Lines should wobble slightly with natural hand pressure variation — thicker where the pen pressed harder, thinner on quick strokes. Boxes aren't perfectly rectangular. All text is handwritten with slight unevenness. No digital perfection.

Think through the layout before generating. The diagram has two main zones: the upper zone with three horizontal paths converging on SketchUp, and a lower zone with the VCAD subsystem. The Driver box is a hub connecting both zones.

LAYOUT:
Upper left: Large "Supex" title spanning three lines of height.
Upper right of title: A short underlined tagline, then two feature lines below.
Middle band: Main architecture diagram flowing left to right (Agent/CLI/REPL paths to SketchUp).
Lower band: VCAD subsystem below the Driver, flowing right to the Viewer.

HEADER TEXT:
- Title: "Supex" (large)
- Tagline: "SketchUp + Agentic Coding" (underlined, short!)
- Feature 1: "Agents scripting + introspection feedback"
- Feature 2: "Humans steering Agents + SketchUp GUI + REPL/IDE"

DIAGRAM — UPPER ZONE (SketchUp paths):
Three paths flow from left to right, all ending at "Supex Runtime" inside a large "SketchUp" box on the right.

IMPORTANT ARROW RULES:
- MCP cloud is ONLY between Agent and Driver. MCP does NOT connect to JSON-RPC cloud.
- CLI arrow goes INTO the Driver box (CLI is just another entry point into the same Python driver process).
- Driver has exactly ONE output arrow → into JSON-RPC :9876 cloud (NOT directly to Runtime!)
- The JSON-RPC :9876 cloud then has ONE arrow out → to Runtime
- No box connects directly to Runtime — all connections go THROUGH clouds.

Clouds are wavy outlines only — no background fill, just the wavy border shape with text inside.

ALIGNMENT: The three entry-point boxes (REPL, AI Agent, CLI) must be vertically aligned along the same left column — stacked on top of each other at the left edge of the diagram. They are the starting points, all at the same x-position. The two JSON-RPC clouds (:4433 and :9876) must also be vertically aligned with each other — same x-position, just different rows.

Top path: "REPL\n./repl" box → separate "JSON-RPC :4433" cloud → Runtime (arrives at a different point on Runtime's left edge than the other path).

Middle path (main): "AI Agent\nClaude" box → "MCP" cloud → "Driver\nPython" box → "JSON-RPC :9876" cloud → Runtime (arrives at a separate point on Runtime's left edge).

CLI entry: "CLI\n./supex" box → arrow into the same "Driver" box from below-left. The CLI and MCP are two entry points into the same Driver — show CLI entering the Driver box, not the cloud. A small annotation "CLI + MCP" or two small labels on the Driver box edges can hint at this.

Inside SketchUp box: Runtime has two small dots on its left edge where the two paths arrive (no labels on the dots). Below it, separate boxes for "Supex StdLib" and "SketchUp API". A small 3D cube doodle inside SketchUp box.

Internal dashed arrows:
- Runtime → StdLib
- StdLib → API
- Runtime → API
- API → cube
- cube → Runtime (feedback loop)

DIAGRAM — LOWER ZONE (VCAD subsystem):
Below the main horizontal flow, a second path branches DOWN from the Driver box.

Driver → "JSON-RPC :9877" cloud → "VCAD Sidecar\nRust" box.

The VCAD Sidecar box is the centerpiece of the lower zone. Inside or next to it, show a small pipeline annotation in a handwritten style:
  Loon → BRep → mesh

From the Driver box, a separate arrow goes DOWN-RIGHT via "WebSocket :9878" cloud → "VCAD Viewer\nTauri" box. The Driver relays mesh data from the Sidecar to the Viewer.

From the VCAD Sidecar box, a dashed arrow goes UP-RIGHT labeled "DAE file" curving back toward the SketchUp box (representing filesystem-based mesh exchange). Put a small disk/file icon on this arrow. This arrow should enter SketchUp from below.

Inside or near the VCAD Viewer box, draw a small wireframe 3D solid (e.g. a chamfered cube or a shape with a fillet) to suggest BRep preview.

IMPORTANT VCAD RULES:
- The VCAD Sidecar does NOT connect directly to SketchUp — the mesh is exchanged via filesystem (Sidecar writes DAE file, Driver tells SketchUp to import it). For visual clarity, show this as a dashed arrow from Sidecar to SketchUp labeled "DAE file" with a small disk/file icon on the arrow to suggest filesystem exchange.
- The Driver is the hub: it talks to both SketchUp (:9876) AND the Sidecar (:9877)
- The Viewer connects to the Driver via WebSocket (:9878), NOT to the Sidecar — the Driver relays mesh data. There must be NO arrow between Sidecar and Viewer — they never communicate directly.

COLORS:
Fill boxes with FLAT, UNIFORM pastel tints — single solid color per box, absolutely no gradients, no shading, no color transitions. Every box fill must look like a single marker swatch.
- Pink/red tint: Runtime, StdLib, API, REPL (Ruby)
- Light green tint: Driver, CLI (Python)
- Light blue tint: SketchUp outer box
- Light gray tint (#D5D5D5): AI Agent
- Warm rust tint (#D4A574): VCAD Sidecar, VCAD Viewer (Rust — a flat sandy-tan, clearly distinct from Claude's darker #CA7C5E, NO gradient)

Small legend in bottom-right corner: five colored squares with labels Ruby, Python, SketchUp, Rust, Other. As single line. The "Other" square uses the same light gray as the AI Agent box.

SMALL DETAILS:
Terminal icon near CLI and REPL. Robot doodle near AI Agent. Gear icon near Driver. The wireframe cube inside SketchUp represents 3D models. A small crab doodle (Ferris mascot) near the VCAD Sidecar. The VCAD Viewer gets a small screen/window icon.

AVOID: No logos, no gradients, no digital effects, no screenshots.

REFERENCE: Attached is the previous version of this diagram. Match its hand-drawn style, pen weight, color palette, and overall feel — this is an update, not a redesign.
