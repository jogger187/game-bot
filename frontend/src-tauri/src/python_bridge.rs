// Python 子進程管理 — 透過 JSON-RPC over stdin/stdout 與 Python 核心引擎通信
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

static REQUEST_ID: AtomicU64 = AtomicU64::new(1);

/// JSON-RPC 2.0 請求格式
#[derive(Debug, Serialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    id: u64,
    method: String,
    params: Value,
}

/// JSON-RPC 2.0 回應格式
#[derive(Debug, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: u64,
    pub result: Option<Value>,
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
    pub data: Option<Value>,
}

/// Python 引擎橋接器
pub struct PythonBridge {
    child: Mutex<Option<Child>>,
    python_path: String,
    engine_path: String,
}

impl PythonBridge {
    pub fn new(python_path: &str, engine_path: &str) -> Self {
        Self {
            child: Mutex::new(None),
            python_path: python_path.to_string(),
            engine_path: engine_path.to_string(),
        }
    }

    /// 啟動 Python 引擎子進程
    pub fn start(&self) -> Result<u32, String> {
        let mut guard = self.child.lock().map_err(|e| e.to_string())?;

        if guard.is_some() {
            return Err("Python 引擎已在運行中".to_string());
        }

        let child = Command::new(&self.python_path)
            .arg(&self.engine_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("無法啟動 Python 引擎: {}", e))?;

        let pid = child.id();
        *guard = Some(child);
        Ok(pid)
    }

    /// 停止 Python 引擎子進程
    pub fn stop(&self) -> Result<(), String> {
        let mut guard = self.child.lock().map_err(|e| e.to_string())?;

        if let Some(ref mut child) = *guard {
            child.kill().map_err(|e| format!("無法停止 Python 引擎: {}", e))?;
            child.wait().ok();
        }

        *guard = None;
        Ok(())
    }

    /// 發送 JSON-RPC 請求並等待回應
    pub fn call(&self, method: &str, params: Value) -> Result<Value, String> {
        let mut guard = self.child.lock().map_err(|e| e.to_string())?;

        let child = guard
            .as_mut()
            .ok_or("Python 引擎尚未啟動")?;

        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id: REQUEST_ID.fetch_add(1, Ordering::SeqCst),
            method: method.to_string(),
            params,
        };

        // 寫入 stdin
        let stdin = child
            .stdin
            .as_mut()
            .ok_or("無法存取 Python 引擎 stdin")?;

        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("序列化請求失敗: {}", e))?;

        writeln!(stdin, "{}", request_json)
            .map_err(|e| format!("寫入 Python 引擎失敗: {}", e))?;

        stdin
            .flush()
            .map_err(|e| format!("刷新 stdin 失敗: {}", e))?;

        // 從 stdout 讀取回應
        let stdout = child
            .stdout
            .as_mut()
            .ok_or("無法存取 Python 引擎 stdout")?;

        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        reader
            .read_line(&mut line)
            .map_err(|e| format!("讀取 Python 引擎回應失敗: {}", e))?;

        let response: JsonRpcResponse = serde_json::from_str(&line)
            .map_err(|e| format!("解析回應失敗: {} (原始: {})", e, line.trim()))?;

        if let Some(error) = response.error {
            return Err(format!("Python 引擎錯誤 [{}]: {}", error.code, error.message));
        }

        response.result.ok_or("回應中缺少 result".to_string())
    }

    /// 檢查引擎是否運行中
    pub fn is_running(&self) -> bool {
        let guard = self.child.lock();
        match guard {
            Ok(g) => g.is_some(),
            Err(_) => false,
        }
    }
}

impl Drop for PythonBridge {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}
