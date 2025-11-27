"""Documentation browsing CLI commands."""

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.tree import Tree

from supex_driver.mcp.resources import (
    get_resources_path,
    list_available_classes,
    list_available_namespaces,
    list_available_pages,
    load_api_doc,
    load_page_doc,
    load_resource_file,
    find_similar_classes,
)

app = typer.Typer(name="docs", help="Browse SketchUp API documentation")
console = Console()


def check_docs_available() -> bool:
    """Check if documentation is available."""
    docs_path = get_resources_path() / "docs"
    return docs_path.exists() and (docs_path / "index.md").exists()


@app.callback(invoke_without_command=True)
def docs_main(ctx: typer.Context):
    """Browse SketchUp API documentation.

    Without subcommand, shows documentation hierarchy (same as 'docs tree').
    """
    if ctx.invoked_subcommand is None:
        tree_docs()


# Target column for descriptions (accounting for tree indentation)
# Tree indent is ~4 chars per level: "├── " at root, "│   ├── " at level 1, etc.
DESC_COLUMN = 44

def _format_entry(name: str, description: str, depth: int = 0) -> str:
    """Format a tree entry with globally aligned description.

    Args:
        name: The item name
        description: Description text
        depth: Tree depth (0 = root, 1 = first children, etc.)
    """
    # Tree prefix width: 4 chars base + 4 chars per depth level
    tree_prefix_width = 4 + (4 * depth)
    # Calculate padding to align description to DESC_COLUMN
    name_end_col = tree_prefix_width + len(name)
    padding = " " * max(2, DESC_COLUMN - name_end_col)

    if description:
        return f"[cyan]{name}[/cyan]{padding}[dim]{description}[/dim]"
    return f"[cyan]{name}[/cyan]"


@app.command("tree")
def tree_docs(
    full: bool = typer.Option(False, "--full", "-f", help="Show all classes without truncation"),
):
    """Show documentation hierarchy with URIs."""
    if not check_docs_available():
        console.print("[red]Documentation not available.[/red]")
        console.print("[dim]Generate with: ./docgen/scripts/generate_docs.sh[/dim]")
        raise typer.Exit(1)

    tree = Tree("[bold]supex://docs/[/bold]")

    # Core documentation (depth 0)
    tree.add(_format_entry("index", "Documentation index", depth=0))
    tree.add(_format_entry("workflow", "Complete workflow guide", depth=0))
    tree.add(_format_entry("best-practices", "Geometry lessons learned", depth=0))
    tree.add(_format_entry("quick-reference", "Quick reference", depth=0))

    # Pages (depth 1)
    pages = list_available_pages()
    if pages:
        pages_branch = tree.add("[bold]pages/[/bold]")
        page_descriptions = {
            "generating-geometry": "Geometry creation approaches",
            "importer-options": "Importer configuration",
            "exporter-options": "Exporter configuration",
        }
        for page in pages:
            desc = page_descriptions.get(page, "")
            pages_branch.add(_format_entry(page, desc, depth=1))

    # API documentation (depth 1)
    api_branch = tree.add("[bold]api/[/bold]")
    api_branch.add(_format_entry("index", "API overview", depth=1))

    # Top-level classes (exclude namespace modules and special files)
    all_classes = list_available_classes()
    exclude_top_level = {"pages", "Geom", "Sketchup", "TOP_LEVEL"}
    top_level = [c for c in all_classes if "/" not in c and c not in exclude_top_level]

    top_level_descriptions = {
        "Array": "SketchUp Array extensions",
        "Length": "Length unit handling",
        "Numeric": "Unit conversion methods",
        "String": "String to length parsing",
    }

    for cls in sorted(top_level):
        desc = top_level_descriptions.get(cls, "")
        api_branch.add(_format_entry(cls, desc, depth=1))

    # Namespaces (depth 2 for contents)
    namespaces = list_available_namespaces()
    for ns in sorted(namespaces):
        ns_classes = [c for c in all_classes if c.startswith(f"{ns}/")]
        ns_branch = api_branch.add(f"[bold]{ns}/[/bold]")

        # Count classes
        class_count = len(ns_classes)
        ns_branch.add(_format_entry("index", f"{class_count} classes", depth=2))

        # Show classes (all if --full, otherwise first 5)
        classes_to_show = sorted(ns_classes) if full else sorted(ns_classes)[:5]
        for cls_path in classes_to_show:
            cls_name = cls_path.split("/")[-1]
            ns_branch.add(f"[cyan]{cls_name}[/cyan]")

        if not full and len(ns_classes) > len(classes_to_show):
            ns_branch.add(f"[dim]... and {len(ns_classes) - len(classes_to_show)} more[/dim]")

    console.print(tree)
    console.print()
    console.print("[dim]Use 'supex docs show <uri>' to view documentation[/dim]")


