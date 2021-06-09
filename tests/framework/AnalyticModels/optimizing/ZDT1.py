# Copyright 2017 Battelle Energy Alliance, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# from https://en.wikipedia.org/wiki/Test_functions_for_optimization
#
# takes input parameters x,y
# returns value in "ans"
# constrained function
# optimal minimum at f(-3.1302468, -1.5821422) = -106.7645367
# parameter range is -10 <= x <= 0, -6.5 <= y <= 0
import numpy as np

def evaluate(x):
  """
    Evaluates ZDT1 function.
    @ In, x, float, value
    @ In, y, float, value
    @ Out, evaluate, value at x, y
  """
  dim = len(x)
  f1 = x[0]
  g = 1 + 9 * np.sum(x[1:dim]/(dim-1))
  h = 1 - np.sqrt(f1/g)
  f2 = g * h
  return [f1, f2]

def constraint(x,y):
  """
    Evaluates the constraint function @ a given point (x,y)
    @ In, x, float, value of the design variable x
    @ In, y, float, value of the design variable y
    @ Out, g(x,y), float, $g(x, y) = 25 - ((x+5.)**2 + (y+5.)**2)$
            the way the constraint is designed is that
            the constraint function has to be >= 0,
            so if:
            1) f(x,y) >= 0 then g = f
            2) f(x,y) >= a then g = f - a
            3) f(x,y) <= b then g = b - f
            4) f(x,y)  = c then g = 0.001 - (f(x,y) - c)
  """
  pass

###
# RAVEN hooks
###

def run(self,Inputs):
  """
    RAVEN API
    @ In, self, object, RAVEN container
    @ In, Inputs, dict, additional inputs
    @ Out, None
  """
  objectives = evaluate(self.x)
  self.ans1 = objectives[0]
  self.ans2 = objectives[1]

def constrain(self):
  """
    Constrain calls the constraint function.
    @ In, self, object, RAVEN container
    @ Out, explicitConstrain, float, positive if the constraint is satisfied
           and negative if violated.
  """
  pass