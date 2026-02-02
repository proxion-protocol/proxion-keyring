import os

root_dir = r"c:\Users\hobo\Desktop\Proxion\integrations"
target = 'fuse_script = os.path.abspath(os.path.join(os.getcwd(), "../proxion-fuse/mount.py"))'
replacement = 'fuse_script = os.path.abspath(os.path.join(os.getcwd(), "../../proxion-fuse/mount.py"))'

for root, dirs, files in os.walk(root_dir):
    for name in files:
        if name.startswith("start_") and name.endswith(".py"):
            path = os.path.join(root, name)
            with open(path, "r") as f:
                content = f.read()
            
            if target in content:
                print(f"Updating {path}")
                new_content = content.replace(target, replacement)
                with open(path, "w") as f:
                    f.write(new_content)
            else:
                print(f"Skipping {path} (target not found or already updated)")
