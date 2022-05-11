# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for aqt_tensor."""

from absl.testing import absltest
from aqt.jax import aqt_tensor
from aqt.tensorflow import aqt_stats_test_base
from aqt.tensorflow import aqt_tensor_test_base
import jax
import jax.numpy as jnp
import numpy as np


def f32(x):
  """Casts 'x' to be a float32 jax array."""
  return jnp.array(x, dtype=jnp.float32)


class StatsTest(aqt_stats_test_base.StatsTest):
  """Tests for Stats class.

  Refer to aqt_stats_test_base.StatsTest for more details.
  """

  def set_stats(self, data_shape, config):
    self._stats = aqt_tensor.Stats.init_stats(
        data_shape=data_shape, config=config)

  def update(self, sample, weight):
    self._stats = self._stats.with_update(f32(sample), f32(weight))

  def get_sum_of_ones(self):
    return self._stats.sum_of_ones

  def get_sum_of_vals(self):
    return self._stats.sum_of_vals

  def get_max_of_abs_vals(self):
    return self._stats.max_dev()

  def get_sum_of_l1_vals(self):
    return self._stats.sum_of_l1_vals

  def get_sum_of_lp_vals(self):
    return self._stats.sum_of_lp_vals

  def set_ema_update_count(self, ema_update_count):
    self._stats = self._stats.replace(ema_update_count=ema_update_count)


class AqtTensorQuantizerTest(aqt_tensor_test_base.AqtTensorQuantizerTest):
  """Tests for AqtTensorQuantizer class.

  Refer to aqt_test_shared_base.AqtTensorQuantizerTest for more details.
  """

  _quant_state = {}

  def make_tensor_quantizer(self, data_shape, config, name="tq"):
    quant = aqt_tensor.TensorQuantizer(data_shape=data_shape, config=config,
                                       name=name)
    self._quant_state[name] = quant.init(jax.random.PRNGKey(0))
    return quant

  def update_quantizer(self, quant, sample, weight, event_count):
    _, self._quant_state[quant.name] = quant.apply(
        self._quant_state[quant.name],
        sample,
        weight,
        int(event_count),
        method=quant.update,
        mutable="TensorQuantizer")

  def to_quant(self, quant, x, train=True):
    return quant.apply(
        self._quant_state[quant.name], x, train, method=quant._to_quant)

  def from_quant_scale(self, quant, train=True):
    return quant.apply(
        self._quant_state[quant.name],  #
        train,
        method=quant._from_quant_scale)

  def init(self):
    pass

  def get_scale(self, quant):
    return self._quant_state[quant.name]["TensorQuantizer"]["scale"]

  def get_last_update(self, quant):
    return self._quant_state[quant.name]["TensorQuantizer"]["last_update"]

  def get_clip_range(self, quant):
    return quant.apply(self._quant_state[quant.name], method=quant.clip_range)

  def get_quantized_variable(self, quant):
    return self._quant_state[
        quant.name]["TensorQuantizer"]["quantized_variable"]

  def test_pass_through(self):
    inp = jnp.float32(100)
    eps = jnp.finfo(jnp.float32).eps

    def fn(x):
      return x * eps + eps

    actual = aqt_tensor.pass_through(inp, fn)
    expected = fn(inp)

    # Pass-through function should return the same output as fn(x).
    np.testing.assert_equal(actual, expected)

    # The gradient of fn() should be 1.0 since STE makes it pretend to be an
    # identity function during the backward pass.
    np.testing.assert_equal(jnp.array(1.0),
                            jax.grad(aqt_tensor.pass_through)(inp, fn))

if __name__ == "__main__":
  absltest.main()