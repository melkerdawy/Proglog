"""Implements the generic progress logger class, and the ProgressBar class.
"""

from tqdm import tqdm, tqdm_notebook
from collections import OrderedDict

SETTINGS = {
    'notebook': False
}

class ProgressLogger:
    """Generic class for progress loggers.

    A progress logger contains a "state" dictionnary.

    Parameters
    ----------
    init_state
      Dictionnary representing the initial state.
    """

    def __init__(self, init_state=None):

        self.state = {}
        if init_state is not None:
            self.state.update(init_state)

    def callback(self, **kw):
        """Execute something after the state has been updated by the given
        state elements.

        This default callback does nothing, overwrite it by subclassing
        """
        pass

    def iter(self, **kw):
        """Iterate through a list while updating the state.

        Examples
        --------

        >>> for username in logger.iter(user=['tom', 'tim', 'lea']:
        >>>     # At every loop, logger.state['user'] is updated
        >>>     print (username)

        """
        for field, iterable in kw.items():
            for it in iterable:
                self(**{field: it})
                yield it


    def __call__(self, **kw):
        self.state.update(kw)
        self.callback(**kw)

class ProgressBarLogger(ProgressLogger):
    """Generic class for progress loggers.

    A progress logger contains a "state" dictionnary

    Parameters
    ----------

    init_state
      Initial state of the logger

    bars
      Either None (will be initialized with no bar) or a list/tuple of bar
      names (``['main', 'sub']``) which will be initialized with index -1 and
      no total, or a dictionary (possibly ordered) of bars, of the form
      ``{bar_1: {title: 'bar1', index: 2, total:23}, bar_2: {...}}``

    ignored_bars
      Either None (newly met bars will be added) or a list of blacklisted bar
      names, or ``'all_others'`` to signify that all bar names not already in
      ``self.bars`` will be ignored.
    """

    def __init__(self, init_state=None, bars=None, ignored_bars=None):
        ProgressLogger.__init__(self, init_state)
        if bars is None:
            bars = OrderedDict()
        elif isinstance(bars, (list, tuple)):
            bars = OrderedDict([
                (b, dict(title=b, index=-1, total=None, message=None))
                for b in bars
            ])
        if isinstance(ignored_bars, (list, tuple)):
            ignored_bars = set(ignored_bars)
        self.ignored_bars = ignored_bars
        self.state['bars'] = bars

    @property
    def bars(self):
        """Return ``self.state['bars'].``"""
        return self.state['bars']

    def bar_is_ignored(self, bar):
        if self.ignored_bars is None:
            return False
        elif self.ignored_bars == 'all_others':
            return (bar not in self.bars)
        else:
            return bar not in self.ignored_bars

    def iter_bar(self, **kw):
        """Iterate through a list while updating a state bar.

        Examples
        --------
        >>> for username in logger.iter_bar(user=['tom', 'tim', 'lea']:
        >>>     # At every loop, logger.state['bars']['user'] is updated
        >>>     # to {index: i, total: 3, title:'user'}
        >>>     print (username)

        """
        bar, iterable = kw.popitem()

        if bar in self.ignored_bars:
            return iterable
        if hasattr(iterable, '__len__'):
            self(**{bar + '__total': len(iterable)})

        def new_iterable():
            for i, it in enumerate(iterable):
                self(**{bar + '__index': i})
                yield it
            self(**{bar + '__index': i + 1})
        return new_iterable()

    def bars_callback(self, bar, attr, value, old_value=None):
        """Execute a custom action after the progress bars are updated.

        Parameters
        ----------
        bar
          Name/ID of the bar to be modified.

        attr
          Attribute of the bar attribute to be modified

        value
          New value of the attribute

        old_value
          Previous value of this bar's attribute.

        This default callback does nothing, overwrite it by subclassing.
        """
        pass

    def __call__(self, **kw):

        items = sorted(kw.items(), key=lambda kv: not kv[0].endswith('total'))
        for key, value in items:
            if '__' in key:
                bar, attr = key.split('__')
                if bar in self.ignored_bars:
                    continue
                kw.pop(key)
                if (bar not in self.bars) and (bar not in self.ignored_bars):
                    self.bars[bar] = dict(title=bar, index=-1,
                                          total=None, message=None)
                old_value = self.bars[bar][attr]
                self.bars[bar][attr] = value
                self.bars_callback(bar, attr, value, old_value)
        self.state.update(kw)
        self.callback(**kw)

