"""Diagnostico de telemetria Bambu A1 (Fase 1 + inicio da Fase 2).

Uso:
  python app.py --demo           Roda com dados de exemplo (sem impressora)
  python app.py                  Conecta na impressora (precisa de config.json)
  python app.py --intervalo 5    Atualiza a cada 5 segundos
"""
import argparse
import json
import os
import sys
import time
from collections import deque

import config
import diagnostics as diag
import discovery
import updater
from version import __version__ as APP_VERSION

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Recursos empacotados (somente leitura). Com PyInstaller (--onefile) ficam em
# sys._MEIPASS; rodando como script, ficam ao lado do app.py.
RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
# Arquivos editaveis pelo usuario (config.json): ao lado do .exe quando empacotado,
# senao ao lado do app.py.
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else BASE_DIR

ICONE = {"OK": "[ OK ]", "ATENCAO": "[!]", "FALHA": "[XX]", "INFO": "[i]"}


def render(snapshot, findings):
    s = diag.parse(snapshot)

    def fmt(v, suf=" C"):
        return f"{v:.0f}{suf}" if v is not None else "--"

    linhas = [
        "=" * 60,
        f"  Bambu A1 - Diagnostico ao vivo   ({time.strftime('%H:%M:%S')})",
        "=" * 60,
        f"  Bico:  {fmt(s['nozzle_temper'])} / alvo {fmt(s['nozzle_target'])}",
        f"  Mesa:  {fmt(s['bed_temper'])} / alvo {fmt(s['bed_target'])}",
        f"  Vent. peca: {fmt(s['cooling_fan'], '')}    Vent. hotend: {fmt(s['heatbreak_fan'], '')}",
        f"  Estado: {s['gcode_state'] or '--'}",
        "-" * 60,
    ]
    if not findings:
        linhas.append("  [ OK ] Nenhuma falha detectada pelas regras atuais.")
    else:
        for f in findings:
            linhas.append(f"  {ICONE.get(f.level, '*')} [{f.subsystem}] {f.message}")
            if f.detail:
                linhas.append(f"         {f.detail}")
    linhas.append("=" * 60)
    return "\n".join(linhas)


def run_demo():
    with open(os.path.join(RES_DIR, "sample_report.json"), encoding="utf-8") as f:
        snap = json.load(f)
    _, findings = diag.diagnose(snap, None)
    print(render(snap, findings))
    return 0


def run_live(cfg, intervalo):
    from client import BambuClient  # import tardio: demo nao precisa do paho

    history = deque(maxlen=200)
    latest = {"snapshot": None}

    client = BambuClient(
        cfg["ip"], cfg["serial"], cfg["access_code"],
        on_update=lambda state: latest.__setitem__("snapshot", state),
        on_log=lambda msg: print(f"[info] {msg}"),
    )

    print(f"Conectando em {cfg['ip']} ...  (Ctrl+C para sair)")
    try:
        client.connect()
    except Exception as e:  # noqa: BLE001 - mostrar qualquer erro de rede ao usuario
        print(f"Erro de conexao: {e}")
        return 1

    try:
        while True:
            time.sleep(intervalo)
            snap = latest["snapshot"]
            if snap is None:
                print("Aguardando dados da impressora...")
                continue
            s = diag.parse(snap)
            history.append((time.time(), s))
            _, findings = diag.diagnose(snap, list(history))
            print(render(snap, findings))
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        client.stop()
    return 0


def _connect_flow(config_path, reconfigure=False):
    """Conecta na impressora. Usa o config salvo (atualizando o IP) ou faz a
    configuracao automatica na primeira vez / quando reconfigurar."""
    cfg = config.read_config(config_path)
    if cfg and cfg.get("serial") and cfg.get("access_code") and not reconfigure:
        print("  Procurando a impressora na rede para confirmar o IP...")
        for d in discovery.discover(timeout=5):
            if d.get("serial") == cfg.get("serial"):
                if d["ip"] != cfg.get("ip"):
                    print(f"  IP atualizado: {cfg.get('ip')} -> {d['ip']}")
                cfg["ip"] = d["ip"]
                config.write_config(config_path, cfg)
                break
        run_live(cfg, 3.0)
        return
    _setup_and_connect(config_path)


