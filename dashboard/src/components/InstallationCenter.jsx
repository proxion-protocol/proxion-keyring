import React, { useState, useEffect, useMemo, useCallback } from 'react';
import appsRegistry from '../data/apps.json';

const AppCard = React.memo(({ app, appStatus, isWorking, onAction, onOpenApp }) => {
    const iconUrl = `http://127.0.0.1:8788/suite/icon/${app.id}`;

    return (
        <div className={`app-card-modern ${appStatus.toLowerCase()}`}>
            <div className="card-top">
                <div className="logo-wrapper">
                    <img
                        src={iconUrl}
                        alt={app.name}
                        className="app-logo"
                        crossOrigin="anonymous"
                        loading="lazy"
                        onError={(e) => {
                            e.target.style.display = 'none';
                            e.target.parentElement.querySelector('.app-icon-backup').style.display = 'block';
                        }}
                    />
                    <div className={`app-icon-backup icon-${app.icon || 'default'}`} style={{ display: 'none' }}></div>
                </div>
                <div className="status-badge">
                    <div className={`status-dot ${appStatus.toLowerCase()}`}></div>
                    <span>{appStatus === 'UNINSTALLED' ? 'Available' : appStatus === 'INSTALLING' ? 'Installing...' : appStatus}</span>
                </div>
            </div>

            <div className="card-content">
                <h4>{app.name}</h4>
                <p>{app.description}</p>
            </div>

            <div className="card-actions">
                {appStatus === 'INSTALLING' ? (
                    <button className="btn-modern-primary" disabled style={{ opacity: 0.8, cursor: 'wait' }}>
                        <div className="spinner-tiny"></div>
                        <span>Configuring...</span>
                    </button>
                ) : appStatus === 'UNINSTALLED' ? (
                    <button
                        className="btn-modern-primary"
                        disabled={isWorking}
                        onClick={() => onAction(app.id, 'install')}
                    >
                        {isWorking ? (
                            <>
                                <div className="spinner-tiny"></div>
                                <span>Requesting...</span>
                            </>
                        ) : 'Install App'}
                    </button>
                ) : (
                    <div className="action-row">
                        <button
                            className={`btn-modern-icon ${appStatus === 'RUNNING' ? 'stop' : 'start'}`}
                            title={appStatus === 'RUNNING' ? 'Stop Container' : 'Start Container'}
                            onClick={() => onAction(app.id, appStatus === 'RUNNING' ? 'down' : 'up')}
                        >
                            {appStatus === 'RUNNING' ? '⏹' : '▶'}
                        </button>
                        <button
                            className="btn-modern-secondary"
                            onClick={() => onOpenApp({
                                id: app.id,
                                name: app.name,
                                url: `http://127.0.0.1:${app.port || 80}`,
                                icon: iconUrl
                            })}
                        >
                            Open UI
                        </button>

                        {appStatus !== 'RUNNING' && (
                            <button
                                className="btn-modern-icon trash"
                                title="Uninstall App"
                                onClick={() => {
                                    if (window.confirm(`Are you sure you want to uninstall ${app.name}? Data will be preserved.`)) {
                                        onAction(app.id, 'uninstall');
                                    }
                                }}
                            >
                                🗑
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}, (prev, next) => {
    return prev.appStatus === next.appStatus &&
        prev.isWorking === next.isWorking &&
        prev.app.id === next.app.id;
});

export const InstallationCenter = React.memo(({ proxionToken, onOpenApp }) => {
    const [filter, setFilter] = useState('All');
    // Load cached status from localStorage for instant O(1) display
    const [status, setStatus] = useState(() => {
        try {
            const cached = localStorage.getItem('proxion_app_status');
            return cached ? JSON.parse(cached) : {};
        } catch {
            return {};
        }
    });
    const [installingId, setInstallingId] = useState(null);
    const [pendingInstalls, setPendingInstalls] = useState({});

    const categories = useMemo(() => ['All', ...new Set(appsRegistry.map(a => a.category))], []);

    const fetchStatus = useCallback(async () => {
        if (!proxionToken) return;
        try {
            const resp = await fetch('http://127.0.0.1:8788/suite/status', {
                headers: { 'Proxion-Token': proxionToken }
            });
            const data = await resp.json();
            const remoteApps = data.apps || {};

            // Functional update with shallow comparison
            setStatus(prev => {
                const hasChanged = Object.keys(remoteApps).length !== Object.keys(prev).length ||
                    Object.keys(remoteApps).some(id => remoteApps[id] !== prev[id]);
                if (hasChanged) {
                    // Persist to localStorage for instant load next time
                    localStorage.setItem('proxion_app_status', JSON.stringify(remoteApps));
                    return remoteApps;
                }
                return prev;
            });

            setPendingInstalls(prev => {
                const next = { ...prev };
                let changed = false;
                const now = Date.now();

                Object.keys(next).forEach(appId => {
                    if (remoteApps[appId] === 'RUNNING') {
                        delete next[appId];
                        changed = true;
                    }
                    else if (now - next[appId] > 300000) {
                        delete next[appId];
                        changed = true;
                    }
                });

                return changed ? next : prev;
            });

        } catch (err) {
            console.error("Failed to fetch suite status", err);
        }
    }, [proxionToken]);

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 5000);
        return () => clearInterval(interval);
    }, [fetchStatus]);

    const handleAction = useCallback(async (appId, action) => {
        if (action === 'install') setInstallingId(appId);

        try {
            const resp = await fetch(`http://127.0.0.1:8788/suite/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Proxion-Token': proxionToken
                },
                body: JSON.stringify({ appId })
            });

            if (resp.ok) {
                if (action === 'install') {
                    setPendingInstalls(prev => ({ ...prev, [appId]: Date.now() }));
                }
                else if (action === 'uninstall') {
                    setStatus(prev => ({ ...prev, [appId]: 'UNINSTALLED' }));
                }

                fetchStatus();

                if (action === 'install') {
                    const onboardingSeen = localStorage.getItem('homarr_tutorial_seen');
                    if (!onboardingSeen) {
                        window.dispatchEvent(new CustomEvent('proxion-show-tutorial'));
                        localStorage.setItem('homarr_tutorial_seen', 'true');
                    }
                }
            }
        } catch (err) {
            console.error(`Action ${action} failed for ${appId}`, err);
        } finally {
            if (action === 'install') setInstallingId(null);
        }
    }, [proxionToken, fetchStatus]);

    const filteredApps = useMemo(() =>
        appsRegistry.filter(a => filter === 'All' || a.category === filter),
        [filter]);

    return (
        <div className="installation-center">
            <div className="filter-bar">
                {categories.map(cat => (
                    <button
                        key={cat}
                        className={`filter-btn ${filter === cat ? 'active' : ''}`}
                        onClick={() => setFilter(cat)}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            <div className="app-grid">
                {filteredApps.map(app => (
                    <AppCard
                        key={app.id}
                        app={app}
                        appStatus={pendingInstalls[app.id] ? 'INSTALLING' : (status[app.id] || 'UNINSTALLED')}
                        isWorking={installingId === app.id}
                        onAction={handleAction}
                        onOpenApp={onOpenApp}
                    />
                ))}
            </div>

            <style>{`
            .filter-bar { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 2rem; padding: 0.5rem 0; }
            .filter-bar::-webkit-scrollbar { display: none; }
            .filter-btn { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.7); padding: 0.5rem 1.25rem; border-radius: 20px; font-size: 0.9rem; font-weight: 500; cursor: pointer; transition: all 0.2s ease; white-space: nowrap; }
            .filter-btn:hover { background: rgba(255, 255, 255, 0.1); color: white; transform: translateY(-1px); border-color: rgba(255, 255, 255, 0.2); }
            .filter-btn.active { background: #6366f1; border-color: #6366f1; color: white; }
            .app-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 1rem; padding-bottom: 3rem; }
            .app-card-modern { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; padding: 1.5rem; display: flex; flex-direction: column; transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94); position: relative; overflow: hidden; }
            .app-card-modern:hover { background: rgba(255,255,255,0.06); transform: translateY(-4px); box-shadow: 0 12px 30px rgba(0,0,0,0.3); border-color: rgba(255,255,255,0.1); }
            .app-card-modern.running { border-color: rgba(34, 197, 94, 0.3); }
            .app-card-modern.running:after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, #22c55e, transparent); opacity: 0.5; }
            .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
            .logo-wrapper { width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.2); border-radius: 10px; padding: 8px; }
            .app-logo { width: 100%; height: 100%; object-fit: contain; filter: invert(0.9); }
            .app-icon-backup { width: 24px; height: 24px; background-color: #aaa; mask-size: contain; -webkit-mask-size: contain; mask-repeat: no-repeat; -webkit-mask-repeat: no-repeat; mask-position: center; -webkit-mask-position: center; }
            .status-badge { display: flex; align-items: center; gap: 0.4rem; font-size: 0.75rem; font-weight: 500; color: rgba(255,255,255,0.5); background: rgba(0,0,0,0.2); padding: 0.25rem 0.75rem; border-radius: 20px; }
            .status-dot { width: 6px; height: 6px; border-radius: 50%; background: #666; }
            .status-dot.running { background: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.5); }
            .status-dot.stopped { background: #eab308; }
            .card-content h4 { font-size: 1.1rem; margin: 0 0 0.5rem 0; color: #fff; }
            .card-content p { font-size: 0.85rem; color: #94a3b8; line-height: 1.5; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 2.6rem; }
            .card-actions { margin-top: auto; padding-top: 1.5rem; }
            .btn-modern-primary { width: 100%; padding: 0.75rem; background: #6366f1; color: white; border: none; border-radius: 8px; font-weight: 600; font-size: 0.9rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 0.5rem; transition: all 0.2s; }
            .btn-modern-primary:hover { background: #4f46e5; }
            .btn-modern-primary:disabled { opacity: 0.7; cursor: not-allowed; }
            .action-row { display: flex; gap: 0.5rem; }
            .btn-modern-secondary { flex: 1; padding: 0.6rem; background: rgba(255,255,255,0.1); color: white; border: none; border-radius: 8px; font-weight: 500; font-size: 0.9rem; cursor: pointer; transition: all 0.2s; }
            .btn-modern-secondary:hover { background: rgba(255,255,255,0.15); }
            .btn-modern-icon { width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 8px; border: none; cursor: pointer; font-size: 1rem; }
            .btn-modern-icon.stop { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
            .btn-modern-icon.stop:hover { background: rgba(239, 68, 68, 0.3); }
            .btn-modern-icon.start { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
            .btn-modern-icon.start:hover { background: rgba(34, 197, 94, 0.3); }
            .btn-modern-icon.trash { background: rgba(100, 116, 139, 0.2); color: #94a3b8; }
            .btn-modern-icon.trash:hover { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
            .spinner-tiny { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; }
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            `}</style>
        </div>
    );
});
