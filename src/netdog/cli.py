#!/usr/bin/env python3

import argparse
import sys

from netdog import NetDogIf
from netdog import __version__


PGNAME = "netdog"

VERSION = __version__

def get_version():
    return f"{PGNAME} {VERSION}"

EPILOG = r"""
[Examples]:

* Delegate application layer behavior to other programs via stdin/stdout of subprocess.
  In other words, make stdin/stdout via PIPE correspond to recv/send.
  
  The following is an example of a simple HTTP GET method.  
    
    > %(prog)s -v -e 'python -u httpget.py' 127.0.0.1 80        
    
    ---httpget.py---
    print("GET / HTTP/1.1\r\n", end="")
    while(True): print(f"response = {input()}", file=sys.stderr)
    ----------------
"""% ({"prog": PGNAME})


def app(host, port, is_listen=True, is_udp=False, bufsize=1024, verbose=0, exec=""):
    # create netdogif
    dogif = NetDogIf(is_udp=is_udp, verbose=verbose)

    # start server/client
    if(is_listen):
        dogif.server(host, port)
    else:
        dogif.client(host, port)
    
    # exec
    if(exec):
        dogif.exec(exec)
    else:
        dogif.recv(cb=lambda x: print(x, end="", flush=True))
    
    # wait keyboad input
    while True:
        inp = input()
        dogif.send(inp)



def get_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
        prog=PGNAME,
        description="netdog is a networking tool like netcat.",
        #usage=USAGE,
        epilog=EPILOG
    )

    #arugument groups
    positional = parser.add_argument_group("positional arguments")
    mode = parser.add_argument_group("mode arguments")
    optional = parser.add_argument_group("optional arguments")
    misc = parser.add_argument_group("misc arguments")

    #positional
    positional.add_argument("hostname", nargs="?", type=str, help="Address of bind / connect to.")
    positional.add_argument("port", type=int, help="Port to listen, forward or connect to")

    #mode
    mode.add_argument("-l", "--listen", action="store_true", help="Listen mode: Enable listen mode for inbound connects")
    mode.add_argument("-u", "--udp", action="store_true", help="UDP mode")

    #option
    optional.add_argument("-e", "--exec", metavar="cmd", type=str, help="Execute command")
    optional.add_argument("-C", "--crlf", action="store_true", help="Send CRLF as line-endings (default: LF)")
    optional.add_argument("-b", "--binary", action="store_true", help="Binary mode")
    optional.add_argument("-v", "--verbose", action="count", default=0, help="Verbose. Use -vv or -vvv for more verbosity.")
    
    #misc
    misc.add_argument("-h", "--help", action="help", help="Show this help message and exit")
    misc.add_argument("-V", "--version", action="version", version=get_version(), help="Show version information and exit" )
    
    #parse
    args = parser.parse_args()

    #required arguments
    if(args.hostname is None and not args.listen ):
        parser.print_usage()
        print("%s: error: the following arguments are required: hostname" % (PGNAME), file=sys.stderr)
        sys.exit(1)

    #hostname
    if( args.hostname is None):
        args.hostname = "0.0.0.0"

    return args


def main():
    args = get_args()
    app(args.hostname, args.port, is_listen=args.listen, is_udp=args.udp, verbose=args.verbose, exec=args.exec)

if __name__ == "__main__":
    main()