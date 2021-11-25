from hpack import Encoder, Decoder

e = Encoder()

headers = [
    (':method', 'GET'),
    (':path', '/'),
    (':authority', "192.168.139.133"),
    (':scheme', 'http'),
    ('user-agent', 'a'*3997)
]
encoded_bytes = e.encode(headers)
print(len(encoded_bytes))
#print(encoded_bytes.hex())
for i in range(2):
    encoded_bytes = e.encode(headers)
    print(len(encoded_bytes))
    print(encoded_bytes.hex())