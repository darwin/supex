//! Import extraction and data binding injection for VCAD data imports.
//!
//! Walks the Loon AST to find `[let <binding> [import <extract> "entity:<id>"]]`
//! patterns, rewrites them to internal symbols, and supports injecting resolved
//! data as Loon let-bindings before evaluation.

use loon_lang::ast::{Expr, ExprKind};
use loon_lang::parser::parse;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Valid extract types for imports (data + solid).
const VALID_EXTRACTS: &[&str] = &["dimensions", "bbox", "transform", "solid"];

/// A single import declaration extracted from source.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImportDecl {
    /// Unique import identifier (e.g. "import_0").
    pub import_id: String,
    /// Name of the let-binding in user code.
    pub binding_name: String,
    /// Extract type (e.g. "dimensions", "bbox", "transform").
    pub extract: String,
    /// Entity reference (e.g. "entity:12345").
    pub entity_ref: String,
    /// Internal symbol injected in place of [import ...].
    pub injected_symbol: String,
}

/// Result of import extraction and AST rewrite.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedImports {
    /// List of extracted import declarations.
    pub imports: Vec<ImportDecl>,
    /// Source with [import ...] calls replaced by injected symbols.
    pub transformed_source: String,
}

/// Resolved data for a single import (passed back from driver).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResolvedDataImport {
    /// The extract type.
    pub extract: String,
    /// The injected symbol name.
    pub injected_symbol: String,
    /// Resolved data as JSON value (will be converted to Loon literal).
    pub data: serde_json::Value,
}

/// Native mesh data from a SketchUp solid (manifold group/component).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NativeMeshData {
    /// Flat vertex positions [x0,y0,z0, x1,y1,z1, ...] in mm.
    pub positions: Vec<f64>,
    /// Triangle indices [i0,i1,i2, ...].
    pub indices: Vec<u32>,
    /// Vertex normals [nx0,ny0,nz0, ...].
    pub normals: Vec<f64>,
}

/// Resolved import with support for both data and solid extracts.
///
/// Data imports (dimensions, bbox, transform) carry JSON data that is
/// converted to Loon let-bindings. Solid imports carry a vcad_node_id
/// whose cached ADT tree is injected into the Loon environment directly.
/// Native mesh imports carry triangulated mesh data from SketchUp solids.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResolvedImport {
    /// The extract type (dimensions, bbox, transform, solid).
    pub extract: String,
    /// The injected symbol name (__vcad_import_N).
    pub injected_symbol: String,
    /// Resolved data as JSON value (for data imports).
    #[serde(default)]
    pub data: serde_json::Value,
    /// VCAD node ID for solid imports (ADT retrieved from cache).
    #[serde(default)]
    pub vcad_node_id: Option<String>,
    /// Native mesh data for solid imports from SketchUp solids.
    #[serde(default)]
    pub native_mesh: Option<NativeMeshData>,
}

/// Parse source, extract supported import forms, and rewrite them.
///
/// Matches the pattern:
///   `[let <binding> [import <extract-keyword> "entity:<id>"]]`
///
/// Rewrites each to:
///   `[let <binding> __vcad_import_N]`
///
/// Returns the extracted import declarations and the transformed source.
pub fn extract_and_rewrite_imports(source: &str) -> Result<ExtractedImports, String> {
    let exprs = parse(source).map_err(|e| format!("Parse error: {:?}", e))?;

    let mut imports = Vec::new();
    let mut spans = Vec::new();
    let mut counter = 0u32;
    collect_imports_with_spans(&exprs, &mut imports, &mut spans, &mut counter)?;

    if imports.is_empty() {
        return Ok(ExtractedImports {
            imports: Vec::new(),
            transformed_source: source.to_string(),
        });
    }

    // Build replacements from spans (reverse order to preserve offsets)
    let mut sorted_indices: Vec<usize> = (0..spans.len()).collect();
    sorted_indices.sort_by(|a, b| spans[*b].0.cmp(&spans[*a].0));

    let mut transformed = source.to_string();
    for idx in sorted_indices {
        let (start, end) = spans[idx];
        let symbol = &imports[idx].injected_symbol;
        transformed.replace_range(start..end, symbol);
    }

    Ok(ExtractedImports {
        imports,
        transformed_source: transformed,
    })
}