@app.command("show")
def show_docs(
    uri: str = typer.Argument(..., help="Documentation URI (e.g., Sketchup::Face, docs/api/Geom::Point3d)"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw markdown"),
):
    """Show documentation for a resource.

    Accepts various URI formats:
    - supex://docs/api/Sketchup::Face (full URI)
    - docs/api/Sketchup::Face (path)
    - Sketchup::Face (class name, auto-resolves to api/)
    - generating_geometry (page name, auto-resolves to pages/)
    """
    if not check_docs_available():
        console.print("[red]Documentation not available.[/red]")
        raise typer.Exit(1)

    # Normalize URI
    normalized = uri
    if normalized.startswith("supex://"):
        normalized = normalized[8:]  # Remove supex://
    if normalized.startswith("docs/"):
        normalized = normalized[5:]  # Remove docs/

    content = None

    # Try to resolve the URI
    if normalized == "index":
        content = load_resource_file("index.md")
    elif normalized == "workflow":
        content = load_resource_file("workflow.md")
    elif normalized == "best-practices":
        content = load_resource_file("best_practices.md")
    elif normalized == "quick-reference":
        content = load_resource_file("quick_reference.md")
    elif normalized.startswith("pages/"):
        page_name = normalized[6:]  # Remove pages/
        content = load_page_doc(page_name)
    elif normalized.startswith("api/"):
        # API documentation
        api_path = normalized[4:]  # Remove api/
        if api_path == "index":
            from supex_driver.mcp.resources import load_api_index
            content = load_api_index()
        elif api_path.endswith("/index"):
            # Namespace index
            ns = api_path[:-6]  # Remove /index
            from supex_driver.mcp.resources import load_namespace_index
            content = load_namespace_index(ns)
        else:
            # Class documentation - convert :: to /
            class_path = api_path.replace("::", "/")
            content = load_api_doc(class_path)
    else:
        # Auto-resolve: try as class name first, then as page
        class_path = normalized.replace("::", "/")
        content = load_api_doc(class_path)

        if content is None:
            # Try as page
            content = load_page_doc(normalized)

        if content is None:
            # Try with namespace prefix
            for ns in list_available_namespaces():
                content = load_api_doc(f"{ns}/{class_path}")
                if content:
                    break

    if content is None:
        console.print(f"[red]Documentation not found:[/red] {uri}")

        # Suggest similar
        similar = find_similar_classes(normalized.replace("::", "/"))
        if similar:
            console.print("\n[yellow]Did you mean:[/yellow]")
            for s in similar[:5]:
                ruby_name = s.replace("/", "::")
                console.print(f"  supex://docs/api/{ruby_name}")
        raise typer.Exit(1)

    if raw:
        console.print(content)
    else:
        # Render as markdown with pager for long content
        md = Markdown(content)
        if len(content) > 2000:
            with console.pager():
                console.print(md)
        else:
            console.print(md)


@app.command("search")
def search_docs(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
):
    """Search documentation by name."""
    if not check_docs_available():
        console.print("[red]Documentation not available.[/red]")
        raise typer.Exit(1)

    query_lower = query.lower()
    results = []

    # Search in classes
    for cls in list_available_classes():
        if query_lower in cls.lower():
            ruby_name = cls.replace("/", "::")
            results.append(f"supex://docs/api/{ruby_name}")

    # Search in pages
    for page in list_available_pages():
        if query_lower in page.lower():
            results.append(f"supex://docs/pages/{page}")

    if not results:
        console.print(f"[yellow]No results for:[/yellow] {query}")

        # Try fuzzy search
        similar = find_similar_classes(query)
        if similar:
            console.print("\n[dim]Similar classes:[/dim]")
            for s in similar[:5]:
                ruby_name = s.replace("/", "::")
                console.print(f"  supex://docs/api/{ruby_name}")
        raise typer.Exit(0)

    console.print(f"[green]Found {len(results)} result(s) for:[/green] {query}\n")

    for result in results[:limit]:
        console.print(f"  {result}")

    if len(results) > limit:
        console.print(f"\n[dim]... and {len(results) - limit} more (use --limit to show more)[/dim]")
