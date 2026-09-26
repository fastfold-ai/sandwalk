//! FAS-107 · Fase 1g · deep link nativo desde banners de macOS.
//!
//! El plugin oficial `tauri-plugin-notification` (v2) **no** expone el
//! callback `onAction` en desktop — solo en móvil. La doc de Tauri lo
//! dice explícito: *"The Actions API is only available on mobile
//! platforms."*
//!
//! Aquí registramos un `UNUserNotificationCenterDelegate` propio en
//! macOS que:
//!
//! 1. Envía notificaciones con un `tag` custom en `userInfo` (el id del
//!    chat/terminal que emitió).
//! 2. Al click del usuario en el banner (o entrada en el Notification
//!    Center), extrae el `tag` y emite el evento Tauri
//!    `sandwalk://notification-click` con el tag como payload.
//! 3. El frontend escucha ese evento y llama `openItem(tag)` — el
//!    resolver decide si es standalone o hijo de split y navega al
//!    pane exacto.
//!
//! Implementación nativa Rust con `objc2-user-notifications` — cero
//! dependencia de plugin externo, mismo patrón que Zed.

#![cfg(target_os = "macos")]

use std::io::Write;
use std::sync::OnceLock;

use block2::RcBlock;
use objc2::rc::Retained;
use objc2::runtime::{AnyObject, Bool, ProtocolObject};
use objc2::{define_class, msg_send, MainThreadOnly};
use objc2_foundation::{NSDictionary, NSError, NSObject, NSObjectProtocol, NSString, NSUUID};
use objc2_user_notifications::{
    UNAuthorizationOptions, UNMutableNotificationContent, UNNotification,
    UNNotificationPresentationOptions, UNNotificationRequest, UNNotificationResponse,
    UNUserNotificationCenter, UNUserNotificationCenterDelegate,
};
use tauri::{AppHandle, Emitter};

pub const NOTIFICATION_CLICK_EVENT: &str = "sandwalk://notification-click";

/// Escribe una línea al log de deep link: `~/Library/Logs/Sandwalk/deep-link.log`.
/// Útil en release build donde `eprintln!` se pierde. Antonio abre el
/// archivo con TextEdit y ve paso a paso el flujo (delegate registrado,
/// notif enviada, click recibido, tag extraído).
///
/// FAS-107 · Fase 1j: se abre el archivo una sola vez (OnceLock) y se
/// mantiene abierto en modo append durante la vida del proceso. Antes
/// se abría y cerraba por cada `log_line`, generando syscalls
/// sostenidos en ráfagas de notificaciones. `Mutex<File>` sincroniza
/// escrituras desde el delegate (main thread ObjC) y desde el comando
/// `sandwalk_notify` (thread del runtime Tauri).
static LOG_FILE: OnceLock<std::sync::Mutex<Option<std::fs::File>>> = OnceLock::new();

fn log_line(msg: &str) {
    eprintln!("{msg}");
    let cell = LOG_FILE.get_or_init(|| {
        let file = dirs::home_dir().and_then(|home| {
            let dir = home.join("Library/Logs/Sandwalk");
            std::fs::create_dir_all(&dir).ok()?;
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(dir.join("deep-link.log"))
                .ok()
        });
        std::sync::Mutex::new(file)
    });
    if let Ok(mut guard) = cell.lock() {
        if let Some(file) = guard.as_mut() {
            let _ = writeln!(file, "[{}] {}", chrono_now(), msg);
        }
    }
}

/// Timestamp corto (`HH:MM:SS`) sin dep externo — usa `SystemTime` de std.
fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let h = (secs / 3600) % 24;
    let m = (secs / 60) % 60;
    let s = secs % 60;
    format!("{h:02}:{m:02}:{s:02}")
}

// Guardamos el `AppHandle` en un OnceLock para que el delegate (que vive
// como singleton en el runtime de macOS) pueda emitir eventos al
// frontend sin tenerlo en un campo `ivar`. `AppHandle` es `Clone`,
// `Send` y `Sync`.
static APP_HANDLE: OnceLock<AppHandle> = OnceLock::new();

