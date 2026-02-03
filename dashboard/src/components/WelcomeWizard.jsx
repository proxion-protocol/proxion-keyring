import { useState, useEffect } from 'react';

export const WelcomeWizard = ({ onComplete }) => {
    const [step, setStep] = useState(1);
    const [deps, setDeps] = useState(null);
    const [checking, setChecking] = useState(false);
    const [mode, setMode] = useState(null);

    const steps = [
        { id: 1, title: 'Welcome', description: 'Let\'s get your Proxion Suite ready.' },
        { id: 2, title: 'Environment', description: 'Checking for Docker, WSL2, and FUSE drivers.' },
        { id: 3, title: 'Identity Provider', description: 'Authenticate with your Solid Pod.' },
        { id: 4, title: 'Dashboard', description: 'Finalizing your unified portal.' }
    ];

    const runDependencyCheck = async () => {
        setChecking(true);
        try {
            const resp = await fetch('http://127.0.0.1:8788/system/audit');
            const data = await resp.json();
            setDeps(data);
        } catch (err) {
            console.error("Dependency check failed", err);
            setDeps({
                docker: [false, "Docker not found"],
                wsl: [true, "WSL2 is ready"],
                fuse: [true, "WinFSP is installed"],
                wireguard: [true, "WireGuard found"]
            });
        } finally {
            setChecking(false);
        }
    };

    const handleInstall = async (depKey) => {
        try {
            const resp = await fetch('http://127.0.0.1:8788/system/install', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dep: depKey })
            });
            const data = await resp.json();
            if (resp.ok) {
                // Background polling will catch the update
                runDependencyCheck();
            } else {
                console.error("Install error:", data.error);
            }
        } catch (err) {
            alert("Installation failed: " + err.message);
        }
    };

    useEffect(() => {
        let interval;
        if (step === 2 && deps && Object.values(deps).some(d => !d[0])) {
            interval = setInterval(runDependencyCheck, 5000);
        }
        return () => clearInterval(interval);
    }, [step, deps]);
    useEffect(() => {
        if (step === 4) {
            const timer = setTimeout(() => {
                onComplete({ mode });
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [step, mode, onComplete]);

    return (
        <div className="wizard-overlay">
            <div className="wizard-card">
                <div className="wizard-progress">
                    {steps.map(s => (
                        <div key={s.id} className={`dot ${step >= s.id ? 'active' : ''} ${step === s.id ? 'current' : ''}`}></div>
                    ))}
                </div>

                <div className="wizard-content">
                    <h1>{steps[step - 1].title}</h1>
                    <p>{steps[step - 1].description}</p>

                    {step === 1 && (
                        <div className="welcome-step">
                            <div className="hero-icon icon-shield"></div>
                            <p>Proxion transforms your computer into a private citadel. We'll help you set up the foundations now.</p>
                            <button className="btn-primary" onClick={() => setStep(2)}>Get Started</button>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="deps-step">
                            {!deps && !checking && (
                                <button className="btn-secondary" onClick={runDependencyCheck}>Scan System</button>
                            )}
                            {checking && <div className="spinner"></div>}
                            {deps && (
                                <div className="deps-list">
                                    {Object.entries(deps).map(([key, [ok, msg]]) => (
                                        <div key={key} className={`dep-item-premium ${ok ? 'ok' : 'fail'}`}>
                                            <div className="dep-meta">
                                                <span className="icon">{ok ? '✅' : '🔴'}</span>
                                                <div className="text">
                                                    <strong>{key.toUpperCase()}</strong>
                                                    <span>{msg}</span>
                                                </div>
                                            </div>
                                            {!ok && (
                                                <button className="btn-mini-install" onClick={() => handleInstall(key)}>
                                                    Auto-Fix
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                    {Object.values(deps).some(d => !d[0]) && (
                                        <div className="status-indicator">
                                            <div className="spinner-mini"></div>
                                            <span>Auto-refreshing status...</span>
                                        </div>
                                    )}
                                    <button className="btn-primary"
                                        style={{ marginTop: '1rem' }}
                                        disabled={Object.values(deps).some(d => !d[0])}
                                        onClick={() => setStep(3)}
                                    >
                                        Continue
                                    </button>
                                    {Object.values(deps).some(d => !d[0]) && (
                                        <p className="error-text">Please install missing components to continue.</p>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {step === 3 && (
                        <div className="identity-step">
                            <p className="intro-text">
                                Proxion uses the <strong>Solid Protocol</strong> for decentralized identity.
                                Connect your existing WebID or initialize a local provider.
                            </p>

                            <div className="id-options">
                                <button className="btn-option" onClick={() => { setMode('local'); setStep(4); }}>
                                    <div className="icon">🏠</div>
                                    <div className="details">
                                        <strong>Create Local Identity</strong>
                                        <span>Use this device as my primary provider</span>
                                    </div>
                                </button>

                                <button className="btn-option" onClick={() => alert("External Pod connection coming in Phase 2.")}>
                                    <div className="icon">🌐</div>
                                    <div className="details">
                                        <strong>Connect External Pod</strong>
                                        <span>Log in with accurate, inrupt.net, etc.</span>
                                    </div>
                                </button>
                            </div>

                            <p className="hint">
                                Standards-compliant WebID authentication. <a href="https://solidproject.org" target="_blank" rel="noreferrer">Learn more</a>.
                            </p>
                        </div>
                    )}
                </div>
            </div>

            <style>{`
                .wizard-overlay {
                  position: fixed;
                  top: 0; left: 0; right: 0; bottom: 0;
                  background: rgba(0,0,0,0.85);
                  backdrop-filter: blur(8px);
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  z-index: 9999;
                  width: 100vw;
                  height: 100vh;
                }
                .wizard-card {
                  background: #111;
                  border: 1px solid rgba(255,255,255,0.1);
                  width: 90%;
                  max-width: 500px;
                  border-radius: 24px;
                  padding: 2.5rem;
                  text-align: center;
                  box-shadow: 0 20px 50px rgba(0,0,0,0.5);
                  animation: modalEnter 0.4s cubic-bezier(0.16, 1, 0.3, 1);
                }
                @keyframes modalEnter {
                  from { opacity: 0; transform: scale(0.9) translateY(20px); }
                  to { opacity: 1; transform: scale(1) translateY(0); }
                }
                .wizard-progress {
                  display: flex;
                  justify-content: center;
                  gap: 0.75rem;
                  margin-bottom: 2rem;
                }
                .dot {
                  width: 10px; height: 10px;
                  border-radius: 50%;
                  background: rgba(255,255,255,0.1);
                  transition: all 0.3s;
                }
                .dot.active { background: #4f46e5; transform: scale(1.2); }
                .dot.current { box-shadow: 0 0 15px #6366f1; }
                
                .wizard-content h1 { font-size: 1.75rem; margin-bottom: 0.5rem; letter-spacing: -0.02em; }
                .wizard-content p { color: #888; margin-bottom: 2rem; }

                .dep-item-premium {
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                  gap: 1rem;
                  margin-bottom: 0.75rem;
                  padding: 1rem;
                  background: rgba(255,255,255,0.03);
                  border-radius: 12px;
                  border: 1px solid rgba(255,255,255,0.05);
                }
                .dep-item-premium.fail { border-color: rgba(239, 68, 68, 0.2); }
                .dep-meta { display: flex; gap: 1rem; align-items: center; }
                .dep-meta .text { display: flex; flex-direction: column; text-align: left; }
                .btn-mini-install {
                  padding: 0.5rem 1rem;
                  border-radius: 8px;
                  background: #4f46e5;
                  color: white;
                  border: none;
                  font-size: 0.8rem;
                  font-weight: 600;
                  cursor: pointer;
                  transition: all 0.2s;
                }
                .btn-mini-install:hover { background: #6366f1; transform: translateY(-1px); }

                .status-indicator {
                  display: flex;
                  align-items: center;
                  gap: 0.75rem;
                  margin: 1rem 0;
                  color: #6366f1;
                  font-size: 0.8rem;
                  font-weight: 500;
                  animation: fadeIn 0.5s ease-out;
                }
                .spinner-mini {
                  width: 14px;
                  height: 14px;
                  border: 2px solid rgba(99, 102, 241, 0.2);
                  border-top-color: #6366f1;
                  border-radius: 50%;
                  animation: spin 0.8s linear infinite;
                }
                @keyframes spin { to { transform: rotate(360deg); } }
                @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
                @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

                .intro-text { font-size: 0.95rem; line-height: 1.5; color: #a0aec0; margin-bottom: 2rem; }
                .intro-text strong { color: #fff; }

                .id-options {
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                    margin-bottom: 2rem;
                }
                .btn-option {
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    padding: 1.25rem;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 12px;
                    color: white;
                    text-align: left;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .btn-option:hover {
                    background: rgba(255,255,255,0.1);
                    transform: translateY(-2px);
                    border-color: #6366f1;
                }
                .btn-option .icon { font-size: 1.5rem; }
                .btn-option .details { display: flex; flex-direction: column; }
                .btn-option .details strong { display: block; font-size: 1rem; margin-bottom: 0.2rem; }
                .btn-option .details span { font-size: 0.8rem; color: #94a3b8; }
                
                .hint a { color: #6366f1; text-decoration: none; }
                .hint a:hover { text-decoration: underline; }
            `}</style>
        </div>
    );
};
