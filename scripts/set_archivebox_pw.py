from proxion_keyring.identity import load_or_create_identity_key, derive_app_password
import subprocess
import os

key_path = 'c:/Users/hobo/Desktop/Proxion/proxion-keyring/proxion_keyring/identity_private.pem'
key = load_or_create_identity_key(key_path)
pw = derive_app_password(key, 'archivebox')

print(f"Applying ArchiveBox password...")
# Ensure admin exists
subprocess.run(['docker', 'exec', '-i', 'archivebox', 'archivebox', 'manage', 'createsuperuser', '--noinput', '--username', 'admin', '--email', 'admin@proxion.local'], capture_output=True)

# Set password via shell
shell_cmd = f"from django.contrib.auth.models import User; u = User.objects.get(username='admin'); u.set_password('{pw}'); u.save()"
subprocess.run(['docker', 'exec', '-i', 'archivebox', 'archivebox', 'manage', 'shell'], input=shell_cmd, text=True)
print("Done.")
