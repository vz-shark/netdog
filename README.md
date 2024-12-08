# netdog
It is like netcat implemented in python.

## Description  


## Install 

### Requirement

#### Dependency 
- termcolor>=2.5.0  

#### On Windows
- python >= 3.12  
Because netdog using os.set_blocking(). that function was supported on Windows since python 3.12.

### PYPI
```
pip install netdog
```

### Windows Executable file 
There is a pre-built `netdog.exe` using pyinstaller. [(Download here)](https://github.com/vz-shark/netdog/tree/main/dist_exe)

## Usage

```
$ netdog -h
usage: netdog [-l] [-u] [-C] [-h] [-V] [-v] [-e cmd] [--lbcnet {LF,CRLF,CR}] [--lbcsub {LF,CRLF,CR,auto}]
              [--encnet ENCNET] [--encsub ENCSUB]
              [hostname] port

netdog is a networking tool like netcat.

netcat compatible argument:
  hostname              Address of bind / connect to.
  port                  Port to listen, forward or connect to
  -l, --listen          Listen mode: Enable listen mode for inbound connects
  -u, --udp             UDP mode
  -C, --crlf            same as '--lbcnet CRLF'
  -h, --help            Show this help message and exit
  -V, --version         Show version information and exit

netdog extended argument.:
  -v, --verbose         Verbose. Use -vv or -vvv for more verbosity.
  -e cmd, --exec cmd    Execute command
  --lbcnet {LF,CRLF,CR}
                        Line break code for network.    (default: LF)
  --lbcsub {LF,CRLF,CR,auto}
                        Line break code for subprocess. (default: auto)
  --encnet ENCNET       Encoding for network.    (default: 'utf-8')
  --encsub ENCSUB       Encoding for subprocess. (default: 'utf-8')

[Examples]:

* Delegate application layer behavior to other programs via stdin/stdout of subprocess.
  In other words, using PIPE to make correspond recv() to stdin, and correspond stdout to send().

  The following is an example of a simple HTTP GET method.

    > netdog -v -e 'python -u httpget.py' 127.0.0.1 80

    ---httpget.py---
    print("GET / HTTP/1.1\r\n", end="")
    while(True):
      res = input()
      print(f"response = {res}", file=sys.stderr)
    ----------------

```
