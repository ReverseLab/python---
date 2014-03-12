"""
USB Missile Launcher Python Interface

written by Pedram Amini <pamini@tippingpoint.com>
http://dvlabs.tippingpoint.com/blog/2009/02/12/python-interfacing-a-usb-missile-launcher
"""

import ctypes
import struct
import time

class missile:
    def __init__ (self, debug=False):
        self.hid        = ctypes.WinDLL(r"C:\Program Files\USB Missile Launcher\usbhid.dll")
        self.launcher   = self.hid.OpenHID(0x0a81, 0x701, 1)
        self.debug      = debug
        self.HORIZONTAL = 947
        self.VERTICAL   = 91
        self.cmd_map    = \
        {
            "down"  : 0x01,
            "up"    : 0x02,
            "left"  : 0x04,
            "right" : 0x08,
            "fire"  : 0x10,
            "stop"  : 0x20,
            "start" : 0x40,
        }

    def _dbg (self, msg):
        if self.debug:
            print msg

    def _read (self):
        num_bytes = ctypes.create_string_buffer(16)
        read_buff = ctypes.create_string_buffer(2)

        ctypes.windll.kernel32.ReadFile(self.launcher, ctypes.pointer(read_buff), 2, ctypes.pointer(num_bytes), 0)
        self._dbg("read %02x%02x" % (ord(read_buff.raw[0]), ord(read_buff.raw[1])))
        return struct.unpack(">h", read_buff.raw)[0]

    def _write (self, what):
        num_bytes = ctypes.create_string_buffer(16)

        ctypes.windll.kernel32.WriteFile(self.launcher, ctypes.pointer(what), 2, ctypes.pointer(num_bytes), 0)
        self._dbg("writing %02x%02x" % (ord(what.raw[0]), ord(what.raw[1])))

    def command (self, cmd, percent=None):
        last_read = 0

        if cmd.lower() in ["up", "down"]:
            if percent == None:
                percent = 10
        elif cmd.lower() in ["left", "right"]:
            if percent == None:
                percent = 2
        elif cmd.lower() == "fire":
            pass
        else:
            return last_read

        start   = ctypes.create_string_buffer(struct.pack(">h", self.cmd_map["start"]))
        command = ctypes.create_string_buffer(struct.pack(">h", self.cmd_map[cmd.lower()]))
        stop    = ctypes.create_string_buffer(struct.pack(">h", self.cmd_map["stop"]))

        self._write(start)
        self._read()
        self._write(command)

        if cmd.lower() == "fire":
            while 1:
                time.sleep(.1)
                self._write(start)
                last_read = self._read()
                if last_read == self.cmd_map["fire"]:
                    break
        else:
            if percent == 0:
                steps = 1
            elif cmd.lower() in ["left", "right"]:
                steps = int(percent * .01 * self.HORIZONTAL)
            else:
                steps = int(percent * .01 * self.VERTICAL)

            for i in xrange(steps):
                self._write(start)
                last_read = self._read()

        self._write(stop)
        return last_read

    def reset (self):
        """
        XXX - NOT FINISHED YET
        """

        # make sure we have some leeway to move left and to move down.
        self.command("right", 1)
        self.command("up",    1)

        # all the way left.
        print "left"
        while 1:
            ret = self.command("left", 1)
            print ret
            if ret != 0x00:
                break

        # all the way down.
        print "down"
        while 1:
            ret = self.command("down", 1)
            print ret
            if ret == 0x00:
                break

        # half way up and half way right
        self.command("right", 50)
        self.command("up",    50)


########################################################################################################################
if __name__ == "__main__":
    while 1:
        mode = raw_input("[w]eb server or [s]ocket or [c]ommand line? ").lower()

        if mode[0] in ["w", "s", "c"]:
            break

    m = missile(debug=False)

    def command_processor(cmd):
        percent = None
        if " " in cmd:
            try:
                percent = int(cmd.split(" ", 1)[1])
            except:
                pass

        if cmd.startswith("l"):
            m.command("left", percent)
            return True
        elif cmd.startswith("r"):
            m.command("right", percent)
            return True
        elif cmd.startswith("u"):
            m.command("up", percent)
            return True
        elif cmd.startswith("d"):
            m.command("down", percent)
            return True
        elif cmd.startswith("f"):
            m.command("fire")
            return True
        elif cmd.startswith("s"):
            m.reset()
            return True

        return False

    if mode.startswith("w"):
        import BaseHTTPServer
        import threading

        class web_interface_handler (BaseHTTPServer.BaseHTTPRequestHandler):
            def __init__(self, request, client_address, server):
                BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, request, client_address, server)
                self.missile = None

            def do_GET (self):
                self.do_everything()

            def do_HEAD (self):
                self.do_everything()

            def do_POST (self):
                self.do_everything()

            def do_everything (self):
                if "up" in self.path:
                    self.missile.command("up")
                if "down" in self.path:
                    self.missile.command("down")
                if "left" in self.path:
                    self.missile.command("left")
                if "right" in self.path:
                    self.missile.command("right")
                if "fire" in self.path:
                    self.missile.command("fire")

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

                response = """
                <table border=0 cellpadding=20 cellspacing=0 style="font-size: 10em;">
                    <tr><td></td><td><a href="/up">U</a></td><td></td></tr>
                    <tr><td><a href="/left">L</a></td><td><a href="/fire">F</a></td><td><a href="/right">R</a></td></tr>
                    <tr><td></td><td><a href="/down">D</a></td><td></td></tr>
                </table>
                """

                self.wfile.write(response)

        class web_interface_server (BaseHTTPServer.HTTPServer):
            def __init__(self, server_address, RequestHandlerClass, missile):
                BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
                self.RequestHandlerClass.missile = missile

        class web_interface_thread (threading.Thread):
            def __init__ (self, missile):
                threading.Thread.__init__(self)

                self.missile = missile
                self.server  = None

            def run (self):
                self.server = web_interface_server(('', 12345), web_interface_handler, self.missile)
                self.server.serve_forever()

        t = web_interface_thread(m)
        t.start()

    elif mode.startswith("c"):
        while 1:
            cmd = raw_input("cmd> ").lower()

            if cmd == "exit":
                break
            elif command_processor(cmd):
                pass
            elif cmd.startswith("e"):
                ret = eval(cmd.split(" ", 1)[1])
                print "eval returned: %02x" % ret
            else:
                print "valid commands [l]eft [r]ight [u]p [d]own [f]ire re[s]et [e]val <expression>"
    else:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 12345))
        sock.listen(5)

        print "[*] missile control listening on 0.0.0.0:12345"

        while 1:
            client_sock, client_address = sock.accept()
            print "[*] client connection from %s to missile control" % client_address[0]
            client_sock.send("TSRT MISSILE COMMAND... READY\n")
            auth = False

            while 1:
                try:
                    msg = None
                    cmd = client_sock.recv(1024).lower().rstrip()

                    if not cmd:
                        raise Exception
                except:
                    print "[*] client disconnected"

                print "[*] missile received command: %s" % cmd

                if not auth:
                    if cmd == "password":
                        auth = True
                        msg  = "AUTHORIZATION ACCEPTED\n"
                    else:
                        msg  = "UNAUTHORIZED\n"

                elif cmd == "exit":
                    client_sock.close()
                    break
                elif command_processor(cmd):
                    pass
                else:
                    msg = "valid commands [l]eft [r]ight [u]p [d]own [f]ire re[s]et\n"

                if msg:
                    try:
                        client_sock.send(msg)
                    except:
                        print "[*] client disconnected"
                        break
