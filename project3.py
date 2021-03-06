"""
1. Neighborhood-based collaborative filtering
2. Model-based collaborative filtering  

Dataset:
http://files.grouplens.org/datasets/movielens/ml-latest-small.zip

"""
import os
import pdb
import pickle
import bisect  # use to keep a sorted list
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import random

np.random.seed(42)
random.seed(42)

from surprise import KNNBasic, AlgoBase
from surprise.prediction_algorithms.matrix_factorization import NMF, SVD
from surprise.prediction_algorithms.baseline_only import BaselineOnly
from surprise.model_selection import cross_validate, KFold, train_test_split
from surprise import Dataset, Reader, KNNWithMeans, accuracy
from sklearn.metrics import roc_curve, auc
from collections import defaultdict

"""
Constants
"""
PLOT_RESULT = True
USE_PICKLED_RESULTS = True

"""
Loading data, computing rating matrix R

Ratings matrix is denoted by R, and it is an m × n matrix
containing m users (rows) and n movies (columns). The (i, j) 
entry of the matrix is the rating of user i for movie j and 
is denoted by r_ij
"""
df = pd.read_csv("./ml-latest-small/ratings.csv")
reader = Reader(rating_scale=(0.5,5))
data = Dataset.load_from_df(df[['userId','movieId','rating']], reader)

movies = df['movieId'].unique()
users = df['userId'].unique()

print(f"Dataset has {movies.shape[0]} movies & {users.shape[0]} users")
movies_map = dict()
movies_inv_map = dict()
for (i, Id) in enumerate(movies):
  movies_map[Id] = i 
  movies_inv_map[i] = Id

R = np.zeros([users.shape[0], movies.shape[0]])

for idx, row in df.iterrows():
  R[int(row['userId']-1)][movies_map[row['movieId']]] =  row['rating']

print(R)

"""
Question 1: Compute the sparsity of the movie rating dataset, where sparsity is defined by:
sparsity = total num of available ratings / total num of possible ratings
"""
sparsity = len(R[R > 0]) / R.size

"""
Question 2: Plot a histogram showing the frequency of the rating values
"""
bin_width = 0.5
bin_min, bin_max = df['rating'].min(), df['rating'].max()
bins = bins = np.arange(bin_min, bin_max + bin_width, bin_width)  

if PLOT_RESULT:
  plt.figure()
  df['rating'].hist(bins=bins)
  plt.title("rating distribution")
  plt.xlabel("rating")
  plt.ylabel("number of rating")
  plt.show(0)

"""
Question 3: Plot the distribution of the number of ratings received among movies
"""
Rm = np.sum(1.0 * (R > 0), axis=0)
Rm_sorted = np.flip(np.sort(Rm))

if PLOT_RESULT:
  plt.figure()
  plt.bar(range(len(Rm_sorted)), Rm_sorted)
  plt.title("num rating distribution by movie")
  plt.xlabel("movie")
  plt.ylabel("number of rating")
  plt.grid()
  plt.show(0)

"""
Question 4: Plot the distribution of ratings among users
"""
Ru = np.sum(1.0 * (R > 0), axis=1)
Ru_sorted = np.flip(np.sort(Ru))

if PLOT_RESULT:
  plt.figure()
  plt.bar(range(len(Ru_sorted)), Ru_sorted)
  plt.title("num rating distribution by user")
  plt.xlabel("user")
  plt.ylabel("number of rating")
  plt.grid()
  plt.show(0)

"""
Question 5: Explain the salient features of the distribution found in question 3 and their 
implications for the recommendation process

Both distribution seems to be exponentially distributed 
"""

"""
Question 6: Compute the variance of the rating values received by each movie
"""
Rm_var = R.std(axis=0) ** 2
bin_min, bin_max = Rm_var.min(), Rm_var.max()
bins = bins = np.arange(bin_min, bin_max + bin_width, bin_width)

if PLOT_RESULT:
  plt.figure()
  plt.hist(Rm_var, bins=bins)
  plt.xlabel("var of rating for each movie")
  plt.ylabel("num rating")
  plt.grid()
  plt.show(0)

"""
Question 10:
"""
# Initialize kNNWithMeans with sim options
sim_options = {
    'name': 'pearson',
    'user_based': True,
}

# Run k-NN with k=2 to k=100 in increments of 2
k_values = range(2,101,2)
results = []

if USE_PICKLED_RESULTS == True:
  with open('knn.pickle', 'rb') as handle:
    results = pickle.load(handle)
