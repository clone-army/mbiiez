import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile
import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('engine_installer', REPO / 'deploy/install-engines.py')
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)


@pytest.mark.parametrize('value', ['', 'caded,caded', 'unknown', ',caded', 'caded,'])
def test_at_least_one_valid_engine(value):
    with pytest.raises(ValueError): engine.engine_selection(value)
    result = subprocess.run(['bash', str(REPO / 'install.sh'), '--update', '--engines', value, '--dry-run'], capture_output=True)
    assert result.returncode == 2


def test_existing_engines_never_download_or_change(tmp_path, monkeypatch):
    target = tmp_path / 'caded.i386'; target.write_bytes(b'current-engine')
    monkeypatch.setattr(engine, 'caded_download', lambda: pytest.fail('Unexpected download'))
    engine.install(['caded'], REPO, tmp_path)
    assert target.read_bytes() == b'current-engine'


def test_refresh_is_atomic_and_requires_valid_binary(tmp_path, monkeypatch):
    target = tmp_path / 'caded.i386'; target.write_bytes(b'old')
    old = target.open('rb')
    data = bytearray(60); data[:6] = b'\x7fELF\x01\x01'; data[18:20] = b'\x03\x00'
    monkeypatch.setattr(engine, 'caded_download', lambda: bytes(data))
    monkeypatch.setattr(engine.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, 'libraries available', ''))
    engine.install(['caded'], REPO, tmp_path, replace=True)
    assert target.read_bytes() == bytes(data)
    assert old.read() == b'old'  # A running engine's inode is retained.
    old.close()
    monkeypatch.setattr(engine, 'caded_download', lambda: b'not an engine')
    with pytest.raises(ValueError): engine.install(['caded'], REPO, tmp_path, replace=True)
    assert target.read_bytes() == bytes(data)


def test_archive_extracts_only_the_engine_without_writing_paths(tmp_path):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        malicious = tarfile.TarInfo('../../unrelated'); malicious.size = 3
        archive.addfile(malicious, io.BytesIO(b'bad'))
        valid = tarfile.TarInfo('caded.i386'); valid.size = 6
        archive.addfile(valid, io.BytesIO(b'engine'))
    assert engine.binary_from_archive(output.getvalue(), 'caded') == b'engine'
    assert list(tmp_path.iterdir()) == []