/// Walk expressions to find let-import patterns and collect span info.
fn collect_imports_with_spans(
    exprs: &[Expr],
    imports: &mut Vec<ImportDecl>,
    spans: &mut Vec<(usize, usize)>,
    counter: &mut u32,
) -> Result<(), String> {
    for expr in exprs {
        if let ExprKind::List(items) = &expr.kind {
            // Check for bare [import ...] at top level
            if !items.is_empty() {
                if let ExprKind::Symbol(s) = &items[0].kind {
                    if s == "import" {
                        return Err(
                            "IMPORT_FORM_INVALID: [import] must appear as the value in a [let ...] binding"
                                .to_string(),
                        );
                    }
                }
            }

            if items.len() < 3 {
                // Check nested lists for import validation
                check_no_bare_imports(items)?;
                continue;
            }

            // Match [let <binding> <value>]
            let is_let = matches!(&items[0].kind, ExprKind::Symbol(s) if s == "let");
            if !is_let {
                check_no_bare_imports(items)?;
                continue;
            }

            // Check if value is [import ...]
            let value_expr = &items[2];
            if let ExprKind::List(import_items) = &value_expr.kind {
                let is_import =
                    matches!(&import_items[0].kind, ExprKind::Symbol(s) if s == "import");
                if !is_import {
                    check_no_bare_imports(import_items)?;
                    continue;
                }

                // Validate import form: [import <keyword> <string>]
                if import_items.len() != 3 {
                    return Err(format!(
                        "IMPORT_FORM_INVALID: [import] requires exactly 2 arguments (extract and entity_ref), got {}",
                        import_items.len() - 1
                    ));
                }

                // Extract keyword
                let extract = match &import_items[1].kind {
                    ExprKind::Keyword(kw) => kw.clone(),
                    _ => {
                        return Err(
                            "IMPORT_FORM_INVALID: first argument to [import] must be a keyword (:dimensions, :bbox, :transform)"
                                .to_string(),
                        );
                    }
                };

                // Validate extract type
                if !VALID_EXTRACTS.contains(&extract.as_str()) {
                    return Err(format!(
                        "IMPORT_FORM_INVALID: unsupported extract type :{}, must be one of: {}",
                        extract,
                        VALID_EXTRACTS
                            .iter()
                            .map(|s| format!(":{}", s))
                            .collect::<Vec<_>>()
                            .join(", ")
                    ));
                }

                // Extract entity ref
                let entity_ref = match &import_items[2].kind {
                    ExprKind::Str(s) => s.clone(),
                    _ => {
                        return Err(
                            "IMPORT_FORM_INVALID: second argument to [import] must be a string (\"entity:<id>\")"
                                .to_string(),
                        );
                    }
                };

                // Validate entity ref format
                if !entity_ref.starts_with("entity:") {
                    return Err(format!(
                        "IMPORT_FORM_INVALID: entity reference must match \"entity:<integer-id>\", got \"{}\"",
                        entity_ref
                    ));
                }
                let id_part = &entity_ref["entity:".len()..];
                if id_part.parse::<i64>().is_err() {
                    return Err(format!(
                        "IMPORT_FORM_INVALID: entity ID must be an integer, got \"{}\"",
                        id_part
                    ));
                }

                // Extract binding name
                let binding_name = match &items[1].kind {
                    ExprKind::Symbol(s) => s.clone(),
                    _ => {
                        return Err(
                            "IMPORT_FORM_INVALID: let binding name must be a symbol".to_string()
                        );
                    }
                };

                let import_id = format!("import_{}", counter);
                let injected_symbol = format!("__vcad_import_{}", counter);
                *counter += 1;

                imports.push(ImportDecl {
                    import_id,
                    binding_name,
                    extract,
                    entity_ref,
                    injected_symbol,
                });

                // Record span of the [import ...] expression (value_expr, not the whole let)
                spans.push((value_expr.span.start, value_expr.span.end));
            } else {
                check_no_bare_imports_expr(value_expr)?;
            }
        }
    }

    Ok(())
}

