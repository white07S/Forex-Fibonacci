import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import trim_mean
from variables import DRAWDOWN_CRITERIA, TARGET_DENSITY, RECOVERY_CRITERIA, FIB_LEVELS, GET_WEIGHTS_FOR_LONGTERM_MEMORY, DEFAULT_MEMORY_FEATURES

# import Fib object, and retracement-box finders
from utils import *

# import functions to support automatic finding of drawdowns
from dropdown import *

subjective_drawdown = SubjectiveDrawdown(verbose =False, target_density=TARGET_DENSITY)

# a module of fibonacci functions
def calc_fibs(hi,lo):
    """given a high, and a low, get the fibinocci extensions and retracements. """
    return (hi-lo)*np.array(FIB_LEVELS)+lo

def calc_fib_series_on_span(data, start_iloc=None, stop_iloc=None, fib_span=None, do_mask=True, drawdown_criteria = 0.2):
    """given a price series, and two indices that box-in the draw-down, it makes fibonnaci retracements"""
    if fib_span is not None:
        start_iloc, stop_iloc = fib_span
    subdata = data.iloc[start_iloc:stop_iloc]
    # get cummulative-high (notice it takes halfway between body-of-candle and wick
    cummax = get_highs(subdata).cummax()
    # get cummulative low
    cumlow = get_lows(subdata).cummin()
    # series of fibs
    fib_series_ = np.array([calc_fibs(hi,lo) for hi,lo in zip(cummax, cumlow)]).T
    # make indeices
    indices = np.arange(start_iloc, stop_iloc)
    if do_mask:
        # mask out all fibs BEFORE the 20% drawdown (because at those times, we wouldn't know we would soon be making fib-retracements
        in_drawdown = 1*(((cummax - cumlow)/cummax)>=drawdown_criteria)
        if not in_drawdown.any():
            return None,[]

        indx_start_of_credible_fib = in_drawdown.tolist().index(1)
        # new indices
        indices = indices[indx_start_of_credible_fib:]
        # truncate
        fib_series_ = fib_series_[:,indx_start_of_credible_fib:]
    assert len(indices) == fib_series_.shape[-1]
    return fib_series_, indices


