import sqlite3
import os
import json
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

class CVECache:
    """Local cache for CVE metadata and Known Exploited Vulnerabilities (KEV)."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # CVE Metadata Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cves (
                cve_id TEXT PRIMARY KEY,
                severity TEXT,
                cvss_score REAL,
                is_known_exploited INTEGER DEFAULT 0,
                description TEXT,
                last_updated TEXT
            )
        ''')
        
        # Sync Metadata Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def sync_kev(self) -> int:
        """Sync with CISA's Known Exploited Vulnerabilities (KEV) catalog."""
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        
        try:
            resp = requests.get(url, timeout=30)
            if not resp.ok:
                return 0
            
            data = resp.json()
            vulnerabilities = data.get("vulnerabilities", [])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for v in vulnerabilities:
                cve_id = v.get("cveID")
                if not cve_id:
                    continue
                
                # Update or insert KEV status
                cursor.execute('''
                    INSERT INTO cves (cve_id, is_known_exploited, last_updated)
                    VALUES (?, 1, ?)
                    ON CONFLICT(cve_id) DO UPDATE SET
                        is_known_exploited = 1,
                        last_updated = excluded.last_updated
                ''', (cve_id, datetime.now(timezone.utc).isoformat()))
            
            # Update sync timestamp
            cursor.execute('''
                INSERT INTO sync_metadata (key, value)
                VALUES ("last_kev_sync", ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (datetime.now(timezone.utc).isoformat(),))
            
            conn.commit()
            count = cursor.rowcount
            conn.close()
            return len(vulnerabilities)
        except Exception as e:
            print(f"CVECache: KEV sync failed: {e}")
            return 0

    def get_cve_status(self, cve_id: str) -> Dict[str, Any]:
        """Check if a CVE is known to be exploited."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT is_known_exploited, severity, cvss_score FROM cves WHERE cve_id = ?', (cve_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "known_exploited": bool(row[0]),
                "severity": row[1],
                "cvss_score": row[2]
            }
        return {"known_exploited": False, "severity": "UNKNOWN", "cvss_score": 0.0}

    def batch_check_kev(self, cve_ids: List[str]) -> List[str]:
        """Return a list of CVE IDs that are known to be exploited."""
        if not cve_ids:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(cve_ids))
        cursor.execute(f'SELECT cve_id FROM cves WHERE cve_id IN ({placeholders}) AND is_known_exploited = 1', cve_ids)
        exploited = [row[0] for row in cursor.fetchall()]
        conn.close()
        return exploited
