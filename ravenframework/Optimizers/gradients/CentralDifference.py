"""
  Central difference approximation algorithms
  Author:--gairabhi
"""
import copy
from ...utils import mathUtils
from .GradientApproximator import GradientApproximator
lr = None
zeros = None

class CentralDifference(GradientApproximator):
  """
    Enables gradient estimation via central differencing
  """
  @classmethod
  def getInputSpecification(cls):
    """
      Method to get a reference to a class that specifies the input data for class cls.
      @ In, cls, the class for which we are retrieving the specification
      @ Out, specs, InputData.ParameterInput, class to use for specifying input of cls.
    """
    specs = super(CentralDifference, cls).getInputSpecification()
    specs.description = r"""if node is present, indicates that gradient approximation should be performed
        using Central Difference approximation. Central difference makes use of pairs of orthogonal perturbations
        in each dimension of the input space to estimate the local gradient, requiring a total of $2N$
        perturbations, where $N$ is dimensionality of the input space. For example, if the input space
        $\mathbf{i} = (x, y, z)$ for objective function $f(\mathbf{i})$, then CentralDifference chooses
        three perturbations $(\alpha, \beta, \gamma)$ and evaluates the following perturbation points:
        \begin{itemize}
          \item $f(x\pm\alpha, y, z)$,
          \item $f(x, y\pm\beta, z)$,
          \item $f(x, y, z\pm\gamma)$
        \end{itemize}
        and evaluates the gradient $\nabla f = (\nabla^{(x)} f, \nabla^{(y)} f, \nabla^{(z)} f)$ as
        \begin{equation*}
          \nabla^{(x)}f \approx \frac{f(x+\alpha, y, z) - f(x-\alpha, y, z)}{2\alpha},
        \end{equation*}
        and so on for $ \nabla^{(y)}f$ and $\nabla^{(z)}f$.
          """

    return specs

  def chooseEvaluationPoints(self, opt, stepSize, constraints=None):
    """
      Determines new point(s) needed to evaluate gradient
      @ In, opt, dict, current opt point (normalized)
      @ In, stepSize, float, distance from opt point to sample neighbors
      @ In, constraints, dict, optional, constraints to check against when choosing new sample points
      @ Out, evalPoints, list(dict), list of points that need sampling
      @ Out, evalInfo, list(dict), identifying information about points
    """
    dh = self._proximity * stepSize
    evalPoints = []
    evalInfo = []
    # submit a positive and negative side of the opt point for each dimension
    for _, optVar in enumerate(self._optVars):
      optValue = opt[optVar]
      neg = copy.deepcopy(opt)
      pos = copy.deepcopy(opt)
      delta = dh
      neg[optVar] = optValue - delta
      pos[optVar] = optValue + delta
      for s in range(self._numberSamples):

        evalPoints.append(neg)
        evalInfo.append({'type': 'grad',
                        'optVar': optVar,
                        'delta': delta,
                        'side': 'negative',
                        'sampleId': s + 1})

        evalPoints.append(pos)
        evalInfo.append({'type': 'grad',
                        'optVar': optVar,
                        'delta': delta,
                        'side': 'positive',
                        'sampleId': s + 1})

    return evalPoints, evalInfo

  def evaluate(self, opt, grads, infos, objVar):
    """
      Approximates gradient based on evaluated points.
      @ In, opt, dict, current opt point (normalized)
      @ In, grads, list(dict), evaluated neighbor points
      @ In, infos, list(dict), info about evaluated neighbor points
      @ In, objVar, string, objective variable
      @ Out, magnitude, float, magnitude of gradient
      @ Out, direction, dict, versor (unit vector) for gradient direction
      @ Out, foundInf, bool, if True then infinity calculations were used
    """
    gradient = {}
    global lr
    global zeros
    if lr is None:
      import numpy as np
      import sklearn
      import sklearn.linear_model
      lr = sklearn.linear_model.LinearRegression()
      zeros = np.zeros
    X, y= zeros((len(grads), len(self._optVars))),  zeros(len(grads))
    for g, grad in enumerate(grads):
      for i, var in enumerate(self._optVars):
        X[g, i] = grads[g][var]
      y[g] = grads[g][objVar]
    der =  lr.fit(X, y).coef_
    for i, var in enumerate(self._optVars):
      gradient[var] = der[i]

    magnitude, direction, foundInf = mathUtils.calculateMagnitudeAndVersor(list(gradient.values()))
    direction = dict((var, float(direction[v])) for v, var in enumerate(gradient.keys()))

    return magnitude, direction, foundInf

  def numGradPoints(self):
    """
      Returns the number of grad points required for the method
      @ In, None
      @ Out, numGradPoints, int, number grad points times number of samples needed
    """
    return self.N * 2 * self._numberSamples
