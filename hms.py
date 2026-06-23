"""Decodificacao dos codigos HMS (Health Management System) da Bambu Lab.

Cada falha vem no MQTT como um par (attr, code), dois inteiros de 32 bits.
A string legivel e' montada como HMS_XXXX_XXXX_XXXX_XXXX e a severidade
fica nos 16 bits altos de 'code'. A descricao em texto vem do arquivo
'hms_codes.json' (preenchido na Fase 0 a partir do wiki/comunidade).
"""
import json
import os

HMS_WIKI_BASE = "https://wiki.bambulab.com/en/x1/troubleshooting/hmscode"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CODES_PATH = os.path.join(_BASE_DIR, "hms_codes.json")

# Mapeamento de severidade (16 bits altos de 'code').
SEVERIDADE = {1: "Fatal", 2: "Grave", 3: "Comum", 4: "Informacao"}

_descricoes = None


def _slug(attr, code):
    return "%04X_%04X_%04X_%04X" % (
        (attr >> 16) & 0xFFFF, attr & 0xFFFF,
        (code >> 16) & 0xFFFF, code & 0xFFFF,
    )


def format_code(attr, code):
    """Retorna a string canonica, ex: HMS_0300_0100_0003_0001."""
    return "HMS_" + _slug(attr, code)


def severity_label(code):
    return SEVERIDADE.get((code >> 16) & 0xFFFF, "Desconhecida")


def wiki_url(attr, code):
    return f"{HMS_WIKI_BASE}/{_slug(attr, code)}"


def _load_descricoes(path=_CODES_PATH):
    global _descricoes
    if _descricoes is None:
        _descricoes = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    _descricoes = json.load(f).get("codes", {})
            except (ValueError, OSError):
                _descricoes = {}
    return _descricoes


def describe(attr, code):
    """Devolve dict com codigo, severidade, descricao (se conhecida) e link do wiki."""
    code_str = format_code(attr, code)
    return {
        "code": code_str,
        "severity": severity_label(code),
        "description": _load_descricoes().get(code_str, ""),
        "wiki_url": wiki_url(attr, code),
    }
