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


def _sem_aquecer(history, temp_key, janela_s=30, span_min=15, subida_min=2.0):
    """Retorna (subida, span) se a temperatura nao subiu na janela; senao None.

    history: lista de tuplas (timestamp, estado_parseado).
    """
    agora = history[-1][0]
    pontos = [(t, st.get(temp_key)) for (t, st) in history
              if st.get(temp_key) is not None and agora - t <= janela_s]
    if len(pontos) < 2:
        return None
    span = pontos[-1][0] - pontos[0][0]
    if span < span_min:
        return None
    subida = pontos[-1][1] - pontos[0][1]
    if subida < subida_min:
        return (subida, span)
    return None


def rule_heating(s, history):
    """Bico com alvo definido mas que nao esquenta -> aquecedor/termistor."""
    n, tgt = s["nozzle_temper"], s["nozzle_target"]
    if not history or n is None or tgt is None or tgt <= 0 or (tgt - n) <= 10:
        return []
    r = _sem_aquecer(history, "nozzle_temper")
    if r:
        subida, span = r
        return [Finding(
            FALHA, "TH board",
            "Bico nao aquece (temperatura nao sobe)",
            f"Alvo {tgt:.0f} C, atual {n:.0f} C, variacao {subida:+.1f} C em {span:.0f}s. "
            "Suspeita de resistencia (aquecedor) ou termistor da TH board.",
        )]
    return []


def rule_bed_heating(s, history):
    """Mesa com alvo definido mas que nao esquenta."""
    b, tgt = s["bed_temper"], s["bed_target"]
    if not history or b is None or tgt is None or tgt <= 0 or (tgt - b) <= 8:
        return []
    r = _sem_aquecer(history, "bed_temper")
    if r:
        subida, span = r
        return [Finding(
            FALHA, "Mainboard",
            "Mesa nao aquece (temperatura nao sobe)",
            f"Alvo {tgt:.0f} C, atual {b:.0f} C, variacao {subida:+.1f} C em {span:.0f}s. "
            "Verificar o aquecedor da mesa, o cabo da mesa (ponto critico no A1) e o "
            "MOSFET de aquecimento na mainboard.",
        )]
    return []


def rule_overtemp(s):
    """Temperatura muito acima do alvo -> aquecedor possivelmente travado ligado."""
    achados = []
    n, ntgt = s["nozzle_temper"], s["nozzle_target"]
    if n is not None and ntgt is not None and ntgt > 0 and n > ntgt + 25:
        achados.append(Finding(
            FALHA, "TH board",
            "Bico muito acima do alvo (risco de runaway termico)",
            f"Alvo {ntgt:.0f} C, atual {n:.0f} C. Suspeita de MOSFET do aquecedor "
            "em curto (travado ligado) na TH board.",
        ))
    b, btgt = s["bed_temper"], s["bed_target"]
    if b is not None and btgt is not None and btgt > 0 and b > btgt + 20:
        achados.append(Finding(
            FALHA, "Mainboard",
            "Mesa muito acima do alvo (risco de runaway termico)",
            f"Alvo {btgt:.0f} C, atual {b:.0f} C. Suspeita de MOSFET da mesa em curto "
            "(travado ligado) na mainboard.",
        ))
    return achados


def _codes_set(state):
    """Conjunto de codigos HMS ativos num estado parseado."""
    return {hms.format_code(e.get("attr", 0), e.get("code", 0))
            for e in state.get("hms", [])}


def rule_intermittent_hms(s, history, janela_s=120, min_aparicoes=3):
    """Erro HMS que liga e desliga varias vezes = mau contato (cabo/conector).

    O sinal mais forte, so por software, de cabo do cabecote (USB-C) gasto.
    """
    if not history or len(history) < 4:
        return []
    agora = history[-1][0]
    seq = [(t, _codes_set(st)) for (t, st) in history if agora - t <= janela_s]
    if len(seq) < 4:
        return []
    aparicoes = {}
    anterior = set()
    for _, codes in seq:
        for c in codes - anterior:          # transicao ausente -> presente
            aparicoes[c] = aparicoes.get(c, 0) + 1
        anterior = codes
    achados = []
    for c, n in sorted(aparicoes.items()):
        if n >= min_aparicoes:
            achados.append(Finding(
                FALHA, "TH board / cabo",
                f"Erro intermitente: {c} apareceu {n}x",
                f"O erro {c} ligou e desligou {n}x em ~{janela_s // 60} min. Padrao "
                "classico de mau contato: cabo do cabecote (USB-C) ou conector frouxo/"
                "oxidado. Teste trocando o cabo por um bom e reassentando os conectores.",
            ))
    return achados


def rule_sensor_glitch(s, history, janela_s=90, min_glitches=2):
    """Saltos isolados e termicamente impossiveis na leitura do bico = dropout
    momentaneo do sensor (perda de leitura pelo cabo/TH board)."""
    if not history or len(history) < 3:
        return []
    agora = history[-1][0]
    pts = [st.get("nozzle_temper") for (t, st) in history
           if st.get("nozzle_temper") is not None and agora - t <= janela_s]
    if len(pts) < 3:
        return []
    glitches = 0
    for i in range(1, len(pts) - 1):
        ant, cur, prox = pts[i - 1], pts[i], pts[i + 1]
        # ponto isolado bem fora dos dois vizinhos (que estao proximos entre si)
        if abs(ant - prox) < 10 and abs(cur - ant) >= 30 and abs(cur - prox) >= 30:
            glitches += 1
    if glitches >= min_glitches:
        return [Finding(
            FALHA, "TH board / cabo",
            f"Leitura do bico com saltos impossiveis ({glitches}x)",
            "A temperatura do bico deu picos/quedas isolados e termicamente impossiveis, "
            "sinal de perda momentanea de leitura do sensor do cabecote. Aponta para mau "
            "contato no cabo do cabecote (USB-C) ou na TH board.",
        )]
    return []


def diagnose(snapshot, history=None):
    s = parse(snapshot)
    achados = []
    achados += rule_hms(s)
    achados += rule_thermistor(s)
    achados += rule_heatbreak_fan(s)
    achados += rule_overtemp(s)
    if history is not None:
        achados += rule_heating(s, history)
        achados += rule_bed_heating(s, history)
        achados += rule_intermittent_hms(s, history)
        achados += rule_sensor_glitch(s, history)
    return s, achados
