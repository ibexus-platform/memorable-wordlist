import numpy as np
import urllib.request
import requests
import io
import zipfile
import pandas as pd

def download_extract_zip(url, fname):
    """
    Download a ZIP file and extract its contents in memory
    yields (filename, file-like object) pairs
    """
    response = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as thezip:
        return thezip.open(fname)

opener = urllib.request.FancyURLopener({})

accuracy = {}
response_time = {}

badwords = set()
with open('bad-words.txt') as f:
    for l in f.readlines():
        badwords.add(l.replace('\n',''))
with download_extract_zip("http://crr.ugent.be/blp/txt/blp-items.txt.zip",
                          "blp-items.txt") as f:
    for l in f.readlines():
        fields = l.decode('utf-8').split('\t')
        if fields[1] == 'W' and fields[2] != 'NA':
            # it is an actual word
            word = fields[0]
            accuracy[word] = float(fields[4])
            response_time[word] = float(fields[2])

aoa_test_based = {}
aoa_rating = {}
aoa_file = pd.read_excel('http://crr.ugent.be/papers/Master%20file%20with%20all%20values%20for%20test%20based%20AoA%20measures.xlsx')
for i in range(aoa_file.shape[0]):
    w = aoa_file.get_value(col='WORD', index=i)
    if aoa_file.get_value(col='AoAtestbased', index=i) != '#N/A':
        aoa_test_based[w] = float(aoa_file.get_value(col='AoAtestbased', index=i))
    if aoa_file.get_value(col='AoArating', index=i) != '#N/A':
        aoa_rating[w] = float(aoa_file.get_value(col='AoArating', index=i))

gsl_freq = {}
with open('gsl.txt') as f:
    for l in f.readlines():
        fields = l.split(' ')
        gsl_freq[fields[2].replace('\n','')] = float(fields[1])/147 # normalize to dog

subtitles_freq = {}
with opener.open("https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_full.txt") as f:
    for l in f.readlines():
        fields = l.decode('utf-8').split(' ')
        subtitles_freq[fields[0]] = float(fields[1])/125769 # normalize to dog

concreteness = {}
percent_known = {}
with opener.open('http://crr.ugent.be/papers/Concreteness_ratings_Brysbaert_et_al_BRM.txt') as f:
    for l in f.readlines():
        fields = l.decode('utf-8').split('\t')
        if fields[1] == 'Bigram':
            continue # this is the first line
        if fields[1] == '1':
            continue # this is a bigram, and let us just skip them
        concreteness[fields[0]] = float(fields[2])
        percent_known[fields[0]] = float(fields[6])

# In each case higher is more memorable, but in the case of valence
# small numbers may mean things to absolutely avoid.
valence = {}
arousal = {}
dominance = {}
with opener.open('http://crr.ugent.be/papers/Ratings_Warriner_et_al.csv') as f:
    for l in f.readlines():
        fields = l.decode('utf-8').split(',')
        if fields[2] == 'V.Mean.Sum':
            continue # this is the first line
        valence[fields[1]] = float(fields[2])
        arousal[fields[1]] = float(fields[5])
        dominance[fields[1]] = float(fields[8])

min_valence = 3
def get_valence(w):
    if w in valence:
        return valence[w]
    values = []
    for x in valence.keys():
        if w in x:
            values.append(valence[x])
    for x in valence.keys():
        if x in w:
             values.append(valence[x])
    v = sum(values+[min_valence])/(len(values)+1)
    if v < min_valence:
        return v
    return min_valence

good_words = set(percent_known.keys())
for w in sorted(good_words):
    if 'é' in w:
        good_words.remove(w)
    elif w in badwords:
        good_words.remove(w)

def rating(word, verbose=False):
    value = 0.
    if word in aoa_rating:
        if verbose:
            print('                        aoa_rating', aoa_rating[word])
        value += 2*(15-aoa_rating[word])
    if word in aoa_test_based:
        if verbose:
            print('                    aoa_test_based', aoa_test_based[word])
        value += 2*(15-aoa_test_based[word])
    if word in concreteness:
        if verbose:
            print('                      concreteness', concreteness[word])
        value += (concreteness[word]-2)*10
    if word in accuracy:
        if verbose:
            print('                          accuracy', accuracy[word])
        value += (accuracy[word]-0.7)*100
    if word in percent_known:
        if verbose:
            print('                     percent_known', percent_known[word])
        value += (percent_known[word]-0.8)*100
    if word in arousal:
        if verbose:
            print('                           arousal', arousal[word])
        value += (arousal[word]-2)*7
    if word in dominance:
        if verbose:
            print('                         dominance', dominance[word])
        value += (dominance[word]-5)*1

    v = get_valence(word)
    if verbose:
        if word in valence:
            print('                           valence', valence[word])
        else:
            print('                          *valence', v)
    if v < min_valence:
        value += 100*(v - min_valence)
    else:
        value += 10*(v - min_valence)

    if word in gsl_freq:
        value += 5*(gsl_freq[word]+1)
        if verbose:
            print('                               gsl %.3g' % gsl_freq[word])
    if word in subtitles_freq:
        value += subtitles_freq[word]+1
        if verbose:
            print('                         subtitles %.3g' % subtitles_freq[word])

    value -= 2*len(word)

    return value

ordered = list(reversed(sorted(good_words, key=lambda w: rating(w))))


with open('src/words.rs', 'w') as f:
    f.write('pub const LIST: &[&str] = &[\n')
    which = 0
    for w in ordered[:8192]:
        f.write('   "%s",\n' % w)
        r = rating(w)
        print('%5d: %15s %.4g' % (which, w, r))
        rating(w, True)
        which += 1
    f.write('];\n')
