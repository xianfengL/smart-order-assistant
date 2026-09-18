"""Create a private GitHub repository using credentials already stored by Git.

No token is printed, added to a remote URL, written to disk, or included in argv.
Run from the repository root after reviewing and committing the project.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request


def git(*args, capture=True):
    result = subprocess.run(['git', *args], text=True, capture_output=capture, check=True)
    return result.stdout.strip() if capture else ''


env = {**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'}
result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                        text=True, capture_output=True, env=env, timeout=30)
credentials = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or credentials.get('password')
if not token:
    raise SystemExit('No GitHub credential. Complete Git Credential Manager login first.')


def api(path, payload=None):
    request = urllib.request.Request('https://api.github.com' + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json', 'User-Agent': 'OrderlyProjectSetup'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


if git('status', '--porcelain'):
    raise SystemExit('Commit or review all project changes before publishing.')
login = api('/user')['login']
name = 'smart-order-assistant'
try:
    api(f'/repos/{login}/{name}')
except urllib.error.HTTPError as exc:
    if exc.code != 404:
        raise SystemExit(f'GitHub repository check failed: HTTP {exc.code}')
else:
    raise SystemExit(f'Repository {login}/{name} already exists. Refusing to overwrite it; choose a different name.')
try:
    repo = api('/user/repos', {'name': name, 'private': True, 'description': '智能订单 AI 客服助手 · LangGraph / LangChain / FastAPI / Vue / ChromaDB / ECharts MCP', 'auto_init': False})
except urllib.error.HTTPError as exc:
    raise SystemExit(f'GitHub repository creation failed: HTTP {exc.code}')
git('remote', 'add', 'origin', repo['clone_url'])
git('push', '-u', 'origin', 'main', capture=False)
remote = git('ls-remote', 'origin', 'refs/heads/main').split()[0]
commit = git('rev-parse', 'HEAD')
if remote != commit:
    raise SystemExit('Remote commit verification failed')
print(json.dumps({'repository': repo['html_url'], 'visibility': 'private', 'commit': commit}, ensure_ascii=False))
