"""Motor de diagnostico (Fase 2, inicio).

Transforma a telemetria bruta em 'achados' (findings): cada um aponta um
subsistema (TH board / Mainboard) com um nivel de gravidade. As regras aqui
sao conservadoras e seguras; novas regras entram conforme a Fase 0 mapeia
mais falhas reais do A1.
"""
from dataclasses import dataclass

import hms

OK = "OK"
ATENCAO = "ATENCAO"
FALHA = "FALHA"
INFO = "INFO"


@dataclass
class Finding:
    level: str
    subsystem: str
    message: str
    detail: str = ""


def _severity_to_level(sev):
    return {
        "Fatal": FALHA,
        "Grave": FALHA,
        "Comum": ATENCAO,
        "Informacao": INFO,
    }.get(sev, ATENCAO)


def parse(snapshot):
    """Extrai os campos de interesse do bloco 'print' do relatorio MQTT."""
    p = (snapshot or {}).get("print", {}) or {}

    def num(key):
        try:
            return float(p.get(key))
        except (TypeError, ValueError):
            return None

    return {
        "nozzle_temper": num("nozzle_temper"),
        "nozzle_target": num("nozzle_target_temper"),
        "bed_temper": num("bed_temper"),
        "bed_target": num("bed_target_temper"),
        "cooling_fan": num("cooling_fan_speed"),
        "heatbreak_fan": num("heatbreak_fan_speed"),
        "big_fan1": num("big_fan1_speed"),
        "big_fan2": num("big_fan2_speed"),
        "gcode_state": p.get("gcode_state"),
        "print_error": p.get("print_error"),
        "wifi_signal": p.get("wifi_signal"),
        "hms": p.get("hms") or [],
    }


# ---------------------------------------------------------------- regras ----

def rule_hms(s):
    achados = []
    for entry in s["hms"]:
        info = hms.describe(entry.get("attr", 0), entry.get("code", 0))
        achados.append(Finding(
            _severity_to_level(info["severity"]),
            "HMS",
            f"{info['code']} ({info['severity']})",
            info["description"] or f"Consultar: {info['wiki_url']}",
        ))
    return achados


def rule_thermistor(s):
    achados = []
    n = s["nozzle_temper"]
    if n is not None and (n < -15 or n > 360):
        achados.append(Finding(
            FALHA, "TH board",
            "Leitura do termistor do bico fora de faixa",
            f"Valor lido: {n:.0f} C. Termistor possivelmente aberto/curto ou conector solto.",
        ))
    b = s["bed_temper"]
    if b is not None and (b < -15 or b > 150):
        achados.append(Finding(
            FALHA, "Mainboard",
            "Leitura do termistor da mesa fora de faixa",
            f"Valor lido: {b:.0f} C. Verificar termistor da mesa e o cabo (ponto comum de falha no A1).",
        ))
    return achados


def rule_heatbreak_fan(s):
    n, f = s["nozzle_temper"], s["heatbreak_fan"]
    if n is not None and f is not None and n > 50 and f == 0:
        return [Finding(
            FALHA, "TH board",
            "Ventoinha do hotend (dissipador) parada com o bico quente",
            f"Bico a {n:.0f} C e ventoinha do dissipador em 0. Risco de heat creep e "
            "entupimento. Verificar a ventoinha e seu acionamento na TH board.",
        )]
    return []


def rule_heating(s, history):
    """Usa o historico recente para detectar bico que nao aquece.

    history: lista de tuplas (timestamp, nozzle_temper, nozzle_target).
    """
    n, tgt = s["nozzle_temper"], s["nozzle_target"]
    if not history or n is None or tgt is None or tgt <= 0 or (tgt - n) <= 10:
        return []

    agora = history[-1][0]
    janela = [h for h in history if h[1] is not None and agora - h[0] <= 30]
    if len(janela) < 2:
        return []
    span = janela[-1][0] - janela[0][0]
    if span < 15:
        return []
    subida = janela[-1][1] - janela[0][1]
    if subida < 2:
        return [Finding(
            FALHA, "TH board",
            "Bico nao aquece (temperatura nao sobe)",
            f"Alvo {tgt:.0f} C, atual {n:.0f} C, variacao {subida:+.1f} C em {span:.0f}s. "
            "Suspeita de resistencia (aquecedor) ou termistor da TH board.",
        )]
    return []


def diagnose(snapshot, history=None):
    s = parse(snapshot)
    achados = []
    achados += rule_hms(s)
    achados += rule_thermistor(s)
    achados += rule_heatbreak_fan(s)
    if history is not None:
        achados += rule_heating(s, history)
    return s, achados
