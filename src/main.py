import json

import requests
import websocket
from websocket import create_connection

import pigpio

GPIO = pigpio.pi()
SERVO_PIN_ALPHA = 23
SERVO_PIN_GAMMA = 4

def get_relay(token, endpoint='http://localhost:8080/api/v1/relays'):
    """リレーを取得する
    
    Parameters
    ----------
    token : str
        リレーを取得するためのトークン
    endpoint : str, optional
        APIのエンドポイント, by default 'http://localhost:8080/api/v1/relays'
    
    Returns
    -------
    str or None
        成功時：リレー
        失敗時：None
    """
    data = dict(
        token=token
    )
    response = requests.post(endpoint, data=data)
    if response.status_code != requests.codes.ok:
        return None
    # レスポンスデータのパース
    response_data = json.loads(response.text)
    if 'errors' in response_data:
        return None
    if not 'relay' in response_data:
        return None
    return response_data['relay']

# Callback functions
def on_message(ws, message):
    print('[Log] Received: %s' % message)
    message_data = json.loads(message)
    if 'header' in message_data and 'client_id' in message_data['header']:
        with open('settings.json') as fp:
            settings = json.load(fp)
        settings['relay']['client_id'] = message_data['header']['client_id']
        with open('settings.json', mode="w") as fp:
            json.dump(settings, fp)
        print("[Log] Writed client_id: %s" % message_data['header']['client_id'])

    if not 'contents' in message_data:
        return
    if message_data['contents'] == None:
        return
    if 'gyro' in message_data['contents'] and 'gamma' in message_data['contents']['gyro']:
        MIN_PULSEWIDTH = 500
        MAX_PULSEWIDTH = 2500
        MIN_ANGLE_GAMMA = 0
        MAX_ANGLE_GAMMA =  180
        gamma = message_data['contents']['gyro']['gamma']
        if gamma < 0:
            gamma += 180
        servo_angle_gamma = max([MIN_ANGLE_GAMMA, gamma])
        servo_angle_gamma = min([MAX_ANGLE_GAMMA, servo_angle_gamma])
        servo_pulse_gamma = MAX_PULSEWIDTH - (MAX_PULSEWIDTH - MIN_PULSEWIDTH) / (MAX_ANGLE_GAMMA - MIN_ANGLE_GAMMA) * (servo_angle_gamma - MIN_ANGLE_GAMMA)

        MIN_ANGLE_ALPHA = 0
        MAX_ANGLE_ALPHA =  180
        alpha = message_data['contents']['gyro']['alpha']
        if message_data['contents']['gyro']['gamma'] < 0:
            alpha = 180 - alpha
        else:
            alpha = 360 - alpha
        servo_angle_alpha = max([MIN_ANGLE_ALPHA, alpha])
        servo_angle_alpha = min([MAX_ANGLE_ALPHA, servo_angle_alpha])
        servo_pulse_alpha = MAX_PULSEWIDTH - (MAX_PULSEWIDTH - MIN_PULSEWIDTH) / (MAX_ANGLE_ALPHA - MIN_ANGLE_ALPHA) * (servo_angle_alpha - MIN_ANGLE_ALPHA)

        GPIO.set_servo_pulsewidth(SERVO_PIN_ALPHA, servo_pulse_alpha)
        GPIO.set_servo_pulsewidth(SERVO_PIN_GAMMA, servo_pulse_gamma)
        print("alpha: %f, gamma: %f" % (alpha, gamma))


def on_error(ws, error):
    print('[Log] Error: %s' % error)


def on_close(ws):
    print("[Log] %s" % ws)
    print('[Log] Close')


def on_open(ws):
    print('[Log] Open new connection')

    settings = {}
    with open('settings.json') as fp:
        settings = json.load(fp)

    response = {'header': {'cmd': 'connect', 'client_id': None}, 'contents': None}
    if not settings['relay']['relay_token'] == None and not settings['relay']['client_id'] == None:
        response['header']['cmd'] = 'reconnect'
        response['header']['client_id'] = settings['relay']['client_id']

    ws.send(json.dumps(response))
    print("[Log] Sended: %s" % json.dumps(response))

def main():
    settings = {}
    with open('settings.json') as fp:
        settings = json.load(fp)
    
    if not 'token' in settings:
        print('[ERROR] Setting file format error')
        return
    if not 'endpoints' in settings:
        print('[ERROR] Setting file format error')
        return
    if not 'relay_token' in settings['endpoints']:
        print('[ERROR] Setting file format error')
        return
    if not 'relay_websocket' in settings['endpoints']:
        print('[ERROR] Setting file format error')
        return
    if not 'relay' in settings:
        print('[ERROR] Setting file format error')
        return
    if not 'relay_token' in settings['relay']:
        print('[ERROR] Setting file format error')
        return
    if not 'client_id' in settings['relay']:
        print('[ERROR] Setting file format error')
        return

    if settings['relay']['relay_token'] == None:
        token = settings['token']
        endpoint = settings['endpoints']['relay_token']
        settings['relay']['relay_token'] = get_relay(token, endpoint)
        print('[Log] New relay: %s' % settings['relay']['relay_token'])
    
    with open('settings.json', mode='w') as fp:
        json.dump(settings, fp)

    websocket_endpoint = settings['endpoints']['relay_websocket'] % settings['relay']['relay_token']
    print("[Log] Endpoint: %s" % websocket_endpoint)
    ws = websocket.WebSocketApp(websocket_endpoint, on_message=on_message, on_error=on_error, on_open=on_open, on_close=on_close)
    ws.run_forever()

if __name__ == "__main__":
    websocket.enableTrace(False)
    GPIO.set_mode(SERVO_PIN_GAMMA, pigpio.OUTPUT)
    GPIO.set_mode(SERVO_PIN_ALPHA, pigpio.OUTPUT)
    main()