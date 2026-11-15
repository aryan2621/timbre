use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, RunEvent, State};

/// The Python API process plus the per-launch secret the UI must send to it.
struct Backend {
    token: String,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn api_token(backend: State<Backend>) -> String {
    backend.token.clone()
}

/// Debug builds run the repo's Python; release builds run the bundled onedir sidecar
/// (`voiceclone-api/voiceclone-api` inside the app's resource folder).
fn spawn_backend(token: &str, resources: Option<PathBuf>) -> std::io::Result<Child> {
    let mut command = if cfg!(debug_assertions) {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let python = if cfg!(windows) { ".venv/Scripts/python.exe" } else { ".venv/bin/python" };
        let mut command = Command::new(root.join(python));
        command.args(["-m", "app.api.server"]).current_dir(root);
        command
    } else {
        let dir = resources
            .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "no resource folder"))?
            .join("voiceclone-api");
        let name = if cfg!(windows) { "voiceclone-api.exe" } else { "voiceclone-api" };
        let mut command = Command::new(dir.join(name));
        command.current_dir(dir);
        command
    };
    #[cfg(unix)]
    std::os::unix::process::CommandExt::process_group(&mut command, 0);
    // Tauri puts the native servers (llama, whisper, ace) beside the app binary, not in resources.
    if let Some(dir) = std::env::current_exe().ok().and_then(|exe| exe.parent().map(PathBuf::from)) {
        command.env("VOICECLONE_NATIVE_DIR", dir);
    }
    command.env("VOICECLONE_API_TOKEN", token).spawn()
}

/// Kills the sidecar's whole process group, so nothing it spawned outlives it on port 8756 with a stale token.
fn kill_tree(child: &mut Child) {
    let pid = child.id().to_string();
    let _ = if cfg!(windows) {
        Command::new("taskkill").args(["/T", "/F", "/PID", &pid]).status()
    } else {
        Command::new("kill").args(["-KILL", &format!("-{pid}")]).status()
    };
    let _ = child.kill();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let token = uuid::Uuid::new_v4().simple().to_string();
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_notification::init())
        .manage(Backend { token, child: Mutex::new(None) })
        .setup(|app| {
            // A failed start is not fatal: the UI shows "engine not running" and the
            // developer may already run the server by hand.
            let backend = app.state::<Backend>();
            let child = spawn_backend(&backend.token, app.path().resource_dir().ok())
                .map_err(|error| eprintln!("could not start the Timbre API: {error}"))
                .ok();
            *backend.child.lock().unwrap() = child;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![api_token])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(mut child) = app.state::<Backend>().child.lock().unwrap().take() {
                    kill_tree(&mut child);
                }
            }
        });
}
