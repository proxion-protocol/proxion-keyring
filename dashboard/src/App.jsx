import { useState, useEffect } from 'react';
import { QRCodeCanvas as QRCode } from 'qrcode.react';
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
import './App.css';

function App() {
  const [session, setSession] = useState(null);
  const [oidcIssuer, setOidcIssuer] = useState("https://solidcommunity.net");
  const [tunnels, setTunnels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showMobile, setShowMobile] = useState(false);
  const [peers, setPeers] = useState({});
  const [isMobileView, setIsMobileView] = useState(window.location.pathname === '/mobile');
  const [proxionToken, setProxionToken] = useState(localStorage.getItem('proxion_token') || null);
  const [hsId, setHsId] = useState(null);
  const [qrUri, setQrUri] = useState(null);
  const [showWizard, setShowWizard] = useState(!localStorage.getItem('onboarding_complete'));
  const [showTutorial, setShowTutorial] = useState(false);
  const [activeTab, setActiveTab] = useState('apps');

  // Removed auto-resize listener to allow responsive dashboard on mobile browsers
  useEffect(() => {
    // Only check path on mount
    setIsMobileView(window.location.pathname === '/mobile');

    // Auto-fetch token for local development if none exists
    if (!localStorage.getItem('proxion_token')) {
      fetch('http://localhost:8788/session/activate', {
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
      fetch("http://localhost:8788/gateway/challenge", { method: "POST" })
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
        fetch(`http://localhost:8788/gateway/poll?id=${hsId}`)
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
            fetch("http://localhost:8788/system/mount", {
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
    fetch("http://localhost:8788/peers", {
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
    auth.handleRedirect().then(async (sess) => {
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
          const resp = await fetch('http://localhost:8788/session/activate', {
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
    });
  }, []); // Run only on mount

  useEffect(() => {
    if (proxionToken) fetchPeers();
    const interval = setInterval(fetchPeers, 5000);
    return () => clearInterval(interval);
  }, [proxionToken]);

  const handleRevoke = async (pubkey) => {
    if (!window.confirm("Are you sure you want to REVOKE this device? Access will be IMMEDIATELY cut.")) return;

    try {
      await fetch("http://localhost:8788/peers/revoke", {
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

  if (loading) return (
    <div className="center-screen">
      <div className="spinner"></div>
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
            {activeTab === 'apps' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>App Library</h1>
                  <p>Deploy private integrations to your suite.</p>
                </header>
                <InstallationCenter proxionToken={proxionToken} />
              </div>
            )}

            {activeTab === 'mesh' && (
              <div className="view-container">
                <header className="view-header">
                  <h1>Mesh Network</h1>
                  <p>Global encrypted backbone and local discovery.</p>
                </header>
                <RelayManager proxionToken={proxionToken} />
                <MeshManager proxionToken={proxionToken} peers={peers} />
                <Discovery proxionToken={proxionToken} />
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
