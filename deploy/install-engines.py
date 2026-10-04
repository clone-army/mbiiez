#!/usr/bin/env python3
"""Install missing selected engines only; existing/running binaries are never replaced."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import requests

ENGINES = ('openjkded', 'mbiided', 'caded')
RELEASES = 'https://api.github.com/repos/clone-army/OpenJK/releases/latest'


def engine_selection(value):
    names = value.split(',')
    if not names or len(names) != len(set(names)) or any(name not in ENGINES for name in names):
        raise ValueError('Select at least one engine: openjkded,mbiided,caded')
    return names


def download(url, headers=None):
    response = requests.get(url, headers=headers, timeout=(5, 120), stream=True)
    response.raise_for_status()
    data = bytearray()
    for chunk in response.iter_content(65536):
        data.extend(chunk)
        if len(data) > 64 * 1024 * 1024:
            raise ValueError('Engine download exceeds size limit')
    return bytes(data)


def binary_from_archive(data, engine):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        matches = [member for member in archive.getmembers()
                   if Path(member.name).name == engine + '.i386' and member.isfile()]
        if len(matches) != 1 or matches[0].size > 32 * 1024 * 1024:
            raise ValueError('Engine archive does not contain one valid binary')
        return archive.extractfile(matches[0]).read()


def caded_download():
    headers = {'Accept': 'application/vnd.github+json'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    response = requests.get(RELEASES, headers=headers, timeout=(5, 25))
    response.raise_for_status()
    release = response.json()
    assets = {asset['name']: asset['browser_download_url'] for asset in release['assets']}
    archive = download(assets['caded-linux-i386.tar.gz'])
    manifest = download(assets['SHA256SUMS']).decode('ascii')
    matches = re.findall(r'^([0-9a-f]{64})\s+\*?caded-linux-i386\.tar\.gz$', manifest, re.M)
    if len(matches) != 1 or hashlib.sha256(archive).hexdigest() != matches[0]:
        raise ValueError('CADED release checksum verification failed')
    print('Verified CADED release:', release['tag_name'])
    return binary_from_archive(archive, 'caded')


def verify_binary(data):
    # ELF32, little endian, EM_386; do not execute an unchecked download.
    if len(data) < 52 or data[:6] != b'\x7fELF\x01\x01' or data[18:20] != b'\x03\x00':
        raise ValueError('Expected a Linux i386 ELF binary')


def install(names, repo, destination, replace=False):
    destination.mkdir(parents=True, exist_ok=True)
    for engine in names:
        target = destination / (engine + '.i386')
        if (target.exists() or target.is_symlink()) and not replace:
            print('Keeping existing engine:', target)
            continue
        if engine == 'mbiided':
            data = (repo / 'mbiided.i386').read_bytes()
        elif engine == 'caded':
            data = caded_download()
        else:
            data = binary_from_archive(download('https://builds.openjk.org/openjk-2018-02-26-e3f22070-linux.tar.gz'), 'openjkded')
        verify_binary(data)
        fd, temporary = tempfile.mkstemp(prefix='.mbiiez-engine-', dir=destination)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, 0o755)
            libraries = subprocess.run(['ldd', temporary], capture_output=True, text=True, timeout=10)
            if libraries.returncode or 'not found' in libraries.stdout:
                raise ValueError('Engine runtime libraries are missing: ' + libraries.stdout.strip())
            # Hard-link creates only an absent destination; never overwrite a concurrent installer.
            if replace:
                os.replace(temporary, target)
            else:
                os.link(temporary, target)
            print('Installed engine:', target)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--engines', required=True)
    parser.add_argument('--replace', action='store_true', help='Atomically stage selected engine updates; running processes retain their binary')
    args = parser.parse_args()
    try:
        install(engine_selection(args.engines), Path(__file__).resolve().parents[1], Path('/usr/bin'), replace=args.replace)
    except (ValueError, OSError, requests.RequestException, KeyError, tarfile.TarError) as error:
        parser.exit(1, 'Engine installation failed: ' + str(error) + '\n')