else:
  for k in k_values:
    print('\nk = {0:d}'.format(k))
    algo = KNNWithMeans(k=k, sim_options=sim_options)
    results.append(cross_validate(algo, data, measures=['RMSE', 'MAE'], cv=10,
                                verbose=True, n_jobs=-1))
  # Pickle results
  with open('knn.pickle', 'wb') as handle:
    pickle.dump(results, handle)

# Calculate mean scores
mean_scores = np.zeros((50,2))
for counter, result in enumerate(results):
  mean_scores[counter,0] = np.mean(result['test_rmse'])
  mean_scores[counter,1] = np.mean(result['test_mae'])

# Print steady-state value for RMSE and MAE
print('\nRMSE steady-state value: {:.3f}'.format(mean_scores[20,0]))
print('MAE steady-state value: {:.3f}'.format(mean_scores[20,1]))

# Plot mean scores
if PLOT_RESULT:
  # Plot RMSE
  plt.figure(figsize=(15,5))
  plt.subplot(1,2,1)
  plt.plot(k_values, mean_scores[:,0],'-x')
  plt.title('Mean RMSE for k-NN with Cross Validation')
  plt.ylabel('Mean RSME')
  plt.xlabel('Number of $k$ neighbors')

  # Plot MAE
  plt.subplot(1,2,2)
  plt.plot(k_values, mean_scores[:,1],'-x')
  plt.title('Mean MAE for k-NN with Cross Validation')
  plt.ylabel('Mean MAE')
  plt.xlabel('Number of $k$ neighbors')
  plt.tight_layout()
  plt.show()

"""
Question 12: k-NN on popular movies
"""
# Create a dict where each movieId is a key and the values are a list
# of all the ratings for the movieId
ratings = {}
for row in data.raw_ratings:
  # if movieId not in dict, add it
  if row[1] not in ratings:
    ratings[row[1]] = []

  # Add ratings to movieId list
  ratings[row[1]].append(row[2])

# Create dictionary with rating variance for each movieId
variances = {}
for movieId in ratings:
  variances[movieId] = np.var(ratings[movieId])

# Create list with movies with more than 2 ratings
pop_movies = [movie for movie in ratings if len(ratings[movie]) > 2]

# Train/test using cross-validation iterators
kf = KFold(n_splits=10)
k_rmse = 0
rmse_pop = []

if USE_PICKLED_RESULTS == True:
  with open('knn_pop.pickle', 'rb') as handle:
    rmse_pop = pickle.load(handle)
else:
  # Iterate over all k values and calculate RMSE for each
  for k in k_values:
    algo = KNNWithMeans(k=k, sim_options=sim_options)
    for counter, [trainset, testset] in enumerate(kf.split(data)):
      print('\nk = {0:d}, fold = {1:d}'.format(k, counter+1))

      # Train algorithm with 9 unmodified trainsets
      algo.fit(trainset)

      # Test with trimmed test set
      trimmed_testset = [x for x in testset if x[1] in pop_movies]
      predictions = algo.test(trimmed_testset)

      # Compute and print Root Mean Squared Error (RMSE) for each fold
      k_rmse += accuracy.rmse(predictions, verbose=True)

    #Compute mean of all rsme values for each k
    print('Mean RMSE for 10 folds: ', k_rmse/(counter+1))
    rmse_pop.append(k_rmse / (counter+1))
    k_rmse = 0

  # Pickle results
  with open('knn_pop.pickle', 'wb') as handle:
    pickle.dump(rmse_pop, handle)

# Print minimum RMSE
print('\nPopular Movies:')
print('Minimum average RMSE: {:.3f}'.format(np.min(rmse_pop)))


if PLOT_RESULT:
  # Plot RMSE versus k
  plt.plot(k_values, rmse_pop, '-x')
  plt.title('Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')
  plt.show()

"""
Question 13: Unpopular movie trimmed set
"""
rmse_unpop = []
if USE_PICKLED_RESULTS == True:
  with open('knn_unpop.pickle', 'rb') as handle:
    rmse_unpop = pickle.load(handle)