# main maker of fibonacci-retracements & fibonacci-extensions
class FibonacciTechnicalAnalysis:
    """Main object that performs all steps for the automatic Fibonacci TA
    - make_fib_series: used extracting fibonacci extensions/retracements
    - make_fib_features_from_fib_series: used to create features for ML analyses based on fibs
    - make_features: combines both of the above
    """
    def __init__(self, data, drawdown_criteria, recovery_criteria=None, fib_levels=None, do_plot=False, plot_path = "/tmp/"):
        self.data = data
        if fib_levels is None:
            fib_levels = FIB_LEVELS #[0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 4.236, 6.854, 11.09]
        self.fib_levels = fib_levels
        if drawdown_criteria == 'auto':
            # find an automatic fibonacci criteria
            print("finding optimal drawdown criteria")
            try:
                optimal_drawdown_criteria,_ = subjective_drawdown.fit(data = data)
            except Exception:
                print("failed optimizing drawdown criteria, setting to default")
                optimal_drawdown_criteria = DRAWDOWN_CRITERIA

            self.drawdown_criteria = optimal_drawdown_criteria

        else:    
            self.drawdown_criteria = drawdown_criteria

        if isinstance(self.drawdown_criteria, str):
            raise ValueError("'drawdown_criteria' must be percentage 0-1 or 'auto'" )

        # % criteria to judge when a drawdown has fully recovered
        if recovery_criteria is None:
            recovery_criteria = RECOVERY_CRITERIA
        self.recovery_criteria = recovery_criteria

        # whether to make plots, and the plot path
        self.do_plot = do_plot
        self.plot_path = plot_path
    
    def make_fib(self, fib_span, make_features=True):
        """returns a Fib object, given a span between peak and recovery"""
        return Fib(fib_span=fib_span, data=self.data, drawdown_criteria=self.drawdown_criteria, fib_levels=self.fib_levels, recovery_criteria = self.recovery_criteria, make_features = make_features)
    
    def make_fib_series(self, data = None, fib_spans=None, do_plot=None, plot_path = None):
        """
        makes a list of Fibs for a dataset
        if pass a list of fib_spans, then make the series
        or, pass the data and the fib_spans will be calculated
        """
        if do_plot is None:
            do_plot = self.do_plot
        if plot_path is None:
            plot_path = self.plot_path
        if (data is None) and (fib_spans is None):
            raise ValueError("either supply argument 'data' or 'fib_spans'. Both cannot be None")
        elif fib_spans is None:
            fib_spans = find_all_retracement_boxes(data, self.drawdown_criteria, recovery_criteria=self.recovery_criteria)
        # make a list of fibs
        fib_series = [self.make_fib(fib_span) for fib_span in fib_spans]

        # remove null fibs (must pass .is_fib)
        fib_series = [fib for fib in fib_series if fib.is_fib]
        if do_plot and data is not None:

            # plot the price
            fig = plt.figure(figsize=(15,9))
            axs0 = fig.add_subplot(2,1,1)
            #axs0.plot(np.arange(data.shape[0]),np.log(data['High']))
            #axs0.plot(np.arange(data.shape[0]),np.log(data['Low']))
            axs0.plot(data.index,np.log(data['High']))
            axs0.plot(data.index,np.log(data['Low']))
            for fib in fib_series:

                # black line showing the start
                axs0.plot([data.index[fib.series_indices[0]]]*len(fib.fib_levels), np.log(fib.fib_series[:,0]),'b-')                
                for level_ in fib.fib_series:
                    #axs[0].plot(fib.series_indices, np.log(level_))
                    axs0.plot(data.index[fib.series_indices], np.log(level_))

            # also block the max drawdowns
            cummax = get_highs(data).cummax()
            vDrawdowns = (cummax - get_lows(data))/cummax

            axs1 = fig.add_subplot(2,1,2)
            #axs[1].plot(vDrawdowns)
            axs1.plot(vDrawdowns)
            for x in range(5):
                #axs[1].plot(data.index, [x/10]*data.shape[0])
                axs1.plot(data.index, [x/10]*data.shape[0])

            #plt.savefig(self.plot_path + 'fibonacci_timeseries.png')
            fig.savefig(self.plot_path + 'fibonacci_timeseries.png')
            plt.close()
        return fib_series
    
    def make_fib_features(self, fib_series=None, fib_spans=None,  weights_for_longterm_memory = None, do_plot = None, plot_path = None, prefix = "", name_mod=None, feature_defaults = None, return_memory_vectors=False, return_empirical_study=False):
        """main function, creates fibonacci-based features for machine-learning analyses"""
        
        if name_mod is None:
            name_mod = "_d"
        if do_plot is None:
            do_plot = self.do_plot
        if plot_path is None:
            plot_path = self.plot_path
        if weights_for_longterm_memory is None:
            # criteria used for building the long-term memory
            #weights_for_longterm_memory = {'crit1':{'sd':1/365,'mu':0, 'p':1}, 'crit2':{'sd':1/self.drawdown_criteria,'mu':0, 'p':1.3}, 'crit3':{'sd':1/365,'mu':0, 'p':1},  'crit4':{'sd':1/(365*self.drawdown_criteria),'mu':0,'p':1.2}, 'crit5':{'sd':1.3,'mu':-2.6, 'p':1}}            
            weights_for_longterm_memory = GET_WEIGHTS_FOR_LONGTERM_MEMORY(self.drawdown_criteria)
        else:
            weights_for_longterm_memory['crit2']['sd'] = 1/self.drawdown_criteria
            weights_for_longterm_memory['crit4']['sd'] = 1/((1/weights_for_longterm_memory['crit4']['sd'])*self.drawdown_criteria)
        # fib_series: make if not present
        if fib_series is None:
            fib_series = self.make_fib_series(data = self.data, fib_spans=fib_spans, do_plot=do_plot, plot_path = plot_path)
        # create the FibFeatures Object
        fib_features = FibFeatures(data=self.data, fib_series=fib_series, weights_for_longterm_memory = weights_for_longterm_memory, do_plot = do_plot, plot_path = plot_path, prefix = prefix, name_mod=name_mod, feature_defaults = feature_defaults)
        # option to return the memory vectors for empirical analyses
        if return_memory_vectors:
            return fib_features.features(data = self.data, return_memory = return_memory_vectors)
        #make the features        
        (master_features1, master_features2, master_features3), (featnames1, featnames2,featnames3) = fib_features.features(data = self.data, return_memory = return_memory_vectors)
        # return empiricallly derived defaults of features
        if return_empirical_study:
            return fib_features.empiricals
        return pd.DataFrame(np.concatenate((master_features1, master_features2, master_features3), axis=1), index=self.data.index, columns=featnames1 + featnames2 + featnames3)

