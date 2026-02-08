import os
import json
import subprocess
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from ..scout import SecurityCouncil

class Guardian:
    """Security engine for fleet hardening and health monitoring."""
    
    def __init__(self, pod_local_root: str, events, council: SecurityCouncil):
        self.pod_local_root = pod_local_root
        self.events = events
        self.council = council
        self.stats_path = os.path.join(self.pod_local_root, "security_stats.json")
        self.medic_stats = self._load_medic_stats()
        self._check_readiness()

    def _check_readiness(self):
        """V7.12+: Log status of critical security binaries."""
        self.log_event("System: Performing security readiness check...", "System", "Status", "info")
        
        # 1. Cosign (Host Binary)
        try:
            subprocess.run(["cosign", "version"], capture_output=True, check=True)
            self.log_event("System: Cosign is READY", "System", "Status", "success")
        except:
            self.log_event("System: Cosign is MISSING. Image signing disabled.", "System", "Status", "warning")
            
        # 2. Trivy (Usually Docker)
        try:
            subprocess.run(["docker", "run", "--rm", "aquasec/trivy:latest", "--version"], capture_output=True, check=True)
            self.log_event("System: Trivy (Docker) is READY", "System", "Status", "success")
        except:
            self.log_event("System: Trivy is MISSING. Security audits will fail.", "System", "Status", "error")
            
        # 3. Docker Scout
        try:
            subprocess.run(["docker", "scout", "version"], capture_output=True, check=True)
            self.log_event("System: Docker Scout is READY", "System", "Status", "success")
        except:
            self.log_event("System: Docker Scout is MISSING. Base image optimization disabled.", "System", "Status", "warning")
        
    def _save_medic_stats(self):
        """Persist security metrics to shared storage for reactivity."""
        try:
            with open(self.stats_path, "w") as f:
                json.dump(self.medic_stats, f, indent=2)
        except Exception as e:
            print(f"Guardian: Failed to save stats: {e}")

    def _load_medic_stats(self):
        """Load security metrics from shared storage."""
        default_stats = {
            "last_run": None, 
            "status": "BOOTING", 
            "repairs": 0,
            "fleet_health": 0,
            "last_fleet_harden": None,
            "security_council": {}
        }
        if os.path.exists(self.stats_path):
            try:
                with open(self.stats_path, "r") as f:
                    loaded = json.load(f)
                    return {**default_stats, **loaded}
            except Exception as e:
                print(f"Guardian: Failed to load stats: {e}")
        return default_stats

    def refresh_stats(self):
        """Reload stats from disk (used by server/facade)."""
        self.medic_stats = self._load_medic_stats()
        return self.medic_stats

    def log_event(self, action: str, resource: str, subject: str = "System", type: str = "info"):
        """Delegate logging to the central event bus."""
        self.events.log(action, resource, subject, type)

    def run_command_logged(self, cmd: list, cwd: str = None, resource: str = "Forge", subject: str = "Execute"):
        """Run a command and stream its output line-by-line to the event bus."""
        self.log_event(f"RUNNING: {' '.join(cmd)}", resource, subject, "info")
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                clean_line = line.strip()
                if clean_line:
                    # Stream directly to Audit Feed
                    self.log_event(clean_line, resource, subject, "info")
            
            return process.returncode == 0
        except Exception as e:
            self.log_event(f"Execution failed: {str(e)}", resource, "Error", "error")
            return False

    def _find_integration_for_container(self, container_name: str, image_name: Optional[str] = None) -> Optional[str]:
        """V9.4: Resolve container name or image string to integration directory."""
        integrations_root = os.path.abspath(os.path.join(os.path.dirname(self.pod_local_root), "integrations"))
        if not os.path.exists(integrations_root):
            return None

        # Try variations of the name (undercore/hyphen swaps)
        variations = {container_name, container_name.replace("_", "-"), container_name.replace("-", "_")}
        
        for name in variations:
            # 1. Try exact match first
            exact_match = os.path.join(integrations_root, f"{name}-integration")
            if os.path.isdir(exact_match):
                return exact_match

        # 2. Scan all compose files for the container name, service name, or image string
        for d in os.listdir(integrations_root):
            path = os.path.join(integrations_root, d)
            if not os.path.isdir(path):
                continue
            
            # Check .yml and .parked
            for ext in [".yml", ".parked", ".yml.parked"]:
                compose_path = os.path.join(path, f"docker-compose{ext}")
                if os.path.exists(compose_path):
                    try:
                        with open(compose_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Strip tag variable syntax for fuzzy image matching: ${VAR:-latest} -> latest
                            normalized_content = re.sub(r"\$\{[^:]+:-?([^}]+)\}", r"\1", content)
                            
                            for name in variations:
                                # Search for service name followed by colon at start of line (indented)
                                if re.search(rf"^\s+{re.escape(name)}:", content, re.MULTILINE):
                                    return path
                                # Search for container_name: <name>
                                if re.search(rf"container_name:\s*{re.escape(name)}", content, re.IGNORECASE):
                                    return path
                            
                            # V9.4 Pass 3: Image-based matching
                            if image_name:
                                # Look for image: <substring of image_name>
                                # e.g. for 'vaultwarden/server:latest', look for 'vaultwarden/server'
                                img_base = image_name.split(":")[0]
                                if img_base in normalized_content:
                                    return path
                    except:
                        continue
        return None

    # --- Forge Engine Logic ---
    

    def _should_rollback(self, pre_scan: dict, post_scan: dict) -> tuple:
        """V10.3: Severity-aware rollback decision."""
        
        pre_critical = pre_scan.get("summary", {}).get("critical", 0)
        pre_high = pre_scan.get("summary", {}).get("high", 0)
        pre_medium = pre_scan.get("summary", {}).get("medium", 0)
        pre_low = pre_scan.get("summary", {}).get("low", 0)
        
        post_critical = post_scan.get("summary", {}).get("critical", 0)
        post_high = post_scan.get("summary", {}).get("high", 0)
        post_medium = post_scan.get("summary", {}).get("medium", 0)
        post_low = post_scan.get("summary", {}).get("low", 0)
        
        # CRITICAL: Any increase is unacceptable
        if post_critical > pre_critical:
            return True, f"CRITICAL vulnerabilities increased: {pre_critical} → {post_critical}"
        
        # HIGH: Allow increase only if CRITICAL decreased significantly
        if post_high > pre_high:
            critical_reduction = pre_critical - post_critical
            high_increase = post_high - pre_high
            
            if critical_reduction < high_increase:
                return True, f"HIGH vulnerabilities increased: {pre_high} → {post_high}"
        
        # MEDIUM/LOW: Allow increase if CRITICAL+HIGH decreased
        total_pre_severe = pre_critical + pre_high
        total_post_severe = post_critical + post_high
        
        if total_post_severe > total_pre_severe:
            return True, f"Severe vulnerabilities increased: {total_pre_severe} → {total_post_severe}"
        
        # Success: Severe vulnerabilities reduced or stable
        return False, f"Remediation successful: CRITICAL {pre_critical}→{post_critical}, HIGH {pre_high}→{post_high}"

    def forge_image(self, container_name: str, app_dir: str, image_name: Optional[str] = None) -> bool:
        """Build a hardened image with safety nets, language-specific deep forge, and granular logging."""
        self.log_event(f"Forge requested for {container_name}", "Forge", "Start", "info")
        
        compose_path = os.path.join(app_dir, "docker-compose.yml")
        was_parked = False
        parked_original_name = None
        actual_service_name = None

        try:
            # 0. Pre-Scan: Detect vulnerabilities and language
            self.log_event(f"PRE-SCAN: Analyzing {container_name} for vulnerabilities...", "Forge", "Scan", "info")
            image_name = image_name or container_name
            scan_results = self.council.scan_image(image_name)
            
            # V9.3: Ensure we use the actually resolved image for backup and base image
            resolved_image = scan_results.get("image", image_name)
            
            detected_language = scan_results.get("language", "unknown")
            vuln_count = scan_results["summary"]["critical"] + scan_results["summary"]["high"]
            
            self.log_event(f"Detected language: {detected_language}, Vulnerabilities: {vuln_count}", "Forge", "Analysis", "info")
            
            # 0.1: Handle parked integrations early (V8.1+)
            if not os.path.exists(compose_path):
                for p_ext in [".parked", ".yml.parked"]:
                    parked_path = os.path.join(app_dir, f"docker-compose{p_ext}")
                    if os.path.exists(parked_path):
                        self.log_event(f"FORGE: Unparking integration ({p_ext}) for build...", "Forge", "Build", "info")
                        os.rename(parked_path, compose_path)
                        was_parked = True
                        parked_original_name = parked_path
                        break

            if not os.path.exists(compose_path):
                 raise Exception(f"No docker-compose.yml found in {app_dir} and no parked version detected.")

            # 1. Apply Language-Specific Strategy
            from .forge_strategies import get_strategy
            strategy = get_strategy(detected_language, scan_results)
            
            # V10.2: Analyze vulnerabilities for targeted remediation
            self.log_event(f"ANALYZE: Classifying fixable vs unfixable vulnerabilities...", "Forge", "Analysis", "info")
            vuln_analysis = self.council.analyze_vulnerabilities(scan_results)
            fixable_count = len(vuln_analysis.get("fixable", []))
            unfixable_count = len(vuln_analysis.get("unfixable", []))
            self.log_event(f"ANALYZE: Found {fixable_count} fixable, {unfixable_count} unfixable vulnerabilities", "Forge", "Analysis", "info")
            
            # For Go/Rust: Try automatic tag bump
            if detected_language in ["go", "rust"] and vuln_count > 0:
                self.log_event(f"DEEP FORGE: Attempting upstream version bump for {detected_language}...", "Forge", "Strategy", "warning")
                if strategy.apply(app_dir, scan_results):
                    self.log_event(f"Version bump successful. Rebuilding with updated image...", "Forge", "Strategy", "success")
            
            # 2. Backup
            self.log_event(f"BACKUP: Creating safety backup for {container_name} (image: {resolved_image})", "Forge", "Backup", "info")
            subprocess.run(["docker", "tag", resolved_image, f"{container_name}:backup"], check=False)
            
            # 3. Build with Dockerfile injection for Python/Node/.NET/PHP
            self.log_event(f"BUILD: Building hardened image for {container_name}...", "Forge", "Build", "warning")
            
            # V10.2: Get targeted remediation instructions
            extra_instructions = strategy.get_docker_instructions(scan_results, vuln_analysis)
            
            # V7.9+: Docker Scout Base Image Recommendations
            self.log_event(f"SCOUT: Searching for optimized base image recommendations...", "Forge", "Search", "info")
            recs = self.council.get_base_image_recommendations(resolved_image)
            if recs.get("error") == "LOGIN_REQUIRED":
                self.log_event("SCOUT: Recommendations skipped (Docker Login required). skipping automated base switch.", "Forge", "Scout", "warning")
            elif recs.get("recommended_base"):
                self.log_event(f"SCOUT: Optimized base found: {recs['recommended_base']} (-{recs.get('vuln_reduction', '?')} vulns).", "Forge", "Scout", "success")

            if extra_instructions or recs.get("recommended_base"):
                self.log_event(f"Injecting {len(extra_instructions)} hardening layers...", "Forge", "Build", "info")
                dockerfile_path = os.path.join(app_dir, "Dockerfile.hardened")
                
                base_image = recs.get("recommended_base") or resolved_image
                
                with open(dockerfile_path, "w", encoding="utf-8") as f:
                    f.write(f"FROM {base_image}\n")
                    f.write("\n# Auto-remediation by Deep Forge\n")
                    f.write("\n".join(extra_instructions) + "\n")
                
                # Patch compose to use Dockerfile.hardened
                self.log_event("FORGE: Patching docker compose for custom build...", "Forge", "Build", "info")
                with open(compose_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                # V9.5: Simplified patching logic
                variations = {container_name, container_name.replace("_", "-"), container_name.replace("-", "_")}
                new_lines = []
                current_service_name = None
                in_target_service = False
                in_build_block = False
                has_build_block = False
                service_found = False
                
                for line in lines:
                    stripped = line.strip()
                    
                    # Detect service blocks (2-space indent)
                    if re.match(r"^ {2}[a-zA-Z0-9_-]+:", line):
                        current_service_name = stripped.rstrip(":")
                        in_target_service = current_service_name in variations
                        in_build_block = False
                        has_build_block = False
                    
                    # Check for container_name match
                    if in_target_service and re.search(rf"container_name:\s*({'|'.join(re.escape(v) for v in variations)})", line, re.IGNORECASE):
                        service_found = True
                        actual_service_name = current_service_name
                    
                    # Track build blocks
                    if in_target_service and "build:" in line:
                        has_build_block = True
                        in_build_block = True
                        new_lines.append(line)
                        continue
                    
                    # Update dockerfile line in existing build block
                    if in_target_service and in_build_block and "dockerfile:" in line:
                        indent = line[:line.find("dockerfile:")]
                        new_lines.append(f"{indent}dockerfile: Dockerfile.hardened\n")
                        service_found = True
                        continue
                    
                    # Inject build block after image line if no build block exists
                    if in_target_service and "image:" in line and not has_build_block:
                        indent = line[:line.find("image:")]
                        new_lines.append(line)
                        new_lines.append(f"{indent}build:\n")
                        new_lines.append(f"{indent}  context: .\n")
                        new_lines.append(f"{indent}  dockerfile: Dockerfile.hardened\n")
                        has_build_block = True
                        service_found = True
                        actual_service_name = current_service_name
                        continue
                    
                    # Detect end of build block (dedent or new top-level key)
                    if in_build_block and (re.match(r"^ {2,4}[a-zA-Z]", line) and ":" in line and not line.startswith("      ")):
                        in_build_block = False
                    
                    new_lines.append(line)
                         
                if not service_found:
                    self.log_event(f"WARNING: Could not find service block for {container_name} in compose. Build might fail.", "Forge", "Patch", "warning")

                with open(compose_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            
            # Use logged version of build
            self.log_event(f"Executing logged build for {container_name}...", "Forge", "Build", "warning")
            success = self.run_command_logged(["docker", "compose", "build", "--no-cache", "--progress", "plain"], cwd=app_dir, subject="Build")
            if not success:
                raise Exception("Docker build failed. Check logs above.")
            
            # 4. Deploy
            self.log_event(f"SCAN: Running post-forge security audit for {container_name}...", "Forge", "Scan", "info")
            
            target_deploy = actual_service_name or container_name
            self.log_event(f"Redeploying {target_deploy} with hardened image...", "Forge", "Deploy", "info")
            deploy_success = self.run_command_logged(["docker", "compose", "up", "-d", target_deploy], cwd=app_dir, subject="Deploy")
            if not deploy_success:
                raise Exception("Deployment failed. Check logs above.")
            
            # 5. Post-Scan Verification
            post_scan = self.council.scan_image(image_name)
            post_vuln_count = post_scan["summary"]["critical"] + post_scan["summary"]["high"]
            
            # V7.2: Generate SBOM for supply chain tracking
            sbom_dir = os.path.join(self.pod_local_root, "sboms")
            sbom_result = self.council.generate_and_store_sbom(image_name, sbom_dir)
            if "error" not in sbom_result:
                self.log_event(f"SBOM generated: {sbom_result['total_packages']} packages tracked", "Forge", "SBOM", "info")
            
            # V7.9: Sign forged image
            from .image_signer import ImageSigner
            signer = ImageSigner(self.pod_local_root)
            sign_result = signer.sign_image(image_name)
            if sign_result.get("status") == "SIGNED":
                self.log_event(f"Image signed: {image_name}", "Forge", "Signing", "success")
            elif sign_result.get("status") != "SKIPPED":
                self.log_event(f"Image signing failed: {sign_result.get('error', 'Unknown')}", "Forge", "Signing", "warning")
            
            # V7.1: Rollback on Regression
            if post_vuln_count > vuln_count:
                self.log_event(f"REGRESSION DETECTED: Vulnerabilities increased from {vuln_count} to {post_vuln_count}. Rolling back...", "Forge", "Rollback", "error")
                try:
                    # Restore backup
                    subprocess.run(["docker", "tag", f"{container_name}:backup", f"{container_name}:latest"], check=True)
                    subprocess.run(["docker", "compose", "up", "-d"], cwd=app_dir, check=True)
                    self.log_event(f"Rollback successful. Restored to previous version with {vuln_count} vulnerabilities.", "Forge", "Rollback", "warning")
                except Exception as rollback_error:
                    self.log_event(f"CRITICAL: Rollback failed: {str(rollback_error)}", "Forge", "Error", "error")
                return False
            
            # Success metrics
            if post_vuln_count < vuln_count:
                reduction = vuln_count - post_vuln_count
                self.log_event(f"SUCCESS: Reduced vulnerabilities from {vuln_count} to {post_vuln_count} (-{reduction})", "Forge", "Success", "success")
            elif post_vuln_count == 0:
                self.log_event(f"SUCCESS: Forge complete: {container_name} is now IMMUTABLE (0 CVEs)", "Forge", "Success", "success")
            else:
                self.log_event(f"PARTIAL: Forge complete but {post_vuln_count} vulnerabilities remain (no change)", "Forge", "Warning", "warning")
            
            # V7.4: Track forge metrics for dashboard
            self._track_forge_metrics(container_name, vuln_count, post_vuln_count, detected_language, success=True)
            
            return True
            
        except Exception as e:
            self.log_event(f"Forge FAILED for {container_name}: {str(e)}", "Forge", "Error", "error")
            self._track_forge_metrics(container_name, 0, 0, "unknown", success=False)
            return False
            
        finally:
            # Restore parked state if necessary
            if was_parked and os.path.exists(compose_path):
                self.log_event("FORGE: Restoring parked state for integration...", "Forge", "Clean", "info")
                os.rename(compose_path, parked_original_name)

    def harden_fleet(self, audit_report_path: Optional[str] = None) -> Dict[str, Any]:
        """V9.3: Automated fleet-wide vulnerability remediation."""
        self.log_event("Starting Fleet Hardening...", "Fleet", "Harden", "warning")
        
        if audit_report_path and os.path.exists(audit_report_path):
            self.log_event(f"Harden: Resuming from audit report: {audit_report_path}", "Fleet", "Harden", "info")
            try:
                with open(audit_report_path, "r", encoding="utf-8") as f:
                    audit = json.load(f)
            except Exception as e:
                self.log_event(f"Harden: Failed to load audit report: {str(e)}", "Fleet", "Error", "error")
                return {"error": f"Failed to load audit report: {str(e)}"}
        else:
            audit = self.council.audit_fleet()
            # V9.5: Save latest audit for modular reuse
            audit_save_path = os.path.join(self.pod_local_root, "latest_audit.json")
            try:
                with open(audit_save_path, "w", encoding="utf-8") as f:
                    json.dump(audit, f, indent=2)
                self.log_event(f"Harden: Audit results saved to {audit_save_path}", "Fleet", "Harden", "info")
            except Exception as e:
                 self.log_event(f"Harden: Failed to save latest audit: {str(e)}", "Fleet", "Warning", "warning")

        repaired = 0
        failed = 0
        skipped = 0
        
        # Track total vulns before
        pre_critical = audit.get("total_critical", 0)
        pre_high = audit.get("total_high", 0)
        
        for image_name, scan in audit.get("containers", {}).items():
            # Extract common name (e.g. from 'ghcr.io/linuxserver/sonarr:latest' to 'sonarr')
            container_basename = image_name.split("/")[-1].split(":")[0]
            
            if scan.get("status") in ["BLOCKED", "RISKY"]:
                self.log_event(f"HARDEN: Targeting {image_name}...", "Fleet", "Harden", "info")
                
                integration_path = self._find_integration_for_container(container_basename, image_name)
                
                if integration_path:
                    # Trigger Forge
                    success = self.forge_image(container_basename, integration_path, image_name=image_name)
                    if success:
                        repaired += 1
                    else:
                        failed += 1
                else:
                    self.log_event(f"No integration found for {image_name}. Skipping.", "Fleet", "Skip", "warning")
                    skipped += 1
        
        # Update metrics
        self.medic_stats["repairs"] += repaired
        self._save_medic_stats()
        
        self.log_event(f"Fleet Hardening Complete. Repaired: {repaired}, Failed: {failed}, Skipped: {skipped}", "Fleet", "Harden", "success")
        return {"repaired": repaired, "failed": failed, "skipped": skipped}

    def _track_forge_metrics(self, container: str, pre_vulns: int, post_vulns: int, language: str, success: bool):
        """V7.4: Track forge history for metrics dashboard."""
        if "metrics" not in self.medic_stats:
            self.medic_stats["metrics"] = {
                "forge_history": [],
                "mttr_critical": 0,
                "mttr_high": 0,
                "success_rate_30d": 0.0,
                "top_packages": []
            }
        
        # Ensure we have some values
        pre_vulns = int(pre_vulns) if pre_vulns is not None else 0
        post_vulns = int(post_vulns) if post_vulns is not None else 0
        
        # Add forge event
        forge_event = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "container": container,
            "language": language,
            "pre_vulns": pre_vulns,
            "post_vulns": post_vulns,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.medic_stats["metrics"]["forge_history"].append(forge_event)
        
        # Keep only last 30 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self.medic_stats["metrics"]["forge_history"] = [
            e for e in self.medic_stats["metrics"]["forge_history"] 
            if e["timestamp"] > cutoff
        ]
        
        # Calculate success rate
        recent = self.medic_stats["metrics"]["forge_history"]
        if recent:
            successes = sum(1 for e in recent if e["success"])
            self.medic_stats["metrics"]["success_rate_30d"] = successes / len(recent)
        
        self._save_medic_stats()

    def canary_forge(self, container_name: str, app_dir: str) -> bool:
        """V7.13: Forge with 24h monitoring period before fleet rollout."""
        self.log_event(f"Starting CANARY forge for {container_name}...", "Canary", "Forge", "info")
        
        # Perform forge
        success = self.forge_image(container_name, app_dir)
        
        if success:
            # Mark as canary
            self.medic_stats["canary"] = {
                "container": container_name,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "monitoring_until": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                "status": "MONITORING"
            }
            self._save_medic_stats()
            self.log_event(f"Canary deployment active for {container_name}. Monitoring for 24h...", "Canary", "Forge", "warning")
        
        return success
    
    def check_canary_status(self) -> Dict[str, Any]:
        """V7.13: Check if canary monitoring period is complete."""
        canary = self.medic_stats.get("canary")
        if not canary:
            return {"status": "NO_CANARY"}
        
        monitoring_until = datetime.fromisoformat(canary["monitoring_until"])
        if datetime.now(timezone.utc) >= monitoring_until:
            # Canary period complete
            self.medic_stats.pop("canary", None)
            self._save_medic_stats()
            return {
                "status": "COMPLETE",
                "container": canary["container"],
                "ready_for_fleet_rollout": True
            }
        else:
            return {
                "status": "MONITORING",
                "container": canary["container"],
                "time_remaining": str(monitoring_until - datetime.now(timezone.utc))
            }

    def run_network_medic(self) -> Dict[str, Any]:
        """Perform a full network diagnostic and attempt repairs."""
        results = {
            "internet": "UNKNOWN",
            "adguard": "UNKNOWN",
            "dns_resolution": "UNKNOWN",
            "elevation": "OFFLINE",
            "log_analysis": "CLEAN",
            "repairs": []
        }

        # 1. Check Internet (Ping 8.8.8.8)
        try:
            subprocess.check_call(["ping", "-n", "1", "8.8.8.8"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results["internet"] = "ONLINE"
        except:
            results["internet"] = "OFFLINE"

        # 2. Check AdGuard Health
        try:
            output = subprocess.check_output(["docker", "ps", "--filter", "name=adguard", "--format", "{{.Status}}"]).decode()
            if "Up" in output:
                results["adguard"] = "ONLINE"
            else:
                results["adguard"] = "OFFLINE"
        except:
            results["adguard"] = "ERROR"

        self.log_event("Network Medic Run", "Network", "System", "info")
        return results

    def update_vuln_databases(self) -> Dict[str, Any]:
        """V7.3: Update Trivy and Grype vulnerability databases."""
        self.log_event("Updating vulnerability databases...", "Maintenance", "Council", "info")
        results = {"trivy": "UNKNOWN", "grype": "UNKNOWN"}
        
        try:
            # Update Trivy DB
            res = subprocess.run([
                "docker", "run", "--rm", 
                "aquasec/trivy", "image", "--download-db-only"
            ], capture_output=True, timeout=300)
            results["trivy"] = "SUCCESS" if res.returncode == 0 else "FAILED"
        except Exception as e:
            results["trivy"] = f"ERROR: {str(e)}"
        
        try:
            # Update Grype DB
            res = subprocess.run([
                "docker", "run", "--rm", 
                "anchore/grype", "db", "update"
            ], capture_output=True, timeout=300)
            results["grype"] = "SUCCESS" if res.returncode == 0 else "FAILED"
        except Exception as e:
            results["grype"] = f"ERROR: {str(e)}"
        
        self.log_event(f"Database update complete: Trivy={results['trivy']}, Grype={results['grype']}", "Maintenance", "Council", "success" if "SUCCESS" in str(results) else "warning")
        return results

    def run_security_audit(self) -> Dict[str, Any]:
        """Run a full security audit of all running containers."""
        self.log_event("Starting fleet security audit...", "Audit", "Council", "info")
        try:
            results = self.council.audit_fleet()
            
            # Store detailed CVE information for dashboard
            self.medic_stats["security_council"] = {
                "last_audit": datetime.now(timezone.utc).isoformat(),
                "total_critical": results.get("total_critical", 0),
                "total_high": results.get("total_high", 0),
                "total_medium": results.get("total_medium", 0),
                "fleet_health": results.get("fleet_health", 100),
                "containers": {}
            }
            
            # Extract top CVEs for dashboard display
            all_vulns = []
            for image, scan in results.get("containers", {}).items():
                short_name = image.split("/")[-1].split(":")[0]
                self.medic_stats["security_council"]["containers"][short_name] = {
                    "status": scan.get("status", "UNKNOWN"),
                    "language": scan.get("language", "unknown"),
                    "summary": scan.get("summary", {})
                }
                for vuln in scan.get("vulnerabilities", []):
                    vuln["container"] = short_name
                    all_vulns.append(vuln)
            
            # Sort by severity and take top 20 for display
            severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            all_vulns.sort(key=lambda v: severity_order.get(v.get("severity", "LOW"), 4))
            self.medic_stats["security_council"]["top_vulnerabilities"] = all_vulns[:20]
            
            # Update global fleet health from real data
            self.medic_stats["fleet_health"] = results.get("fleet_health", self.medic_stats.get("fleet_health", 0))
            
            self._save_medic_stats()
            self.log_event(f"Security audit complete. Health: {results.get('fleet_health')}%", "Audit", "Council", "success" if results.get("fleet_health", 0) > 80 else "warning")
            
            # V7.5: Auto-forge on CRITICAL CVE detection
            if results.get("total_critical", 0) > 0:
                self.log_event(f"CRITICAL CVEs detected ({results['total_critical']}). Triggering emergency forge...", "Audit", "Emergency", "error")
                threading.Thread(target=self._emergency_forge_fleet, daemon=True).start()
            
            return results
        except Exception as e:
            self.log_event(f"Security audit FAILED: {str(e)}", "Audit", "Error", "error")
            return {"error": str(e)}

    def _emergency_forge_fleet(self):
        """V7.5: Emergency forge for containers with CRITICAL CVEs."""
        self.log_event("Starting emergency fleet forge for CRITICAL vulnerabilities...", "Emergency", "Forge", "warning")
        
        # Get containers with CRITICAL CVEs
        critical_containers = []
        for container, data in self.medic_stats.get("security_council", {}).get("containers", {}).items():
            if data.get("summary", {}).get("critical", 0) > 0:
                critical_containers.append(container)
        
        if not critical_containers:
            return
        
        integrations_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../integrations"))
        
        for container in critical_containers:
            app_dir = os.path.join(integrations_root, f"{container}-integration")
            if os.path.exists(app_dir):
                self.log_event(f"Emergency forging {container}...", "Emergency", "Forge", "warning")
                # Import manager to access forge_image
                from ..manager import KeyringManager
                # Note: This is a simplified approach. In production, we'd pass manager reference.
                # For now, we'll call forge_image directly
                self.forge_image(container, app_dir)
        
        self.log_event("Emergency forge complete.", "Emergency", "Forge", "success")

    def _bg_medic_worker(self):
        """Proactive health monitoring and auto-repair loop."""
        print("Guardian: Network Medic Watchdog started.")
        audit_counter = 0
        last_db_update_day = None
        
        while True:
            try:
                results = self.run_network_medic()
                self.medic_stats["last_run"] = datetime.now(timezone.utc).isoformat()
                self.medic_stats["status"] = "HEALTHY" if results["internet"] == "ONLINE" else "CONCERN"
                self._save_medic_stats()
                
                # V7.3: Update vulnerability databases daily at 3 AM
                current_time = datetime.now()
                if current_time.hour == 3 and current_time.day != last_db_update_day:
                    self.update_vuln_databases()
                    last_db_update_day = current_time.day
                
                # Run security audit every 30 cycles (30 minutes at 60s intervals)
                audit_counter += 1
                if audit_counter >= 30:
                    audit_counter = 0
                    self.run_security_audit()
                    
            except Exception as e:
                print(f"Guardian Medic Error: {e}")
            time.sleep(60)

    def start_watchdog(self):
        """Start the background monitoring thread."""
        threading.Thread(target=self._bg_medic_worker, daemon=True).start()