else:
  for k in k_values:
    algo = KNNWithMeans(k=k, sim_options=sim_options)
    for counter, [trainset, testset] in enumerate(kf.split(data)):
      print('\nk = {0:d}, fold = {1:d}'.format(k, counter+1))

      # Train algorithm with 9 unmodified trainset
      algo.fit(trainset)

      # Test with trimmed test set
      trimmed_testset = [x for x in testset if x[1] not in pop_movies]
      predictions = algo.test(trimmed_testset)

      # Compute and print Root Mean Squared Error (RMSE) for each fold
      k_rmse += accuracy.rmse(predictions, verbose=True)

    #Compute mean of all rsme values for each k
    print('Mean RMSE for 10 folds: ', k_rmse/(counter+1))
    rmse_unpop.append(k_rmse / (counter+1))
    k_rmse = 0

  # Pickle results
  with open('knn_unpop.pickle', 'wb') as handle:
    pickle.dump(rmse_unpop, handle)

# Print minimum RMSE
print('\nUnpopular Movies:')
print('Minimum average RMSE: {:.3f}'.format(np.min(rmse_unpop)))

if PLOT_RESULT:
  # Plot RMSE versus k
  plt.plot(k_values, rmse_unpop, '-x')
  plt.title('Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')
  plt.show()

"""
Question 14: Trimmed test set - movies with more than 5 ratings and variance higher
than 2.
"""
# Create list with high_variance movies
high_var_movies = [movieId for movieId in ratings if len(ratings[movieId]) >=5
                   and variances[movieId] >= 2]

# Empty list to store rmse for each k
rmse_high_var = []

# Using cross-validation iterators
kf = KFold(n_splits=10)
k_rmse = 0

if USE_PICKLED_RESULTS == True:
  with open('knn_var.pickle', 'rb') as handle:
    rmse_high_var = pickle.load(handle)
else:
  for k in k_values:
    algo = KNNWithMeans(k=k, sim_options=sim_options)
    for counter, [trainset, testset] in enumerate(kf.split(data)):
      print('\nk = {0:d}, fold = {1:d}'.format(k, counter+1))

      # Train algorithm with 9 unmodified trainset
      algo.fit(trainset)

      # Test with trimmed test set
      trimmed_testset = [x for x in testset if x[1] in high_var_movies]
      predictions = algo.test(trimmed_testset)

      # Compute and print Root Mean Squared Error (RMSE) for each fold
      k_rmse += accuracy.rmse(predictions, verbose=True)

    # Compute mean of all rsme values for each k
    print('Mean RMSE for 10 folds: ', k_rmse/(counter+1))
    rmse_high_var.append(k_rmse / (counter+1))
    k_rmse = 0

  # Pickle results
  with open('knn_var.pickle', 'wb') as handle:
    pickle.dump(rmse_high_var, handle)

# Print minimum RMSE
print('\nHigh-Variance Movies:')
print('Minimum average RMSE: {:.3f}\n'.format(np.min(rmse_high_var)))

if PLOT_RESULT:
  # Plot RMSE versus k
  plt.plot(k_values, rmse_high_var, '-x')
  plt.title('Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')
  plt.show()

"""
Question 15:
"""
k = 20  # best k value found in question 10
threshold_values = [2.5, 3, 3.5, 4]
roc_results = []

for threshold in threshold_values:
  train_set, test_set = train_test_split(data, test_size = 0.1)
  algo = KNNWithMeans(k=k, sim_options=sim_options)
  algo.fit(train_set)
  predictions = algo.test(test_set)

  # r_ui is the 'true' rating
  y_true = [0 if prediction.r_ui < threshold else 1
                 for prediction in predictions]
  # est is the estimated rating
  y_score = [prediction.est for prediction in predictions]
  fpr, tpr, thresholds = roc_curve(y_true=y_true, y_score=y_score)
  roc_auc = auc(fpr, tpr)
  roc_results.append((fpr, tpr, roc_auc, threshold))

# Plot ROC and include area under curve
if PLOT_RESULT:
  plt.figure(figsize=(15,10))
  lw = 2
  for i, result in enumerate(roc_results):
    plt.subplot(2,2,i+1)
    plt.plot(result[0], result[1], color='darkorange', lw=lw,
             label='ROC curve (area = %0.2f)' % result[2])
    plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve for Threshold = {:.1f}'.format(result[3]), fontsize='xx-large')
    plt.legend(loc="lower right", fontsize='xx-large')
  plt.tight_layout()
  plt.show()



"""
Question 17
"""
kf = KFold(n_splits=10)
rmse, mae = 0, 0
kf_rmse, kf_mae = [], []

