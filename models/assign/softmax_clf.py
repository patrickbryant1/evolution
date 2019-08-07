#!/usr/share/python3
# -*- coding: utf-8 -*-


import argparse
import sys
import numpy as np
from ast import literal_eval
import pandas as pd
import glob
from os import makedirs
from os.path import exists, join

#Preprocessing
from collections import Counter
import math
import time
from ast import literal_eval
from sklearn.model_selection import train_test_split, StratifiedShuffleSplit

#Keras
from tensorflow.keras.models import model_from_json
import tensorflow as tf
from tensorflow.keras import regularizers,optimizers
import tensorflow.keras as keras
from tensorflow.keras.constraints import max_norm
from tensorflow.keras.callbacks import ModelCheckpoint, LearningRateScheduler, Callback
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Dense, Dropout, Activation, Conv1D, Reshape, MaxPooling1D, Dot, Masking
from tensorflow.keras.layers import Activation, RepeatVector, Permute, Multiply, Lambda, GlobalAveragePooling1D
from tensorflow.keras.layers import concatenate, add, Conv1D, BatchNormalization, Flatten, Subtract
from tensorflow.keras.backend import epsilon, clip, get_value, set_value, transpose, variable, square
from tensorflow.layers import AveragePooling1D
from tensorflow.keras.losses import mean_absolute_error, mean_squared_error

#Custom
from lr_finder import LRFinder

import pdb


#Arguments for argparse module:
parser = argparse.ArgumentParser(description = '''A softmax classifier that uses embeddings generated from a pretrained model.''')

parser.add_argument('json_file', nargs=1, type= str,
                  default=sys.stdin, help = 'path to .json file with keras model to be opened')

parser.add_argument('weights', nargs=1, type= str,
                  default=sys.stdin, help = '''path to .h5 file containing weights for net.''')

parser.add_argument('encodings', nargs=1, type= str,
                  default=sys.stdin, help = 'Path to np array with encoded aa sequences.')

parser.add_argument('dataframe', nargs=1, type= str,
                  default=sys.stdin, help = '''path to data to be used for prediction.''')

parser.add_argument('class_embeddings', nargs=1, type= str,
                  default=sys.stdin, help = '''path to class embeddings.''')

parser.add_argument('out_dir', nargs=1, type= str,
                  default=sys.stdin, help = '''path to output directory.''')




#FUNCTIONS

def pad_cut(ar, x, y):
    '''Pads or cuts a 1D array to len x
    '''
    shape = ar.shape

    if max(shape) < x:
        empty = np.zeros((x,y))
        empty[0:len(ar)]=ar
        ar = empty
    else:
        ar = ar[0:x]
    return ar

def load_model(json_file, weights):

	global model

	json_file = open(json_file, 'r')
	model_json = json_file.read()
	model = model_from_json(model_json)
	model.load_weights(weights)
	model._make_predict_function()
	return model

#MAIN
args = parser.parse_args()
json_file = (args.json_file[0])
weights = (args.weights[0])
encodings = args.encodings[0]
dataframe = args.dataframe[0]
class_embeddings = np.load(args.class_embeddings[0], allow_pickle=True)
out_dir = args.out_dir[0]

#Assign data and labels
#Read df
df = pd.read_csv(dataframe)

#Assign data and labels
#Read data
X = np.load(encodings, allow_pickle=True)
y = np.asarray([*df['group_enc']])
#Pad X
padded_X = []
for i in range(0,len(X)):
    padded_X.append(pad_cut(X[i], 300, 21))
X = np.asarray(padded_X)


#Load and run model
model = load_model(json_file, weights)

#Get embedding layers
features1 = Model(inputs=model.input, outputs=model.get_layer('features1').output)
features2 = Model(inputs=model.input, outputs=model.get_layer('features2').output)

#Get average embeddings for all entries
emb1 = np.asarray(features1.predict([X,X]))
emb2 = np.asarray(features2.predict([X,X]))
average_emb = np.average([emb1, emb2], axis = 0)

#Split data
X_train, X_valid, y_train, y_valid = train_test_split(average_emb, y, test_size=0.2, random_state=42)
#Onehot encode labels
y_train = np.eye(max(y)+1)[y_train]
y_valid = np.eye(max(y)+1)[y_valid]
num_classes = max(y)+1
#Compute L1 distance to all class_embeddings
L_dists = []
for i in range(0, len(average_emb)):
    true = y[i]
    diff = np.absolute(class_embeddings-average_emb[i])
    L_dists.append(diff)

def get_batch(batch_size,s="train"):
    """
    Create a batch of L_dists
    """
    if s == 'train':
        X = X_train
        y = y_train
    else:
        X = X_valid
        y = y_valid



    # # randomly sample several classes to use in the batch
    random_samples = np.random.choice(len(X),size=(batch_size,),replace=False) #without replacement

    batch_X = X[random_samples]
    batch_y = y[random_samples]



    return batch_X, batch_y

def generate(batch_size, s="train"):
    """
    a generator for batches, so model.fit_generator can be used.
    """
    while True:
        pairs, targets = get_batch(batch_size,s)
        yield (pairs, targets)

def get_valid(batch_size, s="valid"):
    """
    a generator for batches, so model.fit_generator can be used.
    """
    while True:
        pairs, targets = get_batch(batch_size,s)
        yield (pairs, targets)

#Parameters
input_dim = average_emb[0].shape
batch_size = 32

#lr opt
find_lr = False
#LR schedule
step_size = 5
num_cycles = 3
num_epochs = step_size*2*num_cycles
train_steps = int(len(y_train)/batch_size)*10
valid_steps = int(len(y_valid)/batch_size)
max_lr = 0.0005
min_lr = max_lr/10
lr_change = (max_lr-min_lr)/step_size  #(step_size*num_steps) #How mauch to change each batch
lrate = min_lr

#MODEL
x = keras.Input(shape = input_dim)
#Flatten
flat = Flatten()(x)
#Create softmax classifier
probability = Dense(num_classes, activation='softmax')(flat)



softmax_clf = Model(inputs = [x], outputs = probability)
opt = optimizers.Adam(clipnorm=1.)
softmax_clf.compile(loss='categorical_crossentropy',
              metrics = ['accuracy'],
              optimizer=opt)
#Summary of model
print(softmax_clf.summary())

#LRFinder
if find_lr == True:
  lr_finder = LRFinder(softmax_clf)

  lr_finder.find(np.asarray(X_train), y_train, start_lr=0.00001, end_lr=1, batch_size=batch_size, epochs=1)
  losses = lr_finder.losses
  lrs = lr_finder.lrs
  l_l = np.asarray([lrs, losses])
  np.savetxt(out_dir+'lrs_losses.txt', l_l)
  num_epochs = 0

#LR schedule
class LRschedule(Callback):
  '''lr scheduel according to one-cycle policy.
  '''
  def __init__(self, interval=1):
    super(Callback, self).__init__()
    self.lr_change = lr_change #How mauch to change each batch
    self.lr = min_lr
    self.interval = interval

  def on_epoch_end(self, epoch, logs={}):
    if epoch > 0 and epoch%step_size == 0:
      self.lr_change = self.lr_change*-1 #Change decrease/increase
    self.lr = self.lr + self.lr_change

#Lrate
lrate = LRschedule()
callbacks=[lrate]

softmax_clf.fit_generator(generate(batch_size),
             steps_per_epoch=train_steps,
             epochs=num_epochs,
             validation_data = get_valid(batch_size), #Validate on 1000 examples
             validation_steps = valid_steps,
             shuffle=False, #Feed continuously, since random examples are picked
             callbacks = callbacks)
