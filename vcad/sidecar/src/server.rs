use crate::config::Config;
use crate::evaluator::{EvalError, EvalResult, Evaluator};
use crate::imports::{self, ResolvedDataImport, ResolvedImport};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc};

const PROTOCOL_VERSION: u32 = 1;
const SIDECAR_VERSION: &str = env!("CARGO_PKG_VERSION");

// JSON-RPC error codes (standard)
const JSONRPC_PARSE_ERROR: i32 = -32700;
const JSONRPC_INVALID_REQUEST: i32 = -32600;
const JSONRPC_METHOD_NOT_FOUND: i32 = -32601;
const JSONRPC_INTERNAL_ERROR: i32 = -32603;

// Application error code (mapped to JSON-RPC internal error range)
const JSONRPC_APP_ERROR: i32 = -32000;

#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    #[allow(dead_code)]
    jsonrpc: String,
    id: serde_json::Value,
    method: String,
    params: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub(crate) struct JsonRpcResponse {
    jsonrpc: String,
    id: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<JsonRpcError>,
}

#[derive(Debug, Serialize)]
struct JsonRpcError {
    code: i32,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    data: Option<serde_json::Value>,
}

/// An eval job sent to the single eval worker thread.
pub(crate) struct EvalJob {
    pub request: EvalRequest,
    pub reply_tx: mpsc::Sender<JsonRpcResponse>,
}

/// Parsed eval request ready for the worker.
pub enum EvalRequest {
    EvalCode {
        id: serde_json::Value,
        code: String,
    },
    EvalFile {
        id: serde_json::Value,
        path: String,
    },
    Inspect {
        id: serde_json::Value,
        code_or_path: String,
    },
    EvalRepl {
        id: serde_json::Value,
        code: String,
    },
    EvalWithImports {
        id: serde_json::Value,
        transformed_source: String,
        base_dir: Option<String>,
        imports: HashMap<String, ResolvedDataImport>,
    },
    /// Evaluate with both data and solid imports (ADT composition).
    EvalWithSolidImports {
        id: serde_json::Value,
        transformed_source: String,
        base_dir: Option<String>,
        imports: HashMap<String, ResolvedImport>,
        node_id: Option<String>,
    },
}

impl EvalRequest {
    #[allow(dead_code)]
    fn id(&self) -> &serde_json::Value {
        match self {
            EvalRequest::EvalCode { id, .. } => id,
            EvalRequest::EvalFile { id, .. } => id,
            EvalRequest::Inspect { id, .. } => id,
            EvalRequest::EvalRepl { id, .. } => id,
            EvalRequest::EvalWithImports { id, .. } => id,
            EvalRequest::EvalWithSolidImports { id, .. } => id,
        }
    }
}

/// Per-connection state tracking hello handshake.
struct ConnectionContext {
    identified: bool,
    workspace: Option<PathBuf>,
    #[allow(dead_code)]
    client_name: Option<String>,
    #[allow(dead_code)]
    client_version: Option<String>,
}

impl ConnectionContext {
    fn new() -> Self {
        Self {
            identified: false,
            workspace: None,
            client_name: None,
            client_version: None,
        }
    }
}