k_values = range(2,51,2)
for k in k_values:
  algo = NMF(n_factors=k)
  for trainset, testset in kf.split(data):
    algo.fit(trainset)
    pred = algo.test(testset)
    rmse += accuracy.rmse(pred)
    mae += accuracy.mae(pred)
  kf_rmse.append(rmse / kf.n_splits)
  kf_mae.append(mae / kf.n_splits)
  rmse, mae = 0, 0

if PLOT_RESULT:
  plt.figure()
  plt.plot(k_values, kf_rmse, '-x')
  plt.title('Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('n_factors')
  plt.ylabel('Average RMSE')

  plt.figure()
  plt.plot(k_values, kf_mae, '-x')
  plt.title('Average MAE over $k$ with 10-fold cross validation')
  plt.xlabel('n_factors')
  plt.ylabel('Average MAE')

"""
Question 18
"""

movieDat = pd.read_csv("./ml-latest-small/movies.csv")

indivGenre = []

# write individual genres into a new array
for g in movieDat['genres']:
    for i in g.split('|'):
        indivGenre.append(i)

# list unique individual genres
np.unique(indivGenre)

"""
Question 19: NNMF on Popular Movies
"""
# Using cross-validation iterators
kf = KFold(n_splits=10)
k_rmse = 0
rmse_pop = []

# Iterate over all k values and calculate RMSE for each
for k in k_values:
  algo = NMF(n_factors=k)
  for counter, [trainset, testset] in enumerate(kf.split(data)):
    print('\nk = {0:d}, fold = {1:d}'.format(k, counter+1))

    # Train algorithm with 9 unmodified trainsets
    algo.fit(trainset)

    # Test with trimmed test set
    trimmed_testset = [x for x in testset if x[1] in pop_movies]
    predictions = algo.test(trimmed_testset)

    # Compute and print Root Mean Squared Error (RMSE) for each fold
    k_rmse += accuracy.rmse(predictions, verbose=True)

  #Compute mean of all rmse values for each k
  print('Mean RMSE for 10 folds: ', k_rmse/(counter+1))
  rmse_pop.append(k_rmse / (counter+1))
  k_rmse = 0

print('RMSE values:')
print(rmse_pop)

if PLOT_RESULT:
    # Plot RMSE versus k
    plt.plot(k_values, rmse_pop, '-x')
    plt.title('Average RMSE over $k$ with 10-fold cross validation')
    plt.xlabel('$k$ Nearest Neighbors')
    plt.ylabel('Average RMSE')

"""
Question 20: NNMF on Unpopular Movies
"""
# Train/test using cross-validation iterators
kf = KFold(n_splits=10)
k_rmse = 0

rmse_unpop = []

for k in k_values:
    algo = NMF(n_factors=k, biased=False)

    for counter, [trainset, testset] in enumerate(kf.split(data)):
      print('\nk = {0:d}, fold = {1:d}'.format(k, counter+1))

      # Train algorithm with 9 unmodified trainset
      algo.fit(trainset)

      # Test with unpopular movie trimmed test set
      trimmed_testset = [x for x in testset if x[1] not in pop_movies]
      predictions = algo.test(trimmed_testset)

      # Compute and print Root Mean Squared Error (RMSE) for each fold
      k_rmse += accuracy.rmse(predictions, verbose=True)

    #Compute mean of all rsme values for each k
    print('Mean RMSE for 10 folds: ', k_rmse/(counter+1))
    rmse_unpop.append(k_rmse / (counter+1))
    k_rmse = 0

if PLOT_RESULT:
    # Plot RMSE versus k
    plt.plot(k_values, rmse_unpop, '-x')
    plt.title('Unpopular Test Set: Average RMSE over $k$ with 10-fold cross validation')
    plt.xlabel('$k$ Nearest Neighbors')
    plt.ylabel('Average RMSE')

"""
Question 21: NNMF on High Variance Movies
"""
# Empty list to store rmse for each k
rmse_high_var = []

# Using cross-validation iterators
kf = KFold(n_splits=10)
k_rmse = 0

for k in k_values:
    algo = NMF(n_factors=k, biased=False)
    for counter, [trainset, testset] in enumerate(kf.split(data)):
      print('\nk = {0:d}, fold = {1:d}'.format(k, counter+1))

      # Train algorithm with 9 unmodified trainset
      algo.fit(trainset)

      # Test with trimmed test set
      trimmed_testset = [x for x in testset if x[1] in high_var_movies]
      predictions = algo.test(trimmed_testset)

      # Compute and print Root Mean Squared Error (RMSE) for each fold
      k_rmse += accuracy.rmse(predictions, verbose=True)

    # Compute mean of all rsme values for each k
    print('Mean RMSE for 10 folds: ', k_rmse/(counter+1))
    rmse_high_var.append(k_rmse / (counter+1))
    k_rmse = 0

if PLOT_RESULT:
    # Plot RMSE versus k
    plt.plot(k_values, rmse_high_var, '-x')
    plt.title('High Variance: Average RMSE over $k$ with 10-fold cross validation')
    plt.xlabel('$k$ Nearest Neighbors')
    plt.ylabel('Average RMSE')

"""
Question 22: NNMF ROC Plots
"""
def plotROC(fpr, tpr, roc_auc, threshold):
    plt.figure()
    lw = 2
    plt.plot(fpr, tpr, color='darkorange', lw=lw, label='ROC curve (area = %0.2f)' % roc_auc)
    plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver operating characteristic: Threshold = %s' %threshold)
    plt.legend(loc="lower right")
    plt.show()

k = 20  # best k value found in question 18
threshold_values = [2.5, 3, 3.5, 4]

for threshold in threshold_values:
  train_set, test_set = train_test_split(data, test_size = 0.1)
  algo = NMF(n_factors=k, biased=False)
  algo.fit(train_set)
  predictions = algo.test(test_set)

  # r_ui is the 'true' rating
  y_true = [0 if prediction.r_ui < threshold else 1
                 for prediction in predictions]
  # est is the estimated rating
  y_score = [prediction.est for prediction in predictions]
  fpr, tpr, thresholds = roc_curve(y_true=y_true, y_score=y_score)
  roc_auc = auc(fpr, tpr)

  plotROC(fpr, tpr, roc_auc, threshold)

"""
Question 23: Movie-Latent Factor Interaction
"""
reader = Reader(rating_scale=(0.5,5))
data = Dataset.load_from_df(df[['userId','movieId','rating']], reader)
data = data.build_full_trainset()

movieDat = pd.read_csv('ml-latest-small/movies.csv')

nmf = NMF(n_factors=20, biased=False)
nmf.fit(data)

movies = df['movieId'].unique()  # identify unique movie IDs from the ratings CSV (9724, already sorted)
V = nmf.qi

# get top 10 movie genres for the first 20 columns of the V matrix
for i in range(20):
    Vcol = V[:,i]

    # convert column of V into a list for processing
    VcolOrig = []
    VcolSort = []
    for j in range(len(Vcol)):
        VcolOrig.append(Vcol[j]) # original array for looking up movie index
        VcolSort.append(Vcol[j]) # sorted array for getting top movies

    # sort Vcolumn list in descending order
    VcolSort.sort(reverse=True)

    print('\nIn the %i column, the top 10 movie genres are:' %(i+1))

    for k in range(10):
        movIndex = VcolOrig.index(VcolSort[k])
        movID = movies[movIndex]
        genre = movieDat.loc[movieDat['movieId']==movID]['genres'].values
        print(' %i) ' %(k+1), genre)

"""
Questions 24, 26, 27, 28
"""
kf = KFold(n_splits=10)
algo_list = []
k_rmse, k_mae, k_pop_rmse, k_unpop_rmse, k_high_var_rmse = 0, 0, 0, 0, 0
kf_rmse, kf_mae, rmse_pop, rmse_unpop, rmse_high_var = [], [], [], [], []
k_values = range(2, 51, 2)

if USE_PICKLED_RESULTS and os.path.isfile('mf_bias_rmse.pickle') and os.path.isfile('mf_bias_high_var_rmse.pickle'):
  with open('mf_bias_rmse.pickle', 'rb') as handle:
    kf_rmse = pickle.load(handle)
  with open('mf_bias_mae.pickle', 'rb') as handle:
    kf_mae = pickle.load(handle)
  with open('mf_bias_pop_rmse.pickle', 'rb') as handle:
    rmse_pop = pickle.load(handle)
  with open('mf_bias_unpop_rmse.pickle', 'rb') as handle:
    rmse_unpop = pickle.load(handle)
  with open('mf_bias_high_var_rmse.pickle', 'rb') as handle:
    rmse_high_var = pickle.load(handle)
else:
  for k in k_values:
    algo = SVD(n_factors=k, random_state=42)
    for counter, [trainset, testset] in enumerate(kf.split(data)):
      print('\nk = {0:d}, fold = {1:d}'.format(k, counter + 1))
      algo.fit(trainset)
      pred = algo.test(testset)
      k_rmse += accuracy.rmse(pred)
      k_mae += accuracy.mae(pred)

      pop_testset = [x for x in testset if x[1] in pop_movies]
      pop_pred = algo.test(pop_testset)
      k_pop_rmse += accuracy.rmse(pop_pred)

      unpop_testset = [x for x in testset if x[1] not in pop_movies]
      unpop_pred = algo.test(unpop_testset)
      k_unpop_rmse += accuracy.rmse(unpop_pred)

      high_var_testset = [x for x in testset if x[1] in high_var_movies]
      high_var_pred = algo.test(high_var_testset)
      k_high_var_rmse += accuracy.rmse(high_var_pred)

    kf_rmse.append(k_rmse / kf.n_splits)
    kf_mae.append(k_mae / kf.n_splits)
    rmse_pop.append(k_pop_rmse / kf.n_splits)
    rmse_unpop.append(k_unpop_rmse / kf.n_splits)
    rmse_high_var.append(k_high_var_rmse / kf.n_splits)
    k_rmse, k_mae, k_pop_rmse, k_unpop_rmse, k_high_var_rmse = 0, 0, 0, 0, 0

  # Pickle results
  with open('mf_bias_rmse.pickle', 'wb') as handle:
    pickle.dump(kf_rmse, handle)
  with open('mf_bias_mae.pickle', 'wb') as handle:
    pickle.dump(kf_mae, handle)
  with open('mf_bias_pop_rmse.pickle', 'wb') as handle:
    pickle.dump(rmse_pop, handle)
  with open('mf_bias_unpop_rmse.pickle', 'wb') as handle:
    pickle.dump(rmse_unpop, handle)
  with open('mf_bias_high_var_rmse.pickle', 'wb') as handle:
    pickle.dump(rmse_high_var, handle)

if PLOT_RESULT:
  print(kf_rmse)
  plt.figure()
  plt.plot(k_values, kf_rmse, '-x')
  plt.title('MF with Bias Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')

  print(kf_mae)
  plt.figure()
  plt.plot(k_values, kf_mae, '-x')
  plt.title('MF with Bias Average MAE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average MAE')

  # Plot RMSE versus k
  print(rmse_pop)
  plt.figure()
  plt.plot(k_values, rmse_pop, '-x')
  plt.title('Popular Test Set: Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')

  # Plot RMSE versus k
  print(rmse_unpop)
  plt.figure()
  plt.plot(k_values, rmse_unpop, '-x')
  plt.title('Unpopular Test Set: Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')

  # Plot RMSE versus k
  print(rmse_high_var)
  plt.figure()
  plt.plot(k_values, rmse_high_var, '-x')
  plt.title('High Variance: Average RMSE over $k$ with 10-fold cross validation')
  plt.xlabel('$k$ Nearest Neighbors')
  plt.ylabel('Average RMSE')
  plt.show()

"""
Question 29: MF with Bias ROC Plots
"""

k = 50  # best k value found in question 25
threshold_values = [2.5, 3, 3.5, 4]

for threshold in threshold_values:
  train_set, test_set = train_test_split(data, test_size = 0.1)
  algo = SVD(n_factors=k, random_state=42)
  algo.fit(train_set)
  predictions = algo.test(test_set)

  # r_ui is the 'true' rating
  y_true = [0 if prediction.r_ui < threshold else 1
                 for prediction in predictions]
  # est is the estimated rating
  y_score = [prediction.est for prediction in predictions]
  fpr, tpr, thresholds = roc_curve(y_true=y_true, y_score=y_score)
  roc_auc = auc(fpr, tpr)

  plotROC(fpr, tpr, roc_auc, threshold)


"""
Question 30: Naive Collaborative Filtering

rij_hat = mean(u_j)
"""
class NaiveCollabFilter(AlgoBase):
  def __init__(self):
    AlgoBase.__init__(self)
    self._m_uid = dict()

  def fit(self, trainset):
    AlgoBase.fit(self, trainset)
    self._m_uid.clear()
    for uid, iid, rating in self.trainset.all_ratings():
      if uid in self._m_uid:
        m = self._m_uid[uid][0]
        n = self._m_uid[uid][1] + 1
        m += (rating - m) / n
        self._m_uid[uid] = (m, n)
      else:
        self._m_uid[uid] = (rating, 1)

  def estimate(self, u, i):
    return self._m_uid[u][0] if u in self._m_uid else 0

algo = NaiveCollabFilter()
algo.fit(data.build_full_trainset())

kf = KFold(n_splits=10)
kf_rmse = []
for _, testset in kf.split(data):
  pred = algo.test(testset)
  kf_rmse.append(accuracy.rmse(pred, verbose=True))
print('Naive Collab Fillter RMSE for 10 folds CV: ', np.mean(kf_rmse))

"""
Question 31:
"""
kf_rmse = []
for _, testset in kf.split(data):
  trimmed_testset = [x for x in testset if x[1] in pop_movies]
  pred = algo.test(trimmed_testset)
  kf_rmse.append(accuracy.rmse(pred, verbose=True))
print('Naive Collab Fillter RMSE for 10 folds CV (popular testset): ', np.mean(kf_rmse))

"""
Question 32:
"""
kf_rmse = []
for _, testset in kf.split(data):
  trimmed_testset = [x for x in testset if x[1] not in pop_movies]
  pred = algo.test(trimmed_testset)
  kf_rmse.append(accuracy.rmse(pred, verbose=True))
print('Naive Collab Fillter RMSE for 10 folds CV (not popular testset): ', np.mean(kf_rmse))

"""
Question 33:
"""
kf_rmse = []
for _, testset in kf.split(data):
  trimmed_testset = [x for x in testset if x[1] in high_var_movies]
  pred = algo.test(trimmed_testset)
  kf_rmse.append(accuracy.rmse(pred, verbose=True))
print('Naive Collab Fillter RMSE for 10 folds CV (high var testset): ', np.mean(kf_rmse))

"""
Question 34
Plot the ROC curves (threshold = 3) for the k-NN, NNMF, and
MF with bias based collaborative filters in the same figure. Use the figure to
compare the performance of the filters in predicting the ratings of the movies.

k-NN : k = 20
NNMF : k = 18 or 20
MF   : k = 50
"""
trainset, testset = train_test_split(data, test_size = 0.1)
sim_options = {
  'name': 'pearson',
  'user_based': True
}
knn = KNNWithMeans(k=20, sim_options=sim_options)
nmf = NMF(n_factors=20, biased=False)
svd = SVD(n_factors=50, random_state=42)

plt.figure()
threshold = 3
algos = (('kNN', knn), ('NMMF', nmf), ('MF', svd))
for name, algo in algos:
  algo.fit(trainset)
  pred = algo.test(testset)
  y_true  = [0 if p.r_ui < threshold else 1 for p in pred]
  y_score = [p.est for p in pred]
  fpr, tpr, thresholds = roc_curve(y_true=y_true, y_score=y_score)
  roc_auc = auc(fpr, tpr)
  label =  name + ' ROC curve (area = %0.2f)' % roc_auc
  plt.plot(fpr, tpr, label=label)

plt.plot([0, 1], [0, 1], color='navy', linestyle='--')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curve for Threshold = {:.1f}'.format(threshold))
plt.legend()
plt.show(0)

"""
Question 36:
Plot average precision (Y-axis) against t (X-axis) for the ranking obtained using
k-NN collaborative filter predictions. Also, plot the average recall (Y-axis)
against t (X-axis) and average precision (Y-axis) against average
recall (X-axis). Use the k found in question 11 and sweep t from 1 to 25 in step
sizes of 1. For each plot, briefly comment on the shape of the plot.
"""
def calc_precision_recall(pred, t, threshold=3.0):
  user_ratings = defaultdict(list)
  for uid,_,r_ui, est, _ in pred:
    bisect.insort(user_ratings[uid], (est, r_ui))

  precision, recall  = dict(), dict()
  for uid, ratings in user_ratings.items():
    if len(ratings) < t:
      continue
    # |G|
    G = sum((r_ui >= threshold) for (_, r_ui) in ratings)
    if int(G) == 0:
      continue
    StnG = sum(((est >= threshold) and (est >= threshold)) for (est, r_ui) in ratings[-t:])
    precision[uid], recall[uid] = StnG / t, StnG / G
  return (precision, recall)

kf = KFold(n_splits=10)
ts = list(range(1,25+1))
threshold = 3

sim_options = {
  'name': 'pearson',
  'user_based': True
}

knn_prec, knn_recall = [], []
for t in ts:
  precision_sum, recall_sum = 0.0, 0.0
  knn = KNNWithMeans(k=20, sim_options=sim_options)
  for trainset, testset in kf.split(data):
    knn.fit(trainset)
    pred = knn.test(testset)
    precision, recall = calc_precision_recall(pred, int(t), threshold)
    precision_sum += np.mean(list(precision.values()))
    recall_sum += np.mean(list(recall.values()))
  precision_avg = precision_sum / kf.n_splits
  recall_avg = recall_sum / kf.n_splits
  print(f"kNN t: {t}, precision_avg: {precision_avg}, recall_avg: {recall_avg}")
  knn_prec.append(precision_avg)
  knn_recall.append(recall_avg)

plt.figure()
plt.subplot(2,1,1)
plt.title("kNN: Avg Precision vs t with 10 fold CV")
plt.ylabel("Avg Precision")
plt.plot(ts, knn_prec)

plt.subplot(2,1,2)
plt.title("kNN: Avg Recall vs t with 10 fold CV")
plt.xlabel("t (recommend item set size)")
plt.ylabel("Avg Recall")
plt.plot(ts, knn_recall)

plt.figure()
plt.title("kNN: Avg Precision vs Avg Recall with 10 fold CV")
plt.xlabel("Avg Recall")
plt.ylabel("Avg Precision")
plt.plot(knn_recall, knn_prec)
plt.show(0)

"""
Question 37
"""
nmf_prec, nmf_recall = [], []
for t in ts:
  precision_sum, recall_sum = 0.0, 0.0
  nmf = NMF(n_factors=20, biased=False)
  for trainset, testset in kf.split(data):
    nmf.fit(trainset)
    pred = nmf.test(testset)
    precision, recall = calc_precision_recall(pred, int(t), threshold)
    precision_sum += np.mean(list(precision.values()))
    recall_sum += np.mean(list(recall.values()))
  precision_avg = precision_sum / kf.n_splits
  recall_avg = recall_sum / kf.n_splits
  print(f"NMF t: {t}, precision_avg: {precision_avg}, recall_avg: {recall_avg}")
  nmf_prec.append(precision_avg)
  nmf_recall.append(recall_avg)

plt.figure()
plt.subplot(2,1,1)
plt.title("NMF: Avg Precision vs t with 10 fold CV")
plt.ylabel("Avg Precision")
plt.plot(ts, nmf_prec)

plt.subplot(2,1,2)
plt.title("NMF: Avg Recall vs t with 10 fold CV")
plt.xlabel("t (recommend item set size)")
plt.ylabel("Avg Recall")
plt.plot(ts, nmf_recall)

plt.figure()
plt.title("NMF: Avg Precision vs Avg Recall with 10 fold CV")
plt.xlabel("Avg Recall")
plt.ylabel("Avg Precision")
plt.plot(nmf_recall, nmf_prec)
plt.show(0)

"""
Question 38
"""
mf_prec, mf_recall = [], []
for t in ts:
  precision_sum, recall_sum = 0.0, 0.0
  svd = SVD(n_factors=50, random_state=42)
  for trainset, testset in kf.split(data):
    svd.fit(trainset)
    pred = svd.test(testset)
    precision, recall = calc_precision_recall(pred, int(t), threshold)
    precision_sum += np.mean(list(precision.values()))
    recall_sum += np.mean(list(recall.values()))
  precision_avg = precision_sum / kf.n_splits
  recall_avg = recall_sum / kf.n_splits
  print(f"MF t: {t}, precision_avg: {precision_avg}, recall_avg: {recall_avg}")
  mf_prec.append(precision_avg)
  mf_recall.append(recall_avg)

plt.figure()
plt.subplot(2,1,1)
plt.title("MF: Avg Precision vs t with 10 fold CV")
plt.ylabel("Avg Precision")
plt.plot(ts, mf_prec)

plt.subplot(2,1,2)
plt.title("MF: Avg Recall vs t with 10 fold CV")
plt.xlabel("t (recommend item set size)")
plt.ylabel("Avg Recall")
plt.plot(ts, mf_recall)

plt.figure()
plt.title("MF: Avg Precision vs Avg Recall with 10 fold CV")
plt.xlabel("Avg Recall")
plt.ylabel("Avg Precision")
plt.plot(mf_recall, mf_prec)
plt.show(0)

"""
Question 39
"""
plt.figure()
plt.title("Avg Precision vs Avg Recall with 10 fold CV")
plt.xlabel("Avg Recall")
plt.ylabel("Avg Precision")
plt.plot(knn_recall, knn_prec, label='kNN')
plt.plot(nmf_recall, nmf_prec, label='NMF')
plt.plot(mf_recall, mf_prec, label='MF')
plt.legend()
plt.show(0)
