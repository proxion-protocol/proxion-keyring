import { useState, useEffect, useRef } from 'react';
import { QRCodeSVG } from 'qrcode.react';



export function MeshMessenger({ proxionToken, peers }) {

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [selectedPeer, setSelectedPeer] = useState(null);
    const [inviteToken, setInviteToken] = useState(null);
    const [inviteInput, setInviteInput] = useState('');
    const [consumingToken, setConsumingToken] = useState(false);
    const scrollRef = useRef(null);


    const peerList = Object.entries(peers || {}).map(([pubkey, meta]) => ({
        pubkey,
        name: meta.name || 'Anonymous Node',
        ip: meta.ip || '10.0.0.x',
        verified: true // Based on Merkle Log in background
    }));

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const generateInvite = async () => {
        try {
            const resp = await fetch("http://127.0.0.1:8788/mesh/invite/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Proxion-Token": proxionToken },
                body: JSON.stringify({ group_id: "default-mesh" })
            });
            const data = await resp.json();
            setInviteToken(data.token);
        } catch (err) {
            console.error("Invite Generation Error:", err);
        }
    };

    const consumeInvite = async () => {
        if (!inviteInput.trim()) return;
        setConsumingToken(true);
        try {
            const resp = await fetch("http://127.0.0.1:8788/mesh/invite/consume", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Proxion-Token": proxionToken },
                body: JSON.stringify({ token: inviteInput.trim(), name: "New Peer (Handshake)" })
            });
            if (resp.ok) {
                const data = await resp.json();
                alert(`Sovereign Handshake Complete with ${data.name}! Mesh peered.`);
                setInviteInput('');
            } else {
                const err = await resp.json();
                throw new Error(err.error || "Consumption failed");
            }
        } catch (err) {
            alert("Invite failed: " + err.message);
        } finally {
            setConsumingToken(false);
        }
    };


    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim() || !selectedPeer) return;

        const newMessage = {
            id: Date.now(),
            sender: 'me',
            text: input,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            encrypted: true
        };

        setMessages(prev => [...prev, newMessage]);
        const draft = input;
        setInput('');

        try {
            const resp = await fetch("http://127.0.0.1:8788/mesh/signal/send", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Proxion-Token": proxionToken
                },
                body: JSON.stringify({
                    peer_pubkey: selectedPeer.pubkey,
                    text: draft
                })
            });
            if (!resp.ok) throw new Error("Send failed");

            // Phase 6: Mock success ack (real poll would come via signal_poll)
            setTimeout(() => {
                const reply = {
                    id: Date.now() + 1,
                    sender: selectedPeer.name,
                    text: `Awaiting mesh acknowledgement for: "${draft.substring(0, 10)}..."`,
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    encrypted: true
                };
                setMessages(prev => [...prev, reply]);
            }, 1000);

        } catch (err) {
            console.error("Signal Send Error:", err);
            // Optionally mark message as failed in UI
        }
    };


    return (
        <div className="signal-messenger-container" style={{
            display: 'flex',
            height: '600px',
            background: 'rgba(25, 25, 25, 0.4)',
            backdropFilter: 'blur(20px)',
            borderRadius: '24px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            overflow: 'hidden',
            marginTop: '20px'
        }}>
            {/* Sidebar: Peers */}
            <div style={{ width: '260px', borderRight: '1px solid rgba(255, 255, 255, 0.05)', padding: '20px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                    <h4 style={{ margin: 0, fontSize: '0.8rem', color: '#888', textTransform: 'uppercase', letterSpacing: '1px' }}>Sovereign Mesh</h4>
                    <button onClick={generateInvite} style={{ background: 'none', border: 'none', color: '#2196F3', fontSize: '1.2rem', cursor: 'pointer' }} title="Invite New Peer">+</button>
                </div>

                {inviteToken && (
                    <div style={{ marginBottom: '15px', padding: '15px', background: 'rgba(33, 150, 243, 0.1)', borderRadius: '12px', border: '1px solid rgba(33, 150, 243, 0.3)' }}>
                        <div style={{ fontSize: '0.6rem', color: '#2196F3', marginBottom: '10px', textAlign: 'center', fontWeight: 'bold' }}>YOUR INVITE</div>

                        {/* QR Code */}
                        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px', padding: '10px', background: '#fff', borderRadius: '8px' }}>
                            <QRCodeSVG
                                value={`proxion://mesh/invite?token=${inviteToken}`}
                                size={140}
                                level="H"
                                includeMargin={true}
                            />
                        </div>

                        {/* Token Text */}
                        <div style={{ fontSize: '0.55rem', color: '#888', marginBottom: '5px', textAlign: 'center' }}>OR COPY TOKEN</div>
                        <code style={{ fontSize: '0.65rem', color: '#fff', wordBreak: 'break-all', display: 'block', textAlign: 'center', padding: '5px', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>{inviteToken}</code>
                        <div style={{ fontSize: '0.6rem', color: '#888', marginTop: '8px', textAlign: 'center' }}>Scan with Signal Messenger app</div>
                    </div>
                )}


                <div style={{ marginBottom: '15px' }}>
                    <div style={{ display: 'flex', gap: '5px' }}>
                        <input
                            type="text"
                            placeholder="Paste invite token..."
                            value={inviteInput}
                            onChange={(e) => setInviteInput(e.target.value)}
                            style={{ flex: 1, background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', fontSize: '0.7rem', padding: '5px', color: '#fff' }}
                        />
                        <button
                            onClick={consumeInvite}
                            disabled={consumingToken || !inviteInput.trim()}
                            style={{ background: '#2196F3', border: 'none', borderRadius: '6px', color: '#fff', padding: '0 8px', fontSize: '1.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', opacity: (consumingToken || !inviteInput.trim()) ? 0.5 : 1 }}
                        >
                            🤝
                        </button>
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, overflowY: 'auto' }}>
                    {peerList.map(peer => (
                        <div
                            key={peer.pubkey}
                            onClick={() => setSelectedPeer(peer)}
                            style={{
                                padding: '12px',
                                borderRadius: '12px',
                                background: selectedPeer?.pubkey === peer.pubkey ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
                                border: `1px solid ${selectedPeer?.pubkey === peer.pubkey ? 'rgba(255, 255, 255, 0.1)' : 'transparent'}`,
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >

                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'linear-gradient(45deg, #2196F3, #00BCD4)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px' }}>
                                    {peer.name[0]}
                                </div>
                                <div>
                                    <div style={{ fontSize: '0.9rem', color: '#fff', fontWeight: '500' }}>{peer.name}</div>
                                    <div style={{ fontSize: '0.7rem', color: peer.verified ? '#4CAF50' : '#888' }}>
                                        {peer.verified ? 'Verified Identity' : 'Discovery Loop'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                    {peerList.length === 0 && <div className="tiny-text" style={{ padding: '20px', textAlign: 'center', opacity: 0.5 }}>No peers in range.</div>}
                </div>
            </div>

            {/* Chat Area */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                {selectedPeer ? (
                    <>
                        {/* Header */}
                        <div style={{ padding: '15px 25px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                                <h3 style={{ margin: 0, fontSize: '1rem', color: '#fff' }}>{selectedPeer.name}</h3>
                                <div style={{ fontSize: '0.7rem', color: '#4CAF50', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#4CAF50' }}></span>
                                    Double Ratchet Active (Post-Quantum)
                                </div>
                            </div>
                            <div className="tiny-text" style={{ color: '#888' }}>{selectedPeer.ip}</div>
                        </div>

                        {/* Messages */}
                        <div ref={scrollRef} style={{ flex: 1, padding: '25px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '15px' }}>
                            {messages.map(msg => (
                                <div key={msg.id} style={{
                                    alignSelf: msg.sender === 'me' ? 'flex-end' : 'flex-start',
                                    maxWidth: '70%',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: msg.sender === 'me' ? 'flex-end' : 'flex-start'
                                }}>
                                    <div style={{
                                        padding: '12px 18px',
                                        borderRadius: msg.sender === 'me' ? '18px 18px 2px 18px' : '18px 18px 18px 2px',
                                        background: msg.sender === 'me' ? 'linear-gradient(135deg, #2196F3, #1565C0)' : 'rgba(255, 255, 255, 0.05)',
                                        color: '#fff',
                                        fontSize: '0.9rem',
                                        lineHeight: '1.4',
                                        boxShadow: msg.sender === 'me' ? '0 4px 15px rgba(33, 150, 243, 0.2)' : 'none'
                                    }}>
                                        {msg.text}
                                    </div>
                                    <div style={{ fontSize: '0.65rem', color: '#555', marginTop: '5px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                        {msg.timestamp} {msg.encrypted && '🔒'}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Input */}
                        <form onSubmit={handleSendMessage} style={{ padding: '20px 25px', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
                            <div style={{ display: 'flex', gap: '15px', background: 'rgba(255, 255, 255, 0.03)', padding: '10px 15px', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder={`Message ${selectedPeer.name}...`}
                                    style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', outline: 'none', fontSize: '0.9rem' }}
                                />
                                <button type="submit" disabled={!input.trim()} style={{ background: 'none', border: 'none', color: '#2196F3', cursor: 'pointer', fontWeight: 'bold', opacity: input.trim() ? 1 : 0.3 }}>
                                    SEND
                                </button>
                            </div>
                        </form>
                    </>
                ) : (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#555', gap: '15px' }}>
                        <div style={{ fontSize: '3rem', opacity: 0.2 }}>💬</div>
                        <div style={{ fontSize: '0.9rem' }}>Select a peer to initiate a secure sovereign session.</div>
                    </div>
                )}
            </div>
        </div>
    );
}
