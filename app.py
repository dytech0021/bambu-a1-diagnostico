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

import diagnostics as diag

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    with open(os.path.join(BASE_DIR, "sample_report.json"), encoding="utf-8") as f:
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
            history.append((time.time(), s["nozzle_temper"], s["nozzle_target"]))
            _, findings = diag.diagnose(snap, list(history))
            print(render(snap, findings))
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        client.stop()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Diagnostico de telemetria Bambu A1")
    ap.add_argument("--config", default=os.path.join(BASE_DIR, "config.json"))
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
