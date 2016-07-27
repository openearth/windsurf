import os
import re
import imp
import time
import json
import shutil
import logging
import traceback
import importlib
import numpy as np
import cPickle as pickle
from bmi.api import IBmi
from bmi.wrapper import BMIWrapper
from multiprocessing import Process

import netcdf, parsers


# initialize log
logger = logging.getLogger(__name__)


class WindsurfWrapper:
    '''Windsurf class

    Main class for Windsurf model. Windsurf is a composite model for
    simulating integrated nearshore and aeolian sediment transport.

    '''

    
    regime = None
    

    def __init__(self, configfile=None, restartfile=None):
        '''Initialize the class

        Parameters
        ----------
        configfile : str
            path to JSON configuration file, see
            :func:`~windsurf.model.Windsurf.load_configfile`
        restartfile : str
            path to Pickle restart file

        '''

        self.configfile = configfile
        self.restartfile = restartfile
        self.restart = restartfile is not None


    def run(self, callback=None, subprocess=True):
        '''Spawn model time loop'''

        if subprocess:

            p = Process(target=self.start,
                        args=(callback,))
            p.start()
            p.join()

        else:
            self.start(callback)

            
    def start(self, callback=None):
        '''Start model time loop'''

        # parse callback
        callback = self.parse_callback(callback)

        self.engine = Windsurf(configfile=self.configfile)
        self.engine.initialize()

        self.t = 0
        self.i = 0
        self.iout = 0
        self.tlog = 0.0 # in real-world time
        self.tlast = 0.0 # in simulation time
        self.tstart = time.time() # in real-world time
        self.tstop = self.engine.get_end_time() # in simulation time

        self.output_init()

        if self.restart:
            self.load_restart_file()
        else:
            self.output()

        while self.t < self.tstop:
            if callback is not None:
                callback(self.engine)
            self.set_regime()
            self.engine.update()
            self.t = self.engine.get_current_time()
            self.i += 1
            self.output()
            self.progress()
            self.tlast = self.t

        self.engine.finalize()
        
        logger.debug('End of simulation')


    def set_regime(self):
        '''Set model settings according to current regime

        Checks which regime should be currently active. If the regime
        is changed, the corresponding model parameters are set.

        '''

        regimes = self.engine.get_config_value('regimes')
        scenario = self.engine.get_config_value('scenario')
        times = np.asarray([s[0] for s in scenario])
        idx = np.where(times <= self.t)[0].max()
            
        if idx >= len(scenario):
            logger.warning("Scenario too short, reusing last regime!")
            idx = len(scenario)-1
            
        if scenario[idx][1] != self.regime:
            self.regime = scenario[idx][1]
            logger.info('Switched to regime "%s"' % self.regime)

            for engine, variables in regimes[self.regime].iteritems():
                for name, value in variables.iteritems():
                    logger.debug('Set parameter "%s" in engine "%s" to "%s"' % (name,
                                                                                engine,
                                                                                value))
                    self.engine.set_var('%s.%s' % (engine, name), np.asarray(value))

        
    def parse_callback(self, callback):
        '''Parses callback definition and returns function

        The callback function can be specified in two formats:

        - As a native Python function
        - As a string refering to a Python script and function,
          separated by a colon (e.g. ``example/callback.py:function``)

        Parameters
        ----------
        callback : str or function
            Callback definition

        Returns
        -------
        function
            Python callback function

        '''

        if isinstance(callback, str):
            if ':' in callback:
                fname, func = callback.split(':')
                if os.path.exists(fname):
                    mod = imp.load_source('callback', fname)
                    if hasattr(mod, func):
                        return getattr(mod, func)
        elif hasattr(callback, '__call__'):
            return callback
        elif callback is None:
            return callback

        logger.warn('Invalid callback definition [%s]' % callback)
        return None


    def output_init(self):
        '''Initialize netCDF4 output file

        Creates an empty netCDF4 output file with the necessary
        dimensions, variables, attributes and coordinate reference
        system specification (crs).

        '''

        outputfile = self.engine.get_config_value('netcdf', 'outputfile')
        outputvars = self.engine.get_config_value('netcdf', 'outputvars')
        attributes = self.engine.get_config_value('netcdf', 'attributes')
        crs = self.engine.get_config_value('netcdf', 'crs')
        
        if outputfile is not None and outputvars is not None:
            if not self.restart or not os.path.exists(outputfile):
            
                logger.debug('Initializing output...')
        
                # get dimension names for each variable
                variables = {
                    v : { 'dimensions' : self.engine.get_dimensions(v) }
                    for v in outputvars
                }

                for v in variables.iterkeys():
                    logger.info('Creating netCDF output for "%s"' % v)

                netcdf.initialize(outputfile,
                                  self.read_dimensions(),
                                  variables=variables,
                                  attributes=attributes,
                                  crs=crs)

        
    def output(self):
        '''Write model data to netCDF4 output file'''

        # dump restart and/or backup file if requested
        times = self.engine.get_config_value('restart', 'times')
        if times is not None:
            tr = np.asarray(times)
            if self.tlast > 0. and np.any((tr <= self.t) & (tr > self.tlast)):
                self.dump_restart_file()
                if self.engine.get_config_value('restart', 'backup'):
                    self.create_backup()

        # write output if requested
        if np.mod(self.t, self.engine.tout) < self.t - self.tlast:

            outputfile = self.engine.get_config_value('netcdf', 'outputfile')
            outputvars = self.engine.get_config_value('netcdf', 'outputvars')

            if outputfile is not None and outputvars is not None:
                
                logger.debug('Writing output at t=%0.2f...' % self.t)
            
                # get dimension data for each variable
                variables = {v : self.engine.get_var(v) for v in outputvars}
                variables['time'] = self.t
        
                netcdf.append(outputfile,
                              idx=self.iout,
                              variables=variables)

                self.iout += 1
            
            
    def load_restart_file(self):
        '''Load restart file from previous run'''

        if os.path.exists(self.restartfile):
            with open(self.restartfile, 'r') as fp:
                dump = pickle.load(fp)
                
                self.engine.update(-dump['time'])
                self.t = self.engine.get_current_time()
                self.tlast = self.t
                self.iout = dump['iout']
                self.i = dump['i']
                    
                for engine, variables in dump['data'].iteritems():
                    for var, val in variables.iteritems():
                        self.engine.set_var('%s.%s' % (engine, var), val)
                        
            logger.info('Loaded restart file "%s".' % self.restartfile)
        else:
            logger.error('Restart file "%s" not found' % self.restartfile)

            
    def dump_restart_file(self):
        '''Dump restart file to start next run'''

        fname = 'restart.%d.pkl' % self.t
        if not os.path.exists(fname):

            variables = self.engine.get_config_value('restart', 'variables')
            if variables is not None:

                dump = {
                    'time' : self.t,
                    'iout' : self.iout,
                    'i' : self.i,
                    'data' : {}
                }
        
                for model in self.engine.models.iterkeys():
                    dump['data'][model] = {}

                for var in variables:
                    val = self.engine.get_var(var)
                    engine, var = self.engine._split_var(var)
                    dump['data'][engine][var] = val
            
                with open(fname, 'w') as fp:
                    pickle.dump(dump, fp)
                    
                logger.info('Written restart file "%s".' % fname)


    def create_backup(self):
        '''Create backup file of output file'''

        logger.info('Creating backup file...')

        outputfile = self.engine.get_config_value('netcdf', 'outputfile')
        if outputfile is not None:
            shutil.copyfile(outputfile, '%s~' % outputfile)

            
    def read_dimensions(self):
        '''Read dimensions of composite domain

        Parses individual model engine configuration files and read
        information regarding the dimensions of the composite domain,
        like the bathymetric grid, number of sediment fractions and
        number of bed layers.

        Returns
        -------
        dict
            dictionary with dimension variables

        '''

        dimensions = {}

        if self.engine.models.has_key('xbeach'):
            cfg_xbeach = parsers.XBeachParser(
                self.engine.models['xbeach']['configfile']).parse()
        else:
            cfg_xbeach = {}

        if self.engine.models.has_key('aeolis'):
            cfg_aeolis = parsers.AeolisParser(
                self.engine.models['aeolis']['configfile']).parse()
        else:
            cfg_aeolis = {}

        # x and y
        if len(cfg_xbeach) > 0:
            dimensions['x'] = cfg_xbeach['xfile'].reshape(
                (cfg_xbeach['ny']+1,
                 cfg_xbeach['nx']+1))[0,:]
            dimensions['y'] = cfg_xbeach['yfile'].reshape(
                (cfg_xbeach['ny']+1,
                 cfg_xbeach['nx']+1))[:,0]
        elif len(cfg_aeolis) > 0:
            dimensions['x'] = cfg_aeolis['xgrid_file'].reshape(
                (cfg_aeolis['ny']+1,
                 cfg_aeolis['nx']+1))[0,:]
            dimensions['y'] = cfg_aeolis['ygrid_file'].reshape(
                (cfg_aeolis['ny']+1,
                 cfg_aeolis['nx']+1))[:,0]
        else:
            dimensions['x'] = []
            dimensions['y'] = []

        # layers and fractions
        if len(cfg_aeolis) > 0:
            dimensions['layers'] = np.arange(cfg_aeolis['nlayers']) * \
                                   cfg_aeolis['layer_thickness']
            dimensions['fractions'] = cfg_aeolis['grain_size'][:cfg_aeolis['nfractions']]
        else:
            dimensions['layers'] = []
            dimensions['fractions'] = []

        # ensure lists
        for k, v in dimensions.iteritems():
            try:
                len(v)
            except:
                dimensions[k] = [v]
            
        return dimensions
        
        
    def progress(self, frac=.1):
        '''Log progress

        Parameters
        ----------
        frac : float
            log interval as fraction of simulation time

        '''

        if (np.mod(self.t, self.tstop * frac) < self.t - self.tlast or \
            time.time() - self.tlog > 60.):
                    
            p = min(1, self.t / self.tstop)
            dt1 = time.time() - self.tstart
            dt2 = dt1 / p
            dt3 = dt2 * (1-p)

            fmt = '[%5.1f%%] %s / %s / %s (avg. dt=%5.3f)'

            if p <= 1:
                logger.info(fmt % (p*100.,
                                   time.strftime('%H:%M:%S', time.gmtime(dt1)),
                                   time.strftime('%H:%M:%S', time.gmtime(dt2)),
                                   time.strftime('%H:%M:%S', time.gmtime(dt3)),
                                   self.t / self.i))
                        
                self.tlog = time.time()


