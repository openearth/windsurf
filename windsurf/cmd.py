'''windsurf : a composite model for simulating integrated nearshore and aeolian sediment transport

Usage:
    windsurf <config> [--verbose=LEVEL]

Positional arguments:
    config             configuration file

Options:
    -h, --help         show this help message and exit
    --verbose=LEVEL    print logging messages [default: 30]

Options:
    -h, --help         show this help message and exit

'''


import logging
from model import WindsurfWrapper


def cmd():
    import docopt
    arguments = docopt.docopt(__doc__)

    # initialize logger
    if arguments['--verbose'] is not None:
        logging.basicConfig(format='%(asctime)-15s %(name)-8s %(levelname)-8s %(message)s')
        logging.root.setLevel(int(arguments['--verbose']))
    else:
        logging.root.setLevel(logging.NOTSET)

    # start model
    WindsurfWrapper(arguments['<config>']).run()
    
        
if __name__ == '__main__':
    cmd()
    
