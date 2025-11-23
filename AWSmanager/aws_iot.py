# aws_iot.py
# Minimal AWS IoT MQTT client for MicroPython.
# Tested against umqtt.simple / umqtt.robust builds that support ssl=True and ssl_params.

import utime
import ujson
from umqtt.robust import MQTTClient

class AWSIoTClient:
    """
    AWSIoTClient wraps MQTTClient for TLS mutual auth.
    - place files on ESP32: cert.pem.crt, private.pem.key, root-CA.pem
    - server: '<your-iot-endpoint>.iot.<region>.amazonaws.com'
    """
    def __init__(self, client_id, server, port=8883, keepalive=60,
                 certfile="/cert.pem.crt", keyfile="/private.pem.key", cafile="/root-CA.pem"):
        self.client_id = client_id
        self.server = server
        self.port = port
        self.keepalive = keepalive
        self.certfile = certfile
        self.keyfile = keyfile
        self.cafile = cafile
        self._client = None
        self._cb = None

    def _ssl_params(self):
        # MicroPython on many ESP32 builds accepts ssl_params with 'cert' and 'key' content or file paths.
        # umqtt.robust on many builds accepts ssl=True and ssl_params={'cert':..., 'key':..., 'ca_certs':...}
        # We will attempt to read files and pass contents.
        try:
            with open(self.certfile, 'rb') as f:
                cert = f.read()
            with open(self.keyfile, 'rb') as f:
                key = f.read()
            with open(self.cafile, 'rb') as f:
                ca = f.read()
            return {'cert': cert, 'key': key, 'ca_certs': ca}
        except Exception:
            # Fallback: some builds expect file paths in ssl_params
            return {'certfile': self.certfile, 'keyfile': self.keyfile, 'ca_certs': self.cafile}

    def connect(self, subs=None, msg_callback=None):
        """
        Connect and optionally subscribe.
        subs: list of (topic, qos)
        msg_callback: function(topic, msg_bytes)
        """
        ssl_params = self._ssl_params()
        self._client = MQTTClient(self.client_id, self.server, port=self.port,
                                  keepalive=self.keepalive, ssl=True, ssl_params=ssl_params)
        # assign callback and connect
        if msg_callback:
            self._cb = msg_callback
            self._client.set_callback(self._internal_cb)
        self._client.connect()
        if subs:
            for t, q in subs:
                self._client.subscribe(t, q)

    def _internal_cb(self, topic, msg):
        if self._cb:
            try:
                self._cb(topic.decode() if isinstance(topic, bytes) else topic,
                         msg.decode() if isinstance(msg, bytes) else msg)
            except Exception as e:
                print("Callback error:", e)

    def publish(self, topic, payload, qos=0, retain=False):
        if isinstance(payload, dict):
            payload = ujson.dumps(payload)
        self._client.publish(topic, payload, qos, retain)

    def check_msg(self, wait_ms=0):
        # call regularly to check for incoming messages
        try:
            self._client.check_msg()
        except Exception as e:
            # keep running — reconnect strategy could be added
            print("MQTT check_msg error:", e)

    def disconnect(self):
        try:
            self._client.disconnect()
        except Exception:
            pass
