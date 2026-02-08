import { app, BrowserWindow, Tray, Menu, ipcMain, shell, dialog, nativeImage } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Configuration ---
const IS_DEV = process.env.NODE_ENV === 'development';

// Force local origins to be treated as secure contexts for Crypto API
app.commandLine.appendSwitch('unsafely-treat-insecure-origin-as-secure', 'http://127.0.0.1:8086,http://127.0.0.1:5173');
app.commandLine.appendSwitch('ignore-certificate-errors'); // Allow self-signed local certs for our suite
app.commandLine.appendSwitch('user-data-dir', path.join(app.getPath('userData'), 'chrome-data')); // Help persist the flag context

const PY_MODULE = 'proxion_keyring.rs.server'; // Folder 'rs' is in root
const PY_PORT = 8788; // Port RS runs on

// --- Global State ---
let mainWindow;
let tray;
let pyProc = null;
let sessionContext = { webId: null, token: null };
let managedPorts = new Set(['8787', '8788', '9999']); // Core ports

// --- Loader ---
const loadAppRegistry = () => {
    try {
        const appsPath = path.join(__dirname, '../src/data/apps.json');
        if (fs.existsSync(appsPath)) {
            const apps = JSON.parse(fs.readFileSync(appsPath, 'utf8'));
            apps.forEach(app => {
                if (app.port && app.port !== 0) {
                    managedPorts.add(app.port.toString());
                }
            });
            console.log(`[Main]: Loaded ${managedPorts.size} managed ports from registry.`);
        }
    } catch (err) {
        console.error('[Main]: Failed to load apps.json:', err);
    }
};

// --- Backend Management ---
const startPythonBackend = async () => {
    if (pyProc) return;

    // Check if backend is already running (e.g. manual CLI start)
    try {
        const resp = await fetch(`http://127.0.0.1:${PY_PORT}/mesh/dns/status`, { timeout: 500 });
        if (resp.ok) {
            console.log('[Main]: Backend already running on port ' + PY_PORT + '. Skipping spawn.');
            return;
        }
    } catch (e) {
        // Not running, proceed to start
    }

    // Also check if Pod Proxy (8089) is already running
    try {
        const resp = await fetch('http://127.0.0.1:8889/pod/', { timeout: 500 });
        if (resp.status === 401 || resp.ok) {
            console.log('[Main]: Pod Proxy already running on port 8889. Skipping spawn.');
            return;
        }
    } catch (e) {
        // Not running, proceed to start
    }

    console.log('[Main]: Starting Python Backend...');

    // We assume the user has run the setup wizard, so Environment variables are set globally?
    // Or we might need to set them here.
    // For robustness, let's set the critical ones.
    const env = {
        ...process.env,
        'proxion-keyring_WG_MUTATION': 'true',
        // proxion-keyring_WG_INTERFACE: 'wg-proxion-keyring', // Usually set by wizard globally
        // PYTHONPATH: ... // This is tricky in distributed app.
        // In dev: We rely on current venv/path.
        // In prod: We would bundle a python executable or use pyinstaller.
    };

    // In Dev: Assume 'python' is in PATH and we are at repo root.
    // We need to resolve the repo root from executing path.
    // dashboard/electron/main.js -> dashboard/electron -> dashboard -> proxion-keyring -> REPO ROOT
    const repoRoot = path.resolve(__dirname, '..', '..', '..');

    // Actually, standard structure: proxion-keyring (package) is in CWD?
    // If we run from 'dashboard', we need step up.
    // Let's assume we run from 'dashboard' for now.

    // NOTE: For "It Just Works", we might need to distribute the backend binary.
    // For this Dev stage, we spawn `python`.

    const keyringPath = path.join(__dirname, '../../');
    const corePath = path.join(__dirname, '../../../proxion-core/src');

    pyProc = spawn('python', ['-m', PY_MODULE], {
        cwd: keyringPath, // Should be the folder containing 'proxion-keyring' package
        env: {
            ...env,
            PYTHONPATH: [keyringPath, corePath, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)
        },
        stdio: 'pipe' // Capture output
    });

    pyProc.stdout.on('data', (data) => console.log(`[PY]: ${data}`));
    pyProc.stderr.on('data', (data) => console.error(`[PY ERR]: ${data}`));

    pyProc.on('close', (code) => console.log(`[PY] exited with code ${code}`));
};

const killPythonBackend = () => {
    if (pyProc) {
        console.log('Killing Python Backend...');
        pyProc.kill();
        pyProc = null;
    }
};

