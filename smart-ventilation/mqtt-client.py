import paho.mqtt.client as mqtt
from datetime import datetime
 
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("application/f4994b60-cc34-4cb5-b77c-dc9a5f9de541/#")
 
 
def on_message(client, userdata, msg):
    print(str(datetime.utcnow())+":  "+msg.topic+" "+str(msg.payload))
 
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.tls_set()
client.on_connect = on_connect
client.on_message = on_message
 
client.username_pw_set(username="kisam",password="dd9e3f43-a5bc-440d-8647-9c187376c1ef-kisam")
print("Connecting...")
client.connect("cs1-swp.westeurope.cloudapp.azure.com", 8883, 10)
client.loop_forever()