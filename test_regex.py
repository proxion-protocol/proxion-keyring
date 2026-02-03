import re
import os

full_content = """version: '3'
services:
  calibre-web:
    image: lscr.io/linuxserver/calibre-web:latest
    container_name: calibre-web
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
    volumes:
      - ./config:/config
      - ./books:/books # Local entry point, will be overridden by FUSE
    ports:
      - 8083:8083
    restart: unless-stopped
# Calibre-Web Proxion Binding
services:
  calibre-web:
    volumes:
      - P:/knowledge/calibre/:/books # Proxion Drive P:/knowledge/calibre for e-books
"""

print(f"Content length: {len(full_content)}")

service_blocks = re.split(r"^  (\w+):", full_content, flags=re.MULTILINE)
print(f"Split blocks: {len(service_blocks)}")
for i, b in enumerate(service_blocks):
    print(f"Block {i}: {repr(b[:20])}...")

for i in range(1, len(service_blocks), 2):
    svc_name = service_blocks[i]
    svc_body = service_blocks[i+1]
    print(f"Checking service: {svc_name}")
    
    p_vols = re.findall(r"^[ ]+- (P:/[^ \n]+)", svc_body, re.MULTILINE)
    print(f"  Found P vols: {p_vols}")

# Test direct match on body
test_body = """
    volumes:
      - P:/knowledge/calibre/:/books # Proxion Drive P:/knowledge/calibre for e-books
"""
print("Direct match test:")
print(re.findall(r"^[ ]+- (P:/[^ \n]+)", test_body, re.MULTILINE))
