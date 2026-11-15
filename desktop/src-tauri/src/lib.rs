use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Emitter, Manager, RunEvent, State, WindowEvent};

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

/// macOS: the notification plugin uses Apple's retired API, which never registers the app.
/// These go through UNUserNotificationCenter instead. Other platforms return None and the UI uses the plugin.
#[cfg(target_os = "macos")]
mod native_notify {
    use std::sync::mpsc;
    use std::time::Duration;

    use block2::RcBlock;
    use objc2::runtime::Bool;
    use objc2_foundation::{NSError, NSString};
    use objc2_user_notifications::{
        UNAuthorizationOptions, UNMutableNotificationContent, UNNotificationRequest, UNUserNotificationCenter,
    };

    pub fn authorize() -> bool {
        let (tx, rx) = mpsc::channel();
        let handler = RcBlock::new(move |granted: Bool, _error: *mut NSError| {
            let _ = tx.send(granted.as_bool());
        });
        UNUserNotificationCenter::currentNotificationCenter().requestAuthorizationWithOptions_completionHandler(
            UNAuthorizationOptions::Alert | UNAuthorizationOptions::Sound,
            &handler,
        );
        // The user may sit on the system prompt; give up after a minute rather than hang forever.
        rx.recv_timeout(Duration::from_secs(60)).unwrap_or(false)
    }

    pub fn send(title: &str, body: &str) {
        let content = UNMutableNotificationContent::new();
        content.setTitle(&NSString::from_str(title));
        content.setBody(&NSString::from_str(body));
        let id = NSString::from_str(&uuid::Uuid::new_v4().to_string());
        let request = UNNotificationRequest::requestWithIdentifier_content_trigger(&id, &content, None);
        UNUserNotificationCenter::currentNotificationCenter().addNotificationRequest_withCompletionHandler(&request, None);
    }
}

/// Some(granted) on macOS, None elsewhere (the UI then uses the notification plugin).
#[tauri::command]
async fn notify_authorize() -> Option<bool> {
    #[cfg(target_os = "macos")]
    return Some(native_notify::authorize());
    #[cfg(not(target_os = "macos"))]
    None
}

/// True when the notification was handed to macOS; false means the UI should use the plugin.
#[tauri::command]
async fn notify_native(title: String, body: String) -> bool {
    #[cfg(target_os = "macos")]
    {
        native_notify::send(&title, &body);
        return true;
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = (title, body);
        false
    }
}

/// Opens System Settings on the Notifications pane (macOS only; a no-op elsewhere).
#[tauri::command]
fn open_notification_settings() {
    #[cfg(target_os = "macos")]
    let _ = Command::new("open").arg("x-apple.systempreferences:com.apple.Notifications-Settings.extension").spawn();
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(mut child) = app.state::<Backend>().child.lock().unwrap().take() {
        kill_tree(&mut child);
    }
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
        .invoke_handler(tauri::generate_handler![api_token, notify_authorize, notify_native, open_notification_settings])
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                // Keep the window alive so the UI can show "Closing" while the backend dies.
                api.prevent_close();
                let _ = window.emit("app-closing", ());
                let app = window.app_handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(150)); // let the overlay paint
                    stop_backend(&app);
                    app.exit(0);
                });
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_backend(app);
            }
        });
}
