import { useState, useEffect, useRef } from 'react';

export function AuditFeed({ proxionToken }) {
    const [events, setEvents] = useState([]);
    const feedRef = useRef(null);

    const [backoff, setBackoff] = useState(1000);

    useEffect(() => {
        if (!proxionToken) return;

        let eventSource;
        let timer;

        const connect = () => {
            console.log("[AuditFeed] Connecting to Guardian SSE...");
            eventSource = new EventSource(`http://127.0.0.1:8788/system/events?Proxion-Token=${proxionToken}`);

            eventSource.onmessage = (e) => {
                try {
                    const event = JSON.parse(e.data);
                    setEvents(prev => [...prev.slice(-199), event]); // Keep last 200 to avoid eviction during builds
                    setBackoff(1000); // Reset backoff on success
                } catch (err) {
                    console.error("[AuditFeed] Parse error:", err);
                }
            };

            eventSource.onerror = (err) => {
                console.error("[AuditFeed] SSE Error, reconnecting in", backoff, "ms");
                eventSource.close();
                timer = setTimeout(() => {
                    setBackoff(prev => Math.min(prev * 2, 30000));
                    connect();
                }, backoff);
            };
        };

        connect();

        return () => {
            console.log("[AuditFeed] Closing Guardian SSE");
            if (eventSource) eventSource.close();
            if (timer) clearTimeout(timer);
        };
    }, [proxionToken, backoff]);

    useEffect(() => {
        if (feedRef.current) {
            feedRef.current.scrollTop = feedRef.current.scrollHeight;
        }
    }, [events]);

    const getEventColor = (type) => {
        switch (type) {
            case 'success': return '#4CAF50';
            case 'error': return '#f44336';
            case 'warning': return '#FF9800';
            default: return '#00d2ff';
        }
    };

    return (
        <div className="audit-feed-container" style={{
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid #333',
            borderRadius: '12px',
            padding: '15px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            height: '300px'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, fontSize: '0.9rem', color: '#888', textTransform: 'uppercase' }}>Live Security Audit</h4>
                <div style={{ fontSize: '0.7rem', color: '#4CAF50' }}>● LIVE</div>
            </div>

            <div ref={feedRef} style={{
                flex: 1,
                overflowY: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.8rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '5px'
            }}>
                {events.length === 0 ? (
                    <div style={{ color: '#444' }}>Waiting for security events...</div>
                ) : (
                    events.map((ev, i) => (
                        <div key={i} style={{ display: 'flex', gap: '10px' }}>
                            <span style={{ color: '#555' }}>[{new Date(ev.timestamp || Date.now()).toLocaleTimeString()}]</span>
                            <span style={{ color: getEventColor(ev.type), fontWeight: 'bold' }}>{ev.type?.toUpperCase()}</span>
                            <span style={{ color: '#aaa' }}>{ev.subject}:</span>
                            <span style={{ color: '#fff' }}>{ev.action}</span>
                            <span style={{ color: '#888', fontStyle: 'italic' }}>({ev.resource})</span>
                        </div>
                    ))
                )}
            </div>
            <style>{`
                ::-webkit-scrollbar { width: 4px; }
                ::-webkit-scrollbar-track { background: transparent; }
                ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
            `}</style>
        </div>
    );
}
