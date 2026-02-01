const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Minimize to tray
    hide: () => ipcRenderer.send('hide-app'),
    // Notification bridge if needed
});
