import sys


def main(argv):
    if argv[:1] == ["--version"]:
        print("greeter 0.1.0")
        return 0
    name = argv[0] if argv else "world"
    print("Hello, %s!" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
