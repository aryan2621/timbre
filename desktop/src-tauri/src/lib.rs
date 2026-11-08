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

/// Debug builds run the repo's Python; release builds run the bundled sidecar
/// (`binaries/voiceclone-api`, placed next to the app executable by Tauri).
fn spawn_backend(token: &str) -> std::io::Result<Child> {
    let mut command = if cfg!(debug_assertions) {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let python = if cfg!(windows) { ".venv/Scripts/python.exe" } else { ".venv/bin/python" };
        let mut command = Command::new(root.join(python));
        command.args(["-m", "app.api.server"]).current_dir(root);
        command
    } else {
        let exe = std::env::current_exe()?;
        let name = if cfg!(windows) { "voiceclone-api.exe" } else { "voiceclone-api" };
        Command::new(exe.with_file_name(name))
    };
    command.env("VOICECLONE_API_TOKEN", token).spawn()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let token = uuid::Uuid::new_v4().simple().to_string();
    // A failed start is not fatal: the UI shows "engine not running" and the
    // developer may already run the server by hand.
    let child = spawn_backend(&token)
        .map_err(|error| eprintln!("could not start the Timbre API: {error}"))
        .ok();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(Backend { token, child: Mutex::new(child) })
        .invoke_handler(tauri::generate_handler![api_token])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(mut child) = app.state::<Backend>().child.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
