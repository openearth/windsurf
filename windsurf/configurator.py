import os
import re
import json
import logging
import itertools
import numpy as np
import scipy.signal
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
            model = model.lower()
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
            regime = regime.lower()
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
        
        # model cores
        models = self.input(
            self.get_message('MODELCORES'),
            default=sorted(self.supported_models.keys()),
            multiple=True
        )

        self.add_models(models)

        # variable exchange
        for i, (a, b) in enumerate(itertools.permutations(self.models, 2)):
            exchanges = self.input(
                self.get_message('EXCHANGES', i=i, model_from=a, model_to=b),
                multiple=True
            )

            self.add_exchanges(a, b, exchanges)

        # regimes
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
                self.get_message('REGIMES_MODELCORES', regime=regime),
                default=sorted(self.models.keys()),
                multiple=True)

            for model in models:

                params = self.input(
                    self.get_message('REGIMES_MODELCORES_PARAMS', model=model, regime=regime),
                    multiple=True)

                self.add_params(regime, model, params)


        # scenario
        scenario = WindsurfScenario()

        default = self.input(
            self.get_message('REGIMES_DEFAULT'),
            default=sorted(self.regimes.keys())[0])

        scenario.add_regime(default)

        for regime in self.regimes:
            if regime == default:
                continue
            else:
                timeseries_file = self.input(
                    self.get_message('REGIMES_TIMESERIES', regime=regime))
                threshold = self.input(
                    self.get_message('REGIMES_THRESHOLD', regime=regime))

                scenario.add_regime(regime)

                if os.path.exists(timeseries_file):
                    ts = np.loadtxt(timeseries_file)[:,:2]
                else:
                    print 'ERROR: file not found, skipped regime'

                scenario.add_condition(ts[:,0], ts[:,1], threshold=threshold)

        self.scenario = scenario.render_scenario()
        
        return self.compile_json()
            

    def input(self, q, default=None, multiple=False):

        # increase question counter
        self.n += 1

        # add default value to description
        if default is not None:
            if type(default) is list:
                defaultstr = ', '.join(default)
            else:
                if type(default) is not str:
                    defaultstr = str(default)
                else:
                    defaultstr = default
                default = [default]
                
            q = '%s\n\nDefault: %s' % (q, defaultstr)

        # add prompt
        q = '%s\n\n>> ' % q

        # set indentation
        q = '\n%3d: %s' % (self.n, re.sub('\n *', '\n     ', q))

        # ask for user input
        a = []
        r = ''
        while True:
            r = raw_input(q).strip()
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
        

class WindsurfScenario:


    regimes = {}
    regimes_order = []
    selected_regime = None

    
    def __init__(self, start=0., stop=3600.*24.*365, step=3600., interval=3600.*35, time=None):
        self.interval = interval
        if time is not None:
            self.t = np.asarray(time)
        else:
            self.t = np.arange(start, stop+step, step)


    def add_regime(self, regime, initialize=True):
        self.regimes_order.append(regime)
        self.regimes[regime] = np.asarray([initialize] * len(self.t))
        self.select_regime(regime)


    def select_regime(self, regime):
        if regime in self.regimes.keys():
            self.selected_regime = regime
        else:
            raise ValueError('Unknown regime [%s]' % regime)


    def add_condition(self, t, y, threshold=None, regime=None, exclude=False):

        t = np.asarray(t)
        y = np.asarray(y)
        
        # set regime
        if regime is None:
            regime = self.selected_regime

        # get all peaks
        peaks = np.asarray(scipy.signal.argrelmax(y)[0])

        # remove peaks below threshold
        if threshold is not None:
            peaks = np.delete(peaks, np.where(y[peaks] < threshold)[0])

        # add troughs in between peaks
        troughs = []
        for peak in peaks:
            t1 = t[peak] - self.interval/2
            t2 = t[peak] + self.interval/2
            idx1 = (t >= t1) & (t <= t[peak])
            idx2 = (t <= t2) & (t >= t[peak])
            troughs.append(np.where(idx1)[0][0] + np.argmin(y[idx1]))
            troughs.append(peak + np.argmin(y[idx2]))

        # join close troughs
        while True:
            idx = np.where(t[troughs[2::2]] - t[troughs[1:-1:2]] < self.interval)[0] * 2 + 1
            if len(idx) == 0:
                break
            troughs = np.delete(troughs, np.concatenate((idx, idx+1)))
        troughs = np.concatenate(([0], troughs, [len(t)]))

        # determine regimes
        idx = np.asarray(np.sum([[np.mod(i,2)==0] * n for i, n in enumerate(troughs[1:] - troughs[:-1])]))
        idx = np.interp(self.t, t, idx) >= .5 # interpolate to generic time axis
        self.regimes[regime][idx] = exclude


    def render_scenario(self):

        scenario = np.asarray([None] * len(self.t))

        for regime in self.regimes_order:
            scenario[self.regimes[regime]] = regime

        p = None
        scenario_consolidated = []
        for i, (t, s) in enumerate(zip(self.t, scenario)):
            if s != p:
                scenario_consolidated.append((t,s))
            p = s

        return scenario_consolidated
