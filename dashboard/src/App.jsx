import { useState, useEffect } from 'react';
import { QRCodeCanvas as QRCode } from 'qrcode.react';
import appsRegistry from './data/apps.json';
import { auth, data } from './services/solid';
import { MobileConnect } from './components/MobileConnect';
import { MobileApp } from './components/MobileApp';
import { FederationPolicy } from './components/FederationPolicy';
import { MeshManager } from './components/MeshManager';
import { Discovery } from './components/Discovery';
import { InstallationCenter } from './components/InstallationCenter';
import { WelcomeWizard } from './components/WelcomeWizard';
import { HomarrTutorial } from './components/HomarrTutorial';
import { RelayManager } from './components/RelayManager';
import { StorageManager } from './components/StorageManager';
import { IdentityManager } from './components/IdentityManager';
import { PrivacyShield } from './components/PrivacyShield';
import { FederationInvite } from './components/FederationInvite';
import { HealthGrid } from './components/HealthGrid';
import { Librarian } from './components/Librarian';
import { AuditFeed } from './components/AuditFeed';
import { Guardian } from './components/Guardian';
import './App.css';

function App() {
  const [session, setSession] = useState(null);
  const [oidcIssuer, setOidcIssuer] = useState("https://solidcommunity.net");
  const [tunnels, setTunnels] = useState([]);
  const [loading, setLoading] = useState(!localStorage.getItem('proxion_token') && !localStorage.getItem('local_mode'));
  const [showMobile, setShowMobile] = useState(false);
  const [peers, setPeers] = useState({});
  const [isMobileView, setIsMobileView] = useState(window.location.pathname === '/mobile');
  const [proxionToken, setProxionToken] = useState(localStorage.getItem('proxion_token') || null);
  const [hsId, setHsId] = useState(null);
  const [qrUri, setQrUri] = useState(null);
  const [showWizard, setShowWizard] = useState(!localStorage.getItem('onboarding_complete'));
  const [showTutorial, setShowTutorial] = useState(false);
  const [activeTab, setActiveTab] = useState('apps');
  const [activeApps, setActiveApps] = useState([]); // [{ id, name, url, icon }]
  const [repoRoot, setRepoRoot] = useState(null);


  // Removed auto-resize listener to allow responsive dashboard on mobile browsers
  useEffect(() => {
    const init = async () => {
      try {
        // Initialize repo root for preloads
        const root = await window.electronAPI?.getRepoRoot();
        if (root) {
          setRepoRoot(root);
          window.proxion_repo_root = root; // Keep global for external scripts
        }
      } catch (err) {
        console.error('Initialization error:', err);
      } finally {
        const params = new URLSearchParams(window.location.search);
        setIsMobileView(params.get('view') === 'mobile' || window.location.pathname === '/mobile');
      }
    };
    init();

    // Auto-fetch token for local development if none exists
    if (!localStorage.getItem('proxion_token')) {
      fetch('http://127.0.0.1:8788/session/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ webId: 'local-dashboard', accessToken: 'auto' })
      })
        .then(res => res.json())
        .then(data => {
          if (data.proxion_token) {
            setProxionToken(data.proxion_token);
            localStorage.setItem('proxion_token', data.proxion_token);
            localStorage.setItem('local_mode', 'true');
            setSession({ info: { isLoggedIn: true, webId: 'https://localhost:8788/profile/card#me' }, guest: true });
            console.log('Auto-activated local session with token');
          }
        })
        .catch(err => console.error('Auto-token fetch failed:', err));
    }
  }, []);

  useEffect(() => {
    if (!session?.info.isLoggedIn && !isMobileView) {
      fetch("http://127.0.0.1:8788/gateway/challenge", { method: "POST" })
        .then(res => res.json())
        .then(data => {
          setHsId(data.handshake_id);
          setQrUri(data.qr_uri);
        })
        .catch(err => console.error("Handshake challenge failed", err));
    }
  }, [session, isMobileView]);

  useEffect(() => {
    if (hsId) {
      const poll = setInterval(() => {
        fetch(`http://127.0.0.1:8788/gateway/poll?id=${hsId}`)
          .then(res => {
            if (res.status === 200) return res.json();
            throw new Error("pending");
          })
          .then(data => {
            clearInterval(poll);
            setProxionToken(data.proxion_token);
            localStorage.setItem('proxion_token', data.proxion_token);
            setSession({ info: { isLoggedIn: true, webId: data.webId || "Proxion Guest" }, guest: true });

            // Auto-Mount Drive P: (Dropbox-style)
            fetch("http://127.0.0.1:8788/system/mount", {
              method: "POST",
              headers: { "Proxion-Token": data.proxion_token }
            }).catch(err => console.error("Auto-mount failed", err));
          })
          .catch(() => { });
      }, 2000);
      return () => clearInterval(poll);
    }
  }, [hsId]);

  // Poll for active peers
  const fetchPeers = () => {
    if (!proxionToken) return;
    fetch("http://127.0.0.1:8788/peers", {
      headers: { 'Proxion-Token': proxionToken }
    })
      .then(res => res.json())
      .then(data => {
        if (data.error) console.error("Peer fetch error:", data.error);
        else setPeers(data);
      })
      .catch(err => console.error("Failed to fetch peers", err));
  };

  useEffect(() => {
    // Safety fallback: Never stay in loading state more than 3s
    const safetyTimeout = setTimeout(() => {
      setLoading(false);
    }, 3000);

    auth.handleRedirect().then(async (sess) => {
      clearTimeout(safetyTimeout);
      // Check for Local Mode restoration
      if ((!sess || !sess.info.isLoggedIn) && localStorage.getItem('local_mode') === 'true') {
        sess = {
          info: { isLoggedIn: true, webId: "https://localhost:8788/profile/card#me" },
          guest: true
        };
        console.log("Auto-restored local session");
      }

      setSession(sess);
      setLoading(false);
      if (sess && sess.info.isLoggedIn) {
        // Bridge session to backend
        try {
          const resp = await fetch('http://127.0.0.1:8788/session/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              webId: sess.info.webId,
              accessToken: sess.accessToken
            })
          });
          const data = await resp.json();
          if (data.proxion_token) {
            setProxionToken(data.proxion_token);
            localStorage.setItem('proxion_token', data.proxion_token);
            console.log("Backend session activated with Spec Token");
          }
        } catch (err) {
          console.error("Failed to activate backend session:", err);
        }
      }
    }).catch(err => {
      console.error("Auth handleRedirect failed:", err);
      setLoading(false);
    });
    return () => clearTimeout(safetyTimeout);
  }, []); // Run only on mount

  useEffect(() => {
    if (proxionToken && session?.info.webId) {
      window.electronAPI?.setSessionContext(session.info.webId, proxionToken);
    }
  }, [proxionToken, session]);

  useEffect(() => {
    if (proxionToken) fetchPeers();
    const interval = setInterval(fetchPeers, 5000);
    return () => clearInterval(interval);
  }, [proxionToken]);

  // Auto-populate running apps on startup
  useEffect(() => {
    if (!proxionToken) return;

    fetch('http://127.0.0.1:8788/suite/status', {
      headers: { 'Proxion-Token': proxionToken }
    })
      .then(res => res.json())
      .then(data => {
        const runningApps = data.apps || {};
        const newActiveApps = [];

        Object.entries(runningApps).forEach(([appId, status]) => {
          if (status === 'RUNNING') {
            const appDef = appsRegistry.find(a => a.id === appId);
            if (appDef && appDef.port && appDef.port !== 0) {
              newActiveApps.push({
                id: appDef.id,
                name: appDef.name,
                url: `http://127.0.0.1:${appDef.port}`,
                icon: `http://127.0.0.1:8788/suite/icon/${appDef.id}`
              });
            }
          }
        });

        if (newActiveApps.length > 0) {
          setActiveApps(prev => {
            const currentIds = new Set(prev.map(p => p.id));
            const toAdd = newActiveApps.filter(a => !currentIds.has(a.id));
            return [...prev, ...toAdd];
          });
        }
      })
      .catch(err => console.error("Failed to sync running apps", err));
  }, [proxionToken]);

  const handleRevoke = async (pubkey) => {
    if (!window.confirm("Are you sure you want to REVOKE this device? Access will be IMMEDIATELY cut.")) return;

    try {
      await fetch("http://127.0.0.1:8788/peers/revoke", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Proxion-Token": proxionToken
        },
        body: JSON.stringify({ pubkey })
      });
      // Refresh list
      fetchPeers();
    } catch (err) {
      alert("Failed to revoke peer: " + err.message);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    await auth.login(oidcIssuer);
  };

  const handleLogout = async () => {
    await auth.logout();
    setSession(null);
    setProxionToken(null);
    localStorage.removeItem('proxion_token');
  };

  const handleOpenApp = (app) => {
    setActiveApps(prev => {
      const existing = prev.find(a => a.id === app.id);
      if (existing) return prev;
      return [...prev, {
        ...app,
        url: app.url || `http://127.0.0.1:${app.port || 80}`,
        icon: app.icon || `http://127.0.0.1:8788/suite/icon/${app.id}`
      }];
    });
    setActiveTab(`app-${app.id}`);
  };

  const handleCloseApp = (e, appId) => {
    e.stopPropagation();
    setActiveApps(prev => prev.filter(a => a.id !== appId));
    setActiveTab(current => current === `app-${appId}` ? 'apps' : current);
  };

  const handleOrchestrate = async (action) => {
    if (!confirm(`Are you sure you want to ${action} the entire suite?`)) return;
    try {
      const resp = await fetch("http://127.0.0.1:8788/suite/orchestrate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Proxion-Token": proxionToken
        },
        body: JSON.stringify({ action, target: 'all' })
      });
      if (resp.ok) {
        alert(`${action} command sent to suite.`);
      } else {
        const errorData = await resp.json();
        alert(`Error: ${errorData.error}`);
      }
    } catch (err) {
      console.error("Orchestration failed:", err);
    }
  };

  if (loading) return (
    <div className="center-screen" style={{ flexDirection: 'column', gap: '20px' }}>
      <div className="spinner"></div>
      <div style={{ color: '#4c566a', fontSize: '12px', fontWeight: 'bold' }}>Initializing Sovereign Dashboard...</div>
    </div>
  );

  if (session?.info.isLoggedIn && isMobileView) {
    return (
      <MobileApp
        session={session}
        proxionToken={proxionToken}
        peers={peers}
        onLogout={handleLogout}
        onRevoke={handleRevoke}
      />
    );
  }

  return (
    <div className="app-container">
      {showWizard && <WelcomeWizard onComplete={(data) => {
        setShowWizard(false);
        localStorage.setItem('onboarding_complete', 'true');
        if (data?.mode === 'local') {
          localStorage.setItem('local_mode', 'true');
          // Initialize Local Guest Session
          setSession({
            info: { isLoggedIn: true, webId: "https://localhost:8788/profile/card#me" },
            guest: true
          });
        }
      }}
      />}

      {showTutorial && <HomarrTutorial onClose={() => setShowTutorial(false)} />}

      {!session?.info.isLoggedIn ? (
        <div className="login-card">
          <div className="brand">
            <div className="logo-icon"></div>
            <h1>proxion-keyring</h1>
          </div>
          <p className="tagline">Your personal sovereign cloud infrastructure.</p>

          {localStorage.getItem('local_mode') && (
            <button className="btn-resume-local" onClick={() => setSession({
              info: { isLoggedIn: true, webId: "https://localhost:8788/profile/card#me" },
              guest: true
            })}>
              <div className="icon">🏠</div>
              <span>Continue as Local User</span>
            </button>
          )}

          <form onSubmit={handleLogin} className="login-form">
            <label>Connect with your Solid Pod</label>
            <div className="input-wrapper">
              <input
                type="text"
                value={oidcIssuer}
                onChange={(e) => setOidcIssuer(e.target.value)}
                placeholder="https://solidcommunity.net"
              />
            </div>
            <button type="submit" className="btn-primary">
              Connect Securely
            </button>
          </form>

          <div className="login-divider">
            <span>OR LOGIN WITH APP</span>
          </div>

          <div className="qr-login-box">
            {qrUri ? (
              <div style={{ background: 'white', padding: '10px', borderRadius: '8px', display: 'inline-block' }}>
                <QRCode value={qrUri} size={150} />
              </div>
            ) : <p>Loading handshake...</p>}
            <p className="tiny-text">Scan with your authorized phone.</p>
          </div>

          <p className="help-text">
            Don't have a Pod? <a href="#">Get one here</a>.
            <br /><br />
            <a href="#" style={{ opacity: 0.6 }} onClick={(e) => {
              e.preventDefault();
              if (confirm("Reset setup wizard?")) {
                localStorage.removeItem('onboarding_complete');
                localStorage.removeItem('local_mode');
                window.location.reload();
              }
            }}>Need to restart setup?</a>
          </p>
        </div>
      ) : (
        <div className="control-plane">
          <aside className="sidebar">
            <div className="sidebar-brand">
              <div className="logo-icon-small"></div>
              <span>Proxion</span>
            </div>

            <nav className="sidebar-nav">
              <div className="nav-section">
                <span className="section-label">SYSTEM</span>
                <button className={activeTab === 'apps' ? 'active' : ''} onClick={() => setActiveTab('apps')}>
                  <span className="icon">🏪</span> App Library
                </button>
                <button className={activeTab === 'mesh' ? 'active' : ''} onClick={() => setActiveTab('mesh')}>
                  <span className="icon">🌐</span> Mesh Relay
                </button>
                <button className={activeTab === 'storage' ? 'active' : ''} onClick={() => setActiveTab('storage')}>
                  <span className="icon">💽</span> Storage
                </button>
                <button className={activeTab === 'identity' ? 'active' : ''} onClick={() => setActiveTab('identity')}>
                  <span className="icon">🔑</span> Identity
                </button>
                <button className={activeTab === 'containers' ? 'active' : ''} onClick={() => setActiveTab('containers')}>
                  <span className="icon">🐳</span> Containers
                </button>
                <button className={activeTab === 'security' ? 'active' : ''} onClick={() => setActiveTab('security')}>
                  <span className="icon">🛡️</span> Security
                </button>
                <button className={activeTab === 'librarian' ? 'active' : ''} onClick={() => setActiveTab('librarian')}>
                  <span className="icon">📚</span> Librarian
                </button>
                <button className={activeTab === 'fleet' ? 'active' : ''} onClick={() => setActiveTab('fleet')}>
                  <span className="icon">📱</span> Fleet
                </button>

              </div>

              {activeApps.length > 0 && (
                <div className="nav-section">
                  <span className="section-label">RUNNING</span>
                  {activeApps.map(app => (
                    <button
                      key={app.id}
                      className={`app-tab ${activeTab === `app-${app.id}` ? 'active' : ''}`}
                      onClick={() => setActiveTab(`app-${app.id}`)}
                    >
                      <img src={app.icon} className="icon-img" onError={(e) => e.target.style.display = 'none'} />
                      <span className="app-name">{app.name}</span>
                      <span className="close-x" onClick={(e) => handleCloseApp(e, app.id)}>×</span>
                    </button>
                  ))}
                </div>
              )}
            </nav>

            <div className="sidebar-footer">
              <div className="user-pill">
                <div className="avatar"></div>
                <span>{session?.info?.webId?.split('/')[2] || "User"}</span>
              </div>
              <button onClick={handleLogout} className="btn-logout-small">Logout</button>
            </div>
          </aside>

          <main className="main-viewport">
            <div
              className="view-container"
              style={{ display: activeTab === 'apps' ? 'block' : 'none' }}
            >
              <header className="view-header">
                <h1>App Library</h1>
                <p>Deploy private integrations to your suite.</p>
              </header>
              <InstallationCenter
                proxionToken={proxionToken}
                onOpenApp={handleOpenApp}
              />
            </div>

            {/* Render ALL active apps as hidden webviews to preserve state */}
            {activeApps.map(app => (
              <div
                key={app.id}
                className="webview-container"
                style={{
                  display: activeTab === `app-${app.id}` ? 'flex' : 'none',
                  flex: 1,
                  height: '100%'
                }}
              >
                <webview
                  id={`webview-${app.id}`}
                  src={app.url}
                  partition={`persist:${app.id}`}
                  style={{ width: '100%', height: '100%', border: 'none' }}
                />
              </div>
            ))}

            {activeTab === 'mesh' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>Mesh Network</h1>
                  <p>Global encrypted backbone and local discovery.</p>
                </header>
                <PrivacyShield proxionToken={proxionToken} />
                <RelayManager proxionToken={proxionToken} />
                <MeshManager proxionToken={proxionToken} peers={peers} />
                <Discovery proxionToken={proxionToken} />
              </div>
            )}

            {activeTab === 'containers' && (
              <div className="view-container" style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '2rem' }}>
                <header className="view-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div>
                    <h1>Suite Orchestration</h1>
                    <p>Manage container health and bulk power actions.</p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button className="btn-secondary" onClick={() => handleOrchestrate('restart')}>🔄 Restart All</button>
                    <button className="btn-danger-small" onClick={() => handleOrchestrate('down')}>🛑 Stop All</button>
                    <button className="btn-primary" onClick={() => handleOrchestrate('up')}>🚀 Start All</button>
                  </div>
                </header>
                <HealthGrid proxionToken={proxionToken} />
                <div style={{ flex: 1, marginTop: '2rem', minHeight: '400px', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <webview
                    src="http://127.0.0.1:9001"
                    style={{ width: '100%', height: '100%' }}
                    title="Portainer"
                  />
                </div>
              </div>
            )}

            {activeTab === 'storage' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>Unified Storage</h1>
                  <p>High-performance FUSE mount for your personal Pod.</p>
                </header>
                <StorageManager proxionToken={proxionToken} />
              </div>
            )}

            {activeTab === 'librarian' && (
              <div className="view-container" style={{ height: 'calc(100% - 100px)' }}>
                <header className="view-header">
                  <h1>The Librarian</h1>
                  <p>Web-native browsing of your Unified Stash. No drivers required.</p>
                </header>
                <Librarian proxionToken={proxionToken} />
              </div>
            )}

            {activeTab === 'fleet' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>Fleet Management</h1>
                  <p>Invite devices and manage federation access tokens.</p>
                </header>
                <FederationInvite proxionToken={proxionToken} />
              </div>
            )}

            {activeTab === 'security' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>Security</h1>
                  <p>Consolidated security intelligence and live audit trail.</p>
                </header>
                <Guardian proxionToken={proxionToken} />
                <div style={{ marginTop: '20px' }}>
                  <AuditFeed proxionToken={proxionToken} />
                </div>
              </div>
            )}


            {activeTab === 'identity' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>Identity & Security</h1>
                  <p>Manage devices, keys, and capability audits.</p>
                </header>
                <IdentityManager proxionToken={proxionToken} />

                <div className="card-section">
                  <div className="section-header">
                    <h3>Lined Devices</h3>
                    <button className="btn-secondary btn-sm" onClick={() => setShowMobile(true)}>+ Connect Mobile</button>
                  </div>

                  {showMobile && <MobileConnect onClose={() => setShowMobile(false)} />}

                  <div className="device-list-compact">
                    {Object.keys(peers).length === 0 ? (
                      <p className="empty-msg">No active mobile devices linked.</p>
                    ) : (
                      Object.entries(peers).map(([pubkey, meta]) => (
                        <div className="device-row" key={pubkey}>
                          <div className="device-icon-mini"></div>
                          <div className="device-details">
                            <strong>{meta.name || 'Mobile Device'}</strong>
                            <code>{meta.ip || '10.0.0.x'}</code>
                          </div>
                          <button className="btn-revoke-mini" onClick={() => handleRevoke(pubkey)}>×</button>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <FederationPolicy proxionToken={proxionToken} />
              </div>
            )}

          </main>
        </div>
      )
      }
    </div >
  );
}

export default App;
