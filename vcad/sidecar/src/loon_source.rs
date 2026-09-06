//! Print a loon `Value` back as loon source.
//!
//! Solid imports reach the interpreter as text: a cached ADT tree from another
//! node is printed into the program preamble as a `[let __vcad_import_N ...]`
//! binding. ADT tags become constructor calls (`[Cube 10.0 10.0 10.0]`), which
//! resolve because the VCAD library is prepended to every program. Only data
//! values are printable; closures, channels and other runtime handles are
//! rejected with an error naming the offending value.

use loon_lang::interp::Value;
use std::fmt::Write;

/// Render `value` as a loon expression that evaluates back to the same value.
pub fn value_to_loon_source(value: &Value) -> Result<String, String> {
    let mut out = String::new();
    write_value(value, &mut out)?;
    Ok(out)
}

fn write_value(value: &Value, out: &mut String) -> Result<(), String> {
    match value {
        Value::Int(n) => write!(out, "{n}").unwrap(),
        Value::Float(f) => write_float(*f, out)?,
        Value::Bool(b) => write!(out, "{b}").unwrap(),
        Value::Str(s) => write_str(s, out),
        Value::Keyword(k) => write!(out, ":{k}").unwrap(),
        Value::Unit => out.push_str("()"),
        Value::Vec(items) => {
            out.push_str("#[");
            write_seq(items.iter(), out)?;
            out.push(']');
        }
        Value::Set(items) => {
            out.push_str("#{");
            write_seq(items.iter(), out)?;
            out.push('}');
        }
        Value::Map(map) => {
            out.push('{');
            for (i, (k, v)) in map.iter().enumerate() {
                if i > 0 {
                    out.push(' ');
                }
                write_value(k, out)?;
                out.push(' ');
                write_value(v, out)?;
            }
            out.push('}');
        }
        Value::Tuple(items) => {
            out.push('(');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_value(item, out)?;
            }
            out.push(')');
        }
        Value::Adt(tag, fields) if fields.is_empty() => out.push_str(tag),
        Value::Adt(tag, fields) => {
            out.push('[');
            out.push_str(tag);
            for field in fields {
                out.push(' ');
                write_value(field, out)?;
            }
            out.push(']');
        }
        Value::Fn(_)
        | Value::Builtin(..)
        | Value::DomNode(_)
        | Value::ChannelTx(_)
        | Value::ChannelRx(_)
        | Value::Future(_)
        | Value::AsyncSlot(_)
        | Value::Json(_) => {
            return Err(format!("cannot print {value} as loon source"));
        }
    }
    Ok(())
}

fn write_seq<'a>(items: impl Iterator<Item = &'a Value>, out: &mut String) -> Result<(), String> {
    for (i, item) in items.enumerate() {
        if i > 0 {
            out.push(' ');
        }
        write_value(item, out)?;
    }
    Ok(())
}

fn write_float(f: f64, out: &mut String) -> Result<(), String> {
    if !f.is_finite() {
        return Err(format!("cannot print non-finite float {f} as loon source"));
    }
    // Rust's Display never uses an exponent for f64 and prints the shortest
    // round-tripping decimal; only the decimal point has to be forced so the
    // literal stays a float.
    let s = format!("{f}");
    out.push_str(&s);
    if !s.contains('.') {
        out.push_str(".0");
    }
    Ok(())
}

fn write_str(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\t' => out.push_str("\\t"),
            c => out.push(c),
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;
    use loon_lang::interp::eval_program_with_modules;
    use loon_lang::parser::parse;

    fn f(v: f64) -> Value {
        Value::Float(v)
    }

    fn s(v: &str) -> Value {
        Value::Str(v.into())
    }

    fn adt(tag: &str, fields: Vec<Value>) -> Value {
        Value::Adt(tag.to_string(), fields)
    }

    /// Evaluate `source` with the VCAD library in scope and return its value.
    fn eval(source: &str) -> Value {
        let program = format!("{}\n{}", vcad_loon::VCAD_LIB_SOURCE, source);
        let exprs = parse(&program).expect("printed source must parse");
        eval_program_with_modules(&exprs, None, None, None).expect("printed source must evaluate")
    }

    #[test]
    fn scalars() {
        assert_eq!(value_to_loon_source(&Value::Int(-3)).unwrap(), "-3");
        assert_eq!(value_to_loon_source(&f(10.0)).unwrap(), "10.0");
        assert_eq!(value_to_loon_source(&f(0.25)).unwrap(), "0.25");
        assert_eq!(value_to_loon_source(&f(1e-7)).unwrap(), "0.0000001");
        assert_eq!(value_to_loon_source(&Value::Bool(true)).unwrap(), "true");
        assert_eq!(
            value_to_loon_source(&Value::Keyword("width".into())).unwrap(),
            ":width"
        );
        assert_eq!(value_to_loon_source(&Value::Unit).unwrap(), "()");
    }

    #[test]
    fn strings_are_escaped() {
        let v = s("a \"quoted\" \\ path\nline");
        let src = value_to_loon_source(&v).unwrap();
        assert_eq!(src, "\"a \\\"quoted\\\" \\\\ path\\nline\"");
        assert_eq!(eval(&src), v);
    }

    #[test]
    fn non_finite_float_is_rejected() {
        assert!(value_to_loon_source(&f(f64::NAN)).is_err());
        assert!(value_to_loon_source(&f(f64::INFINITY)).is_err());
    }

    #[test]
    fn runtime_handles_are_rejected() {
        let err = value_to_loon_source(&Value::ChannelTx(0)).unwrap_err();
        assert!(err.contains("cannot print"), "{err}");
    }

    #[test]
    fn solid_adt_round_trips() {
        let cube = adt("Cube", vec![f(20.0), f(20.0), f(20.0)]);
        let cyl = adt("Cylinder", vec![f(5.0), f(30.0)]);
        let moved = adt("Translate", vec![f(1.5), f(0.0), f(-2.0), cyl]);
        let diff = adt("Difference", vec![cube, moved]);

        let src = value_to_loon_source(&diff).unwrap();
        assert_eq!(
            src,
            "[Difference [Cube 20.0 20.0 20.0] [Translate 1.5 0.0 -2.0 [Cylinder 5.0 30.0]]]"
        );
        assert_eq!(eval(&src), diff);
    }

    #[test]
    fn mesh_import_adt_round_trips() {
        let mesh = adt(
            "MeshImport",
            vec![s("/tmp/native-mesh/abc.mesh"), f(1.0), f(1.0), f(1.0)],
        );
        let src = value_to_loon_source(&mesh).unwrap();
        assert_eq!(eval(&src), mesh);
    }

    #[test]
    fn collections_round_trip() {
        let vec = Value::Vec(vec![f(0.0), f(1.0), Value::Int(2)].into());
        let src = value_to_loon_source(&vec).unwrap();
        assert_eq!(src, "#[0.0 1.0 2]");
        assert_eq!(eval(&src), vec);

        let nullary = adt("None", vec![]);
        assert_eq!(value_to_loon_source(&nullary).unwrap(), "None");
        assert_eq!(eval("None"), nullary);
    }

    #[test]
    fn library_expression_round_trips_through_printer() {
        // A value produced by the library itself, printed and re-evaluated,
        // must come back identical — this is the cached-ADT import path.
        let original =
            eval("[difference [cube 20.0 20.0 20.0] [translate 5.0 5.0 0.0 [cylinder 3.0 20.0]]]");
        let src = value_to_loon_source(&original).unwrap();
        assert_eq!(eval(&src), original);
    }
}