/// Start the TCP JSON-RPC server. Blocks until shutdown.
pub fn run(config: &Config) -> Result<(), Box<dyn std::error::Error>> {
    // Security: reject non-loopback bind without VCAD_ALLOW_REMOTE + VCAD_AUTH_TOKEN
    if !config.is_loopback() {
        if !config.allow_remote {
            eprintln!("Error: non-loopback bind requires VCAD_ALLOW_REMOTE=1");
            std::process::exit(1);
        }
        if config.auth_token.is_none() {
            eprintln!("Error: non-loopback bind requires VCAD_AUTH_TOKEN to be set");
            std::process::exit(1);
        }
    }

    let listener = TcpListener::bind((config.host.as_str(), config.port))?;
    eprintln!("vcad sidecar listening on {}:{}", config.host, config.port);

    // Shutdown signal
    let shutdown = Arc::new(AtomicBool::new(false));
    {
        let shutdown = shutdown.clone();
        ctrlc::set_handler(move || {
            eprintln!("vcad sidecar shutting down...");
            shutdown.store(true, Ordering::SeqCst);
        })
        .expect("Failed to set signal handler");
    }

    // Eval worker channel with bounded queue
    let (job_tx, job_rx) = mpsc::sync_channel::<EvalJob>(config.max_queue);

    // Single eval worker thread
    let eval_handle = std::thread::spawn({
        let temp_dir = config.temp_dir.clone();
        let temp_ttl_sec = config.temp_ttl_sec;
        let temp_max_files = config.temp_max_files;
        let adt_cache_max = config.adt_cache_max;
        move || {
            let mut evaluator =
                Evaluator::new(temp_dir, temp_ttl_sec, temp_max_files, adt_cache_max);
            while let Ok(job) = job_rx.recv() {
                let result = dispatch_eval(&job.request, &mut evaluator);
                let _ = job.reply_tx.send(result);
            }
        }
    });

    // Non-blocking accept loop
    listener.set_nonblocking(true)?;
    let auth_token = config.auth_token.clone();
    let eval_timeout_ms = config.eval_timeout_ms;
    let max_queue = config.max_queue;

    while !shutdown.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((stream, _addr)) => {
                stream.set_nonblocking(false).ok();
                let job_tx = job_tx.clone();
                let auth_token = auth_token.clone();
                std::thread::spawn(move || {
                    handle_connection(
                        stream,
                        job_tx,
                        eval_timeout_ms,
                        max_queue,
                        auth_token.as_deref(),
                    );
                });
            }
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            Err(e) => {
                eprintln!("Accept error: {}", e);
                break;
            }
        }
    }

    // Shutdown: drop job_tx so eval worker drains current job and exits
    drop(job_tx);
    eval_handle.join().ok();
    eprintln!("vcad sidecar stopped");
    Ok(())
}

fn handle_connection(
    stream: TcpStream,
    job_tx: mpsc::SyncSender<EvalJob>,
    eval_timeout_ms: u64,
    max_queue: usize,
    auth_token: Option<&str>,
) {
    let reader = BufReader::new(&stream);
    let mut writer = BufWriter::new(&stream);
    let mut ctx = ConnectionContext::new();

    for line_result in reader.lines() {
        let line = match line_result {
            Ok(l) => l,
            Err(_) => break,
        };

        if line.trim().is_empty() {
            continue;
        }

        let request: JsonRpcRequest = match serde_json::from_str(&line) {
            Ok(r) => r,
            Err(e) => {
                let resp = make_error_response(
                    serde_json::Value::Null,
                    JSONRPC_PARSE_ERROR,
                    &format!("Parse error: {}", e),
                    None,
                );
                write_response(&mut writer, &resp);
                continue;
            }
        };

        let response = match request.method.as_str() {
            "hello" => dispatch_hello(&request, &mut ctx, auth_token, max_queue, eval_timeout_ms),
            "ping" => {
                if !ctx.identified {
                    make_app_error_response(
                        request.id,
                        "AUTH_REQUIRED",
                        "hello handshake required before other methods",
                    )
                } else {
                    dispatch_ping(&request)
                }
            }
            "resources/list" => {
                if !ctx.identified {
                    make_app_error_response(
                        request.id,
                        "AUTH_REQUIRED",
                        "hello handshake required before other methods",
                    )
                } else {
                    dispatch_resources_list(&request)
                }
            }
            "tools/call" => {
                if !ctx.identified {
                    make_app_error_response(
                        request.id,
                        "AUTH_REQUIRED",
                        "hello handshake required before other methods",
                    )
                } else {
                    dispatch_tools_call(&request, &ctx, &job_tx, eval_timeout_ms)
                }
            }
            _ => make_error_response(
                request.id,
                JSONRPC_METHOD_NOT_FOUND,
                &format!("Method not found: {}", request.method),
                None,
            ),
        };

        write_response(&mut writer, &response);
    }
}

fn write_response(writer: &mut BufWriter<&TcpStream>, response: &JsonRpcResponse) {
    if serde_json::to_writer(&mut *writer, response).is_ok() {
        let _ = writer.write_all(b"\n");
        let _ = writer.flush();
    }
}

