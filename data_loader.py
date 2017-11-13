"""data_loader
~~~~~~~~~~~~~~

Load the MNIST and RMNIST image data. Can also be used to generate
RMNIST data sets. When run from the command line the program generates
RMNIST/1, RMNIST/5, and RMNIST/10.

"""

#### Libraries
# Standard library
import cPickle
import gzip
import random

random.seed(619) # use a standard seed to make repeatable

# Third-party libraries
import numpy as np

def load_data(n=0, expanded=False, abstract=False):
    """Return the RMNIST/n data as a tuple containing the training data,
    the validation data, and the test data.  Note that n=0 corresponds
    to the MNIST data set, of 50,000 training images, 10,000
    validation images, and 10,000 test images.

    If the expanded flag is set, use the expanded data sets generated
    by expand_rmnist.py. This does not work for n=0.

    If the abstract flag is set, instead of using the raw pixel data,
    use the abstract features generated by
    generate_abstrat_feature.py.

    """
    if expanded: name = "data/rmnist_expanded_{}.pkl.gz".format(n)
    if abstract: name = "data/rmnist_abstract_features_{}.pkl.gz".format(n)
    if n==0: name = "data/mnist.pkl.gz"
    if (not expanded and not abstract and n > 0):
        name = "data/rmnist_{}.pkl.gz".format(n)
    f = gzip.open(name, 'rb')
    training_data, validation_data, test_data = cPickle.load(f)
    f.close()
    return (training_data, validation_data, test_data)

def make_rmnist(n=10):
    """Make a subset of MNIST using n training examples of each digit and
    save into data/rmnist_n.pkl.gz, together with the complete
    validation and test sets.

    """ 
    td, vd, ts = load_data()
    indices = range(50000)
    random.shuffle(indices)
    values = [(j, td[1][j]) for j in indices]
    indices_subset = [[v[0] for v in values if v[1] == j][:n]
                      for j in range(10)]
    flattened_indices = [i for sub in indices_subset for i in sub]
    random.shuffle(flattened_indices)
    td0_prime = [td[0][j] for j in flattened_indices]
    td1_prime = [td[1][j] for j in flattened_indices]
    td_prime = (td0_prime, td1_prime)
    f = gzip.open('data/rmnist_'+str(n)+'.pkl.gz', 'wb')
    cPickle.dump((td_prime, vd, ts), f)
    f.close()

if __name__ == "__main__":
    # Make the ver
    make_rmnist(1)
    make_rmnist(5)
    make_rmnist(10)
