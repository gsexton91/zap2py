import argparse
import sys
from dataclasses import dataclass

from zap2py.core.parser import Engine


@dataclass
class Options:
    a: bool = False; A: str | None = None; b: bool = False; B: int | None = None
    c: str = "cache"; C: str | None = None; d: int = 7; D: bool = False
    e: bool = False; E: str | None = None; F: bool = False; g: bool = False
    i: str | None = None; I: bool = False; j: bool = False; J: str | None = None
    l: str = "en"; L: bool = False; m: int = 0; M: bool = False
    n: int = 0; N: int = 0; o: str = "xmltv.xml"; O: bool = False
    p: str | None = None; P: str | None = None; q: bool = False; R: bool = False
    r: int = 3; s: int = 0; S: float = 0.0; t: str | None = None; T: bool = False
    u: str | None = None; U: bool = False; w: bool = False; W: bool = False
    x: bool = False; Y: str | None = None; Z: str | None = None; z: bool = False
    _9: bool = False; v: bool = False


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zap2xml",
        add_help=True,
        description="Fetch XMLTV EPG data from Zap2it/Gracenote lineups."
    )

    # Boolean flags
    for flag in [
        "a","b","D","e","F","g","I","j","L","M","O","q","R","T",
        "U","w","W","x","z","_9","v"
    ]:
        p.add_argument(f"-{flag}", action="store_true")

    # String options
    p.add_argument("-A", type=str)
    p.add_argument("-C", type=str)
    p.add_argument("-E", type=str)
    p.add_argument("-J", type=str)
    p.add_argument("-o", type=str, default="xmltv.xml")
    p.add_argument("-p", type=str)
    p.add_argument("-P", type=str)
    p.add_argument("-t", type=str)
    p.add_argument("-u", type=str)
    p.add_argument("-Y", type=str)
    p.add_argument("-Z", type=str)
    p.add_argument("-c", type=str, default="cache")
    p.add_argument("-i", type=str, help="input file (optional)")
    p.add_argument("-l", type=str, default="en", help="language code")

    # Integer options
    p.add_argument("-B", type=int)
    p.add_argument("-d", type=int, default=7, help="days to grab")
    p.add_argument("-m", type=int, default=0)
    p.add_argument("-n", type=int, default=0)
    p.add_argument("-N", type=int, default=0)
    p.add_argument("-r", type=int, default=3)
    p.add_argument("-s", type=int, default=0)

    # Float options
    p.add_argument("-S", type=float, default=0.0, help="delay between requests in seconds")

    return p


def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = build_arg_parser()
    ns, _ = parser.parse_known_args(argv)
    opts = Options(**vars(ns))
    
    # Derived defaults
    opts.n = opts.d - opts.n if opts.n else 0

    # Reapply dataclass defaults for any None values
    for field_name, field_def in Options.__dataclass_fields__.items():
        if getattr(opts, field_name) is None:
            setattr(opts, field_name, field_def.default)

    # Ensure S is float
    try:
        opts.S = float(opts.S)
    except Exception:
        opts.S = 0.0

    if opts.S == 0.0:
        print("[WARN] No -S delay specified (default=0.0). "
              "Requests will be sent at full speed; may cause throttling.\n", flush=True)

    Engine(opts).run()


if __name__ == "__main__":
    main()

    