const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    hide: () => ipcRenderer.send('hide-app'),
    getRepoRoot: () => ipcRenderer.invoke('get-repo-root'),
    selectDirectory: () => ipcRenderer.invoke('select-directory'),
    setSessionContext: (webId, token) => ipcRenderer.send('set-session-context', { webId, token }),
    diagPing: () => ipcRenderer.invoke('diag-ping'),
    launchExternalApp: (appId, path) => ipcRenderer.invoke('launch-external-app', { appId, path }),
    seedboxControl: (action) => ipcRenderer.invoke('seedbox:control', action),
    seedboxReadLog: () => ipcRenderer.invoke('seedbox:readlog'),
    getBridgeUrl: () => ipcRenderer.invoke('get-bridge-url')
});
