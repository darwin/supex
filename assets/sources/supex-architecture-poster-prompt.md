Create a GitHub README hero image for "Supex" — a hand-drawn technical diagram.

IMAGE: Technical architecture diagram, sketched with fine-tip pens
CANVAS: 3200×1800px, 16:9, plain white background

STYLE:
Draw this as if sketched quickly with Centropen fine-tip pens. Lines should wobble slightly with natural hand pressure variation — thicker where the pen pressed harder, thinner on quick strokes. Boxes aren't perfectly rectangular. All text is handwritten with slight unevenness. No digital perfection.

Think through the layout before generating. The diagram has a shared cloud that receives arrows from two different sources — make sure this is clear.

LAYOUT:
Upper left: Large "Supex" title spanning three lines of height.
Upper right of title: A short underlined tagline, then two feature lines below.
Bottom half: Full-width architecture diagram flowing left to right.

HEADER TEXT:
- Title: "Supex" (large)
- Tagline: "SketchUp + Agentic Coding" (underlined, short!)
- Feature 1: "Agents scripting + introspection feedback"
- Feature 2: "Humans steering Agents + SketchUp GUI + REPL/IDE"

DIAGRAM DESCRIPTION:
Three paths flow from left to right, all ending at "Supex Runtime" inside a large "SketchUp" box on the right.

IMPORTANT ARROW RULES:
- MCP cloud is ONLY between Agent and Driver. MCP does NOT connect to JSON-RPC cloud.
- Driver has exactly ONE output arrow → into JSON-RPC :9876 cloud (NOT directly to Runtime!)
- CLI has exactly ONE arrow → into the same JSON-RPC :9876 cloud
- The JSON-RPC :9876 cloud then has ONE arrow out → to Runtime socket 1
- No box connects directly to Runtime — all connections go THROUGH clouds.

Clouds are wavy outlines only — no background fill, just the wavy border shape with text inside.

Top path: "AI agent\nclaude" box → "MCP" cloud → "Driver\n./mcp" box → "JSON-RPC :9876" cloud → Runtime socket 1.

Middle path: "CLI\n./supex" box → same "JSON-RPC :9876" cloud → Runtime. (Driver and CLI arrows both enter this one shared cloud)

Bottom path: "REPL\n./repl" box → separate "JSON-RPC :4433" cloud → Runtime.

Inside SketchUp box: Runtime has two socket dots on its left edge. Below it, separate boxes for "Supex StdLib" and "SketchUp API". A small 3D cube doodle inside SketchUp box.

Internal dashed arrows:
- Runtime → StdLib
- StdLib → API
- Runtime → API
- API → cube
- cube → Runtime (feedback loop)

COLORS:
Fill boxes with light pastels based on technology:
- Pink/red tint: Runtime, StdLib, API, REPL (Ruby)
- Light green tint: Driver, CLI (Python)
- Light blue tint: SketchUp outer box
- Claude signature orange tint: AI agent (the warm orange from Claude's branding)

Small legend in bottom-right corner: four colored squares with labels Ruby, Python, SketchUp, Other. As single line.

SMALL DETAILS:
Terminal icon near CLI and REPL. Robot doodle near AI agent. Gear icon near Driver. The wireframe cube inside SketchUp represents 3D models.

AVOID: No logos, no gradients, no digital effects, no screenshots.
