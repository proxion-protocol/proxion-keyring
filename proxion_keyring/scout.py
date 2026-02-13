import subprocess
import json
import os
from typing import Dict, Any, List

class SecurityCouncil:
    """Orchestrates multiple security scanners to provide a unified risk assessment."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.scanners = ["trivy", "grype", "docker-scout"]
        
    def scan_image(self, image_name: str) -> Dict[str, Any]:
        """Run Trivy against an image and return detailed CVE info."""
        # V9.1: Resolve the actual image name if provided as a container name or shorthand
        try:
            inspect_res = subprocess.run(
                ["docker", "inspect", "--format", "{{.Config.Image}}", image_name],
                capture_output=True, text=True, check=False
            )
            if inspect_res.returncode == 0:
                actual_image = inspect_res.stdout.strip()
                if actual_image:
                    image_name = actual_image
        except:
            pass

        results = {
            "image": image_name,
            "vulnerabilities": [],
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "status": "CLEAN",
            "language": "unknown"
        }
        
        print(f"Council: Running Trivy on {image_name}...")
        try:
            res = subprocess.run([
                "docker", "run", "--rm", 
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "aquasec/trivy:latest", "image", 
                "--severity", "CRITICAL,HIGH,MEDIUM", "--format", "json", image_name
            ], capture_output=True, timeout=180)
            if res.returncode == 0 or res.stdout:
                data = json.loads(res.stdout.decode())
                self._parse_trivy_results(data, results)
        except Exception as e:
            results["error"] = str(e)

        # Status Enforcement
        if results["summary"]["critical"] > 0:
            results["status"] = "BLOCKED"
        elif results["summary"]["high"] > 0:
            results["status"] = "RISKY"
        elif results["summary"]["medium"] > 0:
            results["status"] = "CONCERN"
            
        return results

    def _parse_trivy_results(self, data: Dict[str, Any], results: Dict[str, Any]):
        """Extract detailed CVE info from Trivy JSON output."""
        for result in data.get("Results", []):
            pkg_type = result.get("Type", "unknown")
            if pkg_type in ["gobinary", "gomod"]:
                results["language"] = "go"
            elif pkg_type in ["pip", "poetry", "pipenv"]:
                results["language"] = "python"
            elif pkg_type in ["npm", "yarn"]:
                results["language"] = "nodejs"
            elif pkg_type in ["dotnet-core", "nuget"]:
                results["language"] = "dotnet"
            elif pkg_type in ["cargo"]:
                results["language"] = "rust"
            elif pkg_type in ["composer"]:
                results["language"] = "php"
            elif pkg_type in ["gemspec", "bundler"]:
                results["language"] = "ruby"
            elif pkg_type in ["jar", "pom"]:
                results["language"] = "java"
            elif pkg_type == "alpine":
                results["language"] = results.get("language") or "alpine"
            
            # Deep detection based on package groups
            if pkg_type in ["debian", "ubuntu", "centos", "redhat", "fedora"]:
                for vuln in result.get("Vulnerabilities", []):
                    pkg = vuln.get("PkgName", "").lower()
                    if pkg.startswith("python") or pkg.startswith("pip") or pkg == "zlib1g-dev":
                        results["language"] = "python"
                        break
                    if pkg.startswith("node") or pkg.startswith("npm") or pkg.startswith("libnode"):
                        results["language"] = "nodejs"
                        break
            
            # Fallback detection based on package names if language still unknown
            if results["language"] == "unknown":
                for vuln in result.get("Vulnerabilities", []):
                    pkg = vuln.get("PkgName", "").lower()
                    if pkg.startswith("python") or pkg.startswith("pip"):
                        results["language"] = "python"
                        break
                    if pkg.startswith("node") or pkg.startswith("npm"):
                        results["language"] = "nodejs"
                        break
                    if pkg.startswith("ruby") or pkg.startswith("gem"):
                        results["language"] = "ruby"
                        break
                    if pkg.startswith("openjdk") or pkg.startswith("java-") or pkg.startswith("mvn"):
                        results["language"] = "java"
                        break

            for vuln in result.get("Vulnerabilities", []):
                sev = vuln.get("Severity", "UNKNOWN").lower()
                if sev in results["summary"]:
                    results["summary"][sev] += 1

                cve_detail = {
                    "id": vuln.get("VulnerabilityID", "N/A"),
                    "severity": vuln.get("Severity", "UNKNOWN"),
                    "cvss": vuln.get("CVSS", {}).get("nvd", {}).get("V3Score") or vuln.get("CVSS", {}).get("redhat", {}).get("V3Score"),
                    "package": vuln.get("PkgName", "N/A"),
                    "installed_version": vuln.get("InstalledVersion", "N/A"),
                    "fixed_version": vuln.get("FixedVersion", "N/A"),
                    "title": vuln.get("Title", vuln.get("Description", "No description")[:100]),
                    "link": vuln.get("PrimaryURL") or f"https://nvd.nist.gov/vuln/detail/{vuln.get('VulnerabilityID', '')}",
                    "pkg_type": pkg_type
                }
                results["vulnerabilities"].append(cve_detail)

    def audit_fleet(self) -> Dict[str, Any]:
        """Scan all running containers and return aggregated CVE info."""
        fleet_results = {
            "containers": {},
            "total_critical": 0,
            "total_high": 0,
            "total_medium": 0,
            "fleet_health": 100
        }
        
        try:
            # V7.12+: Include stopped containers in the security audit
            output = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Image}}"]).decode()
            images = list(set(img.strip() for img in output.strip().split("\n") if img.strip() and "<none>" not in img))
        except Exception as e:
            fleet_results["error"] = str(e)
            return fleet_results
            
        for image in images:
            if not image or "<none>" in image:
                continue
            scan = self.scan_image(image)
            fleet_results["containers"][image] = scan
            fleet_results["total_critical"] += scan["summary"]["critical"]
            fleet_results["total_high"] += scan["summary"]["high"]
            fleet_results["total_medium"] += scan["summary"]["medium"]
            
        # Calculate health score
        penalty = (fleet_results["total_critical"] * 15) + (fleet_results["total_high"] * 8) + (fleet_results["total_medium"] * 3)
        fleet_results["fleet_health"] = max(0, 100 - penalty)
        
        return fleet_results

    def analyze_vulnerabilities(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """V10.1: Parse scan results to classify fixable vs unfixable vulnerabilities."""
        analysis = {
            "fixable": [],
            "unfixable": [],
            "summary": {
                "fixable_critical": 0,
                "fixable_high": 0,
                "fixable_medium": 0,
                "unfixable_critical": 0,
                "unfixable_high": 0,
                "unfixable_medium": 0
            }
        }
        
        for vuln in scan_results.get("vulnerabilities", []):
            severity = vuln.get("severity", "UNKNOWN").upper()
            fixed_version = vuln.get("fixed_version", "N/A")
            
            vuln_detail = {
                "package": vuln.get("package", "unknown"),
                "current_version": vuln.get("installed_version", "unknown"),
                "fixed_version": fixed_version,
                "cve_id": vuln.get("id", "N/A"),
                "severity": severity,
                "pkg_type": vuln.get("pkg_type", "unknown"),
                "epss_score": 0.0  # Placeholder for EPSS integration
            }
            
            # Classify as fixable if a fixed version is available
            if fixed_version and fixed_version != "N/A" and fixed_version.strip():
                analysis["fixable"].append(vuln_detail)
                if severity == "CRITICAL":
                    analysis["summary"]["fixable_critical"] += 1
                elif severity == "HIGH":
                    analysis["summary"]["fixable_high"] += 1
                elif severity == "MEDIUM":
                    analysis["summary"]["fixable_medium"] += 1
            else:
                vuln_detail["reason"] = "No patch available"
                analysis["unfixable"].append(vuln_detail)
                if severity == "CRITICAL":
                    analysis["summary"]["unfixable_critical"] += 1
                elif severity == "HIGH":
                    analysis["summary"]["unfixable_high"] += 1
                elif severity == "MEDIUM":
                    analysis["summary"]["unfixable_medium"] += 1
        
        return analysis

    def prioritize_vulnerabilities(self, vuln_analysis: Dict[str, Any], limit: int = 20) -> List[Dict]:
        """V10.1: Sort vulnerabilities by severity and exploitability, return top N."""
        fixable = vuln_analysis["fixable"]
        
        # Severity weights
        severity_weight = {
            "CRITICAL": 1000,
            "HIGH": 100,
            "MEDIUM": 10,
            "LOW": 1
        }
        
        # Calculate priority score: (severity_weight * (epss_score + 0.1))
        for vuln in fixable:
            severity = vuln.get("severity", "LOW")
            epss = vuln.get("epss_score", 0.0)
            vuln["priority_score"] = severity_weight.get(severity, 1) * (epss + 0.1)
        
        # Sort by priority (highest first) and limit
        prioritized = sorted(fixable, key=lambda v: v["priority_score"], reverse=True)
        return prioritized[:limit]

    def generate_sbom(self, image_name: str) -> str:
        """Generate SBOM using Syft."""
        print(f"Council: Generating SBOM for {image_name}...")
        try:
            res = subprocess.run([
                "docker", "run", "--rm", 
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "anchore/syft:latest", image_name, "-o", "json"
            ], capture_output=True)
            return res.stdout.decode()
        except Exception as e:
            return json.dumps({"error": str(e)})

    def generate_and_store_sbom(self, image_name: str, output_dir: str) -> Dict[str, Any]:
        """Generate SBOM and save to disk for tracking."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Sanitize image name for filename
        safe_name = image_name.replace("/", "_").replace(":", "_")
        sbom_path = os.path.join(output_dir, f"{safe_name}_sbom.json")
        
        print(f"Council: Generating and storing SBOM for {image_name}...")
        try:
            res = subprocess.run([
                "docker", "run", "--rm", 
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "anchore/syft:latest", image_name, "-o", "json"
            ], capture_output=True, timeout=120)
            
            if res.returncode == 0:
                sbom_data = json.loads(res.stdout.decode())
                
                # Save to disk
                with open(sbom_path, "w") as f:
                    json.dump(sbom_data, f, indent=2)
                
                # Extract summary
                artifacts = sbom_data.get("artifacts", [])
                return {
                    "path": sbom_path,
                    "total_packages": len(artifacts),
                    "languages": list(set(a.get("language", "unknown") for a in artifacts if a.get("language"))),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {"error": "SBOM generation failed", "stderr": res.stderr.decode()}
        except Exception as e:
            return {"error": str(e)}

    def scan_for_secrets(self, image_name: str) -> Dict[str, Any]:
        """V7.8: Scan image for embedded secrets using Trivy."""
        print(f"Council: Scanning {image_name} for secrets...")
        results = {
            "image": image_name,
            "secrets": [],
            "status": "CLEAN"
        }
        
        try:
            res = subprocess.run([
                "docker", "run", "--rm",
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "aquasec/trivy:latest", "image",
                "--scanners", "secret",
                "--format", "json",
                image_name
            ], capture_output=True, timeout=120)
            
            if res.returncode == 0:
                data = json.loads(res.stdout.decode())
                
                for result in data.get("Results", []):
                    for secret in result.get("Secrets", []):
                        results["secrets"].append({
                            "rule_id": secret.get("RuleID"),
                            "category": secret.get("Category"),
                            "severity": secret.get("Severity"),
                            "title": secret.get("Title"),
                            "match": secret.get("Match", "")[:50] + "..."  # Truncate for safety
                        })
                
                if results["secrets"]:
                    results["status"] = "SECRETS_FOUND"
                    
        except Exception as e:
            results["error"] = str(e)
        
        return results

    def enrich_with_epss(self, cve_id: str) -> float:
        """V7.11: Get EPSS (Exploit Prediction Scoring System) score from FIRST.org."""
        try:
            import requests
            resp = requests.get(
                f"https://api.first.org/data/v1/epss?cve={cve_id}",
                timeout=5
            )
            if resp.ok:
                data = resp.json()
                if data.get("data") and len(data["data"]) > 0:
                    return float(data["data"][0].get("epss", 0.0))
        except Exception as e:
            print(f"Council: EPSS lookup failed for {cve_id}: {e}")
        return 0.0
    
    def filter_high_probability_cves(self, vulnerabilities: list, threshold: float = 0.1) -> list:
        """V7.11: Filter CVEs by exploit probability (EPSS > threshold)."""
        filtered = []
        for vuln in vulnerabilities:
            cve_id = vuln.get("cve_id")
            if cve_id:
                epss_score = self.enrich_with_epss(cve_id)
                if epss_score >= threshold:
                    vuln["epss_score"] = epss_score
                    filtered.append(vuln)
        return filtered

    def get_base_image_recommendations(self, image_name: str) -> Dict[str, Any]:
        """V7.12: Fetch base image recommendations from docker scout."""
        print(f"Council: Getting recommendations for {image_name}...")
        try:
            # Try JSON first as it's more robust
            res = subprocess.run([
                "docker", "scout", "recommendations", "--format", "json", image_name
            ], capture_output=True, timeout=120, text=True)
            
            if "Log in" in res.stderr or "Log in" in res.stdout:
                return {"error": "LOGIN_REQUIRED"}

            if res.returncode == 0:
                try:
                    data = json.loads(res.stdout)
                    # Scout JSON structure for recommendations
                    recs = data.get("recommendations", [])
                    for rec in recs:
                        if rec.get("type") == "BASE_IMAGE_UPDATE" and rec.get("recommended_base"):
                            return {
                                "recommended_base": rec["recommended_base"],
                                "vuln_reduction": rec.get("vulnerabilities_fixed", "?")
                            }
                except:
                    pass # Fallback to text parsing
            
            # Fallback text parsing
            res = subprocess.run([
                "docker", "scout", "recommendations", image_name
            ], capture_output=True, timeout=120, text=True)
            
            output = res.stdout
            if "Next base image" in output:
                import re
                match = re.search(r"Next base image is ([\w\.\-/:]+)", output)
                if match:
                    return {"recommended_base": match.group(1).strip()}
                    
        except Exception as e:
            print(f"Council: Scout recommendations failed: {e}")
            
        return {}
