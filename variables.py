'''
These values are derived from my personal experience tune them to your needs.
'''



TARGET_DENSITY = 0.235
DRAWDOWN_CRITERIA=0.2
RECOVERY_CRITERIA=0.02
FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 4.236, 6.854, 11.09, 17.944]

def GET_WEIGHTS_FOR_LONGTERM_MEMORY_ORIG(drawdown_criteria=None):
    """default weights"""
    if drawdown_criteria is None:
        drawdown_criteria = DRAWDOWN_CRITERIA
    return {'crit1': {'sd': 1 / 365, 'mu': 0, 'p': 1}, 'crit2': {'sd': 1 / drawdown_criteria, 'mu': 0, 'p': 1.3}, 'crit3': {'sd': 1 / 365, 'mu': 0, 'p': 1}, 'crit4': {'sd': 1 / (365 * drawdown_criteria), 'mu': 0, 'p': 1.2}, 'crit5': {'sd': 1.3, 'mu': -2.6, 'p': 1}}

#  
DEFAULT_MEMORY_FEATURES = {'max_drawdown': {1: 0.5150874123152283, 2: 0.566382779151033, 3: 0.6531398034264879},
                           'time_since_peak': {1: 6.8089679500637335, 2: 7.651139423056396, 3: 8.308649817574022},
                           'duration': {1: 6.389924016638725, 2: 6.837994549153265, 3: 7.518228268861231},
                           'precovery': {1: -0.05884945292016635, 2: -0.525211373546828, 3: -0.7116667775865574},
                           'fib_lev':{1: -1, 2: -1, 3: -1},
                           'box01':{1: 0.45192856058112363, 2: 0.44829321386954174, 3: 0.45923949807178127}}


def GET_WEIGHTS_FOR_LONGTERM_MEMORY(drawdown_criteria=None):
    """default weights"""
    if drawdown_criteria is None:
        drawdown_criteria = DRAWDOWN_CRITERIA
    return {'crit1': {'sd': 1 / 345.477257, 'mu': 0, 'p': 0.995226003}, 'crit2': {'sd': 1 / drawdown_criteria, 'mu': 0.0934217669, 'p': 1.24536}, 'crit3': {'sd': 1 / 379.78, 'mu': -3.0448261, 'p': 1.00425408}, 'crit4': {'sd': 1 / (347.10 * drawdown_criteria), 'mu': -0.10773, 'p': 1.19487055}, 'crit5': {'sd': 1.3905, 'mu': -2.692115, 'p': 1}}
