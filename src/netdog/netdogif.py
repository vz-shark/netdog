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

class ThreadManager(Singleton):
    def __init__(self):
        self._threads = {}
        self._setup_observer()
    
    def __setitem__(self, key, value):
        self._threads[key] = value
    
    def __getitem__(self, key):
        return(self._threads[key])

    def __str__(self):
        ret = { k: v.is_alive() for k,v in self._threads.items() }
        return(str(ret))

    def _setup_observer(self):
        def _proc_observer():
            oldsts = {}
            while(True):
                newsts = { k: v.is_alive() for k,v in self._threads.items() }
                if(str(newsts) != str(oldsts)):
                    vlog(3, f"new={newsts}, old={oldsts}" ,prefix="<ThreadManagerObserver>")
                    oldsts = newsts
                time.sleep(0.1)
        
        th = threading.Thread(target=_proc_observer, daemon=True)
        #self.__setitem__("_observer", th)
        th.start()
    
    def is_all_alive(self):
        stss =  [ v.is_alive() for v in self._threads.values() ]
        return( all(stss) )
    
    def is_any_dead(self):
        return(not self.is_all_alive())

    def clear(self):
        for k,v in self._threads.items():
            if(v.is_alive()):
                vlog(3, f"clear(): leek: {k} : {v}" ,prefix="<ThreadManagerObserver>")
        self._threads = {}



vlog = VLogger()
thdmng = ThreadManager()




def get_aline(data:str, lb:str="\n"):
    pos = data.find(lb)
    if(pos < 0):
        return("")
    return(data[0: pos+len(lb)])

class LineBuf:
    def __init__(self, lb: Literal["\n", "\r\n", "\r"] ="\n"):
        self._lb = lb
        self._buf = ""
    
    def write(self, data:str | None) -> int:
        assert isinstance(data, (str, None)), f"data is unexpected type: {type(data)}"
        if(data is None):
            return(-1)
        self._buf += data
        return(len(data))
     
    def readline(self, keepends=False) -> str | None:
        aline = get_aline(self._buf, lb=self._lb)
        if(aline):
            self._buf = self._buf[ len(aline) :]
            if(keepends is False):
                aline = aline.rstrip("\r\n")
            return(aline)
        return(None)

    def readline_with_write(self, data:str|None, keepends=False) -> tuple[int, str | None]:
        retint = self.write(data)
        retstr = self.readline(keepends=keepends)
        return(retint, retstr)


class NetIf:
    def __init__(self, is_udp:bool = False):
        self._udp: bool = is_udp
        self._socket:  socket.socket | None = None
        self._listener: socket.socket | None = None
        self._peer_ip:str = ""
        self._peer_port:int = 0


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

        thdmng["reciver"] = threading.Thread(target=_inner_reciver, daemon=True)
        thdmng["reciver"].start()
        return(thdmng["reciver"])

    def shutdown(self):
        if(self._socket):
            self._socket.close()
        if(self._listener):
            self._listener.close()



class PipeIf:
    def __init__(self):
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

        thdmng["reader"] = threading.Thread(target=_inner_reader, name="pipe_reader", daemon=True)
        thdmng["reader"].start()
        return(thdmng["reader"])






class App:
    def __init__(self, 
                 port: int, 
                 addr:str = "", 
                 is_server:bool = False, 
                 is_udp:bool = False, 
                 exec:str = "", 
                 lbnet:str = "\n", 
                 lbsub:str = "\n",
                 encnet:str="utf-8", 
                 encsub:str="utf-8", 
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
        self._encnet:str = encnet
        self._encsub:str = encsub
        self._verbose: int = verbose

        self._netif = NetIf()
        self._pipeif = PipeIf() 
        self._lbbuf_recv = LineBuf(lb=self._lbnet)
        self._lbbuf_read_stdout = LineBuf(lb=self._lbsub)
        self._lbbuf_read_stderr = LineBuf(lb=self._lbsub)

        if(not self.addr):
            if(self._is_server):  self.addr = "0.0.0.0"
            else:                 self.addr = "127.0.0.1"
                

    def start(self):
        def _proc_start():
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
            
            #setup keyin
            self._setup_keyin()

            #main thread loop
            while(True):
                time.sleep(0.1)
                if( thdmng.is_any_dead() ):
                    break
        
        _proc_start()
        
        # for i in range(2):
        #     print(f"###START### {i}")
        #     thdmng.clear()
        #     th = threading.Thread(target=_proc_start, daemon=True)
        #     th.start()
        #     print(f"### start")    
        #     th.join()
        #     print(f"### join")
        #     print("**1**", thdmng)
        #     time.sleep(5)
        #     print("**2**", thdmng)


    
    def _setup_keyin(self):
        def _proc_keyin():
            while(True):
                inp = input()
                self.send_withlb(inp)
        
        thdmng["keyin"] = threading.Thread(target=_proc_keyin, daemon=True)
        thdmng["keyin"].start()
        return(thdmng["keyin"])


    def _setup_recv(self):
        def _inner_cb_recv(data:bytearray):
            data = data.decode(encoding=self._encnet)
            alen, aline = self._lbbuf_recv.readline_with_write(data)
            if(aline is not None ):
                self.write_withlb(aline)
            return        
 
        self._netif.recv_cb(_inner_cb_recv)


    def _setup_exec(self):
        def _inner_cb_read_stdout(data:bytearray):
            data = data.decode(encoding=self._encsub)
            alen, aline = self._lbbuf_read_stdout.readline_with_write(data)
            if(aline is not None ):
                self.send_withlb(aline)
            return

        def _inner_cb_read_stderr(data:bytearray):
            data = data.decode(encoding=self._encsub)
            alen, aline = self._lbbuf_read_stderr.readline_with_write(data)
            if(aline is not None):
                self.print_from_sub(aline)
            return

        self._pipeif.open(self._exec)
        self._pipeif.read_cb(_inner_cb_read_stdout, _inner_cb_read_stderr)


    def send_withlb(self, data:str):
        data += self._lbnet
        self._netif.send(data.encode(encoding=self._encnet))
        

    def write_withlb(self, data:str):
        data = data.rstrip("\r\n")
        data += self._lbsub
        self._pipeif.write_stdin(data.encode(encoding=self._encsub))


    def print_from_sub(self, data:str): 
        ls = data.split(self._lbsub)
        for one in ls:
            one = one.rstrip("\r\n")
            vlog(1, one, prefix="<SubPro>")   
