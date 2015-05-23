#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2015 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Hervé BREDIN - http://herve.niderb.fr


"""
MediaEval Person Discovery Task evaluation.

Usage:
  evaluation [options] <reference.shot> <reference.ref> <reference.eviref> <hypothesis.label> <hypothesis.evidence>

Options:
  -h --help                  Show this screen.
  --version                  Show version.
  --queries=<queries.lst>    Query list.
  --levenshtein=<threshold>  Levenshtein ratio threshold [default: 0.95]
"""

from docopt import docopt
from Levenshtein import ratio
import numpy as np

from common import loadShot, loadLabel, loadEvidence, checkSubmission
from common import loadLabelReference, loadEvidenceReference


def loadFiles(shot, reference, evireference, label, evidence):

    shot = loadShot(shot)
    label = loadLabel(label)
    evidence = loadEvidence(evidence)

    checkSubmission(shot, label, evidence)

    reference = loadLabelReference(reference)
    evireference = loadEvidenceReference(evireference)

    return shot, reference, evireference, label, evidence


def closeEnough(personName, query, threshold):
    return ratio(query, personName) >= threshold


def computeAveragePrecision(vReturned, vRelevant):

    nReturned = len(vReturned)
    nRelevant = len(vRelevant)

    if nRelevant == 0 and nReturned == 0:
        return 1.

    if nRelevant == 0 and nReturned > 0:
        return 0.

    if nReturned == 0 and nRelevant > 0:
        return 0.

    returnedIsRelevant = np.array([item in vRelevant for item in vReturned])
    precision = np.cumsum(returnedIsRelevant) / (1. + np.arange(nReturned))
    return np.sum(precision * returnedIsRelevant) / min(nReturned, nRelevant)


if __name__ == '__main__':

    arguments = docopt(__doc__, version='0.1')

    shot = arguments['<reference.shot>']
    reference = arguments['<reference.ref>']
    evireference = arguments['<reference.eviref>']
    label = arguments['<hypothesis.label>']
    evidence = arguments['<hypothesis.evidence>']
    threshold = float(arguments['--levenshtein'])

    shot, reference, evireference, label, evidence = loadFiles(
        shot, reference, evireference, label, evidence)

    if arguments['--queries']:
        with open(arguments['--queries'], 'r') as f:
            queries = [line.strip() for line in f]

    else:
        # build list of queries from reference
        queries = sorted(set(reference['personName'].unique()))

    # query --> averagePrecision dictionary
    averagePrecision = {}
    correctness = {}

    for query in queries:

        # find most similar personName
        ratios = [(personName, ratio(query, personName))
                  for personName in evidence.personName.unique()]
        best = sorted(ratios, key=lambda x: x[1], reverse=True)[0]

        personName = best[0] if best[1] > threshold else None

        if personName is None:
            averagePrecision[query] = 0.
            correctness[query] = 0.
            continue

        # =====================================================================
        # Evaluation of LABELS
        # =====================================================================

        # get relevant shots for this query, according to reference
        qRelevant = reference[reference.personName == query]
        qRelevant = qRelevant[['videoID', 'shotNumber']]
        qRelevant = set((videoID, shotNumber)
                        for _, videoID, shotNumber in qRelevant.itertuples())

        # get returned shots for this query
        # (i.e. shots containing closest personName)
        qReturned = label[label.personName == personName]

        # sort shots by decreasing confidence
        # (in case of shots returned twice for this query, keep maximum)
        qReturned = (qReturned.groupby(['videoID', 'shotNumber'])
                              .aggregate(np.max)
                              .sort(['confidence'], ascending=False))

        # get list of returned shots in decreasing confidence
        qReturned = list(qReturned.index)

        # compute average precision for this query
        averagePrecision[query] = computeAveragePrecision(qReturned,
                                                          qRelevant)

        # =====================================================================
        # Evaluation of EVIDENCES
        # =====================================================================

        # get evidence shots for this query, according to reference
        qRelevant = evireference[evireference.personName == query]
        qRelevant = qRelevant[['videoID', 'shotNumber', 'source']]

        _qRelevant = set([])
        for _, videoID, shotNumber, source in qRelevant.itertuples():

            if source == 'both':
                _qRelevant.add((videoID, shotNumber, 'audio'))
                _qRelevant.add((videoID, shotNumber, 'image'))
            else:
                _qRelevant.add((videoID, shotNumber, source))

        qRelevant = _qRelevant

        qReturned = evidence[evidence.personName == personName][['videoID', 'shotNumber', 'source']]
        for _, videoID, shotNumber, source in qReturned.itertuples():
            break

        if (videoID, shotNumber, source) in qRelevant:
            correctness[query] = best[1] if best[1] > threshold else 0.
        else:
            correctness[query] = 0.

    MAP = np.mean([averagePrecision[query] for query in queries])
    mCorrectness = np.mean([correctness[query] for query in queries])
    EwMAP = np.mean([correctness[query] * averagePrecision[query] for query in queries])

    print 'EwMAP = %.2f %%' % (100 * EwMAP)
    print 'MAP = %.2f %%' % (100 * MAP)
    print 'C = %.2f %%' % (100 * mCorrectness)
