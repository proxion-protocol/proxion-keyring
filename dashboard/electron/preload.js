import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    // Minimize to tray
    hide: () => ipcRenderer.send('hide-app'),
    // Get repo root for generic path calc
    getRepoRoot: () => ipcRenderer.invoke('get-repo-root'),

});
