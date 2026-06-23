"""Carrega a configuracao da impressora (IP, numero de serie, codigo de acesso)."""
import json
import os
import sys

CAMPOS_OBRIGATORIOS = ["ip", "serial", "access_code"]


def load_config(path="config.json"):
    if not os.path.exists(path):
        print(f"Arquivo de configuracao '{path}' nao encontrado.")
        print("Copie 'config.example.json' para 'config.json' e preencha os dados da impressora.")
        sys.exit(2)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except ValueError as e:
        print(f"Erro ao ler '{path}': {e}")
        sys.exit(2)

    faltando = [k for k in CAMPOS_OBRIGATORIOS if not cfg.get(k)]
    if faltando:
        print(f"Configuracao incompleta. Faltam os campos: {', '.join(faltando)}")
        sys.exit(2)
    return cfg
