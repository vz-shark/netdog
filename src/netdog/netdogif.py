#!/usr/bin/env python3

import os
import socket
import select
import sys
import threading
import subprocess
import time
from typing import Callable, Literal

from termcolor import cprint


class Singleton(object):
    def __new__(cls, *args, **kargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance
    
class VLogger(Singleton):
    def __init__(self):
        self._verbose = 0

    def set_verbose(self, verbose:int):
        self._verbose = verbose

    def __call__(self, verbose_level:int, s:str, /, prefix="<NetDog> ", fd=sys.stderr, color="dark_grey", **kwargs):
        if(self._verbose < verbose_level):
            return
        lvstr = ""
        if(verbose_level > 0):
            lvstr = f"[{verbose_level}]"
        cprint( f"{lvstr}{prefix}{s}", color, file=fd, **kwargs)


vlog = VLogger()



class LineBuf:
    def __init__(self, lb: Literal["\n", "\r\n", "\r"]   ="\n", encoding="utf-8"):
        self._lb = lb
        self._encoding = encoding
        self._buf = ""
    
    def write(self, data:str | bytearray | bytes):
        if(not isinstance(data, str)):
            data = data.decode(encoding=self._encoding)
        self._buf += data
    
    def line_count(self):
        lns = self._buf.split(self._lb)
        return(len(lns))

    def readline(self, data: str | bytearray | bytes | None = "") -> str:
        if(data is None):
            return(None)
        if(len(data)):
            self.write(data)
        lns = self._buf.split(self._lb)
        if(len(lns) != 0):
            self._buf = self._buf[ len(lns[0] + self._lb) :]
            return(lns[0].replace("\r", "").replace("\n", ""))
        return("")



class NetIf:
    def __init__(self, is_udp:bool = False):
        self._udp: bool = is_udp

        self._socket:  socket.socket | None = None
        self._listener: socket.socket | None = None
        self._peer_ip:str = ""
        self._peer_port:int = 0
        self._threads = {}


    def _sock_error(self, msg="", error=None):
        vlog(1, f"[{msg} error!]({self._socket}) {error} ")

    def _create_socket(self):
        ret = None
        try:
            if self._udp:
                vlog(2, "create_socket: UDP")
                ret = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:
                vlog(2, "create_socket: TCP")
                ret =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as error:
            self._sock_error("create_socket", error)
        return(ret)


    def server(self, addr, port, backlog=1):
        try:
            #socket
            self._listener = self._create_socket()
            if(self._udp):
                self._socket = self._listener
            #bind
            vlog(2, f"bind: {addr}:{port}")
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind((addr, port))
            #for tcp
            if(not self._udp):
                #listen
                self._listener.listen(backlog)
                vlog(2, f"listening...")
                #accept
                while(True):
                    rd, _, _ = select.select([self._listener], [], [], 0.5)
                    if(self._listener in rd):
                        break
                csock, peeraddr = self._listener.accept()
                (self._peer_ip, self._peer_port) = peeraddr
                vlog(2, f"accept...ok!, peer={self._peer_ip}:{self._peer_port}")
                self._socket = csock
        except Exception as error:
            self._sock_error("server", error)
    
    def client(self, addr, port):
        try:
            #socket
            self._socket = self._create_socket()
            #connect
            vlog(2, f"connecting... {addr}:{port}")
            self._socket.connect((addr, port))
            vlog(2, f"ok")
            #peer
            self._peer_ip = addr
            self._peer_port = port
        except Exception as error:
            self._sock_error("client", error)
    

    def send(self, data: bytes) -> int:
        sendsiz = 0
        if( self._socket):
            while sendsiz < len(data):
                vlog(3, f"send: {len(data)}byte to {self._peer_ip}:{self._peer_port}")
                vlog(0, f"[Send] --> {data}", prefix="", color=None) 
                try:
                    if self._udp:
                        sendsiz += self._socket.sendto(data, (self._peer_ip, self._peer_port))
                    else:
                        sendsiz += self._socket.send(data)
                except (OSError, socket.error) as error:
                    self._sock_error("Send", error)
        return(sendsiz)


    def recv(self, bufsize=1024) -> bytearray | None:
        data = bytes()
        try:
            if(self._udp):
                (data, addr) = self._socket.recvfrom(bufsize)
                (self._peer_ip, self._peer_port) = addr
            else:
                data  = self._socket.recv(bufsize)
        except socket.error as error:
            self._sock_error("recv", error)
        
        if(len(data) == 0):
            return(None)

        vlog(3, f"recv: {len(data)}byte from {self._peer_ip}:{self._peer_port}")
        vlog(0, f"[Recv] <-- {data}", prefix="", color=None)             
        return(data)


    def recv_cb(self, cb:Callable, bufsize=1024) -> threading.Thread:
        def _inner_reciver():
            while(True):
                data = self.recv()
                if(data is None):
                    break
                cb(data)
            return

        self._threads["reciver"] = threading.Thread(target=_inner_reciver)
        self._threads["reciver"].daemon = True
        self._threads["reciver"].start()
        return(self._threads["reciver"])

    def shutdown(self):
        if(self._socket):
            self._socket.close()
        if(self._listener):
            self._listener.close()



class PipeIf:
    def __init__(self):
        self._threads = {}
        self._execstr = None
        self._pipe = None    
    
    def open(self, exec:str):
        self._execstr = exec
        self._pipe = subprocess.Popen(self._execstr, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        os.set_blocking(self._pipe.stdin.fileno(), False)
        os.set_blocking(self._pipe.stdout.fileno(), False)
        os.set_blocking(self._pipe.stderr.fileno(), False)

    def write_stdin(self, data):
        if(self._pipe is None):
            return
        vlog(2, f"[Pipe] --> {data}")
        self._pipe.stdin.write(data)
        self._pipe.stdin.flush()

    def read_stdout(self) -> str | None:
        if(self._pipe is None):
            return (None)
        data = self._pipe.stdout.read()
        if(data is None or len(data) == 0):
            if(self._pipe.poll()):
                return (None)
            return("")
        vlog(2, f"[Pipe] <-- {data}")
        return(data)

    def read_stderr(self) -> str | None:
        if(self._pipe is None):
            return (None)
        data = self._pipe.stderr.read()
        if(data is None or len(data) == 0):
            if(self._pipe.poll()):
                return (None)
            return("")
        vlog(2, f"[Pipe] *** {data}")
        return(data)

    def read_cb(self, outcb:Callable | None = None, errcb:Callable | None = None):
        def _inner_reader():
            while(True):            
                #stderr
                data = self.read_stderr()
                if( data is None):
                    break
                if(data):
                    if(errcb):
                        errcb(data)

                #stdout
                data = self.read_stdout()
                if( data is None):
                    break
                if(data):
                    if(outcb):
                        outcb(data)
                
                time.sleep(0.01)

        self._threads["reader"] = threading.Thread(target=_inner_reader, name="pipe_reader")
        self._threads["reader"].daemon = True
        self._threads["reader"].start()
        return(self._threads["reader"])






class App:
    def __init__(self, 
                 port: int, 
                 addr:str = "", 
                 is_server:bool = False, 
                 is_udp:bool = False, 
                 exec:str = "", 
                 lbnet:str = "\n", 
                 lbsub:str = "\n",
                 encoding="utf-8", 
                 verbose:int=0):
        
        #set logger verbose level
        vlog.set_verbose(verbose=verbose)

        self.port = port
        self.addr = addr

        self._is_server: bool = is_server
        self._is_udp: bool = is_udp,

        self._exec = exec
        self._lbnet:str = lbnet
        self._lbsub:str = lbsub
        self._encoding:str = encoding
        self._verbose: int = verbose

        self._netif = NetIf()
        self._pipeif = PipeIf() 
        self._lbbuf_recv = LineBuf()
        self._lbbuf_read_stdout = LineBuf()
        self._lbbuf_read_stderr = LineBuf()
        self._threads = {}

        if(not self.addr):
            if(self._is_server):  self.addr = "0.0.0.0"
            else:                 self.addr = "127.0.0.1"
                

    def start(self):
        # wait peer 
        if(self._is_server):
            self._netif.server(self.addr, self.port)
        else:
            self._netif.client(self.addr, self.port)

        #setup recv
        self._setup_recv()

        #setup exec
        if(self._exec):
            self._setup_exec()
        
        #keyboad input
        while(True):
            inp = input()
            self.send_withlb(inp)

    def _setup_recv(self):
        def _inner_cb_recv(data:bytearray):
            data = data.decode(encoding=self._encoding)
            data = self._lbbuf_recv.readline(data)
            self.write_withlb(data)
            return        
 
        self._netif.recv_cb(_inner_cb_recv)

    def _setup_exec(self):
        def _inner_cb_read_stdout(data:bytearray):
            data = data.decode(encoding=self._encoding)
            data = self._lbbuf_read_stdout.readline(data)
            self.send_withlb(data)
            return

        def _inner_cb_read_stderr(data:bytearray):
            data = data.decode(encoding=self._encoding)
            data = self._lbbuf_read_stderr.readline(data)
            self.print_from_sub(data)
            return

        self._pipeif.open(self._exec)
        self._pipeif.read_cb(_inner_cb_read_stdout, _inner_cb_read_stderr)


    def send_withlb(self, data:str):
        data += self._lbnet
        self._netif.send(data.encode(encoding=self._encoding))
        
    def write_withlb(self, data:str):
        data = data.rstrip("\r\n")
        data += self._lbsub
        self._pipeif.write_stdin(data.encode(encoding=self._encoding))

    def print_from_sub(self, data:str): 
        ls = data.split(self._lbsub)
        for one in ls:
            one = one.rstrip("\r\n")
            vlog(1, one, prefix="<SubPro>")   
