# Bambu A1 — Diagnóstico de telemetria (Fase 1)

Ferramenta de bancada para manutenção de impressoras **Bambu Lab A1 / A1 mini**.
Conecta na impressora pela rede (MQTT local, modo LAN), lê os dados ao vivo
(temperaturas, ventoinhas, estado) e os **códigos de erro HMS**, e aplica regras
que apontam o subsistema com falha (**TH board** ou **mainboard**).

> Esta é a **Fase 1** do roadmap (telemetria) com o **início da Fase 2** (motor de
> regras). Não substitui a inspeção de bancada — ela aponta *o subsistema* com
> falha, não o componente exato.

## O que cada arquivo faz

| Arquivo | Função |
|---|---|
| `app.py` | Programa principal (linha de comando). |
| `client.py` | Conexão MQTT com a impressora. |
| `diagnostics.py` | Motor de regras → gera o laudo. |
| `hms.py` | Decodifica os códigos de erro HMS. |
| `hms_codes.json` | Dicionário de descrições dos códigos (preencher na Fase 0). |
| `config.example.json` | Modelo de configuração da impressora. |
| `sample_report.json` | Dados de exemplo para o modo demo. |

## 1. Pré-requisitos

- **Python 3.9 ou mais novo** ([python.org](https://www.python.org/downloads/) —
  na instalação, marque "Add Python to PATH").
- Instalar a dependência:

```powershell
cd "bambu-diag"
pip install -r requirements.txt
```

## 2. Testar sem impressora (modo demo)

Roda com dados de exemplo, só pra ver o resultado:

```powershell
python app.py --demo
```

## 3. Conectar na impressora (modo ao vivo)

1. **Na tela da A1:** Configurações → ative o **Modo LAN**. Anote o **IP**, o
   **Código de Acesso** e o **número de série** que aparecem ali.
2. Copie `config.example.json` para `config.json` e preencha:

```json
{
  "ip": "192.168.1.50",
  "serial": "01PXXXXXXXXXXXXXX",
  "access_code": "12345678"
}
```

3. Rode:

```powershell
python app.py
```

Saia com `Ctrl+C`. Para mudar o intervalo de atualização: `python app.py --intervalo 5`.

## Regras de diagnóstico já implementadas

- **HMS** — lista cada código de erro ativo com sua severidade.
- **Termistor do bico/mesa** — leitura fora de faixa (aberto/curto/conector solto).
- **Ventoinha do hotend** — parada com o bico quente (risco de *heat creep*).
- **Aquecimento do bico** — não sobe de temperatura mesmo com alvo definido.
- **Aquecimento da mesa** — não sobe de temperatura (aquecedor / cabo da mesa do A1).
- **Sobreaquecimento** — bico ou mesa muito acima do alvo (MOSFET travado ligado).

## Atualização automática

Quando rodando como **executável (`.exe`)**, o programa verifica ao abrir se há
uma versão mais nova publicada nas *Releases* do GitHub. Se houver, ele baixa e
se atualiza sozinho — não precisa entrar no site. Rodando como script Python,
essa verificação é ignorada (você atualiza com `git pull`).

## Próximos passos do roadmap

- **Fase 0:** preencher `hms_codes.json` com os códigos reais do A1 e confirmar o
  acesso MQTT no firmware atual.
- **Fase 2 (em andamento):** mais regras (motores/homing, AMS).
- **Fase 3:** interface visual, histórico por número de série e laudo em PDF.
- **Fase 4–5:** jiga de teste de placa (hardware) com placa de referência.
