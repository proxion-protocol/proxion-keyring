import os
import re
import subprocess
import json
from typing import Dict, List, Any, Optional

def get_strategy(language: str, scanner_results: Dict[str, Any] = None):
    """Factory to return the appropriate forge strategy."""
    strategies = {
        "go": GoRustStrategy(),
        "rust": GoRustStrategy(),
        "python": PythonStrategy(),
        "dotnet": DotNetStrategy(),
        "nodejs": NodeStrategy(),
        "php": PHPStrategy()
    }
    strategy = strategies.get(language, BaseStrategy())
    return strategy

class BaseStrategy:
    def apply(self, app_dir: str, scanner_results: Dict[str, Any]) -> bool:
        """Default strategy: No-op or generic OS-level hardening."""
        return True

    def get_docker_instructions(self, scanner_results: Dict[str, Any]) -> List[str]:
        """Return lines to inject into the Dockerfile."""
        # V9.2: Always include OS hardening if OS vulns detected
        return self._get_os_instructions(scanner_results)

    def _get_os_instructions(self, scanner_results: Dict[str, Any], vuln_analysis: Optional[Dict[str, Any]] = None) -> List[str]:
        """V10.2: Targeted OS remediation based on vulnerability analysis."""
        if not scanner_results:
            return []
        
        # If no analysis provided, fall back to blanket upgrade
        if not vuln_analysis:
            pkg_types = set(v.get("pkg_type") for v in scanner_results.get("vulnerabilities", []))
            if "alpine" in pkg_types:
                return [
                    "# Forge V3: OS Remediation (Alpine)",
                    "RUN (command -v apk >/dev/null && apk update && apk upgrade --no-cache) || true"
                ]
            elif "debian" in pkg_types or "ubuntu" in pkg_types:
                return [
                    "# Forge V3: OS Remediation (Debian/Ubuntu)",
                    "RUN (command -v apt-get >/dev/null && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*) || true"
                ]
            return []
        
        # V10.2: Targeted upgrades based on fixable vulnerabilities
        fixable = vuln_analysis.get("fixable", [])
        debian_packages = [v["package"] for v in fixable if v["pkg_type"] in ["debian", "ubuntu"]]
        alpine_packages = [v["package"] for v in fixable if v["pkg_type"] == "alpine"]
        
        instructions = []
        
        if debian_packages:
            pkg_list = " ".join(debian_packages)
            instructions.extend([
                "# Forge V3: Targeted OS Package Upgrades (Debian/Ubuntu)",
                f"RUN (command -v apt-get >/dev/null && apt-get update && apt-get install --only-upgrade {pkg_list} -y && rm -rf /var/lib/apt/lists/*) || true"
            ])
        
        if alpine_packages:
            pkg_list = " ".join(alpine_packages)
            instructions.extend([
                "# Forge V3: Targeted OS Package Upgrades (Alpine)",
                f"RUN (command -v apk >/dev/null && apk add --upgrade {pkg_list}) || true"
            ])
        
        return instructions

class OSPackageStrategy(BaseStrategy):
    """Fallback strategy specifically for OS-only vulnerabilities."""
    pass

class GoRustStrategy(BaseStrategy):
    """Strategy for statically linked binaries: Automatic Upstream Tag Bumping."""
    def apply(self, app_dir: str, scanner_results: Dict[str, Any]) -> bool:
        # Check for OS-level vulns first - if found, we can't just bump tag, we might need OS forge
        # But Go/Rust containers often don't have package managers. 
        # We still try the tag bump as it's the safest Go-way.
        compose_path = os.path.join(app_dir, "docker-compose.yml")
        if not os.path.exists(compose_path):
            return False

        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the image line
        image_match = re.search(r"image:\s*([^\s:]+)(?::([^\s]+))?", content)
        if not image_match:
            return False

        image_base = image_match.group(1)
        current_tag = image_match.group(2) or "latest"

        print(f"Forge: Checking newer tags for {image_base} (current: {current_tag})")
        if current_tag != "latest":
            new_content = content.replace(f"image: {image_base}:{current_tag}", f"image: {image_base}:latest")
            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Forge: Bumped {image_base} to latest")
            return True
        
        return False

