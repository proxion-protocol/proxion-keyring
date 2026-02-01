const { app, BrowserWindow, Tray, Menu, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// --- Configuration ---
const IS_DEV = process.env.NODE_ENV === 'development';
const PY_MODULE = 'proxion_keyring.rs.server'; // Folder 'rs' is in root
const PY_PORT = 8788; // Port RS runs on

// --- Global State ---
let mainWindow;
let tray;
let pyProc = null;

// --- Backend Management ---
const startPythonBackend = () => {
    if (pyProc) return;

    console.log('Starting Python Backend...');

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

    pyProc = spawn('python', ['-m', PY_MODULE], {
        cwd: path.join(__dirname, '../../'), // Should be the folder containing 'proxion-keyring' package
        env: { ...env, PYTHONPATH: path.join(__dirname, '../../') },
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
        width: 480,
        height: 700,
        show: false, // Wait until ready
        frame: false, // Custom frame look? Or standard. Let's go Standard for now, simple.
        titleBarStyle: 'hiddenInset', // Mac style, or just standard.
        // For Native feel:
        resizable: false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    const startUrl = IS_DEV
        ? 'http://localhost:5173'
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
    const iconPath = path.join(__dirname, '../public/vite.svg'); // Placeholder icon
    tray = new Tray(iconPath);

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
};

// --- Lifecycle ---
app.whenReady().then(() => {
    startPythonBackend();
    createWindow();
    createTray();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    // On Windows, typical to minimize to tray, not quit.
    // We handle this in 'close' event.
});

app.on('before-quit', () => {
    killPythonBackend();
});
