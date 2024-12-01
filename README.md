# netdog
It is like netcat implemented in python.

## Install 

### PYPI
```
pip install netdog
```

### Windows Executable file 
There is a pre-built `netdog.exe` using pyinstaller. [(Download here)](https://github.com/vz-shark/netdog/tree/main/build_exe/)

## Usage

```
$ netdog -h
usage: netdog [-l] [-u] [-e cmd] [-C] [-b] [-v] [-h] [-V] [hostname] port

netdog is a networking tool like netcat.

positional arguments:
  hostname            Address of bind / connect to.
  port                Port to listen, forward or connect to

mode arguments:
  -l, --listen        Listen mode: Enable listen mode for inbound connects
  -u, --udp           UDP mode

optional arguments:
  -e cmd, --exec cmd  Execute command
  -C, --crlf          Send CRLF as line-endings (default: LF)
  -b, --binary        Binary mode
  -v, --verbose       Verbose. Use -vv or -vvv for more verbosity.

misc arguments:
  -h, --help          Show this help message and exit
  -V, --version       Show version information and exit

[Examples]:

* Delegate application layer behavior to other programs via stdin/stdout of subprocess.
  In other words, make stdin/stdout via PIPE correspond to recv/send.

  The following is an example of a simple HTTP GET method.

    > netdog -v -e 'python -u httpget.py' 127.0.0.1 80

    ---httpget.py---
    print("GET / HTTP/1.1\r\n", end="")
    while(True): print(f"response = {input()}", file=sys.stderr)
    ----------------

```