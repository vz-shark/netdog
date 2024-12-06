#!/usr/bin/env python3

import argparse
import sys

import netdog


PGNAME = "netdog"

VERSION = netdog.__version__

def get_version():
    return f"{PGNAME} {VERSION}"

EPILOG = r"""
[Examples]:

* Delegate application layer behavior to other programs via stdin/stdout of subprocess.
  In other words, using PIPE to make correspond recv() to stdin, and correspond stdout to send().   

  The following is an example of a simple HTTP GET method.  
    
    > %(prog)s -v -e 'python -u httpget.py' 127.0.0.1 80        
    
    ---httpget.py---
    print("GET / HTTP/1.1\r\n", end="")
    while(True): 
      res = input()
      print(f"response = {res}", file=sys.stderr)
    ----------------
    
"""% ({"prog": PGNAME})



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
    optional.add_argument("-C", "--crlf", action="store_true", help="same as '--lbnet CRLF'")
#   optional.add_argument("-b", "--binary", action="store_true", help="Binary mode") #Not implemented.
    optional.add_argument("--lbnet", type=str, choices=["LF", "CRLF", "CR"], default="", help="Line break code for network.    (default: LF)")
    optional.add_argument("--lbsub", type=str, choices=["LF", "CRLF", "CR"], default="", help="Line break code for subprocess. (default: LF)")
    optional.add_argument("-v", "--verbose", action="count", default=0, help="Verbose. Use -vv or -vvv for more verbosity.")   
    optional.add_argument("--encnet", type=str, default="utf-8", help="Encoding for network.    (default: 'utf-8')")
    optional.add_argument("--encsub", type=str, default="utf-8", help="Encoding for subprocess. (default: 'utf-8')")
    
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

    #line break
    lbchg = {
        "":         "\n",
        "LF":       "\n",
        "CRLF":     "\r\n",
        "CR":       "\r",
    }

    #lb_net
    if(args.crlf and args.lbnet):
        parser.print_usage()
        print("%s: error: -C and --lbnet and --crlf  are exclusive." % (PGNAME), file=sys.stderr)
        sys.exit(1)
    if(args.crlf):
        args.lbnet = "CRLF"
    args.lbnet = lbchg[args.lbnet]

    #lb_sub
    args.lbsub = lbchg[args.lbsub]

    #hostname
    if( args.hostname is None):
        args.hostname = "0.0.0.0"

    #print args
    if(args.verbose >= 3):
        print(args)


    return args


def main():
    args = get_args()
    app = netdog.App(
            args.port,
            args.hostname, 
            is_server = args.listen,
            is_udp = args.udp, 
            lbnet = args.lbnet, 
            lbsub = args.lbsub, 
            encnet = args.encnet,
            encsub = args.encsub,
            verbose = args.verbose, 
            exec = args.exec
        )
    app.start()

if __name__ == "__main__":
    main()