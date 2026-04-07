import React, { useState, useEffect, useRef } from 'react';

function fmt(bytes) {
    if (bytes >= 1e9) return (bytes / 1e9).toFixed(2) + ' GB';
    if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + ' MB';
    return (bytes / 1e3).toFixed(0) + ' KB';
}

function elapsed(startedAt) {
    const secs = Math.floor((Date.now() / 1000) - startedAt);
    const m = Math.floor(secs / 60), s = secs % 60;
    return `${m}m ${s}s`;
}

function TransferBar({ transfer }) {
    const pct = transfer.remote_bytes > 0
        ? Math.min(100, (transfer.local_bytes / transfer.remote_bytes) * 100)
        : null;

    const color = pct === null ? '#3498db'
        : pct >= 100 ? '#2ecc71'
        : '#3498db';

    return (
        <div style={{
            margin: '12px 0 4px',
            padding: '10px 14px',
            backgroundColor: 'rgba(52, 152, 219, 0.08)',
            border: '1px solid rgba(52, 152, 219, 0.3)',
            borderRadius: '8px',
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
                <span style={{ color: '#3498db', fontWeight: 'bold', maxWidth: '70%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {transfer.name}
                </span>
                <span style={{ color: '#aaa', flexShrink: 0 }}>
                    {elapsed(transfer.started_at)} elapsed
                </span>
            </div>

            <div style={{ height: '6px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                    height: '100%',
                    width: pct !== null ? `${pct}%` : '40%',
                    backgroundColor: color,
                    borderRadius: '3px',
                    transition: 'width 1s ease',
                    ...(pct === null && {
                        animation: 'indeterminate 1.8s ease-in-out infinite',
                        backgroundImage: `linear-gradient(90deg, transparent 0%, ${color} 50%, transparent 100%)`,
                    }),
                }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#aaa', marginTop: '5px' }}>
                <span>{fmt(transfer.local_bytes)} received</span>
                <span>{pct !== null ? `${pct.toFixed(1)}% of ${fmt(transfer.remote_bytes)}` : 'size unknown'}</span>
            </div>
        </div>
    );
}

export function SeedboxPanel({ proxionToken }) {
    const [status, setStatus] = useState('unknown');
    const [logs, setLogs] = useState([]);
    const [transfer, setTransfer] = useState(null);
    const [autoScroll, setAutoScroll] = useState(true);
    const logEndRef = useRef(null);

    const fetchStatus = async () => {
        try {
            const res = await window.electronAPI?.seedboxControl('status');
            if (res) {
                setStatus(res.status);
                if (res.logs && res.logs.length > 0) setLogs(res.logs);
                setTransfer(res.transfer || null);
            }
        } catch (err) {
            console.error("Failed to fetch seedbox status:", err);
        }
    };

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (autoScroll && logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs, autoScroll]);

    const handleStart = async () => {
        try {
            await window.electronAPI?.seedboxControl('start');
            setStatus('starting...');
            setTimeout(fetchStatus, 1000);
        } catch (err) {
            alert("Failed to start daemon: " + err.message);
        }
    };

    const handleStop = async () => {
        if (!window.confirm("Are you sure you want to stop the ingest daemon?")) return;
        try {
            await window.electronAPI?.seedboxControl('stop');
            setStatus('stopping...');
            setTimeout(fetchStatus, 1000);
        } catch (err) {
            alert("Failed to stop daemon: " + err.message);
        }
    };

    const openTransmission = async () => {
        const url = await window.electronAPI?.getBridgeUrl()
            ?? 'http://172.16.0.42:9091/transmission/web/';
        window.open(url, '_blank');
    };

    return (
        <div className="card-section" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h3>Ingest Daemon</h3>
                    <p className="tiny-text" style={{ marginTop: '4px', opacity: 0.8 }}>
                        Automated sync pipeline from Helsinki Transmission to the local Vault.
                    </p>
                    <button
                        onClick={openTransmission}
                        style={{
                            marginTop: '8px',
                            padding: '5px 12px',
                            fontSize: '11px',
                            background: 'rgba(52, 152, 219, 0.15)',
                            border: '1px solid #3498db',
                            borderRadius: '6px',
                            color: '#3498db',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px'
                        }}
                    >
                        ⬇ Helsinki Transmission
                    </button>
                </div>

                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <div className="status-badge" style={{
                        padding: '4px 10px',
                        borderRadius: '12px',
                        fontSize: '11px',
                        fontWeight: 'bold',
                        backgroundColor: status === 'running' ? 'rgba(46, 204, 113, 0.2)' : 'rgba(231, 76, 60, 0.2)',
                        color: status === 'running' ? '#2ecc71' : '#e74c3c',
                        border: `1px solid ${status === 'running' ? '#2ecc71' : '#e74c3c'}`
                    }}>
                        {status.toUpperCase()}
                    </div>

                    {status === 'running' ? (
                        <button className="btn-secondary" style={{ borderColor: '#e74c3c', color: '#e74c3c' }} onClick={handleStop}>Stop Daemon</button>
                    ) : (
                        <button className="btn-primary" style={{ backgroundColor: '#2ecc71' }} onClick={handleStart}>Launch Daemon</button>
                    )}
                </div>
            </div>

            {transfer && <TransferBar transfer={transfer} />}

            <div style={{
                flex: 1,
                backgroundColor: '#1e1e1e',
                borderRadius: '8px',
                marginTop: '15px',
                padding: '10px',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#d4d4d4',
                overflowY: 'auto',
                position: 'relative'
            }}>
                {logs.length === 0 ? (
                    <div style={{ opacity: 0.5, fontStyle: 'italic' }}>No logs available. Daemon may be sleeping or not started.</div>
                ) : (
                    logs.map((log, i) => (
                        <div key={i} style={{
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                            padding: '2px 0',
                            borderBottom: i < logs.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none'
                        }}>
                            {log}
                        </div>
                    ))
                )}
                <div ref={logEndRef} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
                <label style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', opacity: 0.8 }}>
                    <input
                        type="checkbox"
                        checked={autoScroll}
                        onChange={(e) => setAutoScroll(e.target.checked)}
                    />
                    Auto-scroll logs
                </label>
            </div>
        </div>
    );
}