// --- Window Management ---
const createWindow = () => {
    mainWindow = new BrowserWindow({
        width: 1024,
        height: 768,
        show: false, // Wait until ready
        frame: true, // Show standard controls for desktop mode
        titleBarStyle: 'hiddenInset', // Mac style, or just standard.
        // For Native feel:
        resizable: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            webviewTag: true,
            preload: path.join(__dirname, 'preload.cjs'),
        },
    });

    // Intercept requests to inject Proxion Capability tokens
    const filter = {
        urls: ['http://127.0.0.1/*']
    };

    mainWindow.webContents.session.webRequest.onBeforeSendHeaders(filter, (details, callback) => {
        const url = new URL(details.url);

        // Dynamic injection for all managed services
        if (sessionContext.token && (managedPorts.has(url.port) || url.port === '')) {
            // Note: url.port is empty for default ports (80/443), usually not used for local services
            details.requestHeaders['Authorization'] = `Bearer ${sessionContext.token}`;
            details.requestHeaders['X-Proxion-WebID'] = sessionContext.webId;
        }
        callback({ requestHeaders: details.requestHeaders });
    });

    // Special handling for webviews to use our SSO injector
    mainWindow.webContents.on('did-attach-webview', (event, webContents) => {
        webContents.setWindowOpenHandler((details) => {
            return { action: 'allow' };
        });
    });

    const startUrl = IS_DEV
        ? 'http://127.0.0.1:5173'
        : `file://${path.join(__dirname, '../dist/index.html')}`;

    mainWindow.loadURL(startUrl);

    mainWindow.once('ready-to-show', () => mainWindow.show());

    // Prevent closing, just hide to tray (if tray exists)
    mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
        return false;
    });
};

// --- Tray ---
const createTray = () => {
    try {
        // Try to use a proper icon, fallback to a simple colored square if not found
        const iconPath = path.join(__dirname, '../public/vite.svg');
        let icon;

        if (fs.existsSync(iconPath)) {
            // Create a simple 16x16 icon since SVG may not work directly
            icon = nativeImage.createFromPath(iconPath);
            if (icon.isEmpty()) {
                // Fallback: create a small colored icon
                icon = nativeImage.createEmpty();
            }
        } else {
            icon = nativeImage.createEmpty();
        }

        tray = new Tray(icon.isEmpty() ? nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAOUlEQVQ4jWNgGAWjYBSMglGAD/z//58RnzxcAwMDA8PFixflCdrgGhgYGBhOnDhxmJQ4HDVgFNALAAAGTwPffHUZhAAAAABJRU5ErkJggg==') : icon);

        const contextMenu = Menu.buildFromTemplate([
            { label: 'Show Dashboard', click: () => mainWindow.show() },
            { type: 'separator' },
            {
                label: 'Quit proxion-keyring', click: () => {
                    app.isQuitting = true;
                    killPythonBackend();
                    app.quit();
                }
            }
        ]);

        tray.setToolTip('proxion-keyring Secure Link');
        tray.setContextMenu(contextMenu);

        tray.on('double-click', () => mainWindow.show());
    } catch (err) {
        console.warn('[Main]: Failed to create tray icon:', err.message);
    }
};

// --- Lifecycle ---
// Register IPC handlers IMMEDIATELEY
ipcMain.handle('get-repo-root', () => {
    const root = path.resolve(__dirname, '../../');
    return root.replace(/\\/g, '/');
});

ipcMain.handle('select-directory', async () => {
    console.log("[Main]: select-directory handler INVOKED");
    if (!mainWindow) {
        console.error("[Main]: mainWindow is NULL during showOpenDialog");
        return null;
    }
    const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory', 'dontAskAfterLastRelease']
    });
    console.log(`[Main]: Dialog result - Canceled: ${canceled}, Path: ${filePaths?.[0]}`);
    if (canceled) return null;
    return filePaths[0];
});

ipcMain.on('set-session-context', (event, { webId, token }) => {
    console.log(`[Main]: Session context updated for ${webId}`);
    sessionContext = { webId, token };
});

app.whenReady().then(async () => {
    loadAppRegistry();
    await startPythonBackend();
    createWindow();
    createTray();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

// Bypass self-signed cert errors for our local vault
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
    if (url.startsWith('https://localhost:8086')) {
        event.preventDefault();
        callback(true);
    } else {
        callback(false);
    }
});

app.on('window-all-closed', () => {
    // On Windows, typical to minimize to tray, not quit.
    // We handle this in 'close' event.
});

app.on('before-quit', () => {
    killPythonBackend();
});