def _setup_and_connect(config_path):
    """Descobre a impressora na rede, pede so o codigo de acesso e conecta."""
    print("  Procurando impressoras Bambu na rede (uns 6 segundos)...")
    achadas = discovery.discover(timeout=6)

    if not achadas:
        print("  Nenhuma impressora encontrada automaticamente.")
        print("  Confira: impressora ligada, no MESMO Wi-Fi e com Modo LAN ativo.")
        if input("  Quer digitar os dados manualmente? [s/N]: ").strip().lower() != "s":
            return
        ip = input("    IP: ").strip()
        serial = input("    Numero de serie: ").strip()
        code = input("    Codigo de acesso: ").strip()
        if not (ip and serial and code):
            print("  Dados incompletos. Cancelado.")
            return
        cfg = {"ip": ip, "serial": serial, "access_code": code}
    else:
        if len(achadas) == 1:
            alvo = achadas[0]
            print(f"  Encontrada: {alvo.get('name') or 'Bambu'} em "
                  f"{alvo['ip']} (SN {alvo['serial']})")
        else:
            print("  Impressoras encontradas:")
            for i, d in enumerate(achadas, 1):
                print(f"   [{i}] {d.get('name') or 'Bambu'} - {d['ip']} (SN {d['serial']})")
            try:
                alvo = achadas[int(input("  Escolha o numero: ").strip()) - 1]
            except (ValueError, IndexError):
                print("  Selecao invalida.")
                return
        print("  So falta o codigo de acesso (tela da impressora > Modo LAN).")
        code = input("  Codigo de acesso: ").strip()
        if not code:
            print("  Codigo vazio. Cancelado.")
            return
        cfg = {"ip": alvo["ip"], "serial": alvo["serial"], "access_code": code}

    config.write_config(config_path, cfg)
    print("  Configuracao salva. Conectando...")
    run_live(cfg, 3.0)


def run_menu():
    """Menu interativo (modo padrao quando o programa abre sem argumentos)."""
    config_path = os.path.join(APP_DIR, "config.json")

    if updater.check_and_update(APP_VERSION):
        return 0  # vai reiniciar para aplicar a atualizacao

    while True:
        print()
        print("=" * 60)
        print(f"  Bambu A1 - Diagnostico de telemetria  (v{APP_VERSION})")
        print("=" * 60)
        print("  [1] Rodar demo (dados de exemplo, sem impressora)")
        print("  [2] Conectar na impressora")
        print("  [3] Procurar / trocar impressora")
        print("  [4] Sair")
        try:
            escolha = input("  Escolha uma opcao: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if escolha == "1":
            print()
            run_demo()
            input("\n  Pressione Enter para voltar ao menu...")
        elif escolha == "2":
            print()
            _connect_flow(config_path, reconfigure=False)
            input("\n  Pressione Enter para voltar ao menu...")
        elif escolha == "3":
            print()
            _connect_flow(config_path, reconfigure=True)
            input("\n  Pressione Enter para voltar ao menu...")
        elif escolha == "4":
            print("  Ate logo!")
            return 0
        else:
            print("  Opcao invalida.")


def main():
    # Sem argumentos (ex.: clique-duplo no .exe) -> abre o menu interativo.
    if len(sys.argv) == 1:
        return run_menu()

    ap = argparse.ArgumentParser(description="Diagnostico de telemetria Bambu A1")
    ap.add_argument("--config", default=os.path.join(APP_DIR, "config.json"))
    ap.add_argument("--demo", action="store_true",
                    help="Roda com dados de exemplo, sem impressora")
    ap.add_argument("--intervalo", type=float, default=3.0,
                    help="Segundos entre atualizacoes (modo ao vivo)")
    args = ap.parse_args()

    if args.demo:
        return run_demo()

    from config import load_config
    return run_live(load_config(args.config), args.intervalo)


if __name__ == "__main__":
    sys.exit(main())
