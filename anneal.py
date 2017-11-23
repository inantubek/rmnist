"""anneal.py
~~~~~~~~~~~~


"""

from __future__ import print_function

import math
import random

import data_loader

# Third-party libraries
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable
from torch.utils.data import Dataset

# Configuration
n = 10 # use RMNIST/n
expanded = True # Whether or not to use expanded RMNIST training data
if n == 0: epochs = 100
if n == 1: epochs = 500
if n == 5: epochs = 400
if n == 10: epochs = 200
# We decrease the learning rate by 20% every 10 epochs
batch_size = 10
momentum = 0.0
mean_data_init = 0.1
sd_data_init = 0.25
seed = 1
torch.manual_seed(seed)
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((mean_data_init,), (sd_data_init,))
])

params = {"weight_decay": 0.001, "lr": 0.01, "nk1": 10, "nk2": 20, "ensemble_size": 5}

def weight_decay_up(params):
    trial = dict(params)
    trial["weight_decay"] *= 10**0.25
    return trial

def weight_decay_down(params):
    trial = dict(params)
    trial["weight_decay"] /= 10**0.25
    return trial

def lr_up(params):
    trial = dict(params)
    trial["lr"] *= 10**0.25
    return trial

def lr_down(params):
    trial = dict(params)
    trial["lr"] /= 10**0.25
    return trial

def k1_up(params):
    trial = dict(params)
    trial["nk1"] += 2
    return trial

def k1_down(params):
    trial = dict(params)
    if trial["nk1"] > 2: trial["nk1"] -= 2
    return trial

def k2_up(params):
    trial = dict(params)
    trial["nk2"] += 2
    return trial

def k2_down(params):
    trial = dict(params)
    if trial["nk2"] > 2: trial["nk2"] -= 2
    return trial
    
moves = [weight_decay_up, weight_decay_down, lr_up, lr_down, k1_up, k1_down, k2_up, k2_down]

class RMNIST(Dataset):

    def __init__(self, n=0, train=True, transform=None, expanded=False):
        self.n = n
        self.transform = transform
        td, vd, ts = data_loader.load_data(n, expanded=expanded)
        if train: self.data = td
        else: self.data = vd
        
    def __len__(self):
        return len(self.data[0])

    def __getitem__(self, idx):
        data = self.data[0][idx]
        img = (data*256)
        img = img.reshape(28, 28)
        img = Image.fromarray(np.uint8(img))
        if self.transform: img = self.transform(img)
        label = self.data[1][idx]
        return (img, label)

train_dataset = RMNIST(n, train=True, transform=transform, expanded=expanded)
train_loader = torch.utils.data.DataLoader(
    train_dataset, batch_size=batch_size, shuffle=True)
training_data = list(train_loader)

validation_dataset = RMNIST(n, train=False, transform=transform, expanded=expanded)
validation_loader = torch.utils.data.DataLoader(
    validation_dataset, batch_size=100, shuffle=True)
validation_data = list(validation_loader)

class Net(nn.Module):
    
    def __init__(self, activation, params):
        super(Net, self).__init__()
        ks1 = 7
        nk1 = params["nk1"]
        ks2 = 4
        nk2 = params["nk2"]
        self.lin = (((((28-ks1+1)/2)-ks2+1)/2)**2)*nk2
        self.conv1 = nn.Conv2d(1, nk1, kernel_size=ks1)
        self.conv2 = nn.Conv2d(nk1, nk2, kernel_size=ks2)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(self.lin, 300)
        self.fc2 = nn.Linear(300, 10)
        self.activation = activation

    def forward(self, x):
        x = self.activation(F.max_pool2d(self.conv1(x), 2))
        x = self.activation(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
        #x = self.activation(self.conv2_drop(self.conv2(x)))
        x = x.view(-1, self.lin)
        x = self.activation(self.fc1(x))
        x = F.dropout(x, training=self.training)
        x = self.fc2(x)
        return F.log_softmax(x)

def train(epoch, model):
    optimizer = optim.SGD(model.parameters(), lr=params["lr"]*(0.8**(epoch/10+1)), momentum=momentum, weight_decay=params["weight_decay"])
    model.train()
    for batch_idx, (data, target) in enumerate(training_data):
        data, target = Variable(data), Variable(target)
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()

def evaluate(model):
    model.eval()
    validation_loss = 0
    accuracy = 0
    for data, target in validation_data:
        data, target = Variable(data, volatile=True), Variable(target)
        output = model(data)
        validation_loss += F.nll_loss(output, target, size_average=False).data[0]
        pred = output.data.max(1, keepdim=True)[1]
        accuracy += pred.eq(target.data.view_as(pred)).cpu().sum()
    validation_loss /= 10000
    return (accuracy, validation_loss)

def ensemble_accuracy(models):
    for model in models:
        model.eval()
    accuracy = 0
    for data, target in validation_data:
        data, target = Variable(data, volatile=True), Variable(target)
        outputs = [model(data) for model in models]
        pred = sum(output.data for output in outputs).max(1, keepdim=True)[1]
        accuracy += pred.eq(target.data.view_as(pred)).cpu().sum()
    return accuracy

def run():
    models = [Net(F.relu, params) for j in range(params["ensemble_size"])]
    for j, model in enumerate(models):
        print("Training model: {}".format(j))
        for epoch in range(1, epochs + 1):
            train(epoch, model)
    accuracy = ensemble_accuracy(models)
    print('Validation set ensemble accuracy: accuracy: {}/{} ({:.0f}%)'.format(
        accuracy, 10000, 100. * accuracy / 10000))
    return accuracy

def hash_dict(d):
    """Construct a hash of the dict d. A problem with this kind of hashing
    is when the values are floats. To solve this problem we
    essentially hash to 6 significant digits, by multiplying by 10**6
    and then rounding to an integer.
    """
    l = []
    for k, v in d.items():
        if type(v) == float:
            l.append((k, round(v*(10**6))))
        else:
            l.append((k, v))
    return hash(frozenset(l))

def add_dict_to_cache(cache, d, value):
    cache[hash_dict(d)] = value

def get_value_from_cache(cache, d):
    return cache[hash_dict(d)]

def dict_in_cache(cache, d):
    return hash_dict(d) in cache

energy_scale = 80
cache = {}
count = 0
print("\nMove: {}".format(count))
print("Initial parameters: {}".format(params))
accuracy = run()
best_accuracy = accuracy
best_params = params
add_dict_to_cache(cache, params, accuracy)
while True:
    random_move = random.randint(0, len(moves)-1)
    count += 1
    print("\nMove: {}".format(count))
    print("Current accuracy: {}".format(accuracy))
    print("Current params: {}".format(params))
    print("Move: {}".format(moves[random_move].__name__))
    trial_params = moves[random_move](params)
    print("Trialling: {}".format(trial_params))
    if dict_in_cache(cache, trial_params):
        print("Retrieving from cache")
        trial_accuracy = get_value_from_cache(cache, trial_params)
        print('Validation set: accuracy: {}/{} ({:.0f}%)'.format(
            trial_accuracy, 10000, 100. * trial_accuracy / 10000))
    else:
        print("Computing from new parameters")
        trial_accuracy = run()
        add_dict_to_cache(cache, trial_params, trial_accuracy)
    if random.random() < math.exp(-(accuracy-trial_accuracy)/energy_scale):
        print("Move accepted")
        params = trial_params
        accuracy = trial_accuracy
    else:
        print("Move not accepted")
    if accuracy > best_accuracy:
        best_accuracy = accuracy
        best_params = params
    print("Best accuracy so far: {}".format(best_accuracy))
    print("Best params so far: {}".format(best_params))