/// Check that [import ...] doesn't appear outside a let binding.
fn check_no_bare_imports(items: &[Expr]) -> Result<(), String> {
    for item in items {
        check_no_bare_imports_expr(item)?;
    }
    Ok(())
}

/// Recursively check that [import ...] doesn't appear in unexpected positions.
fn check_no_bare_imports_expr(expr: &Expr) -> Result<(), String> {
    if let ExprKind::List(items) = &expr.kind {
        if !items.is_empty() {
            if let ExprKind::Symbol(s) = &items[0].kind {
                if s == "import" {
                    return Err(
                        "IMPORT_FORM_INVALID: [import] must appear as the value in a [let ...] binding"
                            .to_string(),
                    );
                }
            }
        }
        for item in items {
            check_no_bare_imports_expr(item)?;
        }
    }
    Ok(())
}

/// Format a resolved data import as a Loon let-binding string.
///
/// The resulting binding is prepended to the transformed source before evaluation.
/// Example output: `[let __vcad_import_0 {:width 100.0 :height 200.0 :depth 50.0}]`
pub fn format_data_binding(symbol: &str, data: &serde_json::Value) -> String {
    let loon_value = json_to_loon(data);
    format!("[let {} {}]\n", symbol, loon_value)
}

/// Convert a JSON value to a Loon literal string.
fn json_to_loon(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "nil".to_string(),
        serde_json::Value::Bool(b) => if *b { "true" } else { "false" }.to_string(),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                format!("{}", i)
            } else if let Some(f) = n.as_f64() {
                // Ensure float has decimal point for Loon
                let s = format!("{}", f);
                if s.contains('.') {
                    s
                } else {
                    format!("{}.0", s)
                }
            } else {
                n.to_string()
            }
        }
        serde_json::Value::String(s) => {
            format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\""))
        }
        serde_json::Value::Array(arr) => {
            let items: Vec<String> = arr.iter().map(json_to_loon).collect();
            format!("#[{}]", items.join(" "))
        }
        serde_json::Value::Object(map) => {
            let mut pairs = Vec::new();
            for (k, v) in map {
                pairs.push(format!(":{} {}", k, json_to_loon(v)));
            }
            format!("{{{}}}", pairs.join(" "))
        }
    }
}

/// Build the preamble of let-bindings for all resolved imports.
pub fn build_import_preamble(imports: &HashMap<String, ResolvedDataImport>) -> String {
    let mut preamble = String::new();
    for import in imports.values() {
        preamble.push_str(&format_data_binding(&import.injected_symbol, &import.data));
    }
    preamble
}

