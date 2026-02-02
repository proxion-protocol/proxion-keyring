import os

FORBIDDEN = "Proxion"
REPLACEMENT = "Proxion"

def scrub_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if FORBIDDEN in content:
            print(f"Scrubbing: {filepath}")
            new_content = content.replace(FORBIDDEN, REPLACEMENT)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
    except Exception as e:
        # Skip binary or problematic files
        pass

def main():
    root_dir = r"c:\Users\hobo\Desktop\Proxion"
    for root, dirs, files in os.walk(root_dir):
        # Skip git folders
        if ".git" in root:
            continue
            
        for file in files:
            if file.endswith(('.md', '.py', '.yml', '.yaml', '.txt', '.json', '.bat', '.sh', '.jsx', '.css', '.html')):
                scrub_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
