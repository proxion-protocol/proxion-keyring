const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    hide: () => ipcRenderer.send('hide-app'),
    getRepoRoot: () => ipcRenderer.invoke('get-repo-root'),
    selectDirectory: () => ipcRenderer.invoke('select-directory'),
    setSessionContext: (webId, token) => ipcRenderer.send('set-session-context', { webId, token }),
});
