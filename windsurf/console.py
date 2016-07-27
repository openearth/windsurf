import docopt
import logging
from model import WindsurfWrapper
from configurator import WindsurfConfigurator


logging.basicConfig(filename='windsurf.log',
                    format='%(asctime)-15s %(name)-8s %(levelname)-8s %(message)s')


def windsurf():
    '''windsurf : a composite model for simulating integrated nearshore and aeolian sediment transport

    Usage:
        windsurf <config> [--callback=FUNC] [--restart=FILE] [--verbose=LEVEL]

    Positional arguments:
        config             configuration file

    Options:
        -h, --help         show this help message and exit
        --callback=FUNC    reference to callback function (e.g. example/callback.py:callback)
        --restart=FILE     use restart file from previous run
        --verbose=LEVEL    print logging messages [default: 30]

    '''
    
    arguments = docopt.docopt(windsurf.__doc__)

    # initialize logger
    if arguments['--verbose'] is not None:
        logging.root.setLevel(int(arguments['--verbose']))
    else:
        logging.root.setLevel(logging.NOTSET)

    # start model
    model = WindsurfWrapper(configfile=arguments['<config>'],
                            restartfile=arguments['--restart'])
    model.run(callback=arguments['--callback'])


def windsurf_setup():
    '''windsurf-setup : a model setup wizard for the windsurf model

    Usage:
        windsurf-setup

    Options:
        -h, --help         show this help message and exit

    '''

    arguments = docopt.docopt(windsurf_setup.__doc__)

    # start configurator
    print WindsurfConfigurator().wizard()
    
        
if __name__ == '__main__':
    windsurf()
    