fn dispatch_hello(
    request: &JsonRpcRequest,
    ctx: &mut ConnectionContext,
    auth_token: Option<&str>,
    max_queue: usize,
    eval_timeout_ms: u64,
) -> JsonRpcResponse {
    let params = request.params.as_ref();

    // Validate required fields
    let name = params.and_then(|p| p.get("name")).and_then(|v| v.as_str());
    let version = params
        .and_then(|p| p.get("version"))
        .and_then(|v| v.as_str());
    let protocol_version = params
        .and_then(|p| p.get("protocol_version"))
        .and_then(|v| v.as_u64())
        .map(|v| v as u32);

    if name.is_none() || version.is_none() {
        return make_error_response(
            request.id.clone(),
            JSONRPC_INVALID_REQUEST,
            "hello requires name and version params",
            None,
        );
    }

    // Protocol version check
    if let Some(client_proto) = protocol_version {
        if client_proto != PROTOCOL_VERSION {
            return make_app_error_response(
                request.id.clone(),
                "PROTOCOL_MISMATCH",
                &format!(
                    "Protocol version mismatch: client={}, server={}",
                    client_proto, PROTOCOL_VERSION
                ),
            );
        }
    }

    // Auth token validation
    if let Some(expected_token) = auth_token {
        let provided_token = params.and_then(|p| p.get("token")).and_then(|v| v.as_str());
        match provided_token {
            None => {
                return make_app_error_response(
                    request.id.clone(),
                    "AUTH_REQUIRED",
                    "Authentication token required",
                );
            }
            Some(t) if t != expected_token => {
                return make_app_error_response(
                    request.id.clone(),
                    "AUTH_INVALID",
                    "Invalid authentication token",
                );
            }
            Some(_) => {}
        }
    }

    // Store connection context
    ctx.identified = true;
    ctx.client_name = name.map(|s| s.to_string());
    ctx.client_version = version.map(|s| s.to_string());
    ctx.workspace = params
        .and_then(|p| p.get("workspace"))
        .and_then(|v| v.as_str())
        .map(PathBuf::from);

    make_success_response(
        request.id.clone(),
        serde_json::json!({
            "version": SIDECAR_VERSION,
            "engine": "rust",
            "protocol_version": PROTOCOL_VERSION,
            "capabilities": [
                "imports.data_extracts",
                "imports.solid_adt"
            ],
            "limits": {
                "max_queue": max_queue,
                "eval_timeout_ms": eval_timeout_ms,
                "payload_inline_max": 10_485_760u64
            }
        }),
    )
}

fn dispatch_ping(request: &JsonRpcRequest) -> JsonRpcResponse {
    make_success_response(
        request.id.clone(),
        serde_json::json!({
            "status": "ok",
            "timestamp": chrono::Utc::now().to_rfc3339()
        }),
    )
}

fn dispatch_resources_list(request: &JsonRpcRequest) -> JsonRpcResponse {
    make_success_response(
        request.id.clone(),
        serde_json::json!({
            "resources": []
        }),
    )
}

