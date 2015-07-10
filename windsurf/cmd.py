'''windsurf : a composite model for simulating integrated nearshore and aeolian sediment transport

Usage:
    windsurf <config>

Positional arguments:
    config             configuration file

Options:
    -h, --help         show this help message and exit

'''


__all__ = []


from model import Windsurf


def cmd():
    import docopt
    arguments = docopt.docopt(__doc__)

    w = Windsurf(arguments['<config>'])
    w.run()


if __name__ == '__main__':
    cmd()
    
