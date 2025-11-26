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

## API Reference

| Resource | Description |
|----------|-------------|
| `supex://docs/api/index` | Full API index (~30k tokens) - complete class and method listing |
| `supex://docs/api/Sketchup/{Class}` | Class documentation (e.g., Face, Model, Group, Entities) |
| `supex://docs/api/Geom/{Class}` | Geometry classes (e.g., Point3d, Vector3d, Transformation) |
| `supex://docs/api/{Class}` | Top-level classes (e.g., Array, Length, Numeric) |

## When to Use Each Resource

- **Starting a modeling task**: Read `supex://docs/workflow` first
- **Geometry not working as expected**: Read `supex://docs/best-practices`
- **Need method signatures**: Read `supex://docs/api/Sketchup/{Class}` or `supex://docs/api/Geom/{Class}`
- **Searching for a class/method**: Read `supex://docs/api/index` for full listing

## Essential Classes

### Modeling
- `Sketchup/Model` - Main model object, entry point
- `Sketchup/Entities` - Collection of entities, add geometry here
- `Sketchup/Face` - Faces with pushpull, materials
- `Sketchup/Edge` - Edges connecting vertices
- `Sketchup/Group` - Grouped entities for organization

### Geometry Math
- `Geom/Point3d` - 3D points
- `Geom/Vector3d` - 3D vectors
- `Geom/Transformation` - Transformations (move, rotate, scale)
- `Geom/BoundingBox` - Bounding boxes

### Organization
- `Sketchup/ComponentDefinition` - Component definitions
- `Sketchup/ComponentInstance` - Component instances
- `Sketchup/Layer` - Layers/tags
- `Sketchup/Material` - Materials and colors