# modified pd.get_dummies
def get_dummies(series, columns=None):
    """
    just a modified form of pd.get_dummies; allows for missing indices
    'series' is a long vector of integers representing differennt columns of a (external) pd.DataFrame
    """
    if isinstance(columns,int):
        # convert to list of integers
        columns = list(range(columns))
    if series.unique().tolist() == columns:
        # if the columns set and integer-set-in-series are the same, just run pd.get_dummies
        return pd.get_dummies(series, drop_first = False)

    #fake_series_list_expanded = series.tolist() + columns
    #fake_series_index_expanded = series.index.append(memory_mt.index[-1]  + pd.timedelta_range(start='1 day',periods=len(columns)))
    series_expanded =  series.append(pd.Series(columns, index = series.index[-1]  + pd.timedelta_range(start='1 day',periods=len(columns))))
    dummies = pd.get_dummies(series_expanded).iloc[:-len(columns)]
    assert dummies.shape[0] == series.shape[0]
    return dummies

def mask_memory_based_on_indices_in_other_memory(pd_attr, memory_indices, fill):
    """this masks-out columns in pd_attr using the (column)indcies in 'memory_indices', filling them with 'fill';
    if memory_indices is a pandas.core.series.Series, then it is the non-recursive format
    if memory_indices is a list, then it is the recursive application of them
    """
    if isinstance(memory_indices, pd.core.series.Series):
        if fill ==0:
            #mask_ = 1-pd.get_dummies(memory_indices, drop_first=False)
            mask_ = 1-get_dummies(memory_indices, columns = pd_attr.shape[-1])
            masked_attr = pd_attr*mask_[pd_attr.index[0]:]
            return masked_attr
        elif fill>0:
            #mask_ = pd.get_dummies(memory_indices, drop_first=False)*fill+1
            mask_ = get_dummies(memory_indices, columns = pd_attr.shape[-1])*fill+1
            masked_attr = pd_attr*mask_[pd_attr.index[0]:]
            return masked_attr
        elif fill<0:
            # if fill<0, then we must first zero-out the pd_attr-regions and then add/insert the desired-fil
            mask_ = get_dummies(memory_indices, columns = pd_attr.shape[-1])
            mask_ = mask_[pd_attr.index[0]:]
            masked_attr = pd_attr*(1-mask_) + mask_*fill
            return masked_attr
    elif isinstance(memory_indices, list):
        # recursion: notice is it updating 'masked_attr'
        assert isinstance(memory_indices[0], pd.core.series.Series)
        masked_attr = pd_attr.copy()
        for memory_index in memory_indices:
            masked_attr = mask_memory_based_on_indices_in_other_memory(masked_attr, memory_index, fill)
            
        return masked_attr

def rescale_criteria(criteria_vector, wt):
    """scales/weights the criteria when building indices that make Fib features"""
    # want to insert a time-multiplier
    return (criteria_vector*wt['sd'] - wt['mu'])**wt['p']

def tx_feature(x, feature_name):
    return np.log(x+1) if feature_name in ['duration', 'time_since_peak'] else x

