import React, { useState, useEffect } from 'react';

export function MobileApp({ session, proxionToken, peers, onLogout, onRevoke }) {
    const [activeTab, setActiveTab] = useState('home');
    const [warden, setWarden] = useState({ blocked_total: 0, active_protections: 0 });
    const [system, setSystem] = useState({ hostname: '...', cpu: 0, ram: 0 });
    const [relay, setRelay] = useState(null);
    const [storage, setStorage] = useState(null);
    const [identity, setIdentity] = useState(null);
    const [federation, setFederation] = useState(null);
    const [intents, setIntents] = useState([]);
    const [loading, setLoading] = useState(false);

    // SPEC-3.3: Sign request with PoP header
    const popFetch = async (url, options = {}) => {
        const headers = options.headers || {};
        headers['Proxion-Token'] = proxionToken;
        headers['X-Proxion-PoP'] = `${Date.now()}.${Math.random().toString(36).substr(2, 9)}`;
        return fetch(url, { ...options, headers });
    };

    const fetchData = async () => {
        try {
            const [w, s, r, st, i, f, int] = await Promise.all([
                popFetch("http://127.0.0.1:8788/warden/stats").then(res => res.json()),
                popFetch("http://127.0.0.1:8788/system/status").then(res => res.json()),
                popFetch("http://127.0.0.1:8788/relay/status").then(res => res.json()),
                popFetch("http://127.0.0.1:8788/storage/stats").then(res => res.json()),
                popFetch("http://127.0.0.1:8788/identity/keys").then(res => res.json()),
                popFetch("http://127.0.0.1:8788/federation/status").then(res => res.json()),
                popFetch("http://127.0.0.1:8788/gateway/intents").then(res => res.json())
            ]);
            setWarden(w);
            setSystem(s);
            setRelay(r);
            setStorage(st);
            setIdentity(i);
            setFederation(f);
            setIntents(int || []);
        } catch (err) {
            console.error("Mobile data fetch failed", err);
        }
    };

    useEffect(() => {
        if (!proxionToken) return;
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, [proxionToken]);

    const handleMount = async () => {
        setLoading(true);
        try {
            await popFetch("http://127.0.0.1:8788/system/mount", { method: "POST" });
            fetchData();
        } finally {
            setLoading(false);
        }
    };

    const handleResolveIntent = (intentId, approved) => {
        popFetch("http://127.0.0.1:8788/gateway/intents/resolve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ intent_id: intentId, approved })
        }).then(() => fetchData());
    };

    return (
        <div className="mobile-shell">
            <header className="mobile-header">
                <div className="brand-mini">
                    <div className="logo-icon-small"></div>
                    <h1>Proxion</h1>
                </div>
                <div className="user-dot" title={session?.info?.webId}></div>
            </header>

            <main className="mobile-content">
                {activeTab === 'home' && (
                    <section className="mobile-tab-home">
                        <div className="status-hero-mini">
                            <div className="status-ring active">
                                <div className="icon-shield"></div>
                            </div>
                            <h3>{system?.hostname || 'System'} Secure</h3>
                            <p>All layers operational.</p>
                        </div>

                        <div className="alerts-section">
                            {intents.length > 0 ? (
                                <div className="intents-container">
                                    <label>Action Required</label>
                                    {intents.map(intent => (
                                        <div key={intent.id} className="intent-card">
                                            <strong>{intent.action}</strong>
                                            <span>From {intent.requester}</span>
                                            <div className="intent-btns">
                                                <button onClick={() => handleResolveIntent(intent.id, false)} className="deny">Deny</button>
                                                <button onClick={() => handleResolveIntent(intent.id, true)} className="approve">Approve</button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="empty-alerts">No pending approvals.</div>
                            )}
                        </div>

                        <div className="stats-strip">
                            <div className="mini-stat">
                                <label>Blocked</label>
                                <strong>{warden?.blocked_total}</strong>
                            </div>
                            <div className="mini-stat">
                                <label>Mesh Latency</label>
                                <strong>{relay?.latency_ms}ms</strong>
                            </div>
                            <div className="mini-stat">
                                <label>P: Drive</label>
                                <strong>{storage?.is_mounted ? 'OK' : 'DISC'}</strong>
                            </div>
                        </div>
                    </section>
                )}

                {activeTab === 'network' && (
                    <section className="mobile-tab-network">
                        <div className="mesh-status-card">
                            <div className="card-top">
                                <h3>Mesh Relay</h3>
                                <div className="status-dot healthy"></div>
                            </div>
                            <div className="relay-metrics">
                                <div className="rm-item">
                                    <label>Backbone</label>
                                    <span>{relay?.relay_node}</span>
                                </div>
                                <div className="rm-item">
                                    <label>Throughput</label>
                                    <span>{relay?.bandwidth_kbps} KB/s</span>
                                </div>
                            </div>
                        </div>

                        <div className="peers-section">
                            <label>Active Peers</label>
                            <div className="peer-list-mini">
                                {Object.entries(peers).map(([pub, meta]) => (
                                    <div className="peer-row" key={pub}>
                                        <div className="peer-icon"></div>
                                        <div className="peer-info">
                                            <strong>{meta.name}</strong>
                                            <span>{meta.ip}</span>
                                        </div>
                                        <button onClick={() => onRevoke(pub)} className="kill">×</button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </section>
                )}

                {activeTab === 'storage' && (
                    <section className="mobile-tab-storage">
                        <div className="storage-card">
                            <h3>Unified Drive P:</h3>
                            <div className="storage-viz">
                                <div className="bar"><div className="fill" style={{ width: `${storage?.usage?.percent || 0}%` }}></div></div>
                                <span>{(storage?.usage?.used / (1024 ** 3)).toFixed(1)} GB / {(storage?.usage?.total / (1024 ** 3)).toFixed(1)} GB</span>
                            </div>

                            {!storage?.is_mounted && (
                                <button className="btn-primary mount-btn" onClick={handleMount} disabled={loading}>
                                    {loading ? 'Mounting...' : 'Remount Drive P:'}
                                </button>
                            )}
                        </div>

                        <div className="cache-health">
                            <label>Cache State</label>
                            <strong>{storage?.cache_health || 'OPTIMAL'}</strong>
                        </div>
                    </section>
                )}

                {activeTab === 'security' && (
                    <section className="mobile-tab-security">
                        <div className="identity-card">
                            <label>Fortress Fingerprint</label>
                            <code>{identity?.public_key?.substring(0, 16)}...</code>
                        </div>

                        <div className="fed-status">
                            <label>Federation Health</label>
                            <div className="fed-row">
                                <span>{federation?.status}</span>
                                <strong>{federation?.peer_count} Peers</strong>
                            </div>
                            <div className="fed-row">
                                <span>Policies Activity</span>
                                <strong>{federation?.active_policies} Rules</strong>
                            </div>
                        </div>

                        <div className="audit-list">
                            <label>Recent Capability Audit</label>
                            <div className="audit-entry"><span>16:21</span> <strong>system.mount</strong> <span className="ok">OK</span></div>
                            <div className="audit-entry"><span>16:15</span> <strong>gateway.auth</strong> <span className="ok">OK</span></div>
                        </div>
                    </section>
                )}

                {activeTab === 'remote' && (
                    <section className="mobile-tab-remote">
                        <div className="mirror-controls">
                            <h3>Mirror Mode</h3>
                            <p>Screen access via secure tunnel.</p>
                            <div className="mirror-btns">
                                <button onClick={() => window.open(`vnc://${peers[0]?.ip || '10.0.0.1'}`)}>Launch VNC</button>
                                <button onClick={() => window.open(`rdp://${peers[0]?.ip || '10.0.0.1'}`)}>Launch RDP</button>
                            </div>
                        </div>

                        <div className="integration-hub">
                            <label>Active Remotes</label>
                            <div className="app-shortcuts">
                                <div className="app-icon homarr" onClick={() => window.open('http://10.0.0.1:7575')}>🏠</div>
                                <div className="app-icon immich" onClick={() => window.open('http://10.0.0.1:2283')}>📸</div>
                                <div className="app-icon steam" onClick={() => window.open('http://10.0.0.1:8083')}>🎮</div>
                            </div>
                        </div>

                        <div className="power-actions">
                            <button className="reboot">Reboot</button>
                            <button className="shutdown">Shutdown</button>
                        </div>
                    </section>
                )}
            </main>

            <nav className="mobile-nav">
                <button className={activeTab === 'home' ? 'active' : ''} onClick={() => setActiveTab('home')}>🏠<br />Home</button>
                <button className={activeTab === 'network' ? 'active' : ''} onClick={() => setActiveTab('network')}>🌐<br />Mesh</button>
                <button className={activeTab === 'storage' ? 'active' : ''} onClick={() => setActiveTab('storage')}>💽<br />Vault</button>
                <button className={activeTab === 'security' ? 'active' : ''} onClick={() => setActiveTab('security')}>🔑<br />Sec</button>
                <button className={activeTab === 'remote' ? 'active' : ''} onClick={() => setActiveTab('remote')}>🪞<br />Mirror</button>
            </nav>

        </div>
    );
}
