#!/usr/bin/env python3

import os
import socket
import select
import sys
import threading
import subprocess
import time
from typing import Callable, Any

from termcolor import cprint


class NetDogIf:
    def __init__(self, is_udp:bool = False,  is_bin:bool = False, lbstr:str = "\n", encoding="utf-8", verbose:int=0):
        self._udp: bool = is_udp
        self._is_bin: bool = is_bin
        self._lbstr:str = lbstr
        self._encoding:str = encoding
        self._verbose: int = verbose

        self._socket:  socket.socket | None = None
        self._listener: socket.socket | None = None
        self._peer_ip:str = ""
        self._peer_port:int = 0
        self._thread = {}
        self._exec_pipe = None
    
    def _vlog(self, verbose_level:int, s:str, /, prefix="<NetDog> ", fd=sys.stderr, color="dark_grey", **kwargs):
        if(self._verbose < verbose_level):
            return
        lvstr = ""
        if(verbose_level > 0):
            lvstr = f"[{verbose_level}]"
        cprint( f"{lvstr}{prefix}{s}", color, file=fd, **kwargs)

    def _exit(self, retcode:int):
        self._vlog(2, f"exit with {retcode}.")
        self.close()
        sys.exit(retcode)

    def _exit_with_error(self, msg="", error=None):
        self._vlog(1, f"[{msg} error!]({self._socket}) {error} ")
        self._exit(1)

    def _create_socket(self):
        ret = None
        try:
            if self._udp:
                self._vlog(2, "create_socket: UDP")
                ret = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:
                self._vlog(2, "create_socket: TCP")
                ret =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as error:
            self._exit_with_error("create_socket", error)
        return(ret)


    def server(self, addr, port, backlog=1):
        try:
            #socket
            self._listener = self._create_socket()
            if(self._udp):
                self._socket = self._listener
            #bind
            self._vlog(2, f"bind: {addr}:{port}")
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind((addr, port))
            #for tcp
            if(not self._udp):
                #listen
                self._listener.listen(backlog)
                self._vlog(2, f"listening...")
                #accept
                while(True):
                    rd, _, _ = select.select([self._listener], [], [], 0.5)
                    if(self._listener in rd):
                        break
                csock, peeraddr = self._listener.accept()
                (self._peer_ip, self._peer_port) = peeraddr
                self._vlog(2, f"accept...ok!, peer={self._peer_ip}:{self._peer_port}")
                self._socket = csock
        except Exception as error:
            self._exit_with_error("server", error)
    
    def client(self, addr, port):
        try:
            #socket
            self._socket = self._create_socket()
            #connect
            self._vlog(2, f"connecting... {addr}:{port}")
            self._socket.connect((addr, port))
            self._vlog(2, f"ok")
            #peer
            self._peer_ip = addr
            self._peer_port = port
        except Exception as error:
            self._exit_with_error("client", error)
    

    def exec(self, exec:str):
        assert isinstance(exec, str)
        assert len(exec)
        self.make_pipe(exec)

        def _exec_inner_recv(recvdata):
            if(isinstance(recvdata, str)):
                recvdata = recvdata.encode()
            self.write_pipe_stdin(recvdata)

        self.recv(cb=_exec_inner_recv)


        def _exec_inner_pipe_read():
            while(True):            
                #stderr
                data, size = self.read_pipe_stderr()
                if( size < 0):
                    break
                if(data):
                    self._vlog(1, f"{data}", prefix="[SubPro] ")
                #stdout
                data, size = self.read_pipe_stdout()
                if( size < 0):
                    break
                if(data):
                    self.send(data)
                #sleep                            
                time.sleep(0.01)

        self._thread["pipe_reader"] = threading.Thread(target=_exec_inner_pipe_read, name="pipe_reader", daemon=True)
        self._thread["pipe_reader"].start()
        return

    def make_pipe(self, exec):        
        self._exec_pipe = subprocess.Popen(exec, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        os.set_blocking(self._exec_pipe.stdin.fileno(), False)
        os.set_blocking(self._exec_pipe.stdout.fileno(), False)
        os.set_blocking(self._exec_pipe.stderr.fileno(), False)


    def write_pipe_stdin(self, data):
        if(self._exec_pipe is None):
            return
        self._vlog(2, f"[Pipe] --> {data}")
        self._exec_pipe.stdin.write(data)
        self._exec_pipe.stdin.flush()

    def read_pipe_stdout(self) -> str | None:
        if(self._exec_pipe is None):
            return (None, -1)
        data = self._exec_pipe.stdout.read()
        if(data is None or len(data) == 0):
            if(self._exec_pipe.poll()):
                return (None, -1)
            return(None, 0)
        self._vlog(2, f"[Pipe] <-- {data}")
        return(data, len(data))

    def read_pipe_stderr(self) -> str | None:
        if(self._exec_pipe is None):
            return (None, -1)
        data = self._exec_pipe.stderr.read()
        if(data is None or len(data) == 0):
            if(self._exec_pipe.poll()):
                return (None, -1)
            return(None, 0)
        self._vlog(2, f"[Pipe] *** {data}")
        return(data, len(data))


    def send(self, data: bytes | str, lb_conv:bool=True) -> int:
        if( not self._is_bin ):
            if( not isinstance(data, str)):
                data = data.decode(encoding=self._encoding)
            if(lb_conv and self._lbstr is not None):
                data = data.replace("\r", "").replace("\n", "")
                data += self._lbstr
        
        if(isinstance(data, str)):
            data = data.encode(encoding=self._encoding)
        
        sendsiz = 0
        if( self._socket):
            while sendsiz < len(data):
                self._vlog(3, f"send: {len(data)}byte to {self._peer_ip}:{self._peer_port}")
                self._vlog(0, f"[Send] --> {data}", prefix="", color=None) 

                try:
                    if self._udp:
                        sendsiz += self._socket.sendto(data, (self._peer_ip, self._peer_port))
                    else:
                        sendsiz += self._socket.send(data)
                except (OSError, socket.error) as error:
                    self._exit_with_error("Send", error)
        return(sendsiz)


    def recv(self, size:int=-1, bufsize=1024, cb:Callable = None ) -> str | bytearray | None:
        def _recv_inner() -> str | bytearray | None:
            self._vlog(3, f"recv:  bufsize={bufsize}, cb={cb}" )
    
            if(self._is_bin):
                data = bytearray()
            else:
                data  = ""
            
            while True:
                try:
                    if(self._udp):
                        (bdat, addr) = self._socket.recvfrom(bufsize)
                        (self._peer_ip, self._peer_port) = addr
                    else:
                        bdat  = self._socket.recv(bufsize)
                except socket.error as error:
                    self._exit_with_error("recv", error)
                
                if(len(bdat) == 0):
                    self._vlog(3, f"recv break: length=0")
                    break

                self._vlog(3, f"recv: {len(bdat)}byte from {self._peer_ip}:{self._peer_port}")
                self._vlog(0, f"[Recv] <-- {bdat}", prefix="", color=None) 
                
                if( isinstance(data, str)):
                    data += bdat.decode(encoding=self._encoding)            
                    if data.endswith("\n"):
                        self._vlog(3, f"recv break: <LF>")
                        break
                else:
                    data.append(bdat)
                    if(size == -1 or size > len(data)):
                        self._vlog(3, f"recv break: binary size")
                        break

            if(len(data) == 0):
                data = None
            return(data)
        

        ret = None
        if(cb):
            def reciver_proc():
                while(True):
                    data = _recv_inner()
                    if(data is None):
                        self._exit(0)
                        break
                    cb(data)

            self._thread["reciver"] = threading.Thread(target=reciver_proc)
            self._thread["reciver"].daemon = True
            self._thread["reciver"].start()
            ret = None
        else:
            ret = _recv_inner()
        return(ret)


    def close(self):
        if(self._socket):
            self._socket.close()
        if(self._listener):
            self._listener.close()