define_class!(
    #[unsafe(super(NSObject))]
    #[thread_kind = MainThreadOnly]
    #[name = "SandwalkNotificationDelegate"]
    struct SandwalkNotificationDelegate;

    unsafe impl NSObjectProtocol for SandwalkNotificationDelegate {}

    unsafe impl UNUserNotificationCenterDelegate for SandwalkNotificationDelegate {
        /// Click del usuario en el banner o en la entrada del
        /// Notification Center. Extraemos el `tag` de `userInfo` y lo
        /// emitimos al frontend.
        #[unsafe(method(userNotificationCenter:didReceiveNotificationResponse:withCompletionHandler:))]
        unsafe fn did_receive_response(
            &self,
            _center: &UNUserNotificationCenter,
            response: &UNNotificationResponse,
            completion_handler: &block2::Block<dyn Fn()>,
        ) {
            log_line("[sandwalk] delegate did_receive_response fired");
            let notification: Retained<UNNotification> = response.notification();
            let request = notification.request();
            let content = request.content();
            let user_info: Retained<NSDictionary> = content.userInfo();
            let key = NSString::from_str("tag");
            // FAS-107 · Fase 1j: `downcast_ref::<NSString>()` es
            // seguro — devuelve `None` si el objeto no es NSString.
            // Antes usábamos `transmute` que crasheaba si el valor
            // guardado en userInfo cambiaba de tipo (edge case:
            // notif del sistema legacy sin `tag`, o valor no string).
            let key_obj: &AnyObject = key.as_ref();
            let tag_obj: Option<Retained<AnyObject>> =
                unsafe { msg_send![&*user_info, objectForKey: key_obj] };
            let tag_str: Option<String> = tag_obj
                .as_deref()
                .and_then(|obj| obj.downcast_ref::<NSString>())
                .map(|ns| ns.to_string());
            if let Some(tag) = tag_str {
                log_line(&format!("[sandwalk] delegate tag={:?}", tag));
                if !tag.is_empty() {
                    if let Some(handle) = APP_HANDLE.get() {
                        match handle.emit(NOTIFICATION_CLICK_EVENT, tag.clone()) {
                            Ok(_) => log_line(&format!(
                                "[sandwalk] delegate emitted event tag={:?}",
                                tag
                            )),
                            Err(err) => log_line(&format!(
                                "[sandwalk] delegate emit ERROR: {}",
                                err
                            )),
                        }
                    } else {
                        log_line("[sandwalk] delegate APP_HANDLE not set");
                    }
                }
            } else {
                log_line("[sandwalk] delegate userInfo has no 'tag' key");
            }
            completion_handler.call(());
        }

        /// Cuando la app está en foreground, macOS por defecto NO
        /// muestra el banner. Sandwalk quiere el banner también en ese
        /// caso (para que el usuario lo vea aunque tenga la app abierta
        /// pero mirando otro tab). Devolvemos `.banner | .sound` para
        /// forzarlo.
        #[unsafe(method(userNotificationCenter:willPresentNotification:withCompletionHandler:))]
        unsafe fn will_present(
            &self,
            _center: &UNUserNotificationCenter,
            _notification: &UNNotification,
            completion_handler: &block2::Block<dyn Fn(UNNotificationPresentationOptions)>,
        ) {
            let options = UNNotificationPresentationOptions::Banner
                | UNNotificationPresentationOptions::Sound;
            completion_handler.call((options,));
        }
    }
);

/// Registra el delegate custom en el `UNUserNotificationCenter` global.
/// Debe llamarse una vez durante el `setup()` del `tauri::Builder`,
/// desde el main thread. El permiso de notificaciones ya se maneja
/// vía `tauri-plugin-notification` (frontend `requestPermission`).
static AUTHORIZATION_REQUESTED: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);

/// True cuando el proceso corre dentro de un `.app` bundle con
/// `CFBundleIdentifier`. En `tauri:dev` el binario suelto vive en
/// `target/debug/sandwalk-desktop` sin bundle real — llamar a
/// `UNUserNotificationCenter.currentNotificationCenter()` tira
/// `bundleProxyForCurrentProcess is nil` y crashea toda la app.
fn is_bundled() -> bool {
    // Check por path del executable: solo un `.app` real vive dentro de
    // `X.app/Contents/MacOS/binary`. En `tauri:dev` el binario está en
    // `target/debug/sandwalk-desktop` — sin `.app/Contents/MacOS/` en
    // la ruta. Chequear `bundleIdentifier` no sirve porque Tauri lo
    // asigna igual en dev.
    match std::env::current_exe() {
        Ok(path) => path
            .to_str()
            .map(|s| s.contains(".app/Contents/MacOS/"))
            .unwrap_or(false),
        Err(_) => false,
    }
}

