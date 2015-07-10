import os
import json
import logging
from bmi.api import IBmi
from bmi.wrapper import BMIWrapper


# initialize log
logger = logging.getLogger(__name__)


class Windsurf(IBmi):
    '''Windsurf BMI class

    BMI compatible class for calling the Windsurf composite model.
    '''

    t = 0.

    def __init__(self, configfile=None):
        '''Initialize the class

        Parameters
        ----------
        configfile : string
            path to JSON configuration file, see :func:`~windsurf.model.Windsurf._load_configfile`
        '''
        
        self.configfile = configfile
        self._load_configfile()


    def __enter__(self):
        '''Enter the class'''

        return self
        
        
    def __exit__(self, errtype, errobj, traceback):
        '''Exit the class

        Parameters
        ----------
        errtype : type
            type representation of exception class
        errobj : Exception
            exception object
        traceback : traceback
            traceback stack
        '''

        self.finalize()
        if errobj:
            raise errobj


    def _load_configfile(self):
        '''Load configuration file

        A minimal JSON configuration file contains the following:

        .. code-block:: json

           {
               "time" : {
                   "start" : 0.0,
                   "stop"  : 3600.0
               },
               "models" : {
                   "xbeach" : {
                       "engine" : "xbeach",
                       "engine_path" : "",
                       "configfile" : "params.txt"
                   },
                   "aeolis" : {
                       "engine" : "aeolis",
                       "engine_path" : "",
                       "configfile" : "aeolis.txt"
                   }
               }
           }
        '''

        if os.path.exists(self.configfile):
            with open(self.configfile, 'r') as fp:
                config = json.load(fp)
                self.tstart = config['time']['start']
                self.tstop  = config['time']['stop']
                self.models = config['models']
        else:
            raise IOError('File not found: %s' % self.configfile)
        

    def get_current_time(self):
        return self.t

    
    def get_end_time(self):
        return self.tstart

    
    def get_start_time(self):
        return self.tstop

    
    def get_var(self):
        pass

    
    def get_var_count(self):
        pass

    
    def get_var_name(self):
        pass

    
    def get_var_rank(self):
        pass

    
    def get_var_shape(self):
        pass

    
    def get_var_type(self):
        pass

    
    def inq_compound(self):
        pass

    
    def inq_compound_field(self):
        pass

    
    def set_var(self):
        pass

    
    def set_var_index(self):
        pass

    
    def set_var_slice(self):
        pass

    
    def initialize(self):
        '''Initialize model libraries and configuration'''

        # initialize model libraries
        for name, props in self.models.iteritems():
            
            logger.info('Loading library "%s"...' % name)

            # support local libraries
            if props['engine_path'] and \
               os.path.isabs(props['engine_path']) and \
               os.path.exists(props['engine_path']):
                
                logger.debug('Adding library "%s" to path...' % props['engine_path'])
                os.environ['LD_LIBRARY_PATH'] = props['engine_path']
                os.environ['DYLD_LIBRARY_PATH'] = props['engine_path'] # Darwin

            # initialize bmi wrapper
            self.models[name]['_wrapper'] = BMIWrapper(
                engine=props['engine'],
                configfile=props['configfile'] or ''
            )

            # initialize time
            self.models[name]['_time'] = self.t

            # initialize model library
            self.models[name]['_wrapper'].initialize()

    
    def update(self, dt=-1):
        '''Step model libraries into the future

        Parameters
        ----------
        dt : float
            time step, use -1 for automatic time step
        '''

        for name, props in self.models.iteritems():

            # step
            props['_wrapper'].update(dt)

            # update time
            self.models[name]['_time'] = props['_wrapper'].get_current_time()

    
    def finalize(self):
        pass