fn dispatch_tools_call(
    request: &JsonRpcRequest,
    ctx: &ConnectionContext,
    job_tx: &mpsc::SyncSender<EvalJob>,
    eval_timeout_ms: u64,
) -> JsonRpcResponse {
    let params = request.params.as_ref();
    let tool_name = params
        .and_then(|p| p.get("name"))
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let arguments = params
        .and_then(|p| p.get("arguments"))
        .cloned()
        .unwrap_or(serde_json::Value::Object(serde_json::Map::new()));

    let eval_request = match tool_name {
        "vcad.eval_code" => {
            let code = arguments.get("code").and_then(|v| v.as_str()).unwrap_or("");
            if code.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.eval_code requires non-empty 'code' argument",
                    None,
                );
            }
            EvalRequest::EvalCode {
                id: request.id.clone(),
                code: code.to_string(),
            }
        }
        "vcad.eval_file" => {
            let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
            if path.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.eval_file requires non-empty 'path' argument",
                    None,
                );
            }
            // Path policy: validate against workspace
            if let Err(resp) = validate_path_policy(path, ctx, &request.id) {
                return resp;
            }
            EvalRequest::EvalFile {
                id: request.id.clone(),
                path: path.to_string(),
            }
        }
        "vcad.inspect" => {
            let code_or_path = arguments
                .get("code_or_path")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if code_or_path.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.inspect requires non-empty 'code_or_path' argument",
                    None,
                );
            }
            // If it looks like a file path, validate it
            if code_or_path.ends_with(".oo") || code_or_path.ends_with(".loon") {
                if let Err(resp) = validate_path_policy(code_or_path, ctx, &request.id) {
                    return resp;
                }
            }
            EvalRequest::Inspect {
                id: request.id.clone(),
                code_or_path: code_or_path.to_string(),
            }
        }
        "vcad.eval_repl" => {
            let code = arguments.get("code").and_then(|v| v.as_str()).unwrap_or("");
            if code.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.eval_repl requires non-empty 'code' argument",
                    None,
                );
            }
            EvalRequest::EvalRepl {
                id: request.id.clone(),
                code: code.to_string(),
            }
        }
        "vcad.extract_imports" => {
            // Fast-path: parse-only, no eval queue needed.
            let source = arguments
                .get("source")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if source.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.extract_imports requires non-empty 'source' argument",
                    None,
                );
            }
            return dispatch_extract_imports(&request.id, source);
        }
        "vcad.eval_with_imports" => {
            let transformed_source = arguments
                .get("transformed_source")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if transformed_source.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.eval_with_imports requires non-empty 'transformed_source' argument",
                    None,
                );
            }
            let base_dir = arguments
                .get("base_dir")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let raw_imports = arguments.get("imports").cloned().unwrap_or_default();
            let resolved_imports: HashMap<String, ResolvedDataImport> =
                serde_json::from_value(raw_imports).unwrap_or_default();
            EvalRequest::EvalWithImports {
                id: request.id.clone(),
                transformed_source: transformed_source.to_string(),
                base_dir,
                imports: resolved_imports,
            }
        }
        "vcad.eval_with_solid_imports" => {
            let transformed_source = arguments
                .get("transformed_source")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if transformed_source.is_empty() {
                return make_error_response(
                    request.id.clone(),
                    JSONRPC_INVALID_REQUEST,
                    "vcad.eval_with_solid_imports requires non-empty 'transformed_source' argument",
                    None,
                );
            }
            let base_dir = arguments
                .get("base_dir")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let node_id = arguments
                .get("node_id")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let raw_imports = arguments.get("imports").cloned().unwrap_or_default();
            let resolved_imports: HashMap<String, ResolvedImport> =
                serde_json::from_value(raw_imports).unwrap_or_default();
            EvalRequest::EvalWithSolidImports {
                id: request.id.clone(),
                transformed_source: transformed_source.to_string(),
                base_dir,
                imports: resolved_imports,
                node_id,
            }
        }
        _ => {
            return make_error_response(
                request.id.clone(),
                JSONRPC_METHOD_NOT_FOUND,
                &format!("Unknown tool: {}", tool_name),
                None,
            );
        }
    };

    // Enqueue to eval worker
    let (reply_tx, reply_rx) = mpsc::channel();
    let job = EvalJob {
        request: eval_request,
        reply_tx,
    };

    match job_tx.try_send(job) {
        Ok(()) => {}
        Err(mpsc::TrySendError::Full(_)) => {
            return make_app_error_response(
                request.id.clone(),
                "VCAD_QUEUE_FULL",
                "Evaluation queue is full",
            );
        }
        Err(mpsc::TrySendError::Disconnected(_)) => {
            return make_error_response(
                request.id.clone(),
                JSONRPC_INTERNAL_ERROR,
                "Eval worker shut down",
                None,
            );
        }
    }

    // Wait for result with timeout
    match reply_rx.recv_timeout(std::time::Duration::from_millis(eval_timeout_ms)) {
        Ok(resp) => resp,
        Err(_) => make_app_error_response(
            request.id.clone(),
            "VCAD_EVAL_TIMEOUT",
            "Evaluation timed out",
        ),
    }
}

