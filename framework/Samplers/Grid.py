"""
  This module contains the Grid sampling strategy

  Created on May 21, 2016
  @author: alfoa
  supercedes Samplers.py from alfoa
"""
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
#if not 'xrange' in dir(__builtins__): xrange = range
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------

#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
from .ForwardSampler import ForwardSampler
#Internal Modules End--------------------------------------------------------------------------------

class Grid(ForwardSampler):
  """
    Samples the model on a given (by input) set of points
  """
  def __init__(self):
    """
    Default Constructor that will initialize member variables with reasonable
    defaults or empty lists/dictionaries where applicable.
    @ In, None
    @ Out, None
    """
    ForwardSampler.__init__(self)
    self.printTag = 'SAMPLER GRID'
    self.axisName             = []           # the name of each axis (variable)
    self.gridInfo             = {}           # {'name of the variable':Type}  --> Type: CDF/Value
    self.externalgGridCoord   = False        # boolean attribute. True if the coordinate list has been filled by external source (see factorial sampler)
    self.gridCoordinate       = []           # current grid coordinates
    self.gridEntity           = GridEntities.returnInstance('GridEntity',self)

  def localInputAndChecks(self,xmlNode):
    """
      Class specific xml inputs will be read here and checked for validity.
      @ In, xmlNode, xml.etree.ElementTree.Element, The xml element node that will be checked against the available options specific to this Sampler.
      @ Out, None
    """
    if 'limit' in xmlNode.attrib.keys(): self.raiseAnError(IOError,'limit is not used in Grid sampler')
    self.limit = 1
    self.gridEntity._readMoreXml(xmlNode,dimensionTags=["variable","Distribution"],messageHandler=self.messageHandler, dimTagsPrefix={"Distribution":"<distribution>"})
    grdInfo = self.gridEntity.returnParameter("gridInfo")
    for axis, value in grdInfo.items(): self.gridInfo[axis] = value[0]
    if len(self.toBeSampled.keys()) != len(grdInfo.keys()): self.raiseAnError(IOError,'inconsistency between number of variables and grid specification')
    self.axisName = list(grdInfo.keys())
    self.axisName.sort()

  def localGetInitParams(self):
    """
      Appends a given dictionary with class specific member variables and their
      associated initialized values.
      @ In, None
      @ Out, paramDict, dict, dictionary containing the parameter names as keys
        and each parameter's initial value as the dictionary values
    """
    paramDict = {}
    for variable,value in self.gridInfo.items():
      paramDict[variable+' is sampled using a grid in '] = value
    return paramDict

  def localGetCurrentSetting(self):
    """
      Appends a given dictionary with class specific information regarding the
      current status of the object.
      @ In, None
      @ Out, paramDict, dict, dictionary containing the parameter names as keys
        and each parameter's initial value as the dictionary values
    """
    paramDict = {}
    for var, value in self.values.items():
      paramDict['coordinate '+var+' has value'] = value
    return paramDict

  def localInitialize(self):
    """
      Will perform all initialization specific to this Sampler. For instance,
      creating an empty container to hold the identified surface points, error
      checking the optionally provided solution export and other preset values,
      and initializing the limit surface Post-Processor used by this sampler.
      @ In, None
      @ Out, None
    """
    self.gridEntity.initialize()
    self.limit = self.gridEntity.len()


  def localGenerateInput(self,model,myInput):
    """
      Function to select the next most informative point for refining the limit
      surface search.
      After this method is called, the self.inputInfo should be ready to be sent
      to the model
      @ In, model, model instance, an instance of a model
      @ In, myInput, list, a list of the original needed inputs for the model (e.g. list of files, etc.)
      @ Out, None
    """
    self.inputInfo['distributionName'] = {} #Used to determine which distribution to change if needed.
    self.inputInfo['distributionType'] = {} #Used to determine which distribution type is used
    weight = 1.0
    found=False
    while not found:
      recastDict = {}
      for i in range(len(self.axisName)):
        varName = self.axisName[i]
        if self.gridInfo[varName]=='CDF':
          if self.distDict[varName].getDimensionality()==1: recastDict[varName] = [self.distDict[varName].ppf]
          else: recastDict[varName] = [self.distDict[varName].inverseMarginalDistribution,[self.variables2distributionsMapping[varName]['dim']-1]]
        elif self.gridInfo[varName]!='value': self.raiseAnError(IOError,self.gridInfo[varName]+' is not know as value keyword for type. Sampler: '+self.name)
      if self.externalgGridCoord: currentIndexes, coordinates = self.gridEntity.returnIteratorIndexesFromIndex(self.gridCoordinate), self.gridEntity.returnCoordinateFromIndex(self.gridCoordinate, True, recastDict)
      else                      : currentIndexes, coordinates = self.gridEntity.returnIteratorIndexes(), self.gridEntity.returnPointAndAdvanceIterator(True,recastDict)
      if coordinates == None: raise utils.NoMoreSamplesNeeded
      coordinatesPlusOne  = self.gridEntity.returnShiftedCoordinate(currentIndexes,dict.fromkeys(self.axisName,1))
      coordinatesMinusOne = self.gridEntity.returnShiftedCoordinate(currentIndexes,dict.fromkeys(self.axisName,-1))
      for i in range(len(self.axisName)):
        varName = self.axisName[i]
        # compute the SampledVarsPb for 1-D distribution
        if ("<distribution>" in varName) or (self.variables2distributionsMapping[varName]['totDim']==1):
          for key in varName.strip().split(','):
            self.inputInfo['distributionName'][key] = self.toBeSampled[varName]
            self.inputInfo['distributionType'][key] = self.distDict[varName].type
            self.values[key] = coordinates[varName]
            self.inputInfo['SampledVarsPb'][key] = self.distDict[varName].pdf(self.values[key])
        # compute the SampledVarsPb for N-D distribution
        else:
            if self.variables2distributionsMapping[varName]['reducedDim']==1:    # to avoid double count;
              distName = self.variables2distributionsMapping[varName]['name']
              ndCoordinate=[0]*len(self.distributions2variablesMapping[distName])
              positionList = self.distributions2variablesIndexList[distName]
              for var in self.distributions2variablesMapping[distName]:
                variable = utils.first(var.keys())
                position = utils.first(var.values())
                ndCoordinate[positionList.index(position)] = float(coordinates[variable.strip()])
                for key in variable.strip().split(','):
                  self.inputInfo['distributionName'][key] = self.toBeSampled[variable]
                  self.inputInfo['distributionType'][key] = self.distDict[variable].type
                  self.values[key] = coordinates[variable]
              # Based on the discussion with Diego, we will use the following to compute SampledVarsPb.
              self.inputInfo['SampledVarsPb'][varName] = self.distDict[varName].pdf(ndCoordinate)
        # Compute the ProbabilityWeight
        if ("<distribution>" in varName) or (self.variables2distributionsMapping[varName]['totDim']==1):
          if self.distDict[varName].getDisttype() == 'Discrete':
            weight *= self.distDict[varName].pdf(coordinates[varName])
          else:
            if self.gridInfo[varName]=='CDF':
              if coordinatesPlusOne[varName] != sys.maxsize and coordinatesMinusOne[varName] != -sys.maxsize:
                midPlusCDF   = (coordinatesPlusOne[varName]+self.distDict[varName].cdf(self.values[key]))/2.0
                midMinusCDF  = (coordinatesMinusOne[varName]+self.distDict[varName].cdf(self.values[key]))/2.0
                self.inputInfo['ProbabilityWeight-'+varName.replace(",","-")] = midPlusCDF - midMinusCDF
                weight *= midPlusCDF - midMinusCDF
              if coordinatesMinusOne[varName] == -sys.maxsize:
                midPlusCDF   = (coordinatesPlusOne[varName]+self.distDict[varName].cdf(self.values[key]))/2.0
                midMinusCDF  = 0.0
                self.inputInfo['ProbabilityWeight-'+varName.replace(",","-")] = midPlusCDF - midMinusCDF
                weight *= midPlusCDF - midMinusCDF
              if coordinatesPlusOne[varName] == sys.maxsize:
                midPlusCDF   = 1.0
                midMinusCDF  = (coordinatesMinusOne[varName]+self.distDict[varName].cdf(self.values[key]))/2.0
                self.inputInfo['ProbabilityWeight-'+varName.replace(",","-")] = midPlusCDF - midMinusCDF
                weight *= midPlusCDF - midMinusCDF
            else:   # Value
              if coordinatesPlusOne[varName] != sys.maxsize and coordinatesMinusOne[varName] != -sys.maxsize:
                midPlusValue   = (self.values[key]+coordinatesPlusOne[varName])/2.0
                midMinusValue  = (self.values[key]+coordinatesMinusOne[varName])/2.0
                weight *= self.distDict[varName].cdf(midPlusValue) - self.distDict[varName].cdf(midMinusValue)
                self.inputInfo['ProbabilityWeight-'+varName.replace(",","-")] = self.distDict[varName].cdf(midPlusValue) - self.distDict[varName].cdf(midMinusValue)
              if coordinatesMinusOne[varName] == -sys.maxsize:
                midPlusValue   = (self.values[key]+coordinatesPlusOne[varName])/2.0
                self.inputInfo['ProbabilityWeight-'+varName.replace(",","-")] = self.distDict[varName].cdf(midPlusValue) - 0.0
                weight *= self.distDict[varName].cdf(midPlusValue) - 0.0
              if coordinatesPlusOne[varName] == sys.maxsize:
                midMinusValue  = (self.values[key]+coordinatesMinusOne[varName])/2.0
                self.inputInfo['ProbabilityWeight-'+varName.replace(",","-")] = 1.0 - self.distDict[varName].cdf(midMinusValue)
                weight *= 1.0 - self.distDict[varName].cdf(midMinusValue)
        # ND variable
        else:
          if self.variables2distributionsMapping[varName]['reducedDim']==1:    # to avoid double count of weight for ND distribution; I need to count only one variable instaed of N
            distName = self.variables2distributionsMapping[varName]['name']
            ndCoordinate=np.zeros(len(self.distributions2variablesMapping[distName]))
            dxs=np.zeros(len(self.distributions2variablesMapping[distName]))
            positionList = self.distributions2variablesIndexList[distName]
            for var in self.distributions2variablesMapping[distName]:
              variable = utils.first(var.keys()).strip()
              position = utils.first(var.values())
              if self.gridInfo[variable]=='CDF':
                if coordinatesPlusOne[variable] != sys.maxsize and coordinatesMinusOne[variable] != -sys.maxsize:
                  up   = self.distDict[variable].inverseMarginalDistribution(coordinatesPlusOne[variable] ,self.variables2distributionsMapping[variable]['dim']-1)
                  down = self.distDict[variable].inverseMarginalDistribution(coordinatesMinusOne[variable],self.variables2distributionsMapping[variable]['dim']-1)
                  dxs[positionList.index(position)] = (up - down)/2.0
                  ndCoordinate[positionList.index(position)] = coordinates[variable] - (coordinates[variable] - down)/2.0 + dxs[positionList.index(position)]/2.0
                if coordinatesMinusOne[variable] == -sys.maxsize:
                  up = self.distDict[variable].inverseMarginalDistribution(coordinatesPlusOne[variable] ,self.variables2distributionsMapping[variable]['dim']-1)
                  dxs[positionList.index(position)] = (coordinates[variable.strip()]+up)/2.0 - self.distDict[varName].returnLowerBound(positionList.index(position))
                  ndCoordinate[positionList.index(position)] = ((coordinates[variable.strip()]+up)/2.0 + self.distDict[varName].returnLowerBound(positionList.index(position)))/2.0
                if coordinatesPlusOne[variable] == sys.maxsize:
                  down = self.distDict[variable].inverseMarginalDistribution(coordinatesMinusOne[variable],self.variables2distributionsMapping[variable]['dim']-1)
                  dxs[positionList.index(position)] = self.distDict[varName].returnUpperBound(positionList.index(position)) - (coordinates[variable.strip()]+down)/2.0
                  ndCoordinate[positionList.index(position)] = (self.distDict[varName].returnUpperBound(positionList.index(position)) + (coordinates[variable.strip()]+down)/2.0) /2.0
              else:
                if coordinatesPlusOne[variable] != sys.maxsize and coordinatesMinusOne[variable] != -sys.maxsize:
                  dxs[positionList.index(position)] = (coordinatesPlusOne[variable] - coordinatesMinusOne[variable])/2.0
                  ndCoordinate[positionList.index(position)] = coordinates[variable.strip()] - (coordinates[variable.strip()]-coordinatesMinusOne[variable])/2.0 + dxs[positionList.index(position)]/2.0
                if coordinatesMinusOne[variable] == -sys.maxsize:
                  dxs[positionList.index(position)]          =  (coordinates[variable.strip()]+coordinatesPlusOne[variable])/2.0 - self.distDict[varName].returnLowerBound(positionList.index(position))
                  ndCoordinate[positionList.index(position)] = ((coordinates[variable.strip()]+coordinatesPlusOne[variable])/2.0 + self.distDict[varName].returnLowerBound(positionList.index(position)))/2.0
                if coordinatesPlusOne[variable] == sys.maxsize:
                  dxs[positionList.index(position)]          =  self.distDict[varName].returnUpperBound(positionList.index(position)) - (coordinates[variable.strip()]+coordinatesMinusOne[variable])/2.0
                  ndCoordinate[positionList.index(position)] = (self.distDict[varName].returnUpperBound(positionList.index(position)) + (coordinates[variable.strip()]+coordinatesMinusOne[variable])/2.0) /2.0
            self.inputInfo['ProbabilityWeight-'+varName.replace(",","!")] = self.distDict[varName].cellIntegral(ndCoordinate,dxs)
            weight *= self.distDict[varName].cellIntegral(ndCoordinate,dxs)
      newpoint = tuple(self.values[key] for key in self.values.keys())
      inExisting,_,_ = mathUtils.NDInArray(np.array(self.existing.keys()),newpoint,tol=self.restartTolerance)
      if not inExisting:
        found=True
        self.raiseADebug('New point found: '+str(newpoint))
      else:
        self.counter+=1
        self.inputInfo['prefix'] = str(self.counter)
        if self.counter>=self.limit: raise utils.NoMoreSamplesNeeded
        self.raiseADebug('Point',newpoint,'found in restart.')
      self.inputInfo['PointProbability' ] = reduce(mul, self.inputInfo['SampledVarsPb'].values())
      self.inputInfo['ProbabilityWeight'] = copy.deepcopy(weight)
      self.inputInfo['SamplerType'] = 'Grid'
