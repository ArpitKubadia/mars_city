"""
Implemented following
[Wei, Li, et al. "Assumption-Free Anomaly Detection in Time Series."
SSDBM. Vol. 5. 2005.]
"""
from __future__ import division, print_function
import string
from collections import deque, namedtuple
from itertools import islice
from datetime import datetime

import numpy as np
from numpy import sqrt
from scipy.stats import norm


Analysis = namedtuple('Analysis', ['score', 'bitmp1', 'bitmp2'])


class AssumptionFreeAA(object):
    def __init__(self, word_size=10, window_factor=100,
                 lead_window_factor=3, lag_window_factor=30,
                 recursion_level=2):
        """
        window_size = word_size * window_factor
        lead_window_factor = lead_window_factor
        lead_window_size = lead_window_factor * window_size
        lag_window_factor = lag_window_factor
        lag_window_size = lag_window_factor * window_size
        universe_size = lead_window_size + lag_window_size
        """
        self._window_factor = window_factor
        self._window_size = window_factor * word_size
        self._lead_window_factor = lead_window_factor
        self._lead_window_size = lead_window_factor * self._window_size
        self._lag_window_factor = lag_window_factor
        self._lag_window_size = lag_window_factor * self._window_size
        self.universe_size = self._lead_window_size + self._lag_window_size

        self._word_size = word_size
        self._recursion_level = recursion_level
        self._lead_window = deque(maxlen=self._lead_window_size)
        self._lag_window = deque(maxlen=self._lag_window_size)

        self.last_timestamp = datetime.min


    @classmethod
    def _sax(cls, data, alphbt_size=4, word_size=10):
        """
        calculates the SAX discretization for the given data.
        Input:
            data:           sequential collection of datapoints.
                            It must be a numpy array of shape (n,)
            alphbt_size:    the size of the alphabet
            word_size:      size of each SAX word
        Output:
            List of words generated according to the SAX algorithm.
        Notes:
            based on https://gist.github.com/slnovak/912927
            by Stefan Novak
        """
        # Scale data to have a mean of 0 and a standard deviation of 1.
        scaled_data = data - np.mean(data)
        scaled_data *= 1.0/scaled_data.std()

        # Calculate our breakpoint locations.
        breakpoints = norm.ppf(np.linspace(1./alphbt_size,
                                           1-1./alphbt_size,
                                           alphbt_size-1))
        breakpoints = np.concatenate((breakpoints, np.array([np.Inf])))
        
        # Split the scaled_data into phrase_length pieces.
        scaled_data = np.array_split(scaled_data, word_size)

        # Calculate the mean for each section.  
        section_means = [np.mean(section) for section in scaled_data]

        try:
            # Figure out which break each section is in
            # based on the section_means and calculated breakpoints.                                       
            section_locations = [np.where(breakpoints > section_mean)[0][0]
                                 for section_mean in section_means]
        except:
            print("data: %s" % data)
            print("scaled_data: %s" % scaled_data)
            print("section_means: %s" % section_means)
            print("breakpoints: %s" % breakpoints)
            raise
        # Convert the location into the corresponding letter.                                   
        sax_phrases = ''.join([string.ascii_letters[ind]
                               for ind in section_locations])

        return sax_phrases


    @classmethod
    def _dist(cls, A, B):
        """
        Returns \sum_{i=0}^{n} \sum_{j=0}^{n} (A_{ij}-B_{ij})^2
        """
        return np.power(A-B, 2).sum()


    @classmethod
    def _build_combinations(cls, alphabet, combinations=set(),
                            combination_len=2):
        """
        Returns all combination_len length combinations from the
        alphabet's characters.
        """
        if len(combinations) == 0:
            combinations = set(a for a in alphabet)
            combination_len -= 1

        if combination_len <= 0:
            return combinations
        else:
            return AssumptionFreeAA._build_combinations(alphabet,
                                  set(c+a for a in alphabet
                                          for c in combinations),
                                  combination_len - 1)



    @classmethod
    def _count_substr(cls, stack, needle):
        """
        Counts occurrences of needle in stack.
        Example: in aaaa there are 3 occurrences of aa
        """
        count = 0
        for i in range(len(stack)-len(needle)+1):
            if stack[i:i+len(needle)] == needle:
                count += 1

        return count


    @classmethod
    def _count_frequencies(cls, words, alphabet, subword_len=2):
        combinations = AssumptionFreeAA._build_combinations(alphabet, set(),
                                                           subword_len)
        """
        Builds a dictionary of frequencies, looking in the list words,
        of subwords of length subword_len.
        """
        freqs = {c:0. for c in combinations}

        for word in words:
            for key in freqs:
                freqs[key] += AssumptionFreeAA._count_substr(word, key)

        return freqs


    @classmethod
    def _build_bitmap(cls, freqs):
        """
        Builds a bitmap of size len(freqs)).
        Each cell in the bitmap is proportional to the frequency of a subword.
        """
        matrix_size = sqrt(len(freqs))
        bitmap = np.zeros(shape=(matrix_size, matrix_size))
        ordered_keys = sorted(freqs.keys())

        max_value = max(freqs.values())
        i = 0
        j = 0
        for key in ordered_keys:
            if max_value != 0:
                freqs[key] /= max_value
            else:
                freqs[key] = 0

            j = j % matrix_size
            bitmap[i, j] = freqs[key]
            j += 1
            if j == matrix_size:
                i += 1

        return bitmap


    @classmethod
    def _get_words(cls, window, feature_size, word_size):
        """
        Splits window in feature_size sized chunks, calculates
        their SAX representation and returns a list with those representations.
        """
        if len(window) % feature_size != 0:
            print("%s\n%s\n%s"%(window, feature_size, word_size))
            raise Exception()
        words = []
        factor = int(len(window)/feature_size)
        for i in range(factor):
            window_slice = list(islice(window, i*feature_size, (i+1)*feature_size))
            word = cls._sax(data=np.array(window_slice), word_size=word_size)
            words.append(word)

        return words



    def detect(self, datapoints, last_timestamp):
        """
        Calculates the datapoints' anomaly score according to:
        http://alumni.cs.ucr.edu/~ratana/SSDBM05.pdf
        """
        self.last_timestamp = last_timestamp
        analysis_result = []
        for datapoint in datapoints:
            if len(self._lead_window) == self._lead_window_size:
                self._lag_window.append(self._lead_window.popleft())
            self._lead_window.append(datapoint)

            if (len(self._lead_window) == self._lead_window_size
                    and len(self._lag_window) == self._lag_window_size):
                lead_words = self._get_words(window=self._lead_window,
                                            feature_size=self._window_size,
                                            word_size=self._word_size)
                lag_words = self._get_words(self._lag_window,
                                           self._window_size,
                                           self._word_size)

                lead_freqs = self._count_frequencies(lead_words, 'abcd',
                                                    self._recursion_level)
                lag_freqs = self._count_frequencies(lag_words, 'abcd',
                                                    self._recursion_level)

                lead_bitmap = self._build_bitmap(lead_freqs)
                lag_bitmap = self._build_bitmap(lag_freqs)

                analysis_result.append(
                    Analysis(self._dist(lead_bitmap, lag_bitmap),
                            lead_bitmap,
                            lag_bitmap))

        return analysis_result