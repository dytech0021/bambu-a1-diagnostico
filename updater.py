"""Auto-atualizacao do executavel a partir das releases do GitHub.

Ao abrir o .exe, compara a versao local com a ultima release publicada e, se
houver uma mais nova, baixa o novo .exe e se substitui automaticamente (sem
precisar entrar no site). So funciona quando rodando empacotado (PyInstaller).

Nunca bloqueia o uso: qualquer erro (sem internet, etc.) e' ignorado e o
programa segue normalmente.
"""
import json
import os
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

REPO = "dytech0021/bambu-a1-diagnostico"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "bambu-a1-diagnostico.exe"
_HEADERS = {"User-Agent": "bambu-diag-updater", "Accept": "application/vnd.github+json"}


def _ver(v):
    """Converte 'v0.2.0' em (0, 2, 0) para comparar versoes."""
    nums = []
    for parte in str(v).lstrip("vV").split("."):
        try:
            nums.append(int(parte))
        except ValueError:
            nums.append(0)
    return tuple(nums)


def _latest_release():
    req = Request(API_LATEST, headers=_HEADERS)
    with urlopen(req, timeout=8) as r:
        data = json.load(r)
    tag = data.get("tag_name", "")
    url = None
    for asset in data.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            url = asset.get("browser_download_url")
            break
    return tag, url


def _download(url, dest):
    req = Request(url, headers={"User-Agent": "bambu-diag-updater"})
    with urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _swap_and_restart(new_exe, current_exe):
    """Cria um .bat que espera este processo fechar, troca o .exe e reabre."""
    bat = current_exe + ".update.bat"
    script = (
        "@echo off\r\n"
        "ping 127.0.0.1 -n 2 >nul\r\n"
        ":retry\r\n"
        f'move /y "{new_exe}" "{current_exe}" >nul 2>&1\r\n'
        f'if exist "{new_exe}" (\r\n'
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        "  goto retry\r\n"
        ")\r\n"
        f'start "" "{current_exe}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="ascii") as f:
        f.write(script)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)


def check_and_update(current_version):
    """Verifica e aplica atualizacao. Retorna True se o app vai reiniciar."""
    if not getattr(sys, "frozen", False):
        return False  # so atualiza o executavel empacotado
    try:
        print("  Verificando atualizacoes...")
        tag, url = _latest_release()
        if not tag or not url:
            return False
        if _ver(tag) <= _ver(current_version):
            print(f"  Voce ja esta na versao mais recente (v{current_version}).")
            return False
        print(f"  Nova versao encontrada: {tag} (atual: v{current_version}).")
        print("  Baixando atualizacao...")
        current_exe = sys.executable
        new_exe = os.path.join(os.path.dirname(current_exe),
                               ASSET_NAME.replace(".exe", ".new.exe"))
        _download(url, new_exe)
        print("  Atualizacao baixada. Reiniciando para aplicar...")
        _swap_and_restart(new_exe, current_exe)
        return True
    except Exception as e:  # noqa: BLE001 - nunca bloquear o uso por causa de update
        print(f"  Nao foi possivel atualizar agora ({type(e).__name__}). Seguindo...")
        return False