class Windsurf(IBmi):
    '''Windsurf BMI class

    BMI compatible class for calling the Windsurf composite model.

    '''

    t = 0.0

    def __init__(self, configfile=None):
        '''Initialize the class

        Parameters
        ----------
        configfile : str
            path to JSON configuration file, see 
            :func:`~windsurf.model.Windsurf.load_configfile`

        '''
        
        self.configfile = configfile
        self.load_configfile()


    def __enter__(self):
        '''Enter the class'''
        
        self.initialize()
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


    def load_configfile(self):
        '''Load configuration file

        A JSON configuration file may contain the following:

        .. literalinclude:: ../example/windsurf.json
           :language: json

        See for more information section :ref:`configuration`.

        '''

        if os.path.exists(self.configfile):

            # store current working directory
            self.cwd = os.getcwd()

            # change working directry to location of configuration file
            if not os.path.isabs(self.configfile):
                self.configfile = os.path.abspath(self.configfile)
            fpath, fname = os.path.split(self.configfile)
            os.chdir(fpath)
            logger.debug('Changed directory to "%s"' % fpath)

            with open(fname, 'r') as fp:
                self.config = json.load(fp)
                self.tstart = self.get_config_value('time', 'start')
                self.tstop = self.get_config_value('time', 'stop')
                self.tout = self.get_config_value('netcdf', 'interval')
                self.models = self.get_config_value('models')
        else:
            raise IOError('File not found: %s' % self.configfile)
        

    def get_current_time(self):
        '''Return current model time'''
        return self.t

    
    def get_end_time(self):
        '''Return model stop time'''
        return self.tstop

    
    def get_start_time(self):
        '''Return model start time'''
        return self.tstart

    
    def get_var(self, name):
        '''Return array from model engine'''
        engine, name = self._split_var(name)
        return self.models[engine]['_wrapper'].get_var(name).copy()

    
    def get_var_count(self):
        raise NotImplemented(
            'BMI extended function "get_var_count" is not implemented yet')

    
    def get_var_name(self, i):
        raise NotImplemented(
            'BMI extended function "get_var_name" is not implemented yet')

    
    def get_var_rank(self, name):
        '''Return array rank or 0 for scalar'''
        engine, name = self._split_var(name)
        return self.models[engine]['_wrapper'].get_var_rank(name)

    
    def get_var_shape(self, name):
        '''Return array shape'''
        engine, name = self._split_var(name)
        return self.models[engine]['_wrapper'].get_var_shape(name)

    
    def get_var_type(self, name):
        '''Return type string, compatible with numpy'''
        engine, name = self._split_var(name)
        return self.models[engine]['_wrapper'].get_var_type(name)

    
    def inq_compound(self, name):
        raise NotImplemented(
            'BMI extended function "inq_compound" is not implemented yet')

    
    def inq_compound_field(self, name):
        raise NotImplemented(
            'BMI extended function "inq_compound_field" is not implemented yet')

    
    def set_var(self, name, value):
        '''Set array in model engine'''
        engine, name = self._split_var(name)
        self.models[engine]['_wrapper'].set_var(name, value)

    
    def set_var_index(self, name, index, value):
        raise NotImplemented(
            'BMI extended function "set_var_index" is not implemented yet')

    
    def set_var_slice(self, name, start, count, value):
        raise NotImplemented(
            'BMI extended function "set_var_slice" is not implemented yet')

    
    def initialize(self):
        '''Initialize model engines and configuration'''

        # initialize model engines
        for name, props in self.models.iteritems():
            
            logger.info('Loading library "%s"...' % name)

            # support local engines
            if props.has_key('engine_path') and \
               props['engine_path'] and \
               os.path.isabs(props['engine_path']) and \
               os.path.exists(props['engine_path']):
                
                logger.debug('Adding library "%s" to path...' % props['engine_path'])
                os.environ['LD_LIBRARY_PATH'] = props['engine_path']
                os.environ['DYLD_LIBRARY_PATH'] = props['engine_path'] # Darwin

            # initialize bmi wrapper
            try:
                # try external library
                self.models[name]['_wrapper'] = BMIWrapper(
                    engine=props['engine'],
                    configfile=props['configfile'] or ''
                )
            except RuntimeError:
                # try python package
                try:
                    p, c = props['engine'].rsplit('.', 1)
                    mod = importlib.import_module(p)
                    engine = getattr(mod, c)
                    self.models[name]['_wrapper'] = engine(configfile=props['configfile'] or '')
                except:
                    raise RuntimeError('Engine not found [%s]' % props['engine'])

            # initialize time
            self.models[name]['_time'] = self.t

            # initialize model engine
            self.models[name]['_wrapper'].initialize()

    
    def update(self, dt=-1):
        '''Step model engines into the future

        Step all model engines into the future and check if engines
        are at the same point in time. If not, repeat stepping into
        the future of lagging engines until all engines are
        (approximately) at the same point in time. Exchange data if
        necessary.

        Parameters
        ----------
        dt : float
            time step, use -1 for automatic time step

        '''

        t0 = self.t
        target_time = None
        engine_last = None

        for engine in self.models.iterkeys():
            self.models[engine]['_target'] = None

        # repeat update until target time step is reached for all engines
        while target_time is None or np.any([m['_time'] < target_time
                                             for m in self.models.itervalues()]):

            # determine model engine with maximum lag
            engine = self._get_engine_maxlag()
            e = self.models[engine]
            now = e['_time']

            # exchange data if another model engine is selected
            try:
                if engine != engine_last:
                    self._exchange_data(engine)
            except:
                logger.error('Failed to exchange data from "%s" to "%s"!' % (engine_last, engine))
                logger.error(traceback.format_exc())

            # step model engine in future
            try:
                e['_wrapper'].update(dt)
            except:
                logger.error('Failed to update "%s"!' % engine)
                logger.error(traceback.format_exc())

            # update time
            e['_time'] = e['_wrapper'].get_current_time()
            e['_target'] = e['_time']

            logger.debug(
                'Step engine "%s" from t=%0.2f to t=%0.2f into the future...' % (
                    engine,
                    now,
                    e['_time']))

            # determine target time step after first update
            if target_time is None and \
               np.all([m['_target'] is not None for m in self.models.itervalues()]):
                
                target_time = np.max([m['_time'] for m in self.models.itervalues()])
                logger.debug('Set target time step to t=%0.2f' % target_time)

            engine_last = engine

        self.t = np.mean([m['_time'] for m in self.models.itervalues()])
        logger.debug('Arrived in future at t=%0.2f' % self.t)


    def finalize(self):
        '''Finalize model engines'''

        # finalize model engines
        for name, props in self.models.iteritems():
            self.models[name]['_wrapper'].finalize()


    def _exchange_data(self, engine):
        '''Exchange data from all model engines to a given model engine

        Reads exchange configuration and looks for items where the
        given model engine is in the "var_to" field and reads the
        corresponding "var_from" variable from the model engine
        specified by the "var_to" variable.

        Parameters
        ----------
        engine : str
            model engine to write data to

        '''

        exchange = self.get_config_value('exchange')
        if exchange is not None:
            for ex in exchange:
                engine_to, var_to = self._split_var(ex['var_to'])
                engine_from, var_from = self._split_var(ex['var_from'])
                if engine_to == engine:
                
                    logger.debug('Exchange "%s" to "%s"' % (
                        ex['var_from'],
                        ex['var_to']))

                    try:
                        val = self.models[engine_from]['_wrapper'].get_var(var_from)
                    except:
                        logger.error('Failed to get "%s" from "%s"!' % (var_from, engine_from))
                        logger.error(traceback.format_exc())

                    try:
                        self.models[engine_to]['_wrapper'].set_var(var_to, val)
                    except:
                        logger.error('Failed to set "%s" in "%s"!' % (var_to, engine_to))
                        logger.error(traceback.format_exc())
    

    def _get_engine_maxlag(self):
        '''Get model engine with maximum lag from current time

        Returns
        -------
        str
            name of model engine with larges lag

        '''

        lag = np.inf
        engine = None
        
        for name, props in self.models.iteritems():
            if props['_time'] < lag:
                lag = props['_time']
                engine = name

        return engine


    def _split_var(self, name):
        '''Split variable name in engine and variable part

        Split a string into two strings where the first string is the
        name of the model engine that holds the variable and the
        second is the variable name itself. If the original string
        contains a dot (.) the left and right side of the dot are
        chosen as the engine and variable name respectively. If the
        original string contains no dot the default engine is chosen
        for the given variable name. If no default engine is defined
        for the given variable name a ValueError is raised.

        Parameters
        ----------
        name : str
            name of variable, including engine

        Returns
        -------
        str
            name of model engine
        str
            name of variable
        
        Examples
        --------
        >>> self._split_var('xbeach.zb')
            ('xbeach', 'zb')
        >>> self._split_var('zb')
            ('xbeach', 'zb')
        >>> self._split_var('aeolis.zb')
            ('aeolis', 'zb')
        >>> self._split_var('aeolis.Ct')
            ('aeolis', 'Ct')
        >>> self._split_var('Ct')
            ('aeolis', 'Ct')
        >>> self._split_var('aeolis.Ct.avg')
            ('aeolis', 'Ct.avg')

        '''

        parts = name.split('.')

        engine = None
        name = None
        
        if len(parts) == 1:
            name = parts[0]
        elif len(parts) == 2:
            if parts[0] in self.models.keys():
                engine, name = parts
            else:
                name = '.'.join(parts)
        else:
            engine = parts[0]
            name = '.'.join(parts)

        if engine is None:
            if name.split('.')[0] in ['Cu', 'Ct', 'supply', 'pickup', 'mass', 'uth',
                                      'uw', 'uws', 'uwn', 'udir']:
                engine = 'aeolis'
            elif name.split('.')[0] in ['zb', 'zs', 'zs0', 'H']:
                engine = 'xbeach'
            else:
                raise ValueError(
                    'Unknown variable "%s", specify engine using "<engine>.%s"' % (
                        name, name))
            
        return engine, name


    def get_config_value(self, *keys, **kwargs):
        '''Get configuration values by traversing JSON structure while checking existence

        Parameters
        ----------
        keys : str
            traverse into JSON configuration structure

        Return
        ------
        value form JSON configuration file or (partial) structure or None if non-existent

        '''

        if kwargs.has_key('cfg'):
            cfg = kwargs['cfg']
        else:
            cfg = None
            
        if cfg is None:
            cfg = self.config

        if len(keys) > 0:
            if cfg.has_key(keys[0]):
                cfg = self.get_config_value(*keys[1:], cfg=cfg[keys[0]])
            else:
                cfg = None

        return cfg
    
        
    @staticmethod
    def get_dimensions(var):

        var = var.split('.')[0]
        
        if var in ['mass']:
            dims = (u'time', u'y', u'x', u'layers', u'fractions')
        elif var in ['d10', 'd50', 'd90', 'moist', 'thlyr']:
            dims = (u'time', u'y', u'x', u'layers')
        elif var in ['Cu', 'Ct', 'uth', 'supply', 'pickup', 'p']:
            dims = (u'time', u'y', u'x', u'fractions')
        elif var in ['x', 'z', 'zb', 'zs', 'uw', 'udir', 'H']:
            dims = (u'time', u'y', u'x')
        elif var in []:
            dims = (u'time',)
        else:
            dims = (u'time', u'y', u'x')
            
        return dims
