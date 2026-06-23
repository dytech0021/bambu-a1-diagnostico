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

A conexão é **automática**: o programa descobre a impressora na rede sozinho.

1. **Na tela da A1:** ative o **Modo LAN** e anote só o **Código de Acesso**.
2. Abra o programa e escolha **`[2]` Conectar na impressora**.
3. Ele procura a A1 na rede (IP e número de série são detectados sozinhos),
   mostra qual encontrou e pede **apenas o código de acesso**.
4. Pronto — conecta e começa a mostrar os dados ao vivo. Para sair, `Ctrl+C`.

O programa salva isso num `config.json` ao lado dele. Nas próximas vezes, o
`[2]` já conecta direto (e re-localiza a impressora caso o IP tenha mudado).
Use **`[3]` Procurar / trocar impressora** para reconfigurar.

> Requisito: o PC e a impressora precisam estar na **mesma rede Wi-Fi**.
> Se a descoberta automática falhar (rede com multicast bloqueado), o programa
> oferece digitar IP/série/código manualmente.

## Regras de diagnóstico já implementadas

- **HMS** — lista cada código de erro ativo com sua severidade.
- **Termistor do bico/mesa** — leitura fora de faixa (aberto/curto/conector solto).
- **Ventoinha do hotend** — parada com o bico quente (risco de *heat creep*).
- **Aquecimento do bico** — não sobe de temperatura mesmo com alvo definido.
- **Aquecimento da mesa** — não sobe de temperatura (aquecedor / cabo da mesa do A1).
- **Sobreaquecimento** — bico ou mesa muito acima do alvo (MOSFET travado ligado).
- **Erro intermitente (HMS oscilando)** — erro que liga/desliga várias vezes:
  mau contato no cabo do cabeçote (USB‑C) ou conector.
- **Salto impossível na leitura do bico** — pico/queda isolado e termicamente
  impossível = perda momentânea de leitura do sensor (cabo / TH board).

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