/// Build the preamble of let-bindings for data imports only (skipping solid).
///
/// Solid imports are injected directly into the Loon environment, not as
/// source-level let-bindings.
pub fn build_data_preamble(imports: &HashMap<String, ResolvedImport>) -> String {
    let mut preamble = String::new();
    for import in imports.values() {
        if import.extract != "solid" {
            preamble.push_str(&format_data_binding(&import.injected_symbol, &import.data));
        }
    }
    preamble
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_single_import() {
        let source = r#"[let host-dims [import :dimensions "entity:12345"]]
[cube 10.0 10.0 10.0]"#;

        let result = extract_and_rewrite_imports(source).unwrap();

        assert_eq!(result.imports.len(), 1);
        let imp = &result.imports[0];
        assert_eq!(imp.binding_name, "host-dims");
        assert_eq!(imp.extract, "dimensions");
        assert_eq!(imp.entity_ref, "entity:12345");
        assert_eq!(imp.injected_symbol, "__vcad_import_0");
        assert!(result.transformed_source.contains("__vcad_import_0"));
        assert!(!result.transformed_source.contains("[import"));
    }

    #[test]
    fn test_extract_multiple_imports() {
        let source = r#"[let dims [import :dimensions "entity:100"]]
[let bb [import :bbox "entity:200"]]
[cube 1.0 1.0 1.0]"#;

        let result = extract_and_rewrite_imports(source).unwrap();

        assert_eq!(result.imports.len(), 2);
        assert_eq!(result.imports[0].extract, "dimensions");
        assert_eq!(result.imports[0].injected_symbol, "__vcad_import_0");
        assert_eq!(result.imports[1].extract, "bbox");
        assert_eq!(result.imports[1].injected_symbol, "__vcad_import_1");
        assert!(result.transformed_source.contains("__vcad_import_0"));
        assert!(result.transformed_source.contains("__vcad_import_1"));
    }

    #[test]
    fn test_no_imports() {
        let source = "[cube 10.0 10.0 10.0]";
        let result = extract_and_rewrite_imports(source).unwrap();
        assert!(result.imports.is_empty());
        assert_eq!(result.transformed_source, source);
    }

    #[test]
    fn test_invalid_extract_type() {
        let source = r#"[let x [import :color "entity:1"]]"#;
        let result = extract_and_rewrite_imports(source);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("IMPORT_FORM_INVALID"));
    }

    #[test]
    fn test_invalid_entity_ref() {
        let source = r#"[let x [import :dimensions "node:abc"]]"#;
        let result = extract_and_rewrite_imports(source);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("IMPORT_FORM_INVALID"));
    }

    #[test]
    fn test_non_integer_entity_id() {
        let source = r#"[let x [import :dimensions "entity:abc"]]"#;
        let result = extract_and_rewrite_imports(source);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("IMPORT_FORM_INVALID"));
    }

    #[test]
    fn test_bare_import_rejected() {
        let source = r#"[import :dimensions "entity:1"]"#;
        let result = extract_and_rewrite_imports(source);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("IMPORT_FORM_INVALID"));
    }

    #[test]
    fn test_import_wrong_arg_count() {
        let source = r#"[let x [import :dimensions]]"#;
        let result = extract_and_rewrite_imports(source);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("IMPORT_FORM_INVALID"));
    }

    #[test]
    fn test_json_to_loon_map() {
        let data = serde_json::json!({"width": 100.0, "height": 200.0, "depth": 50.0});
        let loon = json_to_loon(&data);
        assert!(loon.contains(":width"));
        assert!(loon.contains(":height"));
        assert!(loon.contains(":depth"));
        assert!(loon.starts_with('{'));
        assert!(loon.ends_with('}'));
    }

    #[test]
    fn test_json_to_loon_array() {
        let data = serde_json::json!([1.0, 2.0, 3.0]);
        let loon = json_to_loon(&data);
        assert_eq!(loon, "#[1.0 2.0 3.0]");
    }

    #[test]
    fn test_json_to_loon_nested() {
        let data = serde_json::json!({"min": [0.0, 0.0, 0.0], "max": [10.0, 20.0, 30.0]});
        let loon = json_to_loon(&data);
        assert!(loon.contains(":min #[0.0 0.0 0.0]"));
        assert!(loon.contains(":max #[10.0 20.0 30.0]"));
    }

    #[test]
    fn test_format_data_binding() {
        let data = serde_json::json!({"width": 100.0});
        let binding = format_data_binding("__vcad_import_0", &data);
        assert!(binding.starts_with("[let __vcad_import_0 "));
        assert!(binding.contains(":width 100.0"));
        assert!(binding.ends_with("]\n"));
    }

    #[test]
    fn test_build_import_preamble() {
        let mut imports = HashMap::new();
        imports.insert(
            "import_0".to_string(),
            ResolvedDataImport {
                extract: "dimensions".to_string(),
                injected_symbol: "__vcad_import_0".to_string(),
                data: serde_json::json!({"width": 50.0}),
            },
        );
        let preamble = build_import_preamble(&imports);
        assert!(preamble.contains("[let __vcad_import_0"));
        assert!(preamble.contains(":width 50.0"));
    }

    #[test]
    fn test_transform_extract() {
        let source = r#"[let tr [import :transform "entity:42"]]
[cube 1.0 1.0 1.0]"#;

        let result = extract_and_rewrite_imports(source).unwrap();

        assert_eq!(result.imports.len(), 1);
        assert_eq!(result.imports[0].extract, "transform");
        assert_eq!(result.imports[0].entity_ref, "entity:42");
    }

    #[test]
    fn test_solid_extract() {
        let source = r#"[let bracket [import :solid "entity:67890"]]
[difference bracket [cube 10.0 10.0 10.0]]"#;

        let result = extract_and_rewrite_imports(source).unwrap();

        assert_eq!(result.imports.len(), 1);
        assert_eq!(result.imports[0].extract, "solid");
        assert_eq!(result.imports[0].entity_ref, "entity:67890");
        assert_eq!(result.imports[0].injected_symbol, "__vcad_import_0");
        assert!(result.transformed_source.contains("__vcad_import_0"));
        assert!(!result.transformed_source.contains("[import"));
    }

    #[test]
    fn test_mixed_data_and_solid_imports() {
        let source = r#"[let dims [import :dimensions "entity:100"]]
[let bracket [import :solid "entity:200"]]
[cube 1.0 1.0 1.0]"#;

        let result = extract_and_rewrite_imports(source).unwrap();

        assert_eq!(result.imports.len(), 2);
        assert_eq!(result.imports[0].extract, "dimensions");
        assert_eq!(result.imports[1].extract, "solid");
    }

    #[test]
    fn test_commented_out_imports_ignored() {
        let source = r#"; commented out import
;[let cutout [import :solid "entity:37395"]]

[cube 100.0 100.0 20.0]"#;

        let result = extract_and_rewrite_imports(source).unwrap();
        assert!(result.imports.is_empty());
        assert_eq!(result.transformed_source, source);
    }

    #[test]
    fn test_commented_import_with_active_import() {
        let source = r#";[let old [import :solid "entity:111"]]
[let dims [import :dimensions "entity:222"]]
[cube 10.0 10.0 10.0]"#;

        let result = extract_and_rewrite_imports(source).unwrap();
        assert_eq!(result.imports.len(), 1, "only the uncommented import is extracted");
        assert_eq!(result.imports[0].extract, "dimensions");
        assert_eq!(result.imports[0].entity_ref, "entity:222");
        // The commented line stays in source text but is not extracted as an import
        assert!(result.transformed_source.contains(";[let old"));
    }

    #[test]
    fn test_build_data_preamble_skips_solid() {
        let mut imports = HashMap::new();
        imports.insert(
            "import_0".to_string(),
            ResolvedImport {
                extract: "dimensions".to_string(),
                injected_symbol: "__vcad_import_0".to_string(),
                data: serde_json::json!({"width": 50.0}),
                vcad_node_id: None,
                native_mesh: None,
            },
        );
        imports.insert(
            "import_1".to_string(),
            ResolvedImport {
                extract: "solid".to_string(),
                injected_symbol: "__vcad_import_1".to_string(),
                data: serde_json::Value::Null,
                vcad_node_id: Some("bracket-node".to_string()),
                native_mesh: None,
            },
        );
        let preamble = build_data_preamble(&imports);
        assert!(preamble.contains("__vcad_import_0"));
        assert!(!preamble.contains("__vcad_import_1"));
    }
}