class PythonStrategy(BaseStrategy):
    """Strategy for Python: Targeted pip upgrades + OS updates."""
    def get_docker_instructions(self, scanner_results: Dict[str, Any], vuln_analysis: Optional[Dict[str, Any]] = None) -> List[str]:
        """V10.2: Targeted Python package upgrades."""
        instructions = self._get_os_instructions(scanner_results, vuln_analysis)
        
        # If no analysis, fall back to blanket upgrade
        if not vuln_analysis:
            packages = set()
            for vuln in scanner_results.get("vulnerabilities", []):
                if vuln.get("pkg_type") in ["pip", "poetry", "pipenv", "python-pkg"]:
                    pkg = vuln.get("package")
                    if pkg:
                        packages.add(pkg)
            
            if packages:
                pkgs_str = " ".join(packages)
                instructions.extend([
                    "# Forge V3: Python Package Remediation",
                    f"RUN pip install --no-cache-dir --upgrade {pkgs_str} || true",
                    "RUN (pip freeze > /app/requirements.lock 2>/dev/null) || true"
                ])
            return instructions
        
        # V10.2: Targeted upgrades with specific versions
        fixable = [v for v in vuln_analysis.get("fixable", []) if v["pkg_type"] in ["pip", "poetry", "pipenv", "python-pkg"]]
        
        if fixable:
            upgrades = [f"{v['package']}=={v['fixed_version']}" for v in fixable]
            instructions.extend([
                "# Forge V3: Targeted Python Package Upgrades",
                f"RUN pip install --no-cache-dir {' '.join(upgrades)} || true",
                "RUN (pip freeze > /app/requirements.lock 2>/dev/null) || true"
            ])
        
        return instructions

class NodeStrategy(BaseStrategy):
    """Strategy for Node.js: npm audit fix + OS updates."""
    def get_docker_instructions(self, scanner_results: Dict[str, Any], vuln_analysis: Optional[Dict[str, Any]] = None) -> List[str]:
        """V10.2: Targeted Node.js package upgrades."""
        instructions = self._get_os_instructions(scanner_results, vuln_analysis)
        
        # If no analysis, fall back to npm audit fix
        if not vuln_analysis:
            instructions.extend([
                "# Forge V3: Node.js Package Remediation",
                "RUN npm audit fix --force || true",
                "RUN (npm i --package-lock-only 2>/dev/null) || true"
            ])
            return instructions
        
        # V10.2: Targeted upgrades with specific versions
        fixable = [v for v in vuln_analysis.get("fixable", []) if v["pkg_type"] in ["npm", "yarn"]]
        
        if fixable:
            upgrades = [f"{v['package']}@{v['fixed_version']}" for v in fixable]
            instructions.extend([
                "# Forge V3: Targeted npm Package Upgrades",
                f"RUN npm install {' '.join(upgrades)} || true",
                "RUN (npm i --package-lock-only 2>/dev/null) || true"
            ])
        
        return instructions

class DotNetStrategy(BaseStrategy):
    """Strategy for .NET Core: dotnet restore evaluation + OS updates."""
    def get_docker_instructions(self, scanner_results: Dict[str, Any]) -> List[str]:
        instructions = self._get_os_instructions(scanner_results)
        instructions.extend([
            f"# Deep Forge: .NET Remediation",
            f"RUN dotnet restore --force-evaluate || true"
        ])
        return instructions

class PHPStrategy(BaseStrategy):
    """Strategy for PHP: composer update + OS updates."""
    def get_docker_instructions(self, scanner_results: Dict[str, Any]) -> List[str]:
        instructions = self._get_os_instructions(scanner_results)
        instructions.extend([
            f"# Deep Forge: PHP Remediation",
            f"RUN composer update --no-interaction || true"
        ])
        return instructions
