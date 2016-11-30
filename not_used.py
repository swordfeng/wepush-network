
# States:
#   0 - init
#   1 - syn_sent
#   2 - syn_recv
#   3 - connected
class UTPSocket:
    sockets = {}
    def handle_message(data, addr, proto):
        if len(data) < 20: # less than a header
            return
        type_ver, ext, connection_id, time, timediff, wnd_size, seq_nr, ack_nr = struct.unpack('!BBHIIIHH', data)
        typ = type_ver >> 4
        ver = type_ver & 0xf
        exts = []
        pointer = 20
        try:
            while ext != 0:
                next_ext, length = struct.unpack('!HH', data[pointer:])
                extdata = data[pointer+4:pointer+4+length]
                exts.append((ext, extdata))
                ext = next_ext
                pointer = pointer + length
                if pointer > len(data):
                    return
        except:
            return
        if typ == 4: # SYN
            if connection_id + 1 in sockets:
                # do reset
            sock = UTPSocket(connection_id, connection_id + 1, addr, proto)
            # handle crypto setup
        else:
            if connection_id not in sockets:
                # send reset
                return
            sock = sockets[connection_id]
            if typ == 1: # FIN
                # close socket, send fin if we have not
            elif typ == 0: # DATA
                sock = UTPSocket.getSocket(connection_id)
                # update cc
                # if sack update cc
                # put data into buffer, if has continous data notify upper
            elif typ == 2: # STATE
                sock = UTPSocket.getSocket(connection_id)
                # update cc
                # if sack update cc
                # if crypto setup handle it
            elif typ == 3: # RESET
                # do reset
    def connect(addr, proto):
        connection_id, = struct.unpack('!H', randombytes(2))
        UTPSocket(connection_id + 1, connection_id, addr, proto)
        # send SYN
    def __init__(self, send_conn_id, recv_conn_id, remote_addr, proto):
        self.send_conn_id = send_conn_id
        self.recv_conn_id = recv_conn_id
        self.remote_addr = remote_addr
        self.proto = proto
        self.state = 0
        sockets[recv_conn_id] = self
    def write(self, data):

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, is_server = False, protoFactory):
        pass
    def connection_made(self, transport):
        # this is port listening
        self.transport = transport
        pass
    def connection_lost(self, exc):
        # port is closed
        pass
    def datagram_received(self, data, addr):
        if len(data) < 20: # less than a header
            return
        UTPSocket.handle_message(data, addr, self)
    def error_received(self, exc):
        pass