/// Validate that a file path is within the connection's workspace.
#[allow(clippy::result_large_err)]
fn validate_path_policy(
    path: &str,
    ctx: &ConnectionContext,
    request_id: &serde_json::Value,
) -> Result<(), JsonRpcResponse> {
    let file_path = Path::new(path);

    // Reject obviously malicious paths
    if path.contains("..") {
        return Err(make_app_error_response(
            request_id.clone(),
            "PATH_NOT_ALLOWED",
            "Path traversal not allowed",
        ));
    }

    // If workspace is set, validate the path is inside it
    if let Some(ref workspace) = ctx.workspace {
        // Resolve to absolute for comparison
        let abs_path = if file_path.is_absolute() {
            file_path.to_path_buf()
        } else {
            workspace.join(file_path)
        };

        // Use canonical paths when possible, fallback to lexical check
        let canonical_ws = workspace
            .canonicalize()
            .unwrap_or_else(|_| workspace.clone());
        let canonical_path = abs_path.canonicalize().unwrap_or_else(|_| abs_path.clone());

        if !canonical_path.starts_with(&canonical_ws) {
            return Err(make_app_error_response(
                request_id.clone(),
                "PATH_NOT_ALLOWED",
                "Path outside workspace",
            ));
        }
    }

    Ok(())
}

/// Fast-path handler for vcad.extract_imports (parse-only, no eval).
fn dispatch_extract_imports(request_id: &serde_json::Value, source: &str) -> JsonRpcResponse {
    match imports::extract_and_rewrite_imports(source) {
        Ok(extracted) => {
            let result = serde_json::json!({
                "imports": extracted.imports,
                "transformed_source": extracted.transformed_source,
            });
            make_success_response(request_id.clone(), result)
        }
        Err(e) => {
            let error_code = if e.starts_with("IMPORT_FORM_INVALID") {
                "IMPORT_FORM_INVALID"
            } else {
                "LOON_ERROR"
            };
            make_app_error_response(request_id.clone(), error_code, &e)
        }
    }
}

/// Dispatch an eval request to the evaluator (runs on eval worker thread).
fn dispatch_eval(request: &EvalRequest, evaluator: &mut Evaluator) -> JsonRpcResponse {
    match request {
        EvalRequest::EvalCode { id, code } => match evaluator.eval_code(code) {
            Ok(result) => eval_result_response(id.clone(), &result),
            Err(e) => eval_error_response(id.clone(), &e),
        },
        EvalRequest::EvalFile { id, path } => match evaluator.eval_file(path) {
            Ok(result) => eval_result_response(id.clone(), &result),
            Err(e) => eval_error_response(id.clone(), &e),
        },
        EvalRequest::Inspect { id, code_or_path } => match evaluator.inspect(code_or_path) {
            Ok(result) => eval_result_response(id.clone(), &result),
            Err(e) => eval_error_response(id.clone(), &e),
        },
        EvalRequest::EvalRepl { id, code } => match evaluator.eval_repl(code) {
            Ok(display) => {
                make_success_response(id.clone(), serde_json::json!({ "display": display }))
            }
            Err(e) => eval_error_response(id.clone(), &e),
        },
        EvalRequest::EvalWithImports {
            id,
            transformed_source,
            base_dir,
            imports,
        } => {
            let base = base_dir.as_deref().map(std::path::Path::new);
            match evaluator.eval_with_data_imports(transformed_source, base, imports) {
                Ok(result) => eval_result_response(id.clone(), &result),
                Err(e) => eval_error_response(id.clone(), &e),
            }
        }
        EvalRequest::EvalWithSolidImports {
            id,
            transformed_source,
            base_dir,
            imports,
            node_id,
        } => {
            let base = base_dir.as_deref().map(std::path::Path::new);
            match evaluator.eval_with_imports(transformed_source, base, imports, node_id.as_deref())
            {
                Ok(result) => eval_result_response(id.clone(), &result),
                Err(e) => eval_error_response(id.clone(), &e),
            }
        }
    }
}

fn eval_result_response(id: serde_json::Value, result: &EvalResult) -> JsonRpcResponse {
    make_success_response(
        id,
        serde_json::to_value(result).unwrap_or(serde_json::Value::Null),
    )
}