class TqdmProgressBarLogger(ProgressBarLogger):
    """Tqdm-powered progress bar for console or Notebooks.

    Parameters
    ----------
    init_state
      Initial state of the logger

    bars
      Either None (will be initialized with no bar) or a list/tuple of bar
      names (``['main', 'sub']``) which will be initialized with index -1 and
      no total, or a dictionary (possibly ordered) of bars, of the form
      ``{bar_1: {title: 'bar1', index: 2, total:23}, bar_2: {...}}``

    ignored_bars
      Either None (newly met bars will be added) or a list of blacklisted bar
      names, or ``'all_others'`` to signify that all bar names not already in
      ``self.bars`` will be ignored.


    leave_bars

    notebook
      True will make the bars look nice (HTML) in the jupyter notebook. It is
      advised to leave to 'default' as the default can be globally set from
      inside a notebook with ``import proglog; proglog.notebook_mode()``.

    print_messages
      If True, every ``logger(message='something')`` will print a message in
      the console / notebook
    """

    def __init__(self, init_state=None, bars=None, leave_bars=False,
                 ignored_bars=(), notebook='default', print_messages=True):
        ProgressBarLogger.__init__(self, init_state=init_state, bars=bars,
                                   ignored_bars=ignored_bars)
        self.leave_bars = leave_bars
        self.tqdm_bars = OrderedDict([
            (bar, None)
            for bar in self.bars
        ])
        if notebook == 'default':
            notebook = SETTINGS['notebook']
        self.notebook = notebook
        self.print_messages = print_messages
        self.tqdm = (tqdm_notebook if self.notebook else tqdm)

    def new_tqdm_bar(self, bar):
        """Create a new tqdm bar, possibly replacing an existing one."""
        if (bar in self.tqdm_bars) and (self.tqdm_bars[bar] is not None):
            self.close_tqdm_bar(bar)
        infos = self.bars[bar]
        self.tqdm_bars[bar] = self.tqdm(
           total=infos['total'],
           desc=infos['title'],
           postfix=infos['message'],
           leave=self.leave_bars
        )
    def close_tqdm_bar(self, bar):
        """Close and erase the tqdm bar"""
        self.tqdm_bars[bar].close()
        self.tqdm_bars[bar] = None

    def bars_callback(self, bar, attr, value, old_value):
        if (bar not in self.tqdm_bars) or (self.tqdm_bars[bar] is None):
            self.new_tqdm_bar(bar)
        if attr == 'index':
            if value >= old_value:
                total = self.bars[bar]['total']
                if total and (value >= total):
                    self.close_tqdm_bar(bar)
                else:
                    self.tqdm_bars[bar].update(value - old_value)


            else:
                self.new_tqdm_bar(bar)
                self.tqdm_bars[bar].update(value + 1)
        elif attr == 'message':
            self.tqdm_bars[bar].set_postfix(value)
    def callback(self, **kw):
        if self.print_messages and ('message' in kw) and kw['message']:
            self.tqdm.write(kw['message'])

class RqWorkerProgressLogger:
    def __init__(self, job):
        self.job = job
        if 'progress_data' not in self.job.meta:
            self.job.meta['progress_data'] = {}
            self.job.save()

    def callback(self, **kw):
        self.job.meta['progress_data'] = self.state
        self.job.save()

class RqWorkerBarLogger(ProgressBarLogger, RqWorkerProgressLogger):

    def __init__(self, job, init_state=None, bars=None, ignored_bars=()):
        RqWorkerBarLogger.__init__(self, job)
        ProgressBarLogger.__init__(init_state=init_state, bars=bars,
                                   ignored_bars=ignored_bars)