def numpy_trimmed_mean(array, trim=0.1):
    """ trim values and take mean"""
    # get bottom and top 10% quantiles
    #qlow, qhi = np.quantile(array, [trim,1-trim])
    #
    # case1 if there is no diversity, then the qlow and qhi will be equal
    #if qlow == qhi:
    #    return array.mean()
    #
    #return array[np.where((array > qlow) & (array < qhi))[0]].mean()
    return trim_mean(array, proportiontocut = trim)

def fibs_get_default_features(names_of_features_to_return = None, which_memory=None):
    """returns default-values for ['max_drawdown', 'time_since_peak', 'duration', 'precovery'] for those price-points before any fibonacci-retracement/extension has happened
    these should be empiricially calculated based on "average" retracements/extensions 
    """
    if which_memory is None:
        which_memory = 1
    
    # extract default features (memory) for this memory
    default_features = {featnm:memory_values[which_memory] for featnm,memory_values in DEFAULT_MEMORY_FEATURES.items()}
    #default_features = {'max_drawdown': [0.2,0.2,0.2][which_memory], 'time_since_peak':[6.0,6.0,6.0][which_memory],  'duration':[3,3,3][which_memory], 'precovery':[-0.3,-0.3,-0.3][which_memory], 'fib_lev':[-1,-1,-1][which_memory], 'topdist':[0.22,0.22,0.22][which_memory], 'botdist':[0.091,0.091,0.091][which_memory]}
    
    if names_of_features_to_return is None:
        return default_features
    
    return {k:default_features[k] for k in names_of_features_to_return}

#class
class MemoryArray(np.ndarray):
    """subclass of numpy.array, but which a few more functions and attributes"""
    def __new__(
        cls,
        data,
        memory_sequence=1,
        credible_start = 10**10,
        credible_start_loc = None,
        time_indices = None,
        ):
        self = np.asarray(data).view(cls)
        self.memory_sequence = memory_sequence
        self.credible_start = credible_start
        self.credible_start_loc = credible_start_loc
        self.time_indices = time_indices
        
        return self
    
    def update_credible_start(self, credible_start, credible_start_loc=None):
        """track """
        if isinstance(credible_start, (float, np.float64)):
            credible_start = int(credible_start)

        if isinstance(credible_start, (int, np.int64)):
            if self.credible_start is None:
                self.credible_start = int(credible_start)
            else:
                self.credible_start = min(self.credible_start, int(credible_start))

        elif isinstance(credible_start, pd._libs.tslibs.timestamps.Timestamp):
            if self.credible_start_loc is None:
                self.credible_start_loc = credible_start
            else:
                self.credible_start_loc = min(self.credible_start_loc,credible_start)
        if credible_start_loc is not None:
            if self.credible_start_loc is None:
                self.credible_start_loc = credible_start_loc
            else:
                self.credible_start_loc = min(self.credible_start_loc,credible_start_loc)
    
    def numpy(self):
        """ return as an np.array"""
        return np.asarray(self)


class FeatureArray(np.ndarray):
    """subclass of numpy.array, but which a few more functions and attributes"""
    def __new__(
        cls,
        data,
        columns = None,
        memory_sequence=1,
        credible_start = 10**10,
        credible_start_loc = None,
        time_indices = None,
        ):
        self = np.asarray(data).view(cls)
        self.columns = columns
        self.memory_sequence = memory_sequence
        self.credible_start = credible_start
        self.credible_start_loc = credible_start_loc
        self.time_indices = time_indices
        
        return self
    
    def update_credible_start(self, credible_start, credible_start_loc=None):
        """track """
        if isinstance(credible_start, int):
            self.credible_start = min(self.credible_start, credible_start)
        elif isinstance(credible_start, pd._libs.tslibs.timestamps.Timestamp):
            if self.credible_start_loc is None:
                self.credible_start_loc = credible_start
            else:
                self.credible_start_loc = min(self.credible_start_loc,credible_start)
        if credible_start_loc is not None:
            if self.credible_start_loc is None:
                self.credible_start_loc = credible_start_loc
            else:
                self.credible_start_loc = min(self.credible_start_loc,credible_start_loc)
    
    def numpy(self):
        """ return as an np.array"""
        return np.asarray(self)
    
    def insert(self, data, iterable, column=None):
        if isinstance(column,int):
            self[iterable,column] = data
        elif isinstance(column,str) and (column in self.columns):
            self[iterable, self.columns.index(column)] = data
    
    def get(self, iterable, column=None):
        if isinstance(column,int):
            return self.numpy()[iterable,column]
        
        elif isinstance(column,str) and (column in self.columns):
            return self.numpy()[iterable, self.columns.index(column)]

