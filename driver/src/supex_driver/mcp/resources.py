"""Documentation resources helper module for Supex MCP server.

This module provides utilities for loading and serving SketchUp API documentation
via MCP resources.
"""

from pathlib import Path


def get_resources_path() -> Path:
    """Get the absolute path to driver/resources directory.

    Navigates from this file (mcp/resources.py) up to resources:
    resources.py -> mcp -> supex_driver -> src -> driver -> resources
    """
    return Path(__file__).parent.parent.parent.parent / "resources"


def get_docs_not_generated_message() -> str:
    """Return message for when API documentation is not generated."""
    return (
        "API documentation is not generated. "
        "Run `docgen/scripts/generate_docs.sh` to generate it (recommended), "
        "or consult online documentation at https://ruby.sketchup.com/"
    )


def load_api_doc(class_path: str) -> str | None:
    """Load API documentation for a specific class.

    Args:
        class_path: Path to class documentation, e.g.:
            - "Sketchup/Face" -> resources/docs/api/Sketchup/Face.md
            - "Geom/Point3d" -> resources/docs/api/Geom/Point3d.md
            - "Array" -> resources/docs/api/Array.md

    Returns:
        Documentation content as string, or None if not found.
    """
    api_path = get_resources_path() / "docs" / "api"
    file_path = api_path / f"{class_path}.md"

    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return None


def load_api_index() -> str | None:
    """Load the full API documentation index."""
    index_path = get_resources_path() / "docs" / "api" / "INDEX.md"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return None


def load_resource_file(filename: str) -> str | None:
    """Load a file from driver/resources/docs directory."""
    file_path = get_resources_path() / "docs" / filename
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return None


def list_available_classes() -> list[str]:
    """List all available class documentation paths.

    Returns:
        Sorted list of class paths like ["Array", "Geom/BoundingBox", "Sketchup/Face", ...]
    """
    api_path = get_resources_path() / "docs" / "api"
    if not api_path.exists():
        return []

    classes = []
    for md_file in api_path.rglob("*.md"):
        if md_file.name == "INDEX.md":
            continue
        rel_path = md_file.relative_to(api_path)
        classes.append(str(rel_path.with_suffix("")))
    return sorted(classes)


def find_similar_classes(query: str, limit: int = 5) -> list[str]:
    """Find classes with names similar to query.

    Args:
        query: Class name to search for (e.g., "face", "Point3d")
        limit: Maximum number of suggestions to return

    Returns:
        List of similar class paths
    """
    available = list_available_classes()

    # Extract the class name from path (last component)
    query_name = query.split("/")[-1].lower()

    matches = []
    for cls in available:
        cls_name = cls.split("/")[-1].lower()
        if query_name in cls_name or cls_name in query_name:
            matches.append(cls)

    return matches[:limit]
