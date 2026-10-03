"""Execute installer orchestration in an isolated fake host, without root/services/network."""
import os
from pathlib import Path
import subprocess
import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['cli', 'api', 'web'])
@pytest.mark.parametrize('existing', [False, True])
def test_profiles_and_safe_updates(tmp_path, mode, existing):
    repo = tmp_path / 'repo'; repo.mkdir()
    host = tmp_path / 'host'; host.mkdir()
    calls = tmp_path / 'calls'
    text = (REPO / 'install.sh').read_text()
    for original in ['/opt/openjk', '/etc/systemd/system', '/usr/local/bin']:
        replacement = host / original.lstrip('/')
        replacement.mkdir(parents=True, exist_ok=True)
        text = text.replace(original, str(replacement))
    text = text.replace('(( EUID == 0 ))', 'true')
    (repo / 'install.sh').write_text(text)
    (repo / 'deploy').mkdir()
    (repo / 'deploy/bootstrap-game.sh').write_text('echo bootstrap >> "$CALLS"\n')
    for service in ['api', 'web']:
        (repo / f'install_{service}.sh').write_text(f'echo {service} >> "$CALLS"\n')
    (repo / 'requirements.lock').write_text('')
    (repo / 'mbiiez.conf.example').write_text('example')
    python = host / 'opt/openjk/venv/bin/python3'
    if existing:
        (repo / 'mbiiez.conf').write_text('original-config')
        (repo / '.install-profile').write_text(mode + '\n')
        python.parent.mkdir(parents=True)
        python.write_text('#!/bin/bash\necho python "$@" >> "$CALLS"\n')
        python.chmod(0o755)
    else:
        # Fresh game bootstrap also prepares Python, just like the real helper.
        (repo / 'deploy/bootstrap-game.sh').write_text(
            f'mkdir -p "{python.parent}"\n'
            f"printf '#!/bin/bash\\necho python \"$@\" >> \"$CALLS\"\\n' > '{python}'\n"
            f'chmod +x "{python}"\necho bootstrap >> "$CALLS"\n')
    result = subprocess.run(['bash', str(repo / 'install.sh'), '--mode', mode],
                            env={**os.environ, 'CALLS': str(calls)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    recorded = calls.read_text().splitlines()
    assert ('bootstrap' in recorded) == (not existing)
    assert ('api' in recorded) == (mode == 'api')
    assert ('web' in recorded) == (mode == 'web')
    assert any('pip install -r' in line for line in recorded)
    assert any('pip check' in line for line in recorded)
    assert (repo / '.install-profile').read_text().strip() == mode
    assert (repo / 'mbiiez.conf').read_text() == ('original-config' if existing else 'example')
    # No args on the next invocation must retain the same profile and skip bootstrap.
    result = subprocess.run(['bash', str(repo / 'install.sh'), '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 0
    assert f'Profile: {mode}; game bootstrap: 0' in result.stdout


def test_legacy_web_detection_and_explicit_update(tmp_path):
    script = (REPO / 'install.sh').read_text()
    system = tmp_path / 'units'; system.mkdir()
    (system / 'mbii-web.service').touch()
    script = script.replace('/etc/systemd/system', str(system))
    (tmp_path / 'install.sh').write_text(script)
    result = subprocess.run(['bash', str(tmp_path / 'install.sh'), '--update', '--dry-run'],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert 'Profile: web; game bootstrap: 0' in result.stdout
