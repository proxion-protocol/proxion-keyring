import { useState, useEffect } from 'react';

export function Librarian({ proxionToken }) {
    const [path, setPath] = useState('/');
    const [entries, setEntries] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchEntries = async (targetPath) => {
        setLoading(true);
        setError(null);
        try {
            const resp = await fetch(`http://127.0.0.1:8788/storage/ls?path=${encodeURIComponent(targetPath)}`, {
                headers: { 'Proxion-Token': proxionToken }
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            setEntries(data);
            setPath(targetPath);
        } catch (err) {
            console.error("[Librarian] LS Failed:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (proxionToken) fetchEntries('/');
    }, [proxionToken]);

    const navigateTo = (newPath) => {
        fetchEntries(newPath);
    };

    const goBack = () => {
        if (path === '/') return;
        const parts = path.split('/').filter(Boolean);
        parts.pop();
        navigateTo('/' + parts.join('/'));
    };

    const formatSize = (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDate = (mtime) => {
        return new Date(mtime * 1000).toLocaleString();
    };

    return (
        <div className="librarian-container" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '15px',
            height: '100%',
            background: 'rgba(255,255,255,0.02)',
            borderRadius: '12px',
            padding: '20px',
            border: '1px solid #333'
        }}>
            <div className="browser-header" style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button
                    onClick={goBack}
                    disabled={path === '/'}
                    className="btn-secondary"
                    style={{ padding: '5px 12px', opacity: path === '/' ? 0.3 : 1 }}
                >
                    UP
                </button>
                <div className="path-bar" style={{
                    flex: 1,
                    background: '#000',
                    padding: '8px 15px',
                    borderRadius: '6px',
                    fontFamily: 'monospace',
                    fontSize: '0.9rem',
                    color: '#00d2ff',
                    border: '1px solid #222'
                }}>
                    {path}
                </div>
                <button onClick={() => fetchEntries(path)} className="btn-secondary" style={{ padding: '8px' }}>🔄</button>
            </div>

            <div className="browser-content" style={{
                flex: 1,
                overflowY: 'auto',
                border: '1px solid #222',
                borderRadius: '8px',
                background: 'rgba(0,0,0,0.2)'
            }}>
                {loading ? (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>Scanning Stash...</div>
                ) : error ? (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#f44336' }}>Error: {error}</div>
                ) : entries.length === 0 ? (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#444' }}>This folder is empty.</div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead style={{ background: 'rgba(255,255,255,0.05)', textAlign: 'left' }}>
                            <tr>
                                <th style={{ padding: '10px 15px' }}>Name</th>
                                <th style={{ padding: '10px 15px' }}>Size</th>
                                <th style={{ padding: '10px 15px' }}>Modified</th>
                                <th style={{ padding: '10px 15px' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map((entry, i) => (
                                <tr
                                    key={i}
                                    style={{
                                        borderBottom: '1px solid #222',
                                        transition: 'background 0.2s'
                                    }}
                                    className="browser-row"
                                >
                                    <td
                                        onClick={() => entry.type === 'directory' ? navigateTo(entry.path) : null}
                                        style={{ padding: '12px 15px', display: 'flex', alignItems: 'center', gap: '10px', cursor: entry.type === 'directory' ? 'pointer' : 'default' }}
                                    >
                                        <span style={{ fontSize: '1.2rem' }}>{entry.type === 'directory' ? '📁' : '📄'}</span>
                                        <span style={{ color: entry.type === 'directory' ? '#00d2ff' : '#fff' }}>{entry.name}</span>
                                    </td>
                                    <td style={{ padding: '12px 15px', color: '#888' }}>
                                        {entry.type === 'file' ? formatSize(entry.size) : '--'}
                                    </td>
                                    <td style={{ padding: '12px 15px', color: '#666' }}>
                                        {entry.mtime ? formatDate(entry.mtime) : '--'}
                                    </td>
                                    <td style={{ padding: '12px 15px' }}>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <button
                                                className="btn-secondary"
                                                title="Share with Peer"
                                                style={{ padding: '4px 8px', fontSize: '0.75rem', color: '#00d2ff' }}
                                                onClick={async (e) => {
                                                    e.stopPropagation();
                                                    const webId = prompt("Enter the WebID or Public Key of the recipient:");
                                                    if (!webId) return;

                                                    try {
                                                        const r = await fetch("http://127.0.0.1:8788/sharing/invite", {
                                                            method: 'POST',
                                                            headers: {
                                                                'Content-Type': 'application/json',
                                                                'Proxion-Token': proxionToken
                                                            },
                                                            body: JSON.stringify({
                                                                webId: webId,
                                                                resource: `stash://${entry.path}`,
                                                                actions: "read"
                                                            })
                                                        });
                                                        const data = await r.json();
                                                        if (r.ok) {
                                                            alert(`Sharing invitation created!\nID: ${data.invitation_id}\nRecipient: ${webId}`);
                                                        } else {
                                                            alert(`Sharing failed: ${data.error}`);
                                                        }
                                                    } catch (err) {
                                                        alert(err.message);
                                                    }
                                                }}
                                            >
                                                🤝
                                            </button>
                                            {entry.type === 'file' && (
                                                <button
                                                    className="btn-secondary"
                                                    style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                                    onClick={() => window.open(`http://127.0.0.1:8889/pod${entry.path}`, '_blank')}
                                                >
                                                    📥
                                                </button>
                                            )}
                                            <button
                                                className="btn-secondary"
                                                style={{ padding: '4px 8px', fontSize: '0.75rem', color: '#f44336' }}
                                                onClick={async (e) => {
                                                    e.stopPropagation();
                                                    if (confirm(`Delete ${entry.name}?`)) {
                                                        try {
                                                            const r = await fetch(`http://127.0.0.1:8788/storage/file?path=${encodeURIComponent(entry.path)}`, {
                                                                method: 'DELETE',
                                                                headers: { 'Proxion-Token': proxionToken }
                                                            });
                                                            if (r.ok) fetchEntries(path);
                                                            else alert("Delete failed");
                                                        } catch (err) {
                                                            alert(err.message);
                                                        }
                                                    }
                                                }}
                                            >
                                                🗑️
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
            <style>{`
                .browser-row:hover {
                    background: rgba(255, 255, 255, 0.05);
                }
                .browser-row:active {
                    background: rgba(255, 255, 255, 0.1);
                }
            `}</style>
        </div>
    );
}