def make_default_features(nrows, ncols=None, default_features=None, which_memory=None, names_of_features_to_return = None):
    """ makes an empty numpy array with feature defaults"""
    if default_features is None:
        # fill with these defaults
        default_features = fibs_get_default_features(which_memory=which_memory)
    
    if names_of_features_to_return is None:
        names_of_features_to_return = ['max_drawdown', 'time_since_peak', 'duration', 'precovery', 'fib_lev', 'box01']#'topdist', 'botdist']
    
    if ncols is None:
        ncols = len(names_of_features_to_return)
    
    assert ncols ==  len(names_of_features_to_return)
    
    # initialize new empty array
    features = np.empty((nrows,ncols),dtype=np.float64)
    
    # fill the columns with default values
    for i_col,featnm in enumerate(names_of_features_to_return):
        
        features[:,i_col].fill(default_features[featnm])
    
    return FeatureArray(features, columns = names_of_features_to_return)

class FibFeatures:
    """ """
    def __init__(self, data, fib_series, weights_for_longterm_memory = None, do_plot = False, plot_path = "/tmp/", prefix = "", name_mod=None, feature_defaults = None, do_log_transform_fib_levels=True):
        """
        fib_series: list of Fibs
        weights_for_longterm_memory: constants, used to classify which retracements 
        """
        # time indices,
        self.data_indices = data.index
        # total number of points
        self.n_total = data.shape[0] #fib_series[0].n_total
        # fib_series
        self.fib_series = fib_series
        # names of features
        self.nm_features = ['max_drawdown', 'time_since_peak', 'duration', 'precovery', 'fib_lev']
        # suffix to modify feature names
        if name_mod is None:
            name_mod = "_d"
        self.name_mod=name_mod
        self.do_plot = do_plot
        # get the fibonacci fib_lelves
        self.fib_levels = FIB_LEVELS#fib_series[0].fib_levels
        self.n_levels = len(self.fib_levels)
        # number of fibs in fib_series
        self.n_fibs = len(fib_series)
        # whether to do a semi-log transformation of fib_levels indicator:
        # .. np.log(1+2* FIB_LEVEL)-1 # ensures -1 is base
        self.do_log_transform_fib_levels = do_log_transform_fib_levels
        # if there are any drawdowns/fib-retracements
        if self.n_fibs>0:
            
            # Recovery and Drawdown criteria: get from fib objects
            self.drawdown_criteria = fib_series[0].drawdown_criteria
            self.recovery_criteria = fib_series[0].recovery_criteria
            # default weighting-coefficients  building the longterm memory
            if weights_for_longterm_memory is None:
                # criteria used for building the long-term memory
                #weights_for_longterm_memory = {'crit1':{'sd':1/365,'mu':0, 'p':1},  'crit2':{'sd':1/self.drawdown_criteria,'mu':0, 'p':1.3}, 'crit3':{'sd':1/365,'mu':0, 'p':1},  'crit4':{'sd':1/(365*self.drawdown_criteria),'mu':0,'p':1.2}, 'crit5':{'sd':1.3,'mu':-2.6, 'p':1}}
                weights_for_longterm_memory = GET_WEIGHTS_FOR_LONGTERM_MEMORY(self.drawdown_criteria)
            else:
                weights_for_longterm_memory['crit2']['sd'] = 1/self.drawdown_criteria
                weights_for_longterm_memory['crit4']['sd'] = 1/((1/weights_for_longterm_memory['crit4']['sd'])*self.drawdown_criteria)
            self.weights_for_longterm_memory = weights_for_longterm_memory
            # path to save plots
            self.plot_path = plot_path
            if plot_path is not None and self.do_plot:
                self.do_plot = os.path.isdir(plot_path)
                self.plot_path = os.path.join(self.plot_path, prefix)
                print(f'WARNING: making PLOTS in {self.plot_path}')

            # monitor empirical (mean) values
            self.empiricals = {'max_drawdown':[], 'time_since_peak':[], 'duration':[], 'precovery':[], 'box01':[]} #'topdist':[], 'botdist':[]}

            # set up features used to build of time-series of retracements
            self._collect_fib_attrs(fib_series, inplace=True)
    
    def _return_defaults(self, which_memory_return_default = None, return_memory_vectors=False):
        """returns default values for features, if the time-series doesn't have enough data to make fibonacci retracements & extensions"""
        if which_memory_return_default is None:
            which_memory_return_default = [1,2,3]
        
        if isinstance(which_memory_return_default,int):
            which_memory_return_default = [which_memory_return_default]
        
        # make empty (dummy) memories
        if return_memory_vectors:
            # make
            memory_arrays_defaults = [MemoryArray(data=-1*np.ones([self.n_levels, self.n_total]), memory_sequence = i) for i in which_memory_return_default]
            if len(memory_arrays_defaults)==1:
                return memory_arrays_defaults[0]
            return memory_arrays_defaults
        
        # make features with constant (default) values
        master_features_default = [make_default_features(nrows=self.n_total, default_features=fibs_get_default_features(which_memory=which_memory)) for which_memory in which_memory_return_default]
        
        # get features-names for defaults 
        nm_features_default = [['fib-%d_%s%s' % (i,nm_,self.name_mod) for nm_ in fd.columns] for fd,i in zip(master_features_default, which_memory_return_default)]
        
        if len(master_features_default)==1:
            return master_features_default[0], nm_features_default[0]
        
        # return default features and names of features
        return master_features_default, nm_features_default
    
    def _collect_fib_attrs(self, fib_series, inplace=True):
        """collect features from a fibonacci-series"""
        # find which fibs are 1 2 or 3
        self.fib_attrs = {'max_drawdown':None, 'time_since_peak':None, 'recovered':None, 'precovery':None,'duration':None, 'volume':None}
        # loop through fibs, get the attrs
        for fibattr_ in self.fib_attrs:

            # collect the time series of attributes for all the Fibs in FibSeries
            self.fib_attrs[fibattr_] = pd.concat({i:fib.features[fibattr_] for i,fib in enumerate(fib_series)},axis=1)
        if not inplace:
            return fib_attrs
    
    def _get_shortterm_memory(self):
        """short-term memory: tracks the current Fibonacci"""
        # S/T criteria 1: lowest time to peak
        if 'memory_st' in dir(self):
            return self.memory_st
        
        if self.n_fibs>=1:
            # if there is at least one drawdown
            return self.fib_attrs['time_since_peak'].fillna(10**9).idxmin(axis=1)
        
        self.memory_st = self._return_defaults(1,True)
        return self.memory_st
    
    def _get_medterm_memory(self, memory_st=None):
        """med-term memory: tracks the 1-lag Fibonacci"""
        if 'memory_mt' in dir(self):
            return self.memory_mt
        
        # check that there are more fibs that 1 (otherwise, there can't be a medium-term memory
        if self.n_fibs>=2:
            
            # earliest qualifying date for a medterm_memory
            self.loc_credible_med_term = self.fib_series[1].loc_start_of_credible_fib
            
            memory_st = self._get_shortterm_memory()
            
            # indicator: medium term memory 
            memory_mt = mask_memory_based_on_indices_in_other_memory( pd_attr=self.fib_attrs['time_since_peak'][self.loc_credible_med_term:].fillna(10**9),memory_indices=memory_st, fill=10**10).idxmin(axis=1)
            self.memory_mt = memory_mt
            return memory_mt
        
        else:
            self.memory_mt = self._return_defaults(2,True)
            return self.memory_mt
    
    def _get_longterm_crit1(self):
        """LT criteria 1: is NOT recovered and oldest-> take the oldest NOT recovered (weight) """
        memory_st = self._get_shortterm_memory()
        memory_mt = self._get_medterm_memory()            
        if self.n_fibs>=2:
            
            self.loc_credible_lt = self.fib_series[2].loc_start_of_credible_fib
            
            # check is not recovered from drawdown
            lt_crit1 = rescale_criteria((1-self.fib_attrs['recovered']).fillna(0)*(self.fib_attrs['time_since_peak'].fillna(0)), wt = self.weights_for_longterm_memory['crit1'])[self.loc_credible_lt:]
            
            # mask out: short-term memory
            lt_crit1 = mask_memory_based_on_indices_in_other_memory(pd_attr=lt_crit1, memory_indices=[memory_st, memory_mt], fill=0)
            
            if self.do_plot:
                # save criteria 1 as a plot to inspect
                plt.figure(figsize=(15,9))
                plt.plot(lt_crit1)
                plt.legend([str(k) for k in lt_crit1.columns]);
                plt.savefig(self.plot_path + 'LTmem3_crit1.png')
                plt.close()
            
            return lt_crit1
        else:
            return None
    
    def _get_longterm_crit2(self):
        """ LONG-TERM CRITERIA 2: deep-draw down"""
        memory_st = self._get_shortterm_memory() 
        memory_mt = self._get_medterm_memory()
        
        if self.n_fibs>=2:
            
            self.loc_credible_lt = self.fib_series[2].loc_start_of_credible_fib
            
            lt_crit2 = rescale_criteria(self.fib_attrs['max_drawdown'], wt = self.weights_for_longterm_memory['crit2'])[self.loc_credible_lt:]
            
            lt_crit2 = mask_memory_based_on_indices_in_other_memory(pd_attr=lt_crit2, memory_indices=[memory_st, memory_mt], fill=0)
            
            if self.do_plot:
                # save criteria 1 as a plot to inspect
                plt.figure(figsize=(15,9))
                plt.plot(lt_crit2)
                plt.legend([str(k) for k in lt_crit2.columns]);
                plt.savefig(self.plot_path + 'LTmem3_crit2.png')
                plt.close()
            
            return lt_crit2
        else:
            return None
    
    def _get_longterm_crit3(self):
        """ LONG-TERM CRITERIA 3: long-duration draw-down"""
        memory_st = self._get_shortterm_memory() 
        memory_mt = self._get_medterm_memory()
        
        if self.n_fibs>=2:
            
            self.loc_credible_lt = self.fib_series[2].loc_start_of_credible_fib
            
            lt_crit3 = rescale_criteria(self.fib_attrs['duration'], wt = self.weights_for_longterm_memory['crit3'])[self.loc_credible_lt:]
            
            lt_crit3 = mask_memory_based_on_indices_in_other_memory(pd_attr=lt_crit3, memory_indices=[memory_st,memory_mt], fill=0)
            
            if self.do_plot:
                # save criteria 1 as a plot to inspect
                plt.figure(figsize=(15,9))
                plt.plot(lt_crit3)
                plt.legend([str(k) for k in lt_crit3.columns]);
                plt.savefig(self.plot_path + 'LTmem3_crit3.png')
                plt.close()
            
            return lt_crit3
        else:
            return None
    
    def _get_longterm_crit4(self):
        """ LONG-TERM CRITERIA 4: total volume (drawdown % x time-in-drawdown)"""
        memory_st = self._get_shortterm_memory() 
        memory_mt = self._get_medterm_memory()
        
        if self.n_fibs>=2:
            
            self.loc_credible_lt = self.fib_series[2].loc_start_of_credible_fib
            
            lt_crit4 = rescale_criteria(self.fib_attrs['volume'], wt = self.weights_for_longterm_memory['crit4'])[self.loc_credible_lt:]
            lt_crit4 = mask_memory_based_on_indices_in_other_memory(pd_attr=lt_crit4, memory_indices=[memory_st, memory_mt], fill=0)
            
            if self.do_plot:
                # save criteria 1 as a plot to inspect
                plt.figure(figsize=(15,9))
                plt.plot(lt_crit4)
                plt.legend([str(k) for k in lt_crit4.columns]);
                plt.savefig(self.plot_path + 'LTmem3_crit4.png')
                plt.close()
            
            return lt_crit4
        else:
            return None
    
    def _get_longterm_crit5(self):
        """ LONG-TERM CRITERIA 5: distance above recovery level, with decay by time"""
        memory_st = self._get_shortterm_memory()
        memory_mt = self._get_medterm_memory()

        if self.n_fibs < 2:
            return None
        # get the start of credible beginning of fib
        self.loc_credible_lt = self.fib_series[2].loc_start_of_credible_fib

        # get basis of the lt_crit5
        attr_precovery_decayed_by_time = self.fib_attrs['precovery']

        # rescale lt_crit5
        lt_crit5 = rescale_criteria(attr_precovery_decayed_by_time,
                                    wt = self.weights_for_longterm_memory['crit5'])

        # smooth out the precovery by a rolling window
        lt_crit5 = lt_crit5.rolling(window= 4, center=False, min_periods =1).mean()[self.loc_credible_lt:]

        # get min to serve as fill
        min_to_fill_for_lt_crit5 = float(lt_crit5.min().min())
        min_to_fill_for_lt_crit5 = min_to_fill_for_lt_crit5*1.3 if min_to_fill_for_lt_crit5<0 else min_to_fill_for_lt_crit5*0.75
        # mask out: med-term memory
        lt_crit5 = mask_memory_based_on_indices_in_other_memory(pd_attr = lt_crit5, memory_indices = [memory_st,memory_mt], fill = min_to_fill_for_lt_crit5) 

        if self.do_plot:
            # save criteria 1 as a plot to inspect
            plt.figure(figsize=(15,9))
            plt.plot(lt_crit5)
            plt.legend([str(k) for k in lt_crit5.columns]);
            plt.savefig(self.plot_path + 'LTmem3_crit5.png')
            plt.close()

        return lt_crit5
    
    def _get_longterm_memory(self, memory_st = None, memory_mt = None):
        """long-term memory: tracks the 2-lag Fibonacci"""
        if 'memory_lt' in dir(self):
            return self.memory_lt
        
        if self.n_fibs<3:
            # return defaults empty if less than 3 fib-retracements
            self.memory_lt = self._return_defaults(3,True)
            return self.memory_lt
        
        lt_crit1 = self._get_longterm_crit1()
        lt_crit2 = self._get_longterm_crit2()
        lt_crit3 = self._get_longterm_crit3()
        lt_crit4 = self._get_longterm_crit4()
        lt_crit5 = self._get_longterm_crit5()
        lt_crit = lt_crit1 +lt_crit2 + lt_crit3 + lt_crit4 + lt_crit5
        if self.do_plot:
            plt.figure(figsize=(15,9))
            plt.plot(lt_crit)
            plt.legend([str(k) for k in lt_crit.columns]);    
            plt.savefig(self.plot_path + 'LTmem3_crit.png')
            plt.close()
            
        # fill nas: notice I fill NAs with the minimum values (because we select by maximizing)
        memory_lt = lt_crit.fillna(float(lt_crit.min().min())).idxmax(axis=1)
        self.memory_lt = memory_lt
        
        if self.do_plot:
            plt.figure(figsize=(15,9))
            plt.plot(memory_lt)
            plt.savefig(self.plot_path + 'LTmem3.png')
            plt.close()
        
        return memory_lt
    



    
