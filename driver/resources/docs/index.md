# Supex Documentation Index

This index provides guidance on available MCP resources for SketchUp Ruby development.

## Quick Start

1. Read `supex://docs/workflow` for complete workflow patterns
2. Read `supex://docs/best-practices` for geometry lessons learned
3. Use `supex://docs/api/{class}` for specific API reference

## Core Documentation

| Resource | Description |
|----------|-------------|
| `supex://docs/workflow` | Complete workflow guide - execution patterns, transaction management, code organization |
| `supex://docs/best-practices` | Geometry lessons learned - profile-first approach, pushpull direction, common pitfalls |

## Guides

| Resource | Description |
|----------|-------------|
| `supex://docs/quick-reference` | Quick reference - most used classes and common entry points |
| `supex://docs/pages/generating_geometry` | Different approaches to create geometry via Ruby API |
| `supex://docs/pages/importer_options` | Configuration options for file importers |
| `supex://docs/pages/exporter_options` | Configuration options for file exporters |

## API Reference

| Resource | Description |
|----------|-------------|
| `supex://docs/api/index` | Full API index (~30k tokens) - complete class and method listing |
| `supex://docs/api/Sketchup::Face` | Class documentation using Ruby syntax |
| `supex://docs/api/Geom::Point3d` | Geometry classes |
| `supex://docs/api/Array` | Top-level classes (no namespace prefix) |

## When to Use Each Resource

- **Starting a modeling task**: Read `supex://docs/workflow` first
- **Geometry not working as expected**: Read `supex://docs/best-practices`
- **Need method signatures**: Read `supex://docs/api/Sketchup::Face` (use Ruby `::` syntax)
- **Searching for a class/method**: Read `supex://docs/api/index` for full listing

## Essential Classes

### Modeling
- `supex://docs/api/Sketchup::Model` - Main model object, entry point
- `supex://docs/api/Sketchup::Entities` - Collection of entities, add geometry here
- `supex://docs/api/Sketchup::Face` - Faces with pushpull, materials
- `supex://docs/api/Sketchup::Edge` - Edges connecting vertices
- `supex://docs/api/Sketchup::Group` - Grouped entities for organization

### Geometry Math
- `supex://docs/api/Geom::Point3d` - 3D points
- `supex://docs/api/Geom::Vector3d` - 3D vectors
- `supex://docs/api/Geom::Transformation` - Transformations (move, rotate, scale)
- `supex://docs/api/Geom::BoundingBox` - Bounding boxes

### Organization
- `supex://docs/api/Sketchup::ComponentDefinition` - Component definitions
- `supex://docs/api/Sketchup::ComponentInstance` - Component instances
- `supex://docs/api/Sketchup::Layer` - Layers/tags
- `supex://docs/api/Sketchup::Material` - Materials and colors
