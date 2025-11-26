import os
import json
import boto3
from datetime import datetime, timedelta
from decimal import Decimal

IOT_ENDPOINT = os.environ.get("IOT_ENDPOINT")
DDB_TABLE = os.environ.get("DDB_TABLE", "SensorTelemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "esp32-sim-01")
VOLTAGE_THRESHOLD = float(os.environ.get("VOLTAGE_THRESHOLD", "14.0"))

ddb = boto3.resource('dynamodb')
table = ddb.Table(DDB_TABLE)
iot = boto3.client('iot-data', endpoint_url=f"https://{IOT_ENDPOINT}")

def simple_linear_predict(xs, ys):
    # least squares slope/intercept
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs)/n
    mean_y = sum(ys)/n
    num = sum((x-mean_x)*(y-mean_y) for x,y in zip(xs,ys))
    den = sum((x-mean_x)**2 for x in xs)
    if den == 0:
        return None
    slope = num/den
    intercept = mean_y - slope*mean_x
    # predict next x (xs[-1] + delta)
    next_x = xs[-1] + (xs[-1]-xs[-2]) if n>=2 else xs[-1] + 1
    return intercept + slope*next_x

def get_recent_voltage_points(device_id, limit=10):
    # Query by device_id sorting by ts descending - DynamoDB Query requires proper keys and index.
    resp = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('device_id').eq(device_id),
        Limit=limit,
        ScanIndexForward=False
    )
    items = resp.get('Items', [])
    # extract timestamp order ascending
    items = list(reversed(items))
    xs = []
    ys = []
    for i, it in enumerate(items):
        payload = it.get('payload') or it
        try:
            v = float(payload.get('INA219_1_Voltage(V)') or payload.get('INA219_1_Voltage') or payload.get('INA219_Voltage(V)') or 0)
            xs.append(i)
            ys.append(v)
        except Exception:
            continue
    return xs, ys

def publish_command(device_id, payload):
    topic = f"sensors/{device_id}/commands"
    iot.publish(topic=topic, qos=1, payload=json.dumps(payload))

def lambda_handler(event, context):
    # This Lambda can be invoked by IoT Rule or CloudWatch schedule
    xs, ys = get_recent_voltage_points(DEVICE_ID, limit=8)
    pred = simple_linear_predict(xs, ys) if xs and ys else None
    message = {"predicted_voltage": pred, "timestamp": datetime.utcnow().isoformat()+"Z"}
    # If predicted voltage crosses threshold or last measured > threshold -> action
    last_v = ys[-1] if ys else None
    if (pred and pred > VOLTAGE_THRESHOLD) or (last_v and last_v > VOLTAGE_THRESHOLD):
        # build command: turn on fan relay, turn off all relays
        cmd = {"relay_1": 0, "relay_2": 0, "relay_3": 0, "relay_4": 0, "fan": 1, "warning": "High voltage predicted/observed"}
        publish_command(DEVICE_ID, cmd)
        message["action"] = "sent_shutdown_and_fan"
    else:
        message["action"] = "no_action"
    return {
        "statusCode": 200,
        "body": json.dumps(message)
    }
