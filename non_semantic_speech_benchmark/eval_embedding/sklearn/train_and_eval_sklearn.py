# coding=utf-8
# Copyright 2020 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""Train and eval a sklearn model."""

import os
import pickle
import time
from absl import logging

import numpy as np

from non_semantic_speech_benchmark import file_utils
from non_semantic_speech_benchmark.eval_embedding import eer_metric
from non_semantic_speech_benchmark.eval_embedding.sklearn import models
from non_semantic_speech_benchmark.eval_embedding.sklearn import sklearn_utils


def train_and_get_score(embedding_name, label_name, label_list, train_glob,
                        eval_glob, test_glob, model_name, l2_normalization,
                        speaker_id_name=None, save_model_dir=None,
                        calculate_equal_error_rate=False):
  """Train and eval sklearn models on data.

  Args:
    embedding_name: Name of embedding.
    label_name: Name of label to use.
    label_list: Python list of all values for label.
    train_glob: Location of training data, as tf.Examples.
    eval_glob: Location of eval data, as tf.Examples.
    test_glob: Location of test data, as tf.Examples.
    model_name: Name of model.
    l2_normalization: Python bool. If `True`, normalize embeddings by L2 norm.
    speaker_id_name: `None`, or name of speaker ID field.
    save_model_dir: If not `None`, write sklearn models to this directory.
    calculate_equal_error_rate: Whether to return score function or Equal Error
      Rate.

  Returns:
    A tuple of Python floats, (eval metric, test metric).
  """
  def _cur_s(s):
    return time.time() - s
  def _cur_m(s):
    return (time.time() - s) / 60.0

  # Read and validate data.
  def _read_glob(glob, name):
    s = time.time()
    npx, npy = sklearn_utils.tfexamples_to_nps(
        glob,
        embedding_name,
        label_name,
        label_list,
        l2_normalization,
        speaker_id_name)
    logging.info('Finished reading %s data: %.2f sec.', name, _cur_s(s))
    return npx, npy
  npx_train, npy_train = _read_glob(train_glob, 'train')
  npx_eval, npy_eval = _read_glob(eval_glob, 'eval')
  npx_test, npy_test = _read_glob(test_glob, 'test')

  # Sanity check npx_*.
  assert npx_train.size > 0
  assert npx_eval.size > 0
  assert npx_test.size > 0

  # Sanity check npy_train.
  assert npy_train.size > 0
  assert np.unique(npy_train).size > 1
  # Sanity check npy_eval.
  assert npy_eval.size > 0
  assert np.unique(npy_eval).size > 1
  # Sanity check npy_test.
  assert npy_test.size > 0
  assert np.unique(npy_test).size > 1

  # Train models.
  d = models.get_sklearn_models()[model_name]()
  logging.info('Made model.')

  s = time.time()
  d.fit(npx_train, npy_train)
  logging.info('Trained model: %.2f min', _cur_m(s))

  if calculate_equal_error_rate:
    # Eval.
    regression_output = d.predict_proba(npx_eval)[:, 1]  # Prob of class 1.
    eval_score = eer_metric.calculate_eer(regression_output, npy_eval)
    # Test.
    regression_output = d.predict_proba(npx_test)[:, 1]  # Prob of class 1.
    test_score = eer_metric.calculate_eer(regression_output, npy_test)
  else:
    # Eval.
    eval_score = d.score(npx_eval, npy_eval)
    # Test.
    test_score = d.score(npx_test, npy_test)
  logging.info('%s: %.3f', model_name, eval_score)
  logging.info('%s: %.3f', model_name, test_score)

  # If `save_model_dir` is present, write model to this directory.
  # To load the model after saving, use:
  # ```python
  # with file_utils.Open(model_filename, 'rb') as f:
  #   m = pickle.load(f)
  # ```
  if save_model_dir:
    file_utils.MaybeMakeDirs(save_model_dir)
    model_filename = os.path.join(save_model_dir, f'{model_name}.pickle')
    with file_utils.Open(model_filename, 'wb') as f:
      pickle.dump(d, f)

  return (eval_score, test_score)
