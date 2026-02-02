import os

# Root directory for artifacts
artifacts_dir = r"c:\Users\hobo\Desktop\Proxion" # Actually need the brain dir
brain_dir = r"c:\Users\hobo\.gemini\antigravity\brain\45c90815-d98a-4578-92e5-2a23eefcdddb"

replacements = {
    "Proxion Suite": "Proxion Suite",
    "Proxion Drive": "Proxion Drive",
    "Proxion Intelligence": "Proxion Intelligence",
    "Proxion OS": "Proxion OS",
    "Proxion Fortress": "Proxion Fortress",
    "Proxion Dashboard": "Proxion Dashboard",
    "Proxion Binding": "Proxion Binding",
    "Proxion Social": "Private Social",
    "Proxion Modern Publishing": "Private Publishing",
    "Proxion Web Archive": "Private Web Archive",
    "Proxion Web Monitor": "Private Web Monitor",
    "Proxion DNS Sinkhole": "Private DNS Sinkhole",
    "Proxion": "Private",
    "Proxion App Store": "Proxion App Installation Interface"
}

target_files = [
    "task.md",
    "implementation_plan.md",
    "walkthrough.md",
    "USER_GUIDE.md",
    "VISION.md",
    "federation_design.md"
]

for filename in target_files:
    path = os.path.join(brain_dir, filename)
    if os.path.exists(path):
        print(f"Refining language in {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