pub fn install_delegate(app_handle: AppHandle) {
    let _ = APP_HANDLE.set(app_handle);
    // FAS-107 · Fase 1h: en `tauri:dev` (binario suelto sin `.app`
    // bundleado) `UNUserNotificationCenter` crashea con
    // `bundleProxyForCurrentProcess is nil`. Solo montamos el delegate
    // cuando la app corre desde un bundle real (release firmado con
    // Developer ID). En dev la app arranca sin banners nativos ni
    // deep link — hay que usar el `.app` en `~/Applications/Sandwalk.app`
    // para probar esas features.
    if !is_bundled() {
        log_line(
            "[sandwalk] UN delegate skipped (not bundled — use ~/Applications/Sandwalk.app for native notifs)",
        );
        return;
    }
    unsafe {
        let mtm = objc2::MainThreadMarker::new()
            .expect("install_delegate must run on main thread");
        let delegate: Retained<SandwalkNotificationDelegate> =
            msg_send![SandwalkNotificationDelegate::alloc(mtm), init];
        let center = UNUserNotificationCenter::currentNotificationCenter();
        let proto: &ProtocolObject<dyn UNUserNotificationCenterDelegate> =
            ProtocolObject::from_ref(&*delegate);
        center.setDelegate(Some(proto));
        log_line("[sandwalk] UN delegate installed");
        // `setDelegate:` guarda una `weak` reference. Retenemos el
        // delegate para toda la vida del proceso con `mem::forget` —
        // `Retained<MainThreadOnly>` no implementa `Send + Sync` así
        // que no podemos guardarlo en un static.
        std::mem::forget(delegate);
    }
    // Notar: pedimos autorización al PRIMER `sandwalk_notify`, no
    // acá. macOS deniega `requestAuthorization` silenciosamente
    // cuando la app aún no está foreground (setup corre antes de que
    // se muestre la ventana). Referencia: Apple doc "Asking
    // Permission to Use Notifications".
}

fn ensure_authorization_requested() {
    use std::sync::atomic::Ordering;
    if !is_bundled() {
        return;
    }
    if AUTHORIZATION_REQUESTED.swap(true, Ordering::AcqRel) {
        return;
    }
    unsafe {
        let center = UNUserNotificationCenter::currentNotificationCenter();
        let options = UNAuthorizationOptions::Alert
            | UNAuthorizationOptions::Sound
            | UNAuthorizationOptions::Badge;
        let completion = RcBlock::new(|granted: Bool, _err: *mut NSError| {
            log_line(&format!(
                "[sandwalk] UN authorization granted = {}",
                granted.as_bool()
            ));
        });
        center.requestAuthorizationWithOptions_completionHandler(options, &completion);
    }
}

/// Envía una notificación nativa con `tag` en `userInfo`. Reemplaza al
/// `sendNotification` del plugin oficial cuando el banner debe ser
/// clickeable — solo así el delegate ve el `tag` de vuelta.
#[tauri::command]
pub fn sandwalk_notify(
    title: String,
    body: Option<String>,
    tag: Option<String>,
) -> Result<(), String> {
    log_line(&format!(
        "[sandwalk] sandwalk_notify title={:?} tag={:?}",
        title, tag
    ));
    // Ver `install_delegate` — llamar a UNUserNotificationCenter en
    // dev bare-binary crashea. Devolvemos error controlado en vez de
    // matar el proceso; el frontend ya cae al plugin oficial cuando
    // sandwalk_notify falla.
    if !is_bundled() {
        return Err("not bundled — UN* unavailable in dev".to_string())
    }
    ensure_authorization_requested();
    unsafe {
        let center = UNUserNotificationCenter::currentNotificationCenter();
        let content = UNMutableNotificationContent::new();
        content.setTitle(&*NSString::from_str(&title));
        if let Some(b) = body.as_deref() {
            content.setBody(&*NSString::from_str(b));
        }
        if let Some(t) = tag.as_deref() {
            let key = NSString::from_str("tag");
            let value = NSString::from_str(t);
            // `dictionaryWithObject:forKey:` de NSDictionary devuelve un
            // dict con un solo par — es la vía más simple sin tener
            // que negociar tipos genéricos.
            let key_obj: &AnyObject = std::mem::transmute::<&NSString, &AnyObject>(&*key);
            let value_obj: &AnyObject = std::mem::transmute::<&NSString, &AnyObject>(&*value);
            let dict: Retained<NSDictionary> = msg_send![
                objc2::class!(NSDictionary),
                dictionaryWithObject: value_obj,
                forKey: key_obj,
            ];
            content.setUserInfo(&*dict);
        }
        let uuid = NSUUID::new();
        let identifier = uuid.UUIDString();
        // trigger: nil → entrega inmediata.
        let request = UNNotificationRequest::requestWithIdentifier_content_trigger(
            &*identifier,
            &*content,
            None,
        );
        // completion: nil — no necesitamos saber cuándo se aceptó la
        // notif; el envío es fire-and-forget. Evita tener que
        // construir un `Block` (RcBlock/StackBlock tiene requisitos
        // de `IntoBlock` que complican por 0 valor real).
        center.addNotificationRequest_withCompletionHandler(&*request, None);
    }
    Ok(())
}
