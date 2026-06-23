"""Cliente MQTT para impressoras Bambu Lab (modo LAN).

Conecta no broker local da impressora (TLS, porta 8883), autentica com o
usuario 'bblp' e o codigo de acesso, assina o topico de relatorio e pede um
'pushall' para receber o estado completo. Os relatorios chegam parciais, entao
sao mesclados num estado acumulado.
"""
import json
import ssl
import threading

import paho.mqtt.client as mqtt

TOPICO_RELATORIO = "device/{serial}/report"
TOPICO_PEDIDO = "device/{serial}/request"
PUSHALL = {"pushing": {"sequence_id": "0", "command": "pushall"}}


def deep_merge(base, update):
    for k, v in update.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


class BambuClient:
    def __init__(self, ip, serial, access_code, port=8883,
                 on_update=None, on_log=None):
        self.ip = ip
        self.serial = serial
        self.port = port
        self.on_update = on_update or (lambda state: None)
        self.on_log = on_log or (lambda msg: None)
        self._state = {}
        self._lock = threading.Lock()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id="bambu-diag")
        self._client.username_pw_set("bblp", access_code)
        self._client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._client.tls_insecure_set(True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def connect(self):
        self._client.connect(self.ip, self.port, keepalive=60)
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()

    def request_full_status(self):
        self._client.publish(TOPICO_PEDIDO.format(serial=self.serial),
                             json.dumps(PUSHALL))

    # ------------------------------------------------------------ callbacks --
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        if rc != 0:
            self.on_log(f"Falha ao conectar (codigo {rc}). "
                        "Confira IP, numero de serie e codigo de acesso.")
            return
        self.on_log("Conectado ao MQTT da impressora.")
        client.subscribe(TOPICO_RELATORIO.format(serial=self.serial))
        self.request_full_status()

    def _on_disconnect(self, client, userdata, *args):
        self.on_log("Desconectado da impressora.")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        with self._lock:
            deep_merge(self._state, payload)
            snapshot = json.loads(json.dumps(self._state))
        self.on_update(snapshot)
