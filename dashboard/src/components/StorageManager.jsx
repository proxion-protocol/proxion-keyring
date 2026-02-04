import { useState, useEffect } from 'react';

export const StorageManager = ({ proxionToken }) => {
    const [data, setData] = useState(null);
    const [config, setConfig] = useState({ stash_sources: [] });
    const [loading, setLoading] = useState(true);
    const [mounting, setMounting] = useState(false);
    const [addingSource, setAddingSource] = useState(false);

    const fetchStorageData = async () => {
        try {
            const statsResp = await fetch('http://127.0.0.1:8788/storage/stats', {
                headers: { 'Proxion-Token': proxionToken }
            });
            setData(await statsResp.json());

            const configResp = await fetch('http://127.0.0.1:8788/storage/config', {
                headers: { 'Proxion-Token': proxionToken }
            });
            setConfig(await configResp.json());
        } catch (err) {
            console.error("Storage data fetch failed", err);
        } finally {
            setLoading(false);
        }
    };

    const handleMount = async (sourceId) => {
        setMounting(true);
        try {
            // Find the source path
            const source = config.stash_sources.find(s => s.id === sourceId) || config.stash_sources[0];
            const resp = await fetch('http://127.0.0.1:8788/system/mount', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Proxion-Token': proxionToken
                },
                body: JSON.stringify({ pod_path: source?.path })
            });
            if (resp.ok) setTimeout(fetchStorageData, 2000);
        } catch (err) {
            console.error("Mount request failed", err);
        } finally {
            setMounting(false);
        }
    };

    const handleUnmount = async () => {
        setMounting(true);
        try {
            const resp = await fetch('http://127.0.0.1:8788/system/unmount', {
                method: 'POST',
                headers: { 'Proxion-Token': proxionToken }
            });
            if (resp.ok) {
                setTimeout(fetchStorageData, 1000);
                alert("P: Drive has been detached. You can now remount to include new disks.");
            }
        } catch (err) {
            console.error("Unmount failed", err);
        } finally {
            setMounting(false);
        }
    };

    const handleAddSource = async () => {
        try {
            console.log("[StorageManager] Add Source clicked");
            if (!window.electronAPI) {
                alert("System Error: Electron API not found. Please fully restart the dashboard.");
                return;
            }

            let path = await window.electronAPI.selectDirectory();
            if (!path) return;

            // Normalize path: Replace backslashes and ensure drive roots have trailing slash
            path = path.replace(/\\/g, '/');
            if (path.length === 2 && path.endsWith(':')) {
                path += '/';
            }

            console.log("[StorageManager] Normalized path:", path);

            // Auto-generate name from path instead of using prompt() which fails in Electron
            const driveMatch = path.match(/^([A-Z]:)/i);
            const driveLetter = driveMatch ? driveMatch[1] : "Disk";
            const name = `${driveLetter} Storage`;

            const existingSources = config.stash_sources || [];
            const newSources = [...existingSources, {
                id: Date.now().toString(),
                name,
                path,
                primary: existingSources.length === 0
            }];

            console.log("[StorageManager] Final sources list for save:", newSources);
            await saveSources(newSources);
        } catch (err) {
            console.error("[StorageManager] Error adding source:", err);
            alert("Unexpected error: " + err.message);
        }
    };

    const handleRemoveSource = async (id) => {
        if (!confirm("Are you sure you want to remove this storage source?")) return;
        const newSources = config.stash_sources.filter(s => s.id !== id);
        await saveSources(newSources);
    };

    const saveSources = async (sources) => {
        try {
            console.log("[StorageManager] Saving sources:", sources);
            const resp = await fetch('http://127.0.0.1:8788/storage/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Proxion-Token': proxionToken
                },
                body: JSON.stringify({ stash_sources: sources })
            });

            if (resp.ok) {
                const updatedConfig = await resp.json();
                console.log("[StorageManager] Saved successfully:", updatedConfig);
                setConfig(updatedConfig);
                fetchStorageData(); // Refresh pooled stats immediately
            } else {
                const error = await resp.json();
                alert("Failed to save storage config: " + (error.error || "Unknown error"));
            }
        } catch (err) {
            console.error("Failed to save sources", err);
            alert("Network error while saving storage config: " + err.message);
        }
    };

    const handleRefresh = async () => {
        setMounting(true);
        try {
            await fetch('http://127.0.0.1:8788/system/unmount', {
                method: 'POST',
                headers: { 'Proxion-Token': proxionToken }
            });
            await new Promise(r => setTimeout(r, 1500));
            // Always mount with all configured sources (backend handles this now)
            await fetch('http://127.0.0.1:8788/system/mount', {
                method: 'POST',
                headers: { 'Proxion-Token': proxionToken }
            });
            setTimeout(fetchStorageData, 2000);
        } catch (err) {
            console.error("Refresh Logic Failed", err);
        } finally {
            setMounting(false);
        }
    };

    useEffect(() => {
        fetchStorageData();
        const interval = setInterval(fetchStorageData, 10000);
        return () => clearInterval(interval);
    }, [proxionToken]);

    if (loading) return <div className="spinner"></div>;

    const usagePercent = data?.usage?.percent || 0;
    const gbUsed = (data?.usage?.used / (1024 ** 3)).toFixed(2);
    const gbTotal = (data?.usage?.total / (1024 ** 3)).toFixed(2);

    return (
        <div className="storage-container">
            <div className="glass-card storage-card">
                <div className="card-header-premium">
                    <div className="header-main">
                        <div className="status-indicator-ring">
                            <div className={`status-dot ${data?.is_mounted ? 'active' : 'idle'}`}></div>
                            <span className="icon-main">📂</span>
                        </div>
                        <div className="header-text">
                            <h3>Solid Pod Unified Hub</h3>
                            <p className="subtitle">Pooled Orchestration across Physical Disks</p>
                        </div>
                    </div>
                    <div className="header-status">
                        <span className={`badge ${data?.is_mounted ? 'badge-success' : 'badge-warning'}`}>
                            {data?.is_mounted ? 'MOUNTED' : 'DETACHED'}
                        </span>
                    </div>
                </div>

                <div className="capacity-analytics">
                    <div className="analytics-header">
                        <label>Global Pool Discovery</label>
                        <span className="analytics-values">
                            <strong>{gbUsed} GB</strong> / {gbTotal === "0.00" ? "???" : gbTotal} GB
                        </span>
                    </div>
                    <div className="premium-progress-bar">
                        <div className="progress-track">
                            <div
                                className="progress-fill-gradient"
                                style={{ width: `${Math.min(usagePercent, 100)}%` }}
                            ></div>
                        </div>
                        <div className="progress-labels">
                            <span>0%</span>
                            <span>{usagePercent.toFixed(1)}% Utilization</span>
                            <span>100%</span>
                        </div>
                    </div>
                </div>

                <div className="source-repository-section">
                    <div className="section-head">
                        <h4>Identified Hardware ({config.stash_sources?.length || 0})</h4>
                        <button className="btn-action-outline" onClick={handleAddSource} disabled={addingSource}>
                            <span className="btn-icon">+</span> Link Physical Disk
                        </button>
                    </div>

                    <div className="source-grid-modern">
                        {config.stash_sources?.map(source => (
                            <div className="disk-item-premium" key={source.id || source.name}>
                                <div className="disk-info">
                                    <span className="disk-icon">💿</span>
                                    <div className="disk-meta">
                                        <span className="disk-name">{source.name}</span>
                                        <code className="disk-path">{source.path}</code>
                                    </div>
                                </div>
                                <div className="disk-actions">
                                    <button className="btn-disk-remove" onClick={() => handleRemoveSource(source.id)} title="Unlink Source">
                                        ✕
                                    </button>
                                </div>
                            </div>
                        ))}
                        {(!config.stash_sources || config.stash_sources.length === 0) && (
                            <div className="empty-state-lux">
                                <p>No physical disks identified. Link a drive to expand your Pod's capacity.</p>
                            </div>
                        )}
                    </div>
                </div>

                <div className="orchestrator-footer">
                    <div className="footer-status">
                        <p className="instruction">
                            {data?.is_mounted
                                ? "Virtual P: drive is live. Folders are indexed at the root level."
                                : "Ready to orchestrate. Click below to mount your unified filesystem."}
                        </p>
                    </div>
                    <div className="footer-actions-grid">
                        <button
                            className={`btn-orchestrate primary ${mounting ? 'loading' : ''}`}
                            onClick={data?.is_mounted ? handleRefresh : () => handleMount()}
                            disabled={mounting || !config.stash_sources?.length}
                        >
                            {mounting ? 'Orchestrating...' : (data?.is_mounted ? 'Sync / Refresh Hub P:' : 'Mount Unified P:')}
                        </button>

                        {data?.is_mounted && (
                            <button
                                className="btn-orchestrate secondary"
                                onClick={handleUnmount}
                                disabled={mounting}
                            >
                                Detach Hub
                            </button>
                        )}
                    </div>
                </div>
            </div>

            <style>{`
                .storage-container {
                    padding: 2rem;
                    max-width: 900px;
                    margin: 0 auto;
                }
                .glass-card {
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    padding: 2.5rem;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                }
                .card-header-premium {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 2.5rem;
                }
                .header-main {
                    display: flex;
                    gap: 1.5rem;
                    align-items: center;
                }
                .status-indicator-ring {
                    position: relative;
                    width: 60px;
                    height: 60px;
                    background: rgba(255, 255, 255, 0.03);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.8rem;
                }
                .status-dot {
                    position: absolute;
                    top: 2px;
                    right: 2px;
                    width: 14px;
                    height: 14px;
                    border-radius: 50%;
                    border: 2px solid #1a1a1a;
                }
                .status-dot.active { background: #00ffcc; box-shadow: 0 0 10px #00ffcc; }
                .status-dot.idle { background: #ffcc00; }
                
                .header-text h3 { margin: 0; font-size: 1.6rem; color: #fff; }
                .subtitle { margin: 0.2rem 0 0; color: rgba(255, 255, 255, 0.5); font-size: 0.9rem; }
                
                .badge {
                    padding: 0.4rem 1rem;
                    border-radius: 30px;
                    font-size: 0.75rem;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                }
                .badge-success { background: rgba(0, 255, 204, 0.1); color: #00ffcc; border: 1px solid rgba(0, 255, 204, 0.2); }
                .badge-warning { background: rgba(255, 204, 0, 0.1); color: #ffcc00; border: 1px solid rgba(255, 204, 0, 0.2); }

                .capacity-analytics { margin-bottom: 3rem; }
                .analytics-header { display: flex; justify-content: space-between; margin-bottom: 1rem; color: rgba(255, 255, 255, 0.7); }
                .progress-track {
                    height: 12px;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    overflow: hidden;
                }
                .progress-fill-gradient {
                    height: 100%;
                    background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
                    transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
                }
                .progress-labels { display: flex; justify-content: space-between; margin-top: 0.8rem; font-size: 0.8rem; color: rgba(255, 255, 255, 0.4); }

                .source-repository-section {
                    background: rgba(0, 0, 0, 0.2);
                    border-radius: 16px;
                    padding: 1.5rem;
                    margin-bottom: 2rem;
                }
                .section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
                .section-head h4 { margin: 0; color: #fff; font-weight: 500; }
                
                .disk-item-premium {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem;
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 12px;
                    margin-bottom: 0.8rem;
                    transition: all 0.2s;
                }
                .disk-item-premium:hover { background: rgba(255, 255, 255, 0.04); transform: translateX(5px); }
                .disk-info { display: flex; gap: 1rem; align-items: center; }
                .disk-icon { font-size: 1.2rem; }
                .disk-name { display: block; color: #fff; font-weight: 500; }
                .disk-path { font-size: 0.8rem; color: rgba(255, 255, 255, 0.4); }
                
                .btn-orchestrate {
                    padding: 1.2rem;
                    border-radius: 12px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                    width: 100%;
                }
                .btn-orchestrate.primary { background: #fff; color: #000; border: none; }
                .btn-orchestrate.primary:hover:not(.disabled) { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(255, 255, 255, 0.15); }
                .btn-orchestrate.secondary { background: transparent; color: #fff; border: 1px solid rgba(255, 255, 255, 0.2); margin-top: 1rem; }
                .btn-orchestrate.disabled { opacity: 0.3; cursor: not-allowed; }

                .footer-status { text-align: center; margin-bottom: 1.5rem; color: rgba(255, 255, 255, 0.6); font-size: 0.9rem; }
            `}</style>
        </div >
    );
};
