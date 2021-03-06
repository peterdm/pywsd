#!/usr/bin/env python -*- coding: utf-8 -*-
#
# Python Word Sense Disambiguation (pyWSD)
#
# Copyright (C) 2014-2015 alvations
# URL:
# For license information, see LICENSE.md

import string
from itertools import chain

from nltk.corpus import wordnet as wn
from nltk.corpus import stopwords
from nltk import word_tokenize, pos_tag

from cosine import cosine_similarity as cos_sim
from utils import lemmatize, porter, lemmatize_sentence

def get_pos_of_ambiguous_word(context_sentence, ambiguous_word):
    return {tok.lower():pos for tok, pos in 
            pos_tag(word_tokenize(context_sentence))}[ambiguous_word][0].lower()

def compare_overlaps_greedy(context, synsets_signatures):
    """
    Calculate overlaps between the context sentence and the synset_signature
    and returns the synset with the highest overlap.
    
    Note: Greedy algorithm only keeps the best sense, see http://goo.gl/OWSfOZ
    
    Only used by original_lesk(). Keeping greedy algorithm for documentary sake, 
    because original_lesks is greedy.
    """
    max_overlaps = 0; lesk_sense = None
    for ss in synsets_signatures:
        overlaps = set(synsets_signatures[ss]).intersection(context)
        if len(overlaps) > max_overlaps:
            lesk_sense = ss
            max_overlaps = len(overlaps)    
    return lesk_sense

def compare_overlaps(context, ambiguous_word, synsets_signatures, \
                     nbest=False, keepscore=False, normalizescore=False):
    """ 
    Calculates overlaps between the context sentence and the synset_signture
    and returns a ranked list of synsets from highest overlap to lowest.
    """
    overlaplen_synsets = [] # a tuple of (len(overlap), synset).
    for ss in synsets_signatures:
        overlaps = set(synsets_signatures[ss]).intersection(context)
        overlaplen_synsets.append((len(overlaps), ss))

    # Rank synsets from highest to lowest overlap.
    ranked_synsets = sorted(overlaplen_synsets, reverse=True)

    # Normalize scores such that it's between 0 to 1. 
    if normalizescore:
        total = float(sum(i[0] for i in ranked_synsets))
        ranked_synsets = [(i/total,j) for i,j in ranked_synsets]


    if nbest: # Returns a ranked list of synsets.
        if not keepscore:
            ranked_synsets = [i[1] for i in sorted(overlaplen_synsets, \
                                                   reverse=True)]
        return ranked_synsets
    else: # Returns only the best sense.
        if len(ranked_synsets) == 0:
            return None
        tiebroken = tiebreak(ambiguous_word, ranked_synsets)
        if not keepscore:
            return tiebroken[1]
        else:
            return tiebroken

def tiebreak(ambiguous_word, ranked_synsets):  # use ambiguous word as a tiebreaker
    first_ranked = ranked_synsets[0]
    most_overlaps = first_ranked[0]

    for ranked_ss in ranked_synsets:
        if ranked_ss[0] < most_overlaps:
            return first_ranked # highest overlap
        else: # equal
            if ranked_ss[1].name() == ambiguous_word + '.n.01': # if the most common sense is tied, use that
                return ranked_ss
            if ranked_ss[1].name().startswith(ambiguous_word + '.n.'): # otherwise any sense  which has the word in it's name
                first_ranked = ranked_ss

    return first_ranked


def original_lesk(context_sentence, ambiguous_word, dictionary=None):
    """
    This function is the implementation of the original Lesk algorithm (1986).
    It requires a dictionary which contains the definition of the different
    sense of each word. See http://goo.gl/8TB15wb
    """
    ambiguous_word = lemmatize(ambiguous_word)
    # If dictionary is not provided, use the WN defintion.
    if not dictionary:
        dictionary = {}
        for ss in wn.synsets(ambiguous_word):
            try: ss_definition = ss.definition().split()
            except: ss_definition = ss.definition.split()
            dictionary[ss] = ss_definition
    best_sense = compare_overlaps_greedy(context_sentence.split(), dictionary)
    return best_sense    

def simple_signature(ambiguous_word, pos=None, lemma=True, stem=False, \
                     hyperhypo=True, stop=True):
    """ 
    Returns a synsets_signatures dictionary that includes signature words of a 
    sense from its:
    (i)   definition
    (ii)  example sentences
    (iii) hypernyms and hyponyms
    """
    synsets_signatures = {}
    for ss in wn.synsets(ambiguous_word):
        # If POS is specified.
        try:
            if pos and str(ss.pos()) != pos:
                continue
        except:
            if pos and str(ss.pos) != pos:
                continue
        
        signature = []
        # Includes definition.
        try: signature+= ss.definition().split()
        except: signature+= ss.definition.split()
        # Includes examples
        try: signature+= list(chain(*[i.split() for i in ss.examples()]))
        except: signature+= list(chain(*[i.split() for i in ss.examples]))
        # Includes lemma_names.
        try: signature+= ss.lemma_names()
        except: signature+= ss.lemma_names
        # Optional: includes lemma_names of hypernyms and hyponyms.
        if hyperhypo == True:
            try: signature+= list(chain(*[i.lemma_names() for i \
                                          in ss.hypernyms()+ss.hyponyms()]))
            except: signature+= list(chain(*[i.lemma_names for i \
                                             in ss.hypernyms()+ss.hyponyms()]))
        # Optional: removes stopwords.
        if stop == True:
            signature = [i for i in signature if i not in stopwords.words('english')]
        # Lemmatized context is preferred over stemmed context
        if lemma == True:
            signature = [lemmatize(i) for i in signature]
        # Matching exact words causes sparsity, so optional matching for stems.
        if stem == True: 
            signature = [porter.stem(i) for i in signature]

        signature = [i.lower() for i in signature]

        synsets_signatures[ss] = signature
    
    return synsets_signatures

