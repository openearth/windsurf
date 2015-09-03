import os
import re
import json
import logging
import itertools
import numpy as np
from mako.template import Template


# initialize log
logger = logging.getLogger(__name__)


class WindsurfConfigurator:

    
    n = 0 # question counter
    
    supported_models = {
        'xbeach':'xbeach',
        'xbeachmi':'xbeachmi.model.XBeachMI',
        'aeolis':'aeolis',
        'cdm':'cdm'
    }

    time = {}
    models = {}
    exchange = []
    regimes = {}
    scenario = []
    netcdf = {}

    
    def __init__(self):
        pass


    def add_models(self, models):
        if type(models) is not list:
            models = [models]
        for model in models:
            if model not in self.supported_models.keys():
                logger.warn('Skipping unsupported model [%s]' % model)
            else:
                self.models[model] = {'engine':self.supported_models[model],
                                      'configfile':'%s.txt' % model}


    def add_exchanges(self, model_from, model_to, params):
        for param in params:
            p1, p2 = [x.strip() for x in param.split('=')]
            self.exchange.append({
                'var_from':'%s.%s' % (model_from, p1),
                'var_to':'%s.%s' % (model_to, p2)
            })
            
        
    def add_regimes(self, regimes):
        if type(regimes) is not list:
            regimes = [regimes]
        for regime in regimes:
            self.regimes[regime] = {}


    def add_params(self, regime, model, params):
        self.regimes[regime][model] = {}
        for param in params:
            k, v = [x.strip() for x in param.split('=')]
            if re.match('^[\d\-\+]$', v):
                v = int(v)
            elif re.match('^[\d\.\-\+e]$', v):
                v = float(v)
            self.regimes[regime][model][k] = v


    def compile_json(self):

        cfg = {
            'time':self.time,
            'models':self.models,
            'exchange':self.exchange,
            'regimes':self.regimes,
            'scenario':self.scenario,
            'netcdf':self.netcdf
        }

        return json.dumps(cfg, indent=4, sort_keys=True)

    
    def wizard(self):

        # http://www.patorjk.com/software/taag/
        # font: Colossal

        self.disp(
            self.get_message('WELCOME')
        )
        
        models = self.input(
            self.get_message('MODELCORES'),
            default=sorted(self.supported_models.keys()),
            multiple=True
        )

        self.add_models(models)

        for i, (a, b) in enumerate(itertools.permutations(self.models, 2)):
            exchanges = self.input(
                self.get_message('EXCHANGES', i=i, model_from=a, model_to=b),
                multiple=True
            )

            self.add_exchanges(a, b, exchanges)

        regimes = self.input(
            self.get_message('REGIMES'),
            default=['calm', 'storm'],
            multiple=True
        )

        self.add_regimes(regimes)

        for regime in self.regimes:

            self.disp(
                self.get_message('CAPTION', caption='Configuration of regime "%s"' % regime)
            )

            models = self.input(
                self.get_message('MODELCORES_IN_REGIME', regime=regime),
                default=sorted(self.models.keys()),
                multiple=True)

            for model in models:

                params = self.input(
                    self.get_message('PARAMS_IN_MODELCORE', model=model, regime=regime),
                    multiple=True)

                self.add_params(regime, model, params)

        return self.compile_json()
            

    def input(self, q, default=None, multiple=False):

        # increase question counter
        self.n += 1

        # add default value to description
        if default is not None:
            if type(default) is list:
                defaultstr = ', '.join(default)
            elif type(default) is not str:
                defaulttr = str(default)
                
            q = '%s\n\nDefault: %s' % (q, defaultstr)

        # add prompt
        q = '%s\n\n>> ' % q

        # set indentation
        q = '\n%3d: %s' % (self.n, re.sub('\n *', '\n     ', q))

        # ask for user input
        a = []
        r = ''
        while True:
            r = raw_input(q).strip().lower()
            q = '      > '
            if len(r) > 0:
                a.append(r)
            if len(r) == 0 or not multiple:
                break

        # use default if no answer is given
        if len(a) == 0 and default is not None:
            a = default

        # parse answer
        for i in range(len(a)):
            if type(a[i]) is str:
                if re.match('^[\d\.\-\+e]$', a[i]):
                    a[i] = float(a[i])

        if multiple:
            return a
        else:
            return a[0]


    def disp(self, msg):
        print msg

        
    def get_message(self, message, **markers):
        template = Template(filename=os.path.join(os.path.split(__file__)[0],
                                                  'wizard_questions.tmpl'))
        markers['_MESSAGE'] = message
        return template.render(**markers).strip()
        