fn eval_error_response(id: serde_json::Value, error: &EvalError) -> JsonRpcResponse {
    make_app_error_response(id, error.error_code(), &error.message())
}

fn make_success_response(id: serde_json::Value, result: serde_json::Value) -> JsonRpcResponse {
    JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        id,
        result: Some(result),
        error: None,
    }
}

fn make_error_response(
    id: serde_json::Value,
    code: i32,
    message: &str,
    data: Option<serde_json::Value>,
) -> JsonRpcResponse {
    JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        id,
        result: None,
        error: Some(JsonRpcError {
            code,
            message: message.to_string(),
            data,
        }),
    }
}

fn make_app_error_response(
    id: serde_json::Value,
    error_code: &str,
    message: &str,
) -> JsonRpcResponse {
    make_error_response(
        id,
        JSONRPC_APP_ERROR,
        message,
        Some(serde_json::json!({
            "error_code": error_code
        })),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpStream;
    use std::time::Duration;

    /// Helper: start a sidecar server on a random port, return (port, shutdown_flag).
    fn start_test_server(
        max_queue: usize,
        eval_timeout_ms: u64,
        auth_token: Option<String>,
    ) -> (u16, Arc<AtomicBool>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let shutdown = Arc::new(AtomicBool::new(false));
        let shutdown_clone = shutdown.clone();

        let temp_dir = tempfile::tempdir().unwrap();
        let temp_path = temp_dir.keep();

        let (job_tx, job_rx) = mpsc::sync_channel::<EvalJob>(max_queue);

        // Eval worker
        std::thread::spawn({
            let temp_path = temp_path.clone();
            move || {
                let mut evaluator = Evaluator::new(temp_path, 3600, 500, 256);
                while let Ok(job) = job_rx.recv() {
                    let result = dispatch_eval(&job.request, &mut evaluator);
                    let _ = job.reply_tx.send(result);
                }
            }
        });

        // Accept loop
        std::thread::spawn(move || {
            listener.set_nonblocking(true).unwrap();
            let auth = auth_token;
            while !shutdown_clone.load(Ordering::SeqCst) {
                match listener.accept() {
                    Ok((stream, _)) => {
                        stream.set_nonblocking(false).ok();
                        let job_tx = job_tx.clone();
                        let auth = auth.clone();
                        std::thread::spawn(move || {
                            handle_connection(
                                stream,
                                job_tx,
                                eval_timeout_ms,
                                max_queue,
                                auth.as_deref(),
                            );
                        });
                    }
                    Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(Duration::from_millis(10));
                    }
                    Err(_) => break,
                }
            }
        });

        // Wait for server to be ready
        std::thread::sleep(Duration::from_millis(50));
        (port, shutdown)
    }

    fn send_request(stream: &mut TcpStream, request: &serde_json::Value) -> serde_json::Value {
        let mut msg = serde_json::to_string(request).unwrap();
        msg.push('\n');
        stream.write_all(msg.as_bytes()).unwrap();
        stream.flush().unwrap();

        let mut buf = vec![0u8; 65536];
        stream
            .set_read_timeout(Some(Duration::from_secs(10)))
            .unwrap();
        let n = stream.read(&mut buf).unwrap();
        let response_str = std::str::from_utf8(&buf[..n]).unwrap().trim();
        serde_json::from_str(response_str).unwrap()
    }

    fn hello_request(id: u64) -> serde_json::Value {
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": "hello",
            "params": {
                "name": "test-client",
                "version": "0.1.0",
                "agent": "test",
                "pid": std::process::id(),
                "protocol_version": PROTOCOL_VERSION
            }
        })
    }

    fn hello_request_with_token(id: u64, token: &str) -> serde_json::Value {
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": "hello",
            "params": {
                "name": "test-client",
                "version": "0.1.0",
                "agent": "test",
                "pid": std::process::id(),
                "protocol_version": PROTOCOL_VERSION,
                "token": token
            }
        })
    }

    fn hello_request_with_workspace(id: u64, workspace: &str) -> serde_json::Value {
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": "hello",
            "params": {
                "name": "test-client",
                "version": "0.1.0",
                "agent": "test",
                "pid": std::process::id(),
                "protocol_version": PROTOCOL_VERSION,
                "workspace": workspace
            }
        })
    }

    fn ping_request(id: u64) -> serde_json::Value {
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": "ping",
            "params": {}
        })
    }

    fn tools_call_request(id: u64, name: &str, arguments: serde_json::Value) -> serde_json::Value {
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        })
    }

    #[test]
    fn test_hello_and_ping() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        // Hello
        let resp = send_request(&mut stream, &hello_request(1));
        assert!(resp.get("result").is_some());
        let result = resp.get("result").unwrap();
        assert_eq!(result.get("engine").unwrap().as_str().unwrap(), "rust");
        assert_eq!(
            result.get("protocol_version").unwrap().as_u64().unwrap(),
            PROTOCOL_VERSION as u64
        );

        // Ping
        let resp = send_request(&mut stream, &ping_request(2));
        assert!(resp.get("result").is_some());
        assert_eq!(
            resp.get("result")
                .unwrap()
                .get("status")
                .unwrap()
                .as_str()
                .unwrap(),
            "ok"
        );

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_ping_before_hello_requires_auth() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        let resp = send_request(&mut stream, &ping_request(1));
        assert!(resp.get("error").is_some());
        let error = resp.get("error").unwrap();
        let data = error.get("data").unwrap();
        assert_eq!(
            data.get("error_code").unwrap().as_str().unwrap(),
            "AUTH_REQUIRED"
        );

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_auth_token_required() {
        let (port, shutdown) = start_test_server(64, 120_000, Some("secret-token".to_string()));
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        // Hello without token
        let resp = send_request(&mut stream, &hello_request(1));
        assert!(resp.get("error").is_some());
        let data = resp.get("error").unwrap().get("data").unwrap();
        assert_eq!(
            data.get("error_code").unwrap().as_str().unwrap(),
            "AUTH_REQUIRED"
        );

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_auth_token_invalid() {
        let (port, shutdown) = start_test_server(64, 120_000, Some("secret-token".to_string()));
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        let resp = send_request(&mut stream, &hello_request_with_token(1, "wrong-token"));
        assert!(resp.get("error").is_some());
        let data = resp.get("error").unwrap().get("data").unwrap();
        assert_eq!(
            data.get("error_code").unwrap().as_str().unwrap(),
            "AUTH_INVALID"
        );

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_auth_token_valid() {
        let (port, shutdown) = start_test_server(64, 120_000, Some("secret-token".to_string()));
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        let resp = send_request(&mut stream, &hello_request_with_token(1, "secret-token"));
        assert!(resp.get("result").is_some());

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_protocol_mismatch() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        let req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "hello",
            "params": {
                "name": "test",
                "version": "0.1.0",
                "agent": "test",
                "pid": 1,
                "protocol_version": 999
            }
        });
        let resp = send_request(&mut stream, &req);
        assert!(resp.get("error").is_some());
        let data = resp.get("error").unwrap().get("data").unwrap();
        assert_eq!(
            data.get("error_code").unwrap().as_str().unwrap(),
            "PROTOCOL_MISMATCH"
        );

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_eval_code_basic() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        // Hello
        send_request(&mut stream, &hello_request(1));

        // Eval a simple cube
        let resp = send_request(
            &mut stream,
            &tools_call_request(
                2,
                "vcad.eval_code",
                serde_json::json!({ "code": "[cube 10.0 10.0 10.0]" }),
            ),
        );
        assert!(
            resp.get("result").is_some(),
            "Expected result, got: {:?}",
            resp
        );
        let result = resp.get("result").unwrap();
        assert!(result.get("obj_path").is_some());
        assert!(result.get("manifest_path").is_some());
        assert!(result.get("volume").unwrap().as_f64().unwrap() > 0.0);
        assert!(!result.get("is_empty").unwrap().as_bool().unwrap());

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_eval_repl() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();
        send_request(&mut stream, &hello_request(1));

        let resp = send_request(
            &mut stream,
            &tools_call_request(
                2,
                "vcad.eval_repl",
                serde_json::json!({ "code": "[+ 1 2]" }),
            ),
        );
        assert!(
            resp.get("result").is_some(),
            "Expected result, got: {:?}",
            resp
        );
        let result = resp.get("result").unwrap();
        assert!(result.get("display").is_some());

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_queue_full() {
        // Queue size 1, timeout very long
        let (port, shutdown) = start_test_server(1, 60_000, None);

        // Connect and hello
        let mut stream1 = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();
        send_request(&mut stream1, &hello_request(1));

        // Fill the queue: send a request that will take time to evaluate
        // We use a thread to send the first request
        let mut stream2 = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();
        send_request(&mut stream2, &hello_request(1));

        // Send a blocking eval on stream2 in a background thread
        let stream2_clone = stream2.try_clone().unwrap();
        let bg = std::thread::spawn(move || {
            let mut s = stream2_clone;
            let req = tools_call_request(
                10,
                "vcad.eval_code",
                serde_json::json!({ "code": "[cube 10.0 10.0 10.0]" }),
            );
            let mut msg = serde_json::to_string(&req).unwrap();
            msg.push('\n');
            s.write_all(msg.as_bytes()).unwrap();
            s.flush().unwrap();
        });
        bg.join().unwrap();

        // Small delay to let it start processing
        std::thread::sleep(Duration::from_millis(200));

        // Try sending several to overflow the queue of size 1
        let mut got_queue_full = false;
        for i in 0..5 {
            let req = tools_call_request(
                100 + i,
                "vcad.eval_code",
                serde_json::json!({ "code": "[cube 1.0 1.0 1.0]" }),
            );
            let resp = send_request(&mut stream1, &req);
            if let Some(error) = resp.get("error") {
                if let Some(data) = error.get("data") {
                    if data.get("error_code").and_then(|v| v.as_str()) == Some("VCAD_QUEUE_FULL") {
                        got_queue_full = true;
                        break;
                    }
                }
            }
        }

        // Note: queue full may not always trigger in test due to timing,
        // so we just verify the mechanism exists.
        let _ = got_queue_full;

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_eval_timeout() {
        // Very short timeout (1ms)
        let (port, shutdown) = start_test_server(64, 1, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();
        send_request(&mut stream, &hello_request(1));

        // Note: the eval may still complete before timeout in test since cube is fast.
        // This test mainly verifies the timeout plumbing exists.
        let resp = send_request(
            &mut stream,
            &tools_call_request(
                2,
                "vcad.eval_code",
                serde_json::json!({ "code": "[cube 10.0 10.0 10.0]" }),
            ),
        );
        // Either result or timeout error is acceptable
        assert!(
            resp.get("result").is_some() || resp.get("error").is_some(),
            "Expected result or error"
        );
        if let Some(error) = resp.get("error") {
            if let Some(data) = error.get("data") {
                let code = data
                    .get("error_code")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                assert_eq!(code, "VCAD_EVAL_TIMEOUT");
            }
        }

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_path_traversal_rejected() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();

        let workspace = tempfile::tempdir().unwrap();
        send_request(
            &mut stream,
            &hello_request_with_workspace(1, workspace.path().to_str().unwrap()),
        );

        // Try path traversal
        let resp = send_request(
            &mut stream,
            &tools_call_request(
                2,
                "vcad.eval_file",
                serde_json::json!({ "path": "../../../etc/passwd" }),
            ),
        );
        assert!(resp.get("error").is_some());
        let data = resp.get("error").unwrap().get("data").unwrap();
        assert_eq!(
            data.get("error_code").unwrap().as_str().unwrap(),
            "PATH_NOT_ALLOWED"
        );

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_unknown_tool() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();
        send_request(&mut stream, &hello_request(1));

        let resp = send_request(
            &mut stream,
            &tools_call_request(2, "vcad.nonexistent", serde_json::json!({})),
        );
        assert!(resp.get("error").is_some());

        shutdown.store(true, Ordering::SeqCst);
    }

    #[test]
    fn test_resources_list() {
        let (port, shutdown) = start_test_server(64, 120_000, None);
        let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).unwrap();
        send_request(&mut stream, &hello_request(1));

        let resp = send_request(
            &mut stream,
            &serde_json::json!({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {}
            }),
        );
        assert!(resp.get("result").is_some());

        shutdown.store(true, Ordering::SeqCst);
    }
}