def simple_lesk(context_sentence, ambiguous_word, \
                pos=None, lemma=True, stem=False, hyperhypo=True, \
                stop=True, context_is_lemmatized=False, \
                nbest=False, keepscore=False, normalizescore=False):
    """
    Simple Lesk is somewhere in between using more than the 
    original Lesk algorithm (1986) and using less signature 
    words than adapted Lesk (Banerjee and Pederson, 2002)
    """
    # Ensure that ambiguous word is a lemma.
    ambiguous_word = lemmatize(ambiguous_word).lower()
    # Get the signatures for each synset.
    ss_sign = simple_signature(ambiguous_word, pos, lemma, stem, hyperhypo)
    # Disambiguate the sense in context.
    if context_is_lemmatized:
        context_sentence = [porter.stem(i.lower()) for i in context_sentence.split()]
    else:
        context_sentence = lemmatize_sentence(context_sentence)
    best_sense = compare_overlaps(context_sentence, ambiguous_word, ss_sign, \
                                    nbest=nbest, keepscore=keepscore, \
                                    normalizescore=normalizescore)  
    return best_sense

def adapted_lesk(context_sentence, ambiguous_word, \
                pos=None, lemma=True, stem=True, hyperhypo=True, \
                stop=True, context_is_lemmatized=False, \
                nbest=False, keepscore=False, normalizescore=False):
    """
    This function is the implementation of the Adapted Lesk algorithm, 
    described in Banerjee and Pederson (2002). It makes use of the lexical 
    items from semantically related senses within the wordnet 
    hierarchies and to generate more lexical items for each sense. 
    see www.d.umn.edu/~tpederse/Pubs/cicling2002-b.pdf‎
    """
    # Ensure that ambiguous word is a lemma.
    ambiguous_word = lemmatize(ambiguous_word)
    # Get the signatures for each synset.
    ss_sign = simple_signature(ambiguous_word, pos, lemma, stem, hyperhypo)
    for ss in ss_sign:
        related_senses = list(set(ss.member_holonyms() + ss.member_meronyms() + 
                                 ss.part_meronyms() + ss.part_holonyms() + 
                                 ss.similar_tos() + ss.substance_holonyms() + 
                                 ss.substance_meronyms()))
    
        try:
            signature = list([j for j in chain(*[i.lemma_names() for i in \
                      related_senses]) if j not in stopwords.words('english')])
        except:
            signature = list([j for j in chain(*[i.lemma_names for i in \
                      related_senses]) if j not in stopwords.words('english')])
    # Lemmatized context is preferred over stemmed context
    if lemma == True:
        signature = [lemmatize(i) for i in signature]
    # Matching exact words causes sparsity, so optional matching for stems.
    if stem == True:
        signature = [porter.stem(i) for i in signature]
    ss_sign[ss]+=signature
  
    # Disambiguate the sense in context.
    if context_is_lemmatized:
        context_sentence = [porter.stem(i) for i in context_sentence.split()]
    else:
        context_sentence = lemmatize_sentence(context_sentence)
    best_sense = compare_overlaps(context_sentence, ambiguous_word, ss_sign, \
                                    nbest=nbest, keepscore=keepscore, \
                                    normalizescore=normalizescore)
    return best_sense

def cosine_lesk(context_sentence, ambiguous_word, \
                pos=None, lemma=True, stem=True, hyperhypo=True, \
                stop=True, context_is_lemmatized=False, \
                nbest=False):
    """ 
    In line with vector space models, we can use cosine to calculate overlaps
    instead of using raw overlap counts. Essentially, the idea of using 
    signatures (aka 'sense paraphrases') is lesk-like.
    """
    # Ensure that ambiguous word is a lemma.
    ambiguous_word = lemmatize(ambiguous_word)
    synsets_signatures = simple_signature(ambiguous_word, pos, lemma, stem, hyperhypo)
    
    if context_is_lemmatized:
        context_sentence = " ".join(context_sentence.split())
    else:
        context_sentence = " ".join(lemmatize_sentence(context_sentence))
    
    scores = []
    for ss, signature in synsets_signatures.items():
        # Lowercase and replace "_" with spaces.
        signature = " ".join(map(str, signature)).lower().replace("_", " ")
        # Removes punctuation.
        signature = [i for i in word_tokenize(signature) \
                     if i not in string.punctuation]
        # Optional: remove stopwords.
        if stop:
            signature = [i for i in signature if i not in stopwords.words('english')]
        # Optional: Lemmatize the tokens.
        if lemma == True:
            signature = [lemmatize(i) for i in signature]
        # Optional: stem the tokens.
        if stem:
            signature = [porter.stem(i) for i in signature]
        scores.append((cos_sim(context_sentence, " ".join(signature)), ss))
        
        if not nbest:
            return sorted(scores, reverse=True)[0][1]
        else:
            return [(j,i) for i,j in sorted(scores, reverse=True)]

