"""
Created on Nov 14, 2013

@author: alfoa
"""
#for future compatibility with Python 3-----------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
if not 'xrange' in dir(__builtins__):
  xrange = range
#End compatibility block for Python 3-------------------------------------------

#External Modules---------------------------------------------------------------
import numpy as np
import ast
#from scipy.interpolate import Rbf, griddata
import numpy.ma as ma
import importlib  # it is used in exec code so it might be detected as unused
import platform
import os
import re
#External Modules End-----------------------------------------------------------

#Internal Modules---------------------------------------------------------------
import utils
import mathUtils
from cached_ndarray import c1darray
from .OutStreamManager import OutStreamManager
#Internal Modules End-----------------------------------------------------------

# set a global variable for backend default setting
if platform.system() == 'Windows':
  disAvail = True
else:
  if os.getenv('DISPLAY'):
    disAvail = True
  else:
    disAvail = False

class OutStreamPlot(OutStreamManager):
  """
    OutStream of type Plot
  """
  def __init__(self):
    """
      Initialization method defines the available plot types, the identifier of
      this object and sets default values for required data.
      @ In, None
      @ Out, None
    """
    OutStreamManager.__init__(self)
    self.type = 'OutStreamPlot'
    self.printTag = 'OUTSTREAM PLOT'
    # available 2D and 3D plot types
    self.availableOutStreamTypes = {2:['scatter', 'line', 'histogram', 'stem', 'step', 'pseudocolor', 'dataMining'],
                                    3:['scatter', 'line', 'stem', 'surface', 'wireframe', 'tri-surface',
                                       'contour', 'filledContour', 'contour3D', 'filledContour3D', 'histogram']}
    # default plot is 2D
    self.dim = 2
    # list of source names
    self.sourceName = []
    # source of data
    self.sourceData = None
    # dictionary of x,y,z coordinates
    self.xCoordinates = None
    self.yCoordinates = None
    self.zCoordinates = None
    # dictionary of x,y,z values
    self.xValues = None
    self.yValues = None
    self.zValues = None
    # color map
    self.colorMapCoordinates = {}
    self.colorMapValues = {}
    # list of the outstream types
    self.outStreamTypes = []
    # interpolate functions available
    self.interpAvail = ['nearest', 'linear', 'cubic', 'multiquadric', 'inverse', 'gaussian', 'Rbflinear', 'Rbfcubic', 'quintic', 'thin_plate']
    # actual plot
    self.actPlot = None
    self.actcm = None
    self.gridSpace = None

    self.clusterLabels = None
    self.clusterValues = None

    # Gaussian Mixtures
    self.mixtureLabels = None
    self.mixtureValues = None
    self.mixtureMeans = None
    self.mixtureCovars = None

  #####################
  #  PRIVATE METHODS  #
  #####################

  def __splitVariableNames(self, what, where):
    """
      Function to split the variable names
      @ In, what, string,  x,y,z or colorMap
      @ In, where, tuple, where[0] = plotIndex, where[1] = variable Index
      @ Out, result, list, splitted variable
    """
    if   what == 'x':
      var = self.xCoordinates [where[0]][where[1]]
    elif what == 'y':
      var = self.yCoordinates [where[0]][where[1]]
    elif what == 'z':
      var = self.zCoordinates [where[0]][where[1]]
    elif what == 'colorMap':
      var = self.colorMapCoordinates[where[0]][where[1]]
    elif what == 'clusterLabels':
      var = self.clusterLabels[where[0]][where[1]]
    elif what == 'mixtureLabels':
      var = self.mixtureLabels[where[0]][where[1]]
    elif what == 'mixtureMeans':
      var = self.mixtureMeans[where[0]][where[1]]
    elif what == 'mixtureCovars':
      var = self.mixtureCovars[where[0]][where[1]]
    # the variable can contain brackets {} (when the symbol "|" is present in the variable name),
    # for example DataName|Input|{RavenAuxiliary|variableName|initial_value} or it can look like DataName|Input|variableName
    if var != None:
      result = [None] * 3
      if   '|input|'  in var.lower():
        match = re.search(r"(\|input\|)", var.lower())
      elif '|output|' in var.lower():
        match = re.search(r"(\|output\|)", var.lower())
      else:
        self.raiseAnError(IOError, 'In Plot ' + self.name + ' for inputted coordinate ' + what + ' the tag "Input" or "Output" (case insensitive) has not been specified (e.g. sourceName|Input|aVariable) in '+var)
      startLoc, endLoc = match.start(), match.end()
      result[0], result[1], result[2] = var[:startLoc], var[startLoc + 1:endLoc - 1], var[endLoc:]
      if '{' in result[-1] and '}' in result[-1]:
        locLower, locUpper = result[-1].find("{"), result[-1].rfind("}")
        result[-1] = result[-1][locLower + 1:locUpper]
    else:
      result = None
    return result

  def __readPlotActions(self, snode):
    """
      Function to read, from the xml input, the actions that are required to be
      performed on this plot
      @ In, snode, xml.etree.ElementTree.Element, xml node containing the action XML node
      @ Out, None
    """
    for node in snode:
      self.options[node.tag] = {}
      if len(node):
        for subnode in node:
          if subnode.tag != 'kwargs':
            self.options[node.tag][subnode.tag] = subnode.text
            if not subnode.text:
              self.raiseAnError(IOError, 'In Plot ' + self.name + '. Problem in sub-tag ' + subnode.tag + ' in ' + node.tag + ' block. Please check!')
          else:
            self.options[node.tag]['attributes'] = {}
            for subsub in subnode:
              try:
                self.options[node.tag]['attributes'][subsub.tag] = ast.literal_eval(subsub.text)
              except:
                self.options[node.tag]['attributes'][subsub.tag] = subsub.text
              if not subnode.text:
                self.raiseAnError(IOError, 'In Plot ' + self.name + '. Problem in sub-tag ' + subnode.tag + ' in ' + node.tag + ' block. Please check!')
      elif node.text:
        if node.text.strip():
          self.options[node.tag][node.tag] = node.text
    if 'how' not in self.options.keys():
      self.options['how'] = {'how':'screen'}

  def __fillCoordinatesFromSource(self):
    """
      Function to retrieve the pointers of the data values (x,y,z)
      @ In, None
      @ Out, __fillCoordinatesFromSource, bool, true if the data are filled, false otherwise
    """
    self.xValues = []
    if self.yCoordinates:
      self.yValues = []
    if self.zCoordinates:
      self.zValues = []
    if self.clusterLabels:
      self.clusterValues = []
    if self.mixtureLabels:
      self.mixtureValues = []
    # if self.colorMapCoordinates[pltindex] != None: self.colorMapValues = []
    for pltindex in range(len(self.outStreamTypes)):
      self.xValues.append(None)
      if self.yCoordinates:
        self.yValues.append(None)
      if self.zCoordinates:
        self.zValues.append(None)
      if self.clusterLabels:
        self.clusterValues.append(None)
      if self.mixtureLabels:
        self.mixtureValues.append(None)
      if self.colorMapCoordinates[pltindex] != None:
        self.colorMapValues[pltindex] = None
    for pltindex in range(len(self.outStreamTypes)):
      if self.sourceData[pltindex].isItEmpty():
        return False
      if self.sourceData[pltindex].type.strip() != 'HistorySet':
        self.xValues[pltindex] = {1:[]}
        if self.yCoordinates:
          self.yValues[pltindex] = {1:[]}
        if self.zCoordinates:
          self.zValues[pltindex] = {1:[]}
        if self.clusterLabels:
          self.clusterValues[pltindex] = {1:[]}
        if self.mixtureLabels:
          self.mixtureValues[pltindex] = {1:[]}
        if self.colorMapCoordinates[pltindex] != None:
          self.colorMapValues[pltindex] = {1:[]}
        for i in range(len(self.xCoordinates [pltindex])):
          xsplit = self.__splitVariableNames('x', (pltindex, i))
          parame = self.sourceData[pltindex].getParam(xsplit[1], xsplit[2], nodeId = 'ending')
          if type(parame) in [np.ndarray, c1darray]:
            self.xValues[pltindex][1].append(np.asarray(parame))
          else:
            conarr = np.zeros(len(parame.keys()))
            index = 0
            for item in parame.values():
              conarr[index] = item[0]
              index += 1
            self.xValues[pltindex][1].append(np.asarray(conarr))
        if self.yCoordinates :
          for i in range(len(self.yCoordinates [pltindex])):
            ysplit = self.__splitVariableNames('y', (pltindex, i))
            parame = self.sourceData[pltindex].getParam(ysplit[1], ysplit[2], nodeId = 'ending')
            if type(parame) in [np.ndarray, c1darray]:
              self.yValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              index = 0
              for item in parame.values():
                conarr[index] = item[0]
                index += 1
              self.yValues[pltindex][1].append(np.asarray(conarr))
        if self.zCoordinates  and self.dim > 2:
          for i in range(len(self.zCoordinates [pltindex])):
            zsplit = self.__splitVariableNames('z', (pltindex, i))
            parame = self.sourceData[pltindex].getParam(zsplit[1], zsplit[2], nodeId = 'ending')
            if type(parame) in [np.ndarray, c1darray]:
              self.zValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              for index in range(len(parame.values())):
                conarr[index] = parame.values()[index][0]
              self.zValues[pltindex][1].append(np.asarray(conarr))
        if self.clusterLabels:
          for i in range(len(self.clusterLabels [pltindex])):
            clustersplit = self.__splitVariableNames('clusterLabels', (pltindex, i))
            parame = self.sourceData[pltindex].getParam(clustersplit[1], clustersplit[2], nodeId = 'ending')
            if type(parame) in [np.ndarray, c1darray]:
              self.clusterValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              for index in range(len(parame.values())):
                conarr[index] = parame.values()[index][0]
              self.clusterValues[pltindex][1].append(np.asarray(conarr))
        if self.mixtureLabels:
          for i in range(len(self.mixtureLabels [pltindex])):
            mixturesplit = self.__splitVariableNames('mixtureLabels', (pltindex, i))
            parame = self.sourceData[pltindex].getParam(mixturesplit[1], mixturesplit[2], nodeId = 'ending')
            if type(parame) in [np.ndarray, c1darray]:
              self.mixtureValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              for index in range(len(parame.values())):
                conarr[index] = parame.values()[index][0]
              self.clusterValues[pltindex][1].append(np.asarray(conarr))
        if self.colorMapCoordinates[pltindex] != None:
          for i in range(len(self.colorMapCoordinates[pltindex])):
            zsplit = self.__splitVariableNames('colorMap', (pltindex, i))
            parame = self.sourceData[pltindex].getParam(zsplit[1], zsplit[2], nodeId = 'ending')
            if type(parame) in [np.ndarray, c1darray]:
              self.colorMapValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              for index in range(len(parame.values())):
                conarr[index] = parame.values()[index][0]
              self.colorMapValues[pltindex][1].append(np.asarray(conarr))
      else:
        # HistorySet
        self.xValues[pltindex] = {}
        if self.yCoordinates:
          self.yValues[pltindex] = {}
        if self.zCoordinates   and self.dim > 2:
          self.zValues[pltindex] = {}
        if self.colorMapCoordinates[pltindex] != None:
          self.colorMapValues[pltindex] = {}
        for cnt, key in enumerate(self.sourceData[pltindex].getInpParametersValues(nodeId = 'RecontructEnding').keys()):
          # the key is the actual history number (ie 1, 2 , 3 etc)
          self.xValues[pltindex][cnt] = []
          if self.yCoordinates:
            self.yValues[pltindex][cnt] = []
          if self.zCoordinates:
            self.zValues[pltindex][cnt] = []
          if self.colorMapCoordinates[pltindex] != None:
            self.colorMapValues[pltindex][cnt] = []
          for i in range(len(self.xCoordinates [pltindex])):
            xsplit = self.__splitVariableNames('x', (pltindex, i))
            datax = self.sourceData[pltindex].getParam(xsplit[1], cnt + 1, nodeId = 'RecontructEnding')
            if xsplit[2] not in datax.keys():
              self.raiseAnError(IOError, "Parameter " + xsplit[2] + " not found as " + xsplit[1] + " in DataObject " + xsplit[0])
            self.xValues[pltindex][cnt].append(np.asarray(datax[xsplit[2]]))
          if self.yCoordinates :
            for i in range(len(self.yCoordinates [pltindex])):
              ysplit = self.__splitVariableNames('y', (pltindex, i))
              datay = self.sourceData[pltindex].getParam(ysplit[1], cnt + 1, nodeId = 'RecontructEnding')
              if ysplit[2] not in datay.keys():
                self.raiseAnError(IOError, "Parameter " + ysplit[2] + " not found as " + ysplit[1] + " in DataObject " + ysplit[0])
              self.yValues[pltindex][cnt].append(np.asarray(datay[ysplit[2]]))
          if self.zCoordinates  and self.dim > 2:
            for i in range(len(self.zCoordinates [pltindex])):
              zsplit = self.__splitVariableNames('z', (pltindex, i))
              dataz = self.sourceData[pltindex].getParam(zsplit[1], cnt + 1, nodeId = 'RecontructEnding')
              if zsplit[2] not in dataz.keys():
                self.raiseAnError(IOError, "Parameter " + zsplit[2] + " not found as " + zsplit[1] + " in DataObject " + zsplit[0])
              self.zValues[pltindex][cnt].append(np.asarray(dataz[zsplit[2]]))
          if self.colorMapCoordinates[pltindex] != None:
            for i in range(len(self.colorMapCoordinates[pltindex])):
              colorSplit = self.__splitVariableNames('colorMap', (pltindex, i))
              dataColor = self.sourceData[pltindex].getParam(colorSplit[1], cnt + 1, nodeId = 'RecontructEnding')
              if colorSplit[2] not in dataColor.keys():
                self.raiseAnError(IOError, "Parameter " + colorSplit[2] + " not found as " + colorSplit[1] + " in DataObject " + colorSplit[0])
              self.colorMapValues[pltindex][cnt].append(np.asarray(dataColor[colorSplit[2]]))
      # check if something has been got or not
      if len(self.xValues[pltindex].keys()) == 0:
        return False
      else:
        for key in self.xValues[pltindex].keys():
          if len(self.xValues[pltindex][key]) == 0:
            return False
          else:
            for i in range(len(self.xValues[pltindex][key])):
              if self.xValues[pltindex][key][i].size == 0:
                return False
      if self.yCoordinates :
        if len(self.yValues[pltindex].keys()) == 0:
          return False
        else:
          for key in self.yValues[pltindex].keys():
            if len(self.yValues[pltindex][key]) == 0:
              return False
            else:
              for i in range(len(self.yValues[pltindex][key])):
                if self.yValues[pltindex][key][i].size == 0:
                  return False
      if self.zCoordinates  and self.dim > 2:
        if len(self.zValues[pltindex].keys()) == 0:
          return False
        else:
          for key in self.zValues[pltindex].keys():
            if len(self.zValues[pltindex][key]) == 0:
              return False
            else:
              for i in range(len(self.zValues[pltindex][key])):
                if self.zValues[pltindex][key][i].size == 0:
                  return False
      if self.clusterLabels :
        if len(self.clusterValues[pltindex].keys()) == 0:
          return False
        else:
          for key in self.clusterValues[pltindex].keys():
            if len(self.clusterValues[pltindex][key]) == 0:
              return False
            else:
              for i in range(len(self.clusterValues[pltindex][key])):
                if self.clusterValues[pltindex][key][i].size == 0:
                  return False
      if self.mixtureLabels :
        if len(self.mixtureValues[pltindex].keys()) == 0:
          return False
        else:
          for key in self.mixtureValues[pltindex].keys():
            if len(self.mixtureValues[pltindex][key]) == 0:
              return False
            else:
              for i in range(len(self.mixtureValues[pltindex][key])):
                if self.mixtureValues[pltindex][key][i].size == 0:
                  return False
      if self.colorMapCoordinates[pltindex] != None:
        if len(self.colorMapValues[pltindex].keys()) == 0:
          return False
        else:
          for key in self.colorMapValues[pltindex].keys():
            if len(self.colorMapValues[pltindex][key]) == 0:
              return False
            else:
              for i in range(len(self.colorMapValues[pltindex][key])):
                if self.colorMapValues[pltindex][key][i].size == 0:
                  return False
    return True

  def __executeActions(self):
    """
      Function to execute the actions that must be performed on this plot (for
      example, set the x,y,z axis ranges, etc.)
      @ In, None
      @ Out, None
    """
    if 'labelFormat' not in self.options.keys():
      if self.dim == 2:
        self.plt.gca().yaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        self.plt.gca().xaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        self.plt.ticklabel_format(**{'style':'sci', 'scilimits':(0, 1), 'useOffset':False, 'axis':'both'})
      if self.dim == 3:
        #self.plt.figure().gca(projection = '3d').yaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        #self.plt.figure().gca(projection = '3d').xaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        #self.plt.figure().gca(projection = '3d').zaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        self.plt3D.ticklabel_format(**{'style':'sci', 'scilimits':(0,1), 'useOffset':False, 'axis':'both'})
    if 'title'        not in self.options.keys():
      if self.dim == 2:
        self.plt.title(self.name, fontdict = {'verticalalignment':'baseline', 'horizontalalignment':'center'})
      if self.dim == 3:
        self.plt3D.set_title(self.name, fontdict = {'verticalalignment':'baseline', 'horizontalalignment':'center'})
    for key in self.options.keys():
      if key in ['how', 'plotSettings', 'figureProperties', 'colorbar']:
        pass
      elif key == 'range':
        if self.dim == 2:
          if 'ymin' in self.options[key].keys():
            self.plt.ylim(ymin = ast.literal_eval(self.options[key]['ymin']))
          if 'ymax' in self.options[key].keys():
            self.plt.ylim(ymax = ast.literal_eval(self.options[key]['ymax']))
          if 'xmin' in self.options[key].keys():
            self.plt.xlim(xmin = ast.literal_eval(self.options[key]['xmin']))
          if 'xmax' in self.options[key].keys():
            self.plt.xlim(xmax = ast.literal_eval(self.options[key]['xmax']))
        elif self.dim == 3:
          if 'xmin' in self.options[key].keys():
            self.plt3D.set_xlim3d(xmin = ast.literal_eval(self.options[key]['xmin']))
          if 'xmax' in self.options[key].keys():
            self.plt3D.set_xlim3d(xmax = ast.literal_eval(self.options[key]['xmax']))
          if 'ymin' in self.options[key].keys():
            self.plt3D.set_ylim3d(ymin = ast.literal_eval(self.options[key]['ymin']))
          if 'ymax' in self.options[key].keys():
            self.plt3D.set_ylim3d(ymax = ast.literal_eval(self.options[key]['ymax']))
          if 'zmin' in self.options[key].keys():
            if 'zmax' not in self.options[key].keys():
              self.raiseAWarning('zmin inputted but not zmax. zmin ignored! ')
            else:self.plt3D.set_zlim(ast.literal_eval(self.options[key]['zmin']), ast.literal_eval(self.options[key]['zmax']))
          if 'zmax' in self.options[key].keys():
            if 'zmin' not in self.options[key].keys():
              self.raiseAWarning('zmax inputted but not zmin. zmax ignored! ')
            else:self.plt3D.set_zlim(ast.literal_eval(self.options[key]['zmin']), ast.literal_eval(self.options[key]['zmax']))
      elif key == 'labelFormat':
        if 'style' not in self.options[key].keys():
          self.options[key]['style'] = 'sci'
        if 'limits' not in self.options[key].keys():
          self.options[key]['limits'] = '(0,0)'
        if 'useOffset' not in self.options[key].keys():
          self.options[key]['useOffset'] = 'False'
        if 'axis' not in self.options[key].keys():
          self.options[key]['axis'] = 'both'
        if self.dim == 2:
          self.plt.ticklabel_format(**{'style':self.options[key]['style'], 'scilimits':ast.literal_eval(self.options[key]['limits']), 'useOffset':ast.literal_eval(self.options[key]['useOffset']), 'axis':self.options[key]['axis']})
        elif self.dim == 3:
          self.plt3D.ticklabel_format(**{'style':self.options[key]['style'], 'scilimits':ast.literal_eval(self.options[key]['limits']), 'useOffset':ast.literal_eval(self.options[key]['useOffset']), 'axis':self.options[key]['axis']})
      elif key == 'camera':
        if self.dim == 2:
          self.raiseAWarning('2D plots have not a camera attribute... They are 2D!!!!')
        elif self.dim == 3:
          if 'elevation' in self.options[key].keys() and 'azimuth' in self.options[key].keys():
            self.plt3D.view_init(elev = float(self.options[key]['elevation']), azim = float(self.options[key]['azimuth']))
          elif 'elevation' in self.options[key].keys() and 'azimuth' not in self.options[key].keys():
            self.plt3D.view_init(elev = float(self.options[key]['elevation']), azim = None)
          elif 'elevation' not in self.options[key].keys() and 'azimuth' in self.options[key].keys():
            self.plt3D.view_init(elev = None, azim = float(self.options[key]['azimuth']))
      elif key == 'title':
        if self.dim == 2:
          self.plt.title(self.options[key]['text'], **self.options[key].get('attributes', {}))
        elif self.dim == 3:
          self.plt3D.set_title(self.options[key]['text'], **self.options[key].get('attributes', {}))
      elif key == 'scale':
        if self.dim == 2:
          if 'xscale' in self.options[key].keys():
            self.plt.xscale(self.options[key]['xscale'], nonposy = 'clip')
          if 'yscale' in self.options[key].keys():
            self.plt.yscale(self.options[key]['yscale'], nonposy = 'clip')
        elif self.dim == 3:
          if 'xscale' in self.options[key].keys():
            self.plt3D.set_xscale(self.options[key]['xscale'], nonposy = 'clip')
          if 'yscale' in self.options[key].keys():
            self.plt3D.set_yscale(self.options[key]['yscale'], nonposy = 'clip')
          if 'zscale' in self.options[key].keys():
            self.plt3D.set_zscale(self.options[key]['zscale'], nonposy = 'clip')
      elif key == 'addText':
        if 'position' not in self.options[key].keys():
          if self.dim == 2 :self.options[key]['position'] = '0.0,0.0'
          else:self.options[key]['position'] = '0.0,0.0,0.0'
        if 'withdash' not in self.options[key].keys():
          self.options[key]['withdash'] = 'False'
        if 'fontdict' not in self.options[key].keys():
          self.options[key]['fontdict'] = 'None'
        else:
          try:
            tempVar = ast.literal_eval(self.options[key]['fontdict'])
            self.options[key]['fontdict'] = str(tempVar)
          except AttributeError:
            self.raiseAnError(TypeError, 'In ' + key + ' tag: can not convert the string "' + self.options[key]['fontdict'] + '" to a dictionary! Check syntax for python function ast.literal_eval')
        if self.dim == 2 :
          self.plt.text(float(self.options[key]['position'].split(',')[0]), float(self.options[key]['position'].split(',')[1]), self.options[key]['text'], fontdict = ast.literal_eval(self.options[key]['fontdict']), **self.options[key].get('attributes', {}))
        elif self.dim == 3:
          self.plt3D.text(float(self.options[key]['position'].split(',')[0]), float(self.options[key]['position'].split(',')[1]), float(self.options[key]['position'].split(',')[2]), self.options[key]['text'], fontdict = ast.literal_eval(self.options[key]['fontdict']), withdash = ast.literal_eval(self.options[key]['withdash']), **self.options[key].get('attributes', {}))
      elif key == 'autoscale':
          if 'enable' not in self.options[key].keys():
            self.options[key]['enable'] = 'True'
          elif self.options[key]['enable'].lower() in utils.stringsThatMeanTrue():
            self.options[key]['enable'] = 'True'
          elif self.options[key]['enable'].lower() in utils.stringsThatMeanFalse():
            self.options[key]['enable'] = 'False'
          if 'axis' not in self.options[key].keys():
            self.options[key]['axis'] = 'both'
          if 'tight' not in self.options[key].keys():
            self.options[key]['tight'] = 'None'

          if self.dim == 2:
            self.plt.autoscale(enable = ast.literal_eval(self.options[key]['enable']), axis = self.options[key]['axis'], tight = ast.literal_eval(self.options[key]['tight']))
          elif self.dim == 3:
            self.plt3D.autoscale(enable = ast.literal_eval(self.options[key]['enable']), axis = self.options[key]['axis'], tight = ast.literal_eval(self.options[key]['tight']))
      elif key == 'horizontalLine':
        if self.dim == 3:
          self.raiseAWarning('horizontalLine not available in 3-D plots!!')
        elif self.dim == 2:
          if 'y' not in self.options[key].keys():
            self.options[key]['y'] = '0'
          if 'xmin' not in self.options[key].keys():
            self.options[key]['xmin'] = '0'
          if 'xmax' not in self.options[key].keys():
            self.options[key]['xmax'] = '1'
          if 'hold' not in self.options[key].keys():
            self.options[key]['hold'] = 'None'
          self.plt.axhline(y = ast.literal_eval(self.options[key]['y']), xmin = ast.literal_eval(self.options[key]['xmin']), xmax = ast.literal_eval(self.options[key]['xmax']), hold = ast.literal_eval(self.options[key]['hold']), **self.options[key].get('attributes', {}))
      elif key == 'verticalLine':
        if self.dim == 3: self.raiseAWarning('verticalLine not available in 3-D plots!!')
        elif self.dim == 2:
          if 'x' not in self.options[key].keys():
            self.options[key]['x'] = '0'
          if 'ymin' not in self.options[key].keys():
            self.options[key]['ymin'] = '0'
          if 'ymax' not in self.options[key].keys():
            self.options[key]['ymax'] = '1'
          if 'hold' not in self.options[key].keys():
            self.options[key]['hold'] = 'None'
          self.plt.axvline(x = ast.literal_eval(self.options[key]['x']), ymin = ast.literal_eval(self.options[key]['ymin']), ymax = ast.literal_eval(self.options[key]['ymax']), hold = ast.literal_eval(self.options[key]['hold']), **self.options[key].get('attributes', {}))
      elif key == 'horizontalRectangle':
        if self.dim == 3: self.raiseAWarning('horizontalRectangle not available in 3-D plots!!')
        elif self.dim == 2:
          if 'ymin' not in self.options[key].keys():
            self.raiseAnError(IOError, 'ymin parameter is needed for function horizontalRectangle!!')
          if 'ymax' not in self.options[key].keys():
            self.raiseAnError(IOError, 'ymax parameter is needed for function horizontalRectangle!!')
          if 'xmin' not in self.options[key].keys():
            self.options[key]['xmin'] = '0'
          if 'xmax' not in self.options[key].keys():
            self.options[key]['xmax'] = '1'
          self.plt.axhspan(ast.literal_eval(self.options[key]['ymin']), ast.literal_eval(self.options[key]['ymax']), xmin = ast.literal_eval(self.options[key]['xmin']), xmax = ast.literal_eval(self.options[key]['xmax']), **self.options[key].get('attributes', {}))
      elif key == 'verticalRectangle':
        if self.dim == 3:
          self.raiseAWarning('vertical_rectangle not available in 3-D plots!!')
        elif self.dim == 2:
          if 'xmin' not in self.options[key].keys():
            self.raiseAnError(IOError, 'xmin parameter is needed for function verticalRectangle!!')
          if 'xmax' not in self.options[key].keys():
            self.raiseAnError(IOError, 'xmax parameter is needed for function verticalRectangle!!')
          if 'ymin' not in self.options[key].keys():
            self.options[key]['ymin'] = '0'
          if 'ymax' not in self.options[key].keys():
            self.options[key]['ymax'] = '1'
          self.plt.axvspan(ast.literal_eval(self.options[key]['xmin']), ast.literal_eval(self.options[key]['xmax']), ymin = ast.literal_eval(self.options[key]['ymin']), ymax = ast.literal_eval(self.options[key]['ymax']), **self.options[key].get('attributes', {}))
      elif key == 'axesBox':
        if   self.dim == 3:
          self.raiseAWarning('axesBox not available in 3-D plots!!')
        elif self.dim == 2:
          self.plt.box(self.options[key][key])
      elif key == 'axis':
          self.plt.axis(self.options[key][key])
      elif key == 'grid':
        if 'b' not in self.options[key].keys():
          self.options[key]['b'] = 'off'
        if self.options[key]['b'].lower() in utils.stringsThatMeanTrue():
          self.options[key]['b'] = 'on'
        elif self.options[key]['b'].lower() in utils.stringsThatMeanFalse():
          self.options[key]['b'] = 'off'
        if 'which' not in self.options[key].keys():
          self.options[key]['which'] = 'major'
        if 'axis' not in self.options[key].keys():
          self.options[key]['axis'] = 'both'
        if self.dim == 2:
          self.plt.grid(b = self.options[key]['b'], which = self.options[key]['which'], axis = self.options[key]['axis'], **self.options[key].get('attributes', {}))
        elif self.dim == 3:
          self.plt3D.grid(b = self.options[key]['b'], **self.options[key].get('attributes', {}))
      else:
        self.raiseAWarning('Try to perform not-predifined action ' + key + '. If it does not work check manual and/or relavite matplotlib method specification.')
        commandArgs = ' '
        import CustomCommandExecuter as execcommand
        for kk in self.options[key]:
          if kk != 'attributes' and kk != key:
            if commandArgs != ' ':
              prefix = ','
            else:
              prefix = ''
            try:
              commandArgs = commandArgs + prefix + kk + '=' + str(ast.literal_eval(self.options[key][kk]))
            except:
              commandArgs = commandArgs + prefix + kk + '="' + str(self.options[key][kk]) + '"'
        try:
          if self.dim == 2:
            execcommand.execCommand('self.plt.' + key + '(' + commandArgs + ')', self)
          elif self.dim == 3:
            execcommand.execCommand('self.plt.' + key + '(' + commandArgs + ')', self)
          # if self.dim == 2:  exec('self.plt.' + key + '(' + commandArgs + ')')
          # elif self.dim == 3:exec('self.plt3D.' + key + '(' + commandArgs + ')')
        except ValueError as ae:
          self.raiseAnError(RuntimeError, '<' + str(ae) + '> -> in execution custom action "' + key + '" in Plot ' + self.name + '.\n ' + self.printTag + ' command has been called in the following way: ' + 'self.plt.' + key + '(' + commandArgs + ')')

  ####################
  #  PUBLIC METHODS  #
  ####################
  def localGetInitParams(self):
    """
      This method is called from the base function. It retrieves the initial
      characteristic params that need to be seen by the whole enviroment
      @ In, None
      @ Out, paramDict, dict, dictionary containing the parameter names as keys
        and each parameter's initial value as the dictionary values
    """
    paramDict = {}
    paramDict['Plot is '] = str(self.dim) + 'D'
    for index in range(len(self.sourceName)):
      paramDict['Source Name ' + str(index) + ' :'] = self.sourceName[index]
    return paramDict

  def endInstructions(self, instructionString):
    """
      Method to execute instructions at end of a step (this is applied when an
      interactive mode is activated)
      @ In, instructionString, string, the instruction to execute
      @ Out, None
    """
    if instructionString == 'interactive' and 'screen' in self.options['how']['how'].split(',') and disAvail:
      self.plt.figure(self.name)
      self.fig.ginput(n = -1, timeout = -1, show_clicks = False)

  def initialize(self, inDict):
    """
      Function called to initialize the OutStream, linking it to the proper data
      @ In, inDict, dict, dictionary that contains all the instantiaced classes
        needed for the actual step. The data is looked for in this dictionary
      @ Out, None
    """
    self.xCoordinates = []
    self.sourceName = []
    if 'figureProperties' in self.options.keys():
      key = 'figureProperties'
      if 'figsize' not in self.options[key].keys():
        self.options[key]['figsize'  ] = 'None'
      if 'dpi' not in self.options[key].keys():
        self.options[key]['dpi'      ] = 'None'
      if 'facecolor' not in self.options[key].keys():
        self.options[key]['facecolor'] = 'None'
      if 'edgecolor' not in self.options[key].keys():
        self.options[key]['edgecolor'] = 'None'
      if 'frameon' not in self.options[key].keys():
        self.options[key]['frameon'  ] = 'True'
      elif self.options[key]['frameon'].lower() in utils.stringsThatMeanTrue():
        self.options[key]['frameon'] = 'True'
      elif self.options[key]['frameon'].lower() in utils.stringsThatMeanFalse():
        self.options[key]['frameon'] = 'False'
      self.fig = self.plt.figure(self.name, figsize = ast.literal_eval(self.options[key]['figsize']), dpi = ast.literal_eval(self.options[key]['dpi']), facecolor = self.options[key]['facecolor'], edgecolor = self.options[key]['edgecolor'], frameon = ast.literal_eval(self.options[key]['frameon']), **self.options[key].get('attributes', {}))
    else:
      self.fig = self.plt.figure(self.name)
    if self.dim == 3:
      self.plt3D = self.fig.add_subplot(111, projection = '3d')
    for pltindex in range(len(self.options['plotSettings']['plot'])):
      self.colorMapCoordinates[pltindex] = None
      if 'y' in self.options['plotSettings']['plot'][pltindex].keys():
        self.yCoordinates = []
      if 'z' in self.options['plotSettings']['plot'][pltindex].keys():
        self.zCoordinates = []
      if 'clusterLabels' in self.options['plotSettings']['plot'][pltindex].keys():
        self.clusterLabels = []
      if 'mixtureLabels' in self.options['plotSettings']['plot'][pltindex].keys():
        self.mixtureLabels = []
      if 'attributes' in self.options['plotSettings']['plot'][pltindex].keys():
        if 'mixtureMeans' in self.options['plotSettings']['plot'][pltindex]['attributes'].keys():
          self.mixtureMeans = []
        if 'mixtureCovars' in self.options['plotSettings']['plot'][pltindex]['attributes'].keys():
          self.mixtureCovars = []
      # if 'colorMap' in self.options['plotSettings']['plot'][pltindex].keys(): self.colorMapCoordinates = {}
    for pltindex in range(len(self.options['plotSettings']['plot'])):
      self.xCoordinates.append(self.options['plotSettings']['plot'][pltindex]['x'].split(','))
      self.sourceName.append(self.xCoordinates [pltindex][0].split('|')[0].strip())
      if 'y' in self.options['plotSettings']['plot'][pltindex].keys():
        self.yCoordinates .append(self.options['plotSettings']['plot'][pltindex]['y'].split(','))
        if self.yCoordinates [pltindex][0].split('|')[0] != self.sourceName[pltindex]:
          self.raiseAnError(IOError, 'Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got y_cord source is' + self.yCoordinates [pltindex][0].split('|')[0])
      if 'z' in self.options['plotSettings']['plot'][pltindex].keys():
        self.zCoordinates .append(self.options['plotSettings']['plot'][pltindex]['z'].split(','))
        if self.zCoordinates [pltindex][0].split('|')[0] != self.sourceName[pltindex]:
          self.raiseAnError(IOError, 'Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got z_cord source is' + self.zCoordinates [pltindex][0].split('|')[0])
      if 'clusterLabels' in self.options['plotSettings']['plot'][pltindex].keys():
        self.clusterLabels .append(self.options['plotSettings']['plot'][pltindex]['clusterLabels'].split(','))
        if self.clusterLabels [pltindex][0].split('|')[0] != self.sourceName[pltindex]:
          self.raiseAnError(IOError, 'Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got clusterLabels source is' + self.clusterLabels [pltindex][0].split('|')[0])
      if 'mixtureLabels' in self.options['plotSettings']['plot'][pltindex].keys():
        self.mixtureLabels .append(self.options['plotSettings']['plot'][pltindex]['mixtureLabels'].split(','))
        if self.mixtureLabels [pltindex][0].split('|')[0] != self.sourceName[pltindex]:
          self.raiseAnError(IOError, 'Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got mixtureLabels source is' + self.mixtureLabels [pltindex][0].split('|')[0])
      if 'colorMap' in self.options['plotSettings']['plot'][pltindex].keys():
        self.colorMapCoordinates[pltindex] = self.options['plotSettings']['plot'][pltindex]['colorMap'].split(',')
        # self.colorMapCoordinates.append(self.options['plotSettings']['plot'][pltindex]['colorMap'].split(','))
        if self.colorMapCoordinates[pltindex][0].split('|')[0] != self.sourceName[pltindex]:
          self.raiseAnError(IOError, 'Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got colorMap_coordinates source is' + self.colorMapCoordinates[pltindex][0].split('|')[0])
      for pltindex in range(len(self.options['plotSettings']['plot'])):
        if 'interpPointsY' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['interpPointsY'] = '20'
        if 'interpPointsX' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['interpPointsX'] = '20'
        if 'interpolationType' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['interpolationType'] = 'linear'
        elif self.options['plotSettings']['plot'][pltindex]['interpolationType'] not in self.interpAvail: self.raiseAnError(IOError, 'surface interpolation unknown. Available are :' + str(self.interpAvail))
        if 'epsilon' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['epsilon'] = '2'
        if 'smooth' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['smooth'] = '0.0'
        if 'cmap' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['cmap'] = 'None'
        #    else:             self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
        elif self.options['plotSettings']['plot'][pltindex]['cmap'] is not 'None' and self.options['plotSettings']['plot'][pltindex]['cmap'] not in self.mpl.cm.datad.keys():
          raise('ERROR. The colorMap you specified does not exist... Available are ' + str(self.mpl.cm.datad.keys()))
        if 'interpolationTypeBackUp' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['interpolationTypeBackUp'] = 'nearest'
        elif self.options['plotSettings']['plot'][pltindex]['interpolationTypeBackUp'] not in self.interpAvail:
          self.raiseAnError(IOError, 'surface interpolation (BackUp) unknown. Available are :' + str(self.interpAvail))
      if 'attributes' in self.options['plotSettings']['plot'][pltindex].keys():
        if 'mixtureMeans' in self.options['plotSettings']['plot'][pltindex]['attributes'].keys():
          self.mixtureMeans.append(self.options['plotSettings']['plot'][pltindex]['attributes']['mixtureMeans'].split(','))
        if 'mixtureCovars' in self.options['plotSettings']['plot'][pltindex]['attributes'].keys():
          self.mixtureCovars.append(self.options['plotSettings']['plot'][pltindex]['attributes']['mixtureCovars'].split(','))
    self.numberAggregatedOS = len(self.options['plotSettings']['plot'])
    # initialize here the base class
    OutStreamManager.initialize(self, inDict)
    # execute actions (we execute the actions here also because we can perform a check at runtime!!
    self.__executeActions()

  def localReadXML(self, xmlNode):
    """
      This Function is called from the base class, It reads the parameters that
      belong to a plot block
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None
    """
    if not 'dim' in xmlNode.attrib.keys():
      self.dim = 2
    else:
      self.dim = int(xmlNode.attrib['dim'])
    if self.dim not in [2, 3]:
      self.raiseAnError(IOError, 'Wrong dimension... 2D or 3D only!!! Got ' + str(self.dim) + 'D')
    foundPlot = False
    for subnode in xmlNode:
      # if actions, read actions block
      if subnode.tag == 'filename':
        self.filename = subnode.text
      if subnode.tag in ['actions']:
        self.__readPlotActions(subnode)
      if subnode.tag in ['plotSettings']:
        self.options[subnode.tag] = {}
        self.options[subnode.tag]['plot'] = []
        for subsub in subnode:
          if subsub.tag == 'gridSpace':
            # if self.dim == 3: self.raiseAnError(IOError, 'SubPlot option can not be used with 3-dimensional plots!')
            self.options[subnode.tag][subsub.tag] = subsub.text.strip()
          elif subsub.tag == 'plot':
            tempDict = {}
            foundPlot = True
            for subsubsub in subsub:
              if subsubsub.tag == 'gridLocation':
                tempDict[subsubsub.tag] = {}
                for subsubsubsub in subsubsub:
                  tempDict[subsubsub.tag][subsubsubsub.tag] = subsubsubsub.text.strip()
              elif subsubsub.tag == 'range':
                tempDict[subsubsub.tag] = {}
                for subsubsubsub in subsubsub:
                  tempDict[subsubsub.tag][subsubsubsub.tag] = subsubsubsub.text.strip()
              elif subsubsub.tag != 'kwargs':
                tempDict[subsubsub.tag] = subsubsub.text.strip()
              else:
                tempDict['attributes'] = {}
                for sss in subsubsub:
                  tempDict['attributes'][sss.tag] = sss.text.strip()
            self.options[subnode.tag][subsub.tag].append(tempDict)
          else:
            self.options[subnode.tag][subsub.tag] = subsub.text.strip()
      if subnode.tag in 'title':
        self.options[subnode.tag] = {}
        for subsub in subnode:
          self.options[subnode.tag][subsub.tag] = subsub.text.strip()
        if 'text'     not in self.options[subnode.tag].keys():
          self.options[subnode.tag]['text'    ] = xmlNode.attrib['name']
        if 'location' not in self.options[subnode.tag].keys():
          self.options[subnode.tag]['location'] = 'center'
# is this 'figureProperties' valid?
      if subnode.tag == 'figureProperties':
        self.options[subnode.tag] = {}
        for subsub in subnode:
          self.options[subnode.tag][subsub.tag] = subsub.text.strip()
    self.type = 'OutStreamPlot'
    if not 'plotSettings' in self.options.keys():
      self.raiseAnError(IOError, 'For plot named ' + self.name + ' the plotSettings block is required.')
    if not foundPlot:
      self.raiseAnError(IOError, 'For plot named' + self.name + ', No plot section has been found in the plotSettings block!')
    self.outStreamTypes = []
    for pltindex in range(len(self.options['plotSettings']['plot'])):
      if not 'type' in self.options['plotSettings']['plot'][pltindex].keys():
        self.raiseAnError(IOError, 'For plot named' + self.name + ', No plot type keyword has been found in the plotSettings/plot block!')
      else:
        if self.availableOutStreamTypes[self.dim].count(self.options['plotSettings']['plot'][pltindex]['type']) == 0:
          self.raiseAMessage('For plot named' + self.name + ', type ' + self.options['plotSettings']['plot'][pltindex]['type'] + ' is not among pre-defined plots! \n The OutstreamSystem will try to construct a call on the fly!', 'ExceptedError')
        self.outStreamTypes.append(self.options['plotSettings']['plot'][pltindex]['type'])
    self.mpl = importlib.import_module("matplotlib")
    # exec('self.mpl =  importlib.import_module("matplotlib")')
    self.raiseADebug('matplotlib version is ' + str(self.mpl.__version__))
    if self.dim not in [2, 3]:
      self.raiseAnError(TypeError, 'This Plot interface is able to handle 2D-3D plot only')
    if not disAvail:
      self.mpl.use('Agg')
    self.plt = importlib.import_module("matplotlib.pyplot")
    if self.dim == 3:
      from mpl_toolkits.mplot3d import Axes3D
    if 'gridSpace' in self.options['plotSettings'].keys():
      grid = map(int, self.options['plotSettings']['gridSpace'].split(' '))
      self.gridSpace = self.mpl.gridspec.GridSpec(grid[0], grid[1])

  def addOutput(self):
    """
      Function to show and/or save a plot (outputs Plot on the screen or on file/s)
      @ In,  None
      @ Out, None
    """
    # fill the x_values,y_values,z_values dictionaries
    if not self.__fillCoordinatesFromSource():
      self.raiseAWarning('Nothing to Plot Yet. Returning.')
      return
    # reactivate the figure
    self.fig = self.plt.figure(self.name)
    self.counter += 1
    if self.counter > 1:
      if self.dim == 2:
        self.fig.clear()
      else:
        if self.actPlot:
          self.plt3D.cla()
    # execute the actions again (we just cleared the figure)
    self.__executeActions()
    # start plotting.... we are here fort that...aren't we?
    # loop over the plots that need to be included in this figure
    from copy import deepcopy
    clusterDict = deepcopy(self.outStreamTypes)
    for pltindex in range(len(self.outStreamTypes)):
      if 'gridLocation' in self.options['plotSettings']['plot'][pltindex].keys():
        x = None
        y = None
        if 'x' in  self.options['plotSettings']['plot'][pltindex]['gridLocation'].keys():
          x = map(int, self.options['plotSettings']['plot'][pltindex]['gridLocation']['x'].strip().split(' '))
        else:
          x = None
        if 'y' in  self.options['plotSettings']['plot'][pltindex]['gridLocation'].keys():
          y = map(int, self.options['plotSettings']['plot'][pltindex]['gridLocation']['y'].strip().split(' '))
        else:
          y = None
        if   (len(x) == 1 and len(y) == 1):
          if self.dim == 2:
            self.plt.subplot(self.gridSpace[x[0], y[0]])
          else:
            self.plt3D = self.plt.subplot(self.gridSpace[x[0], y[0]], projection = '3d')
        elif (len(x) == 1 and len(y) != 1):
          if self.dim == 2:
            self.plt.subplot(self.gridSpace[x[0], y[0]:y[-1]])
          else:
            self.plt3D = self.plt.subplot(self.gridSpace[x[0], y[0]:y[-1]], projection = '3d')
        elif (len(x) != 1 and len(y) == 1):
          if self.dim == 2:
            self.plt.subplot(self.gridSpace[x[0]:x[-1], y[0]])
          else:
            self.plt3D = self.plt.subplot(self.gridSpace[x[0]:x[-1], y[0]], projection = '3d')
        else:
          if self.dim == 2:
            self.plt.subplot(self.gridSpace[x[0]:x[-1], y[0]:y[-1]])
          else:
            self.plt3D = self.plt.subplot(self.gridSpace[x[0]:x[-1], y[0]:y[-1]], projection = '3d')
      # If the number of plots to be shown in this figure > 1, hold the old ones (They are going to be shown together... because unity is much better than separation)
      if len(self.outStreamTypes) > 1:
        self.plt.hold(True)
      if 'gridSpace' in self.options['plotSettings'].keys():
        self.plt.locator_params(axis = 'y', nbins = 4)
        self.plt.ticklabel_format(**{'style':'sci', 'scilimits':(0, 1), 'useOffset':False, 'axis':'both'})
        self.plt.locator_params(axis = 'x', nbins = 2)
        self.plt.ticklabel_format(**{'style':'sci', 'scilimits':(0, 1), 'useOffset':False, 'axis':'both'})
        if 'range' in self.options['plotSettings']['plot'][pltindex].keys():
          axes_range = self.options['plotSettings']['plot'][pltindex]['range']
          if self.dim == 2:
            if 'ymin' in axes_range.keys():
              self.plt.ylim(ymin = ast.literal_eval(axes_range['ymin']))
            if 'ymax' in axes_range.keys():
              self.plt.ylim(ymax = ast.literal_eval(axes_range['ymax']))
            if 'xmin' in axes_range.keys():
              self.plt.xlim(xmin = ast.literal_eval(axes_range['xmin']))
            if 'xmax' in axes_range.keys():
              self.plt.xlim(xmax = ast.literal_eval(axes_range['xmax']))
          elif self.dim == 3:
            if 'xmin' in axes_range.keys():
              self.plt3D.set_xlim3d(xmin = ast.literal_eval(axes_range['xmin']))
            if 'xmax' in axes_range.keys():
              self.plt3D.set_xlim3d(xmax = ast.literal_eval(axes_range['xmax']))
            if 'ymin' in axes_range.keys():
              self.plt3D.set_ylim3d(ymin = ast.literal_eval(axes_range['ymin']))
            if 'ymax' in axes_range.keys():
              self.plt3D.set_ylim3d(ymax = ast.literal_eval(axes_range['ymax']))
            if 'zmin' in axes_range.options['plotSettings']['plot'][pltindex].keys():
              if 'zmax' not in axes_range.options['plotSettings'].keys(): self.raiseAWarning('zmin inputted but not zmax. zmin ignored! ')
              else:self.plt3D.set_zlim(ast.literal_eval(axes_range['zmin']), ast.literal_eval(self.options['plotSettings']['zmax']))
            if 'zmax' in axes_range.keys():
              if 'zmin' not in axes_range.keys():
                self.raiseAWarning('zmax inputted but not zmin. zmax ignored! ')
              else:self.plt3D.set_zlim(ast.literal_eval(axes_range['zmin']), ast.literal_eval(axes_range['zmax']))
        if 'xlabel' not in self.options['plotSettings']['plot'][pltindex].keys():
          if   self.dim == 2:
            self.plt.xlabel('x')
          elif self.dim == 3:
            self.plt3D.set_xlabel('x')
        else:
          if   self.dim == 2:
            self.plt.xlabel(self.options['plotSettings']['plot'][pltindex]['xlabel'])
          elif self.dim == 3:
            self.plt3D.set_xlabel(self.options['plotSettings']['plot'][pltindex]['xlabel'])
        if 'ylabel' not in self.options['plotSettings']['plot'][pltindex].keys():
          if   self.dim == 2:
            self.plt.ylabel('y')
          elif self.dim == 3:
            self.plt3D.set_ylabel('y')
        else:
          if   self.dim == 2:
            self.plt.ylabel(self.options['plotSettings']['plot'][pltindex]['ylabel'])
          elif self.dim == 3:
            self.plt3D.set_ylabel(self.options['plotSettings']['plot'][pltindex]['ylabel'])
        if 'zlabel' in self.options['plotSettings']['plot'][pltindex].keys():
          if   self.dim == 2:
            self.raiseAWarning('zlabel keyword does not make sense in 2-D Plots!')
          elif self.dim == 3 and self.zCoordinates:
            self.plt3D.set_zlabel(self.options['plotSettings']['plot'][pltindex]['zlabel'])
        elif self.dim == 3 and self.zCoordinates:
          self.plt3D.set_zlabel('z')
      else:
        if 'xlabel' not in self.options['plotSettings'].keys():
          if   self.dim == 2:
            self.plt.xlabel('x')
          elif self.dim == 3:
            self.plt3D.set_xlabel('x')
        else:
          if   self.dim == 2:
            self.plt.xlabel(self.options['plotSettings']['xlabel'])
          elif self.dim == 3:
            self.plt3D.set_xlabel(self.options['plotSettings']['xlabel'])
        if 'ylabel' not in self.options['plotSettings'].keys():
          if   self.dim == 2:
            self.plt.ylabel('y')
          elif self.dim == 3:
            self.plt3D.set_ylabel('y')
        else:
          if   self.dim == 2:
            self.plt.ylabel(self.options['plotSettings']['ylabel'])
          elif self.dim == 3:
            self.plt3D.set_ylabel(self.options['plotSettings']['ylabel'])
        if 'zlabel' in self.options['plotSettings'].keys():
          if   self.dim == 2:
            self.raiseAWarning('zlabel keyword does not make sense in 2-D Plots!')
          elif self.dim == 3 and self.zCoordinates:
            self.plt3D.set_zlabel(self.options['plotSettings']['zlabel'])
        elif self.dim == 3 and self.zCoordinates:
          self.plt3D.set_zlabel('z')

      # Let's start plotting
      #################
      #  SCATTER PLOT #
      #################
      self.raiseADebug('creating plot' + self.name)
      if self.outStreamTypes[pltindex] == 'scatter':
        if 's' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['s'] = '20'
        if 'c' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['c'] = 'b'
        if 'marker' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['marker'] = 'o'
        if 'alpha' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['alpha'] = 'None'
        if 'linewidths' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['linewidths'] = 'None'
        for key in self.xValues[pltindex].keys():
          for xIndex in range(len(self.xValues[pltindex][key])):
            for yIndex in range(len(self.yValues[pltindex][key])):
              scatterPlotOptions = {'s':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),
                                    'marker':(self.options['plotSettings']['plot'][pltindex]['marker']),
                                    'alpha':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),
                                    'linewidths':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths'])}
              scatterPlotOptions.update(self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
              if self.dim == 2:
                if self.colorMapCoordinates[pltindex] != None:
                  scatterPlotOptions['c'] = self.colorMapValues[pltindex][key]
                  scatterPlotOptions['cmap'] = self.mpl.cm.get_cmap("winter")
                  if self.actcm:
                    first = False
                  else:
                    first = True
                  if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                    #if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None': self.options['plotSettings']['plot'][pltindex]['cmap'] = 'winter'
                    self.actPlot = self.plt.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], **scatterPlotOptions)
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        m = self.mpl.cm.ScalarMappable(norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        try:
                          self.actcm.draw_all()
                        except:
                          m = self.mpl.cm.ScalarMappable(norm = self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                  else:
                    scatterPlotOptions['cmap'] = self.options['plotSettings']['plot'][pltindex]['cmap']
                    self.actPlot = self.plt.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], **scatterPlotOptions)
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                else:
                  scatterPlotOptions['c'] = self.options['plotSettings']['plot'][pltindex]['c']
                  self.actPlot = self.plt.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], **scatterPlotOptions)
              elif self.dim == 3:
                scatterPlotOptions['rasterized'] = True
                for zIndex in range(len(self.zValues[pltindex][key])):
                  if self.colorMapCoordinates[pltindex] != None:
                    scatterPlotOptions['c'] = self.colorMapValues[pltindex][key]
                    if self.actcm:
                      first = False
                    else:
                      first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex], **scatterPlotOptions)
                      if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                        if first:
                          m = self.mpl.cm.ScalarMappable(norm = self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                        else:
                          self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                          self.actcm.draw_all()
                    else:
                      scatterPlotOptions['cmap'] = self.options['plotSettings']['plot'][pltindex]['cmap']
                      self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex], **scatterPlotOptions)
                      if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                        if first:
                          m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                        else:
                          self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                          self.actcm.draw_all()
                  else:
                    scatterPlotOptions['c'] = self.options['plotSettings']['plot'][pltindex]['c']
                    self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex], **scatterPlotOptions)

      #################
      #   LINE PLOT   #
      #################
      elif self.outStreamTypes[pltindex] == 'line':
        for key in self.xValues[pltindex].keys():
          for xIndex in range(len(self.xValues[pltindex][key])):
            if self.colorMapCoordinates[pltindex] != None:
              self.options['plotSettings']['plot'][pltindex]['interpPointsX'] = str(max(200, len(self.xValues[pltindex][key][xIndex])))
            for yIndex in range(len(self.yValues[pltindex][key])):
              if self.dim == 2:
                if self.yValues[pltindex][key][yIndex].size < 2:
                  return
                xi, yi = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], returnCoordinate = True)
                if self.colorMapCoordinates[pltindex] != None:
                  # if a color map has been added, we use a scattered plot instead...
                  if self.actcm:
                    first = False
                  else:
                    first = True
                  self.actPlot = self.plt.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], c = self.colorMapValues[pltindex][key], **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                  if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        m = self.mpl.cm.ScalarMappable(norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if first:
                      self.actPlot.cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap'])
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                else:
                  self.actPlot = self.plt.plot(xi, yi, **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
              elif self.dim == 3:
                for zIndex in range(len(self.zValues[pltindex][key])):
                  if self.zValues[pltindex][key][zIndex].size <= 3:
                    return
                  if self.colorMapCoordinates[pltindex] != None:
                    # if a color map has been added, we use a scattered plot instead...
                    if self.actcm:
                      first = False
                    else:
                      first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex], c = self.colorMapValues[pltindex][key], marker = '_')
                        if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                          if first:
                            m = self.mpl.cm.ScalarMappable(norm = self.actPlot.norm)
                            m.set_array(self.colorMapValues[pltindex][key])
                            self.actcm = self.fig.colorbar(m)
                            self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                          else:
                            self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                            self.actcm.draw_all()
                    else:
                        self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex],
                                                          c = self.colorMapValues[pltindex][key], cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), marker = '_')
                        if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                          if first:
                            m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                            m.set_array(self.colorMapValues[pltindex][key])
                            self.actcm = self.fig.colorbar(m)
                            self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                          else:
                            self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                            self.actcm.draw_all()
                  else:
                    self.actPlot = self.plt3D.plot(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex], **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
      ##################
      # HISTOGRAM PLOT #
      ##################
      elif self.outStreamTypes[pltindex] == 'histogram':
        if 'bins' not in self.options['plotSettings']['plot'][pltindex].keys():
          if self.dim == 2:
            self.options['plotSettings']['plot'][pltindex]['bins'] = '10'
          else:
            self.options['plotSettings']['plot'][pltindex]['bins'] = '4'
        settings = self.options['plotSettings']['plot'][pltindex]
        keys = settings.keys()
        if 'normed' not in keys:
          settings['normed'] = 'False'
        if 'weights' not in keys:
          settings['weights'] = 'None'
        if 'cumulative' not in keys:
          settings['cumulative'] = 'False'
        if 'histtype' not in keys:
          settings['histtype'] = 'bar'
        if 'align' not in keys:
          settings['align'] = 'mid'
        if 'orientation' not in keys:
          settings['orientation'] = 'vertical'
        if 'rwidth' not in keys:
          settings['rwidth'] = 'None'
        if 'log' not in keys:
          settings['log'] = 'None'
        if 'color' not in keys:
          settings['color'] = 'b'
        if 'stacked' not in keys:
          settings['stacked'] = 'None'
        for key in self.xValues[pltindex].keys():
          for xIndex in range(len(self.xValues[pltindex][key])):
            try:
              colorss = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['color'])
            except:
              colorss = self.options['plotSettings']['plot'][pltindex]['color']
            if self.dim == 2:
              self.plt.hist(self.xValues[pltindex][key][xIndex], bins = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['bins']), normed = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['normed']), weights = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['weights']),
                            cumulative = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cumulative']), histtype = self.options['plotSettings']['plot'][pltindex]['histtype'], align = self.options['plotSettings']['plot'][pltindex]['align'],
                            orientation = self.options['plotSettings']['plot'][pltindex]['orientation'], rwidth = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rwidth']), log = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['log']),
                            color = colorss, stacked = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['stacked']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
            elif self.dim == 3:
              for yIndex in range(len(self.yValues[pltindex][key])):
                hist, xedges, yedges = np.histogram2d(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], bins = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['bins']))
                elements = (len(xedges) - 1) * (len(yedges) - 1)
                if 'x_offset' in self.options['plotSettings']['plot'][pltindex].keys():
                  xoffset = float(self.options['plotSettings']['plot'][pltindex]['x_offset'])
                else:
                  xoffset = 0.25
                if 'y_offset' in self.options['plotSettings']['plot'][pltindex].keys():
                  yoffset = float(self.options['plotSettings']['plot'][pltindex]['y_offset'])
                else:
                  yoffset = 0.25
                if 'dx' in self.options['plotSettings']['plot'][pltindex].keys():
                  dxs = float(self.options['plotSettings']['plot'][pltindex]['dx'])
                else:
                  dxs = (self.xValues[pltindex][key][xIndex].max() - self.xValues[pltindex][key][xIndex].min()) / float(self.options['plotSettings']['plot'][pltindex]['bins'])
                if 'dy' in self.options['plotSettings']['plot'][pltindex].keys():
                  dys = float(self.options['plotSettings']['plot'][pltindex]['dy'])
                else:
                  dys = (self.yValues[pltindex][key][yIndex].max() - self.yValues[pltindex][key][yIndex].min()) / float(self.options['plotSettings']['plot'][pltindex]['bins'])
                xpos, ypos = np.meshgrid(xedges[:-1] + xoffset, yedges[:-1] + yoffset)
                self.actPlot = self.plt3D.bar3d(xpos.flatten(), ypos.flatten(), np.zeros(elements), dxs * np.ones_like(elements), dys * np.ones_like(elements), hist.flatten(), color = colorss, zsort = 'average', **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
      ##################
      #    STEM PLOT   #
      ##################
      elif self.outStreamTypes[pltindex] == 'stem':
          if 'linefmt' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['linefmt'] = 'b-'
          if 'markerfmt' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['markerfmt'] = 'bo'
          if 'basefmt' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['basefmt'] = 'r-'
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                if self.dim == 2:
                  self.actPlot = self.plt.stem(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], linefmt = self.options['plotSettings']['plot'][pltindex]['linefmt'], markerfmt = self.options['plotSettings']['plot'][pltindex]['markerfmt'], basefmt = self.options['plotSettings']['plot'][pltindex]['linefmt'], **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                elif self.dim == 3:
                  # it is a basic stem plot constructed using a standard line plot. For now we do not use the previous defined keywords...
                  for zIndex in range(len(self.zValues[pltindex][key])):
                    for xx, yy, zz in zip(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.zValues[pltindex][key][zIndex]): self.plt3D.plot([xx, xx], [yy, yy], [0, zz], '-')
      ##################
      #    STEP PLOT   #
      ##################
      elif self.outStreamTypes[pltindex] == 'step':
        if self.dim == 2:
          if 'where' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['where'] = 'mid'
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              if self.xValues[pltindex][key][xIndex].size < 2:
                xi = self.xValues[pltindex][key][xIndex]
              else:
                xi = np.linspace(self.xValues[pltindex][key][xIndex].min(), self.xValues[pltindex][key][xIndex].max(), ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['interpPointsX']))
              for yIndex in range(len(self.yValues[pltindex][key])):
                if self.yValues[pltindex][key][yIndex].size <= 3:
                  return
                yi = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex])
                self.actPlot = self.plt.step(xi, yi, where = self.options['plotSettings']['plot'][pltindex]['where'], **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
        elif self.dim == 3:
          self.raiseAWarning('step Plot not available in 3D')
          return
      ########################
      #    PSEUDOCOLOR PLOT  #
      ########################
      elif self.outStreamTypes[pltindex] == 'pseudocolor':
        if self.dim == 2:
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                if not self.colorMapCoordinates:
                  self.raiseAMessage('pseudocolor Plot needs coordinates for color map... Returning without plotting')
                  return
                for zIndex in range(len(self.colorMapValues[pltindex][key])):
                  if self.colorMapValues[pltindex][key][zIndex].size <= 3:
                    return
                  xig, yig, Ci = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.colorMapValues[pltindex][key][zIndex], returnCoordinate = True)
                  if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                    self.actPlot = self.plt.pcolormesh(xig, yig, ma.masked_where(np.isnan(Ci), Ci), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    m = self.mpl.cm.ScalarMappable(norm = self.actPlot.norm)
                  else:
                    self.actPlot = self.plt.pcolormesh(xig, yig, ma.masked_where(np.isnan(Ci), Ci), cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                  m.set_array(ma.masked_where(np.isnan(Ci), Ci))
                  if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                    actcm = self.fig.colorbar(m)
                    actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
        elif self.dim == 3:
          self.raiseAWarning('pseudocolor Plot is considered a 2D plot, not a 3D!')
          return
      ########################
      #     SURFACE PLOT     #
      ########################
      elif self.outStreamTypes[pltindex] == 'surface':
        if self.dim == 2:
          self.raiseAWarning('surface Plot is NOT available for 2D plots, IT IS A 3D!')
          return
        elif self.dim == 3:
          if 'rstride' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['rstride'] = '1'
          if 'cstride' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['cstride'] = '1'
          if 'antialiased' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['antialiased'] = 'False'
          if 'linewidth' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['linewidth'] = '0'
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                for zIndex in range(len(self.zValues[pltindex][key])):
                  if self.zValues[pltindex][key][zIndex].size <= 3:
                    return
                  if self.colorMapCoordinates[pltindex] != None:
                    xig, yig, Ci = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.colorMapValues[pltindex][key][zIndex], returnCoordinate = True)
                  xig, yig, zi = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.zValues[pltindex][key][zIndex], returnCoordinate = True)
                  if self.colorMapCoordinates[pltindex] != None:
                    if self.actcm:
                      first = False
                    else:
                      first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt3D.plot_surface(xig, yig, ma.masked_where(np.isnan(zi), zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), facecolors = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap'])(ma.masked_where(np.isnan(Ci), Ci)), cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), linewidth = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidth']), antialiased = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['antialiased']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    if first:
                      self.actPlot.cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap'])
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        self.actPlot = self.plt3D.plot_surface(xig, yig, ma.masked_where(np.isnan(zi), zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), linewidth = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidth']), antialiased = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['antialiased']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                        if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                            self.actPlot.set_color = self.options['plotSettings']['plot'][pltindex].get('attributes', {})['color']
                        else:
                            self.actPlot.set_color = 'blue'
                    else:
                        self.actPlot = self.plt3D.plot_surface(xig, yig, ma.masked_where(np.isnan(zi), zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), linewidth = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidth']), antialiased = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['antialiased']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
      ########################
      #   TRI-SURFACE PLOT   #
      ########################
      elif self.outStreamTypes[pltindex] == 'tri-surface':
        if self.dim == 2:
          self.raiseAWarning('TRI-surface Plot is NOT available for 2D plots, it is 3D!')
          return
        elif self.dim == 3:
          if 'color' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['color'] = 'b'
          if 'shade' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['shade'] = 'False'
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                for zIndex in range(len(self.zValues[pltindex][key])):
                  metric = (self.xValues[pltindex][key][xIndex] ** 2 + self.yValues[pltindex][key][yIndex] ** 2) ** 0.5
                  metricIndeces = np.argsort(metric)
                  xs = np.zeros(self.xValues[pltindex][key][xIndex].shape)
                  ys = np.zeros(self.yValues[pltindex][key][yIndex].shape)
                  zs = np.zeros(self.zValues[pltindex][key][zIndex].shape)
                  for sindex in range(len(metricIndeces)):
                    xs[sindex] = self.xValues[pltindex][key][xIndex][metricIndeces[sindex]]
                    ys[sindex] = self.yValues[pltindex][key][yIndex][metricIndeces[sindex]]
                    zs[sindex] = self.zValues[pltindex][key][zIndex][metricIndeces[sindex]]
                  surfacePlotOptions = {'color': self.options['plotSettings']['plot'][pltindex]['color'],
                                        'shade':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['shade'])}
                  surfacePlotOptions.update(self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                  if self.zValues[pltindex][key][zIndex].size <= 3:
                    return
                  if self.colorMapCoordinates[pltindex] != None:
                    if self.actcm:
                      first = False
                    else:
                      first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    surfacePlotOptions['cmap'] = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap'])
                    self.actPlot = self.plt3D.plot_trisurf(xs, ys, zs, **surfacePlotOptions)
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        self.actPlot.cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap'])
                        m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] != 'None':
                      surfacePlotOptions["cmap"] = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap'])
                    self.actPlot = self.plt3D.plot_trisurf(xs, ys, zs, **surfacePlotOptions)
      ########################
      #    WIREFRAME  PLOT   #
      ########################
      elif self.outStreamTypes[pltindex] == 'wireframe':
        if self.dim == 2:
          self.raiseAWarning('wireframe Plot is NOT available for 2D plots, IT IS A 3D!')
          return
        elif self.dim == 3:
          if 'rstride' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['rstride'] = '1'
          if 'cstride' not in self.options['plotSettings']['plot'][pltindex].keys():
            self.options['plotSettings']['plot'][pltindex]['cstride'] = '1'
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                for zIndex in range(len(self.zValues[pltindex][key])):
                  if self.zValues[pltindex][key][zIndex].size <= 3:
                    return
                  if self.colorMapCoordinates[pltindex] != None:
                    xig, yig, Ci = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.colorMapValues[pltindex][key][zIndex], returnCoordinate = True)
                  xig, yig, zi = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.zValues[pltindex][key][zIndex], returnCoordinate = True)
                  if self.colorMapCoordinates[pltindex] != None:
                    self.raiseAWarning('Currently, ax.plot_wireframe() in MatPlotLib version: ' + self.mpl.__version__ + ' does not support a colormap! Wireframe plotted on a surface plot...')
                    if self.actcm:
                      first = False
                    else:
                      first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt3D.plot_wireframe(xig, yig, ma.masked_where(np.isnan(zi), zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    self.actPlot = self.plt3D.plot_surface(xig, yig, ma.masked_where(np.isnan(zi), zi), alpha = 0.4, rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                      if first:
                        m = self.mpl.cm.ScalarMappable(cmap = self.actPlot.cmap, norm = self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                      else:
                        self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        self.actPlot = self.plt3D.plot_wireframe(xig, yig, ma.masked_where(np.isnan(zi), zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                        if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                            self.actPlot.set_color = self.options['plotSettings']['plot'][pltindex].get('attributes', {})['color']
                        else:
                            self.actPlot.set_color = 'blue'
                    else:
                        self.actPlot = self.plt3D.plot_wireframe(xig, yig, ma.masked_where(np.isnan(zi), zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))

      ########################
      #     CONTOUR   PLOT   #
      ########################
      elif self.outStreamTypes[pltindex] == 'contour' or self.outStreamTypes[pltindex] == 'filledContour':
        if self.dim == 2:
          if 'numberBins' in self.options['plotSettings']['plot'][pltindex].keys():
            nbins = int(self.options['plotSettings']['plot'][pltindex]['numberBins'])
          else:
            nbins = 5
          for key in self.xValues[pltindex].keys():
            if not self.colorMapCoordinates:
              self.raiseAWarning(self.outStreamTypes[pltindex] + ' Plot needs coordinates for color map... Returning without plotting')
              return
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                for zIndex in range(len(self.colorMapValues[pltindex][key])):
                  if self.actcm:
                    first = False
                  else:
                    first = True
                  xig, yig, Ci = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.colorMapValues[pltindex][key][zIndex], returnCoordinate = True)
                  if self.outStreamTypes[pltindex] == 'contour':
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                        color = self.options['plotSettings']['plot'][pltindex].get('attributes', {})['color']
                      else:
                        color = 'blue'
                      self.actPlot = self.plt.contour(xig, yig, ma.masked_where(np.isnan(Ci), Ci), nbins, colors = color, **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    else:
                      self.actPlot = self.plt.contour(xig, yig, ma.masked_where(np.isnan(Ci), Ci), nbins, **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt.contourf(xig, yig, ma.masked_where(np.isnan(Ci), Ci), nbins, **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                  self.plt.clabel(self.actPlot, inline = 1, fontsize = 10)
                  if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                    if first:
                      self.actcm = self.plt.colorbar(self.actPlot, shrink = 0.8, extend = 'both')
                      self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                    else:
                      self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                      self.actcm.draw_all()
        elif self.dim == 3:
          self.raiseAWarning('contour/filledContour is a 2-D plot, where x,y are the surface coordinates and colorMap vector is the array to visualize!\n               contour3D/filledContour3D are 3-D! ')
          return
      elif self.outStreamTypes[pltindex] == 'contour3D' or self.outStreamTypes[pltindex] == 'filledContour3D':
        if self.dim == 2:
          self.raiseAWarning('contour3D/filledContour3D Plot is NOT available for 2D plots, IT IS A 2D! Check "contour/filledContour"!')
          return
        elif self.dim == 3:
          if 'numberBins' in self.options['plotSettings']['plot'][pltindex].keys():
            nbins = int(self.options['plotSettings']['plot'][pltindex]['numberBins'])
          else:
            nbins = 5
          if 'extend3D' in self.options['plotSettings']['plot'][pltindex].keys():
            ext3D = bool(self.options['plotSettings']['plot'][pltindex]['extend3D'])
          else:
            ext3D = False
          for key in self.xValues[pltindex].keys():
            for xIndex in range(len(self.xValues[pltindex][key])):
              for yIndex in range(len(self.yValues[pltindex][key])):
                for zIndex in range(len(self.colorMapValues[pltindex][key])):
                  if self.actcm:
                    first = False
                  else:
                    first = True
                  xig, yig, Ci = mathUtils.interpolateFunction(self.xValues[pltindex][key][xIndex], self.yValues[pltindex][key][yIndex], self.options['plotSettings']['plot'][pltindex], z = self.colorMapValues[pltindex][key][zIndex], returnCoordinate = True)
                  if self.outStreamTypes[pltindex] == 'contour3D':
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                        color = self.options['plotSettings']['plot'][pltindex].get('attributes', {})['color']
                      else:
                        color = 'blue'
                      self.actPlot = self.plt3D.contour3D(xig, yig, ma.masked_where(np.isnan(Ci), Ci), nbins, colors = color, extend3d = ext3D, **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                    else:
                      self.actPlot = self.plt3D.contour3D(xig, yig, ma.masked_where(np.isnan(Ci), Ci), nbins, extend3d = ext3D, cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt3D.contourf3D(xig, yig, ma.masked_where(np.isnan(Ci), Ci), nbins, extend3d = ext3D, cmap = self.mpl.cm.get_cmap(name = self.options['plotSettings']['plot'][pltindex]['cmap']), **self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                  self.plt.clabel(self.actPlot, inline = 1, fontsize = 10)
                  if 'colorbar' not in self.options.keys() or self.options['colorbar']['colorbar'] != 'off':
                    if first:
                      self.actcm = self.plt.colorbar(self.actPlot, shrink = 0.8, extend = 'both')
                      self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')', ''))
                    else:
                      self.actcm.set_clim(vmin = min(self.colorMapValues[pltindex][key][-1]), vmax = max(self.colorMapValues[pltindex][key][-1]))
                      self.actcm.draw_all()
      ########################
      #   DataMining PLOT    #
      ########################
      elif self.outStreamTypes[pltindex] == 'dataMining':
        from itertools import cycle
        from itertools import cycle
        colors = cycle(['#88CCEE', '#DDCC77', '#AA4499', '#117733', '#332288', '#999933', '#44AA99', '#882255', '#CC6677', '#CD6677', '#DC6877', '#886677', '#AA6677', '#556677', '#CD7865'])
        if 's' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['s'] = '20'
        if 'c' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['c'] = 'b'
        if 'marker' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['marker'] = 'o'
        if 'alpha' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['alpha'] = 'None'
        if 'linewidths' not in self.options['plotSettings']['plot'][pltindex].keys():
          self.options['plotSettings']['plot'][pltindex]['linewidths'] = 'None'
        clusterDict[pltindex] = {}
        for key in self.xValues[pltindex].keys():
          for xIndex in range(len(self.xValues[pltindex][key])):
            for yIndex in range(len(self.yValues[pltindex][key])):
              dataMiningPlotOptions = {'s':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),
                                       'marker':(self.options['plotSettings']['plot'][pltindex]['marker']),
                                       'alpha':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),
                                       'linewidths':ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths'])}
              if self.colorMapCoordinates[pltindex] != None:
                self.raiseAWarning('ColorMap values supplied, however DataMining plots do not use colorMap from input.')
              if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                self.raiseAWarning('ColorSet supplied, however DataMining plots do not use color set from input.')
              if 'cluster' == self.options['plotSettings']['plot'][pltindex]['SKLtype']:
                # TODO: include the cluster Centers to the plot
                if 'noClusters' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  clusterDict[pltindex]['noClusters'] = int(self.options['plotSettings']['plot'][pltindex].get('attributes', {})['noClusters'])
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('noClusters')
                else:
                  clusterDict[pltindex]['noClusters'] = np.amax(self.clusterValues[pltindex][1][0]) + 1
                dataMiningPlotOptions.update(self.options['plotSettings']['plot'][pltindex].get('attributes', {}))
                if   self.dim == 2:
                  clusterDict[pltindex]['clusterValues'] = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 2))
                elif self.dim == 3:
                  clusterDict[pltindex]['clusterValues'] = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 3))
                clusterDict[pltindex]['clusterValues'][:, 0] = self.xValues[pltindex][key][xIndex]
                clusterDict[pltindex]['clusterValues'][:, 1] = self.yValues[pltindex][key][yIndex]
                if self.dim == 2:
                  for k, col in zip(range(int(clusterDict[pltindex]['noClusters'])), colors):
                    myMembers = self.clusterValues[pltindex][1][0] == k
                    self.actPlot = self.plt.scatter(clusterDict[pltindex]['clusterValues'][myMembers, 0], clusterDict[pltindex]['clusterValues'][myMembers, 1] , color = col, **dataMiningPlotOptions)
                elif self.dim == 3:
                  dataMiningPlotOptions['rasterized'] = True
                  for zIndex in range(len(self.zValues[pltindex][key])):
                    clusterDict[pltindex]['clusterValues'][:, 2] = self.zValues[pltindex][key][zIndex]
                  for k, col in zip(range(clusterDict[pltindex]['noClusters']), colors):
                    myMembers = self.clusterValues[pltindex][1][0] == k
                    self.actPlot = self.plt3D.scatter(clusterDict[pltindex]['clusterValues'][myMembers, 0], clusterDict[pltindex]['clusterValues'][myMembers, 1], clusterDict[pltindex]['clusterValues'][myMembers, 2], color = col, **dataMiningPlotOptions)
              elif 'bicluster' == self.options['plotSettings']['plot'][pltindex]['SKLtype']:
                self.raiseAnError(IOError, 'SKLType Bi-Cluster Plots are not implemented yet!..')
              elif 'mixture' == self.options['plotSettings']['plot'][pltindex]['SKLtype']:
                if 'noMixtures' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  clusterDict[pltindex]['noMixtures'] = int(self.options['plotSettings']['plot'][pltindex].get('attributes', {})['noMixtures'])
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('noMixtures')
                else:
                  clusterDict[pltindex]['noMixtures'] = np.amax(self.mixtureValues[pltindex][1][0]) + 1
                if self.dim == 3:
                  self.raiseAnError(IOError, 'SKLType Mixture Plots are only available in 2-Dimensions')
                else:
                  clusterDict[pltindex]['mixtureValues'] = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 2))
                clusterDict[pltindex]['mixtureValues'][:, 0] = self.xValues[pltindex][key][xIndex]
                clusterDict[pltindex]['mixtureValues'][:, 1] = self.yValues[pltindex][key][yIndex]
                if 'mixtureCovars' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  split = self.__splitVariableNames('mixtureCovars', (pltindex, 0))
                  mixtureCovars = self.sourceData[pltindex].getParam(split[1], split[2], nodeId = 'ending')
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('mixtureCovars')
                else:
                  mixtureCovars = None
                if 'mixtureMeans' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  split = self.__splitVariableNames('mixtureMeans', (pltindex, 0))
                  mixtureMeans = self.sourceData[pltindex].getParam(split[1], split[2], nodeId = 'ending')
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('mixtureMeans')
                else:
                  mixtureMeans = None
                # mixtureCovars.reshape(3, 4)
                # mixtureMeans.reshape(3, 4)
                # for i, (mean, covar, col) in enumerate(zip(mixtureMeans, mixtureCovars, colors)):
                for i, col in zip(range(clusterDict[pltindex]['noMixtures']), colors):
                  if not np.any(self.mixtureValues[pltindex][1][0] == i):
                      continue
                  myMembers = self.mixtureValues[pltindex][1][0] == i
#                  self.make_ellipses(mixtureCovars, mixtureMeans, i, col)
                  self.actPlot = self.plt.scatter(clusterDict[pltindex]['mixtureValues'][myMembers, 0], clusterDict[pltindex]['mixtureValues'][myMembers, 1], color = col, **dataMiningPlotOptions)
              elif 'manifold' == self.options['plotSettings']['plot'][pltindex]['SKLtype']:
                if   self.dim == 2:
                  manifoldValues = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 2))
                elif self.dim == 3:
                  manifoldValues = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 3))
                manifoldValues[:, 0] = self.xValues[pltindex][key][xIndex]
                manifoldValues[:, 1] = self.yValues[pltindex][key][yIndex]
                if 'clusterLabels' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  split = self.__splitVariableNames('clusterLabels', (pltindex, 0))
                  clusterDict[pltindex]['clusterLabels'] = self.sourceData[pltindex].getParam(split[1], split[2], nodeId = 'ending')
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('clusterLabels')
                else:
                  clusterDict[pltindex]['clusterLabels'] = None
                if 'noClusters' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  clusterDict[pltindex]['noClusters'] = int(self.options['plotSettings']['plot'][pltindex].get('attributes', {})['noClusters'])
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('noClusters')
                else:
                  clusterDict[pltindex]['noClusters'] = np.amax(self.clusterValues[pltindex][1][0]) + 1
                if self.clusterValues[pltindex][1][0] is not None:
                  if   self.dim == 2:
                    for k, col in zip(range(clusterDict[pltindex]['noClusters']), colors):
                      myMembers = self.clusterValues[pltindex][1][0] == k
                      self.actPlot = self.plt.scatter(manifoldValues[myMembers, 0], manifoldValues[myMembers, 1], color = col, **dataMiningPlotOptions)
                  elif self.dim == 3:
                    dataMiningPlotOptions['rasterized'] = True
                    for zIndex in range(len(self.zValues[pltindex][key])):
                      manifoldValues[:, 2] = self.zValues[pltindex][key][zIndex]
                    for k, col in zip(range(clusterDict[pltindex]['noClusters']), colors):
                      myMembers = self.clusterValues[pltindex][1][0] == k
                      self.actPlot = self.plt3D.scatter(manifoldValues[myMembers, 0], manifoldValues[myMembers, 1], manifoldValues[myMembers, 2], color = col, **dataMiningPlotOptions)
                else:
                  if   self.dim == 2:
                    self.actPlot = self.plt.scatter(manifoldValues[:, 0], manifoldValues[:, 1], **dataMiningPlotOptions)
                  elif self.dim == 3:
                    dataMiningPlotOptions['rasterized'] = True
                    for zIndex in range(len(self.zValues[pltindex][key])):
                      manifoldValues[:, 2] = self.zValues[pltindex][key][zIndex]
                      self.actPlot = self.plt3D.scatter(manifoldValues[:, 0], manifoldValues[:, 1], manifoldValues[:, 2], **dataMiningPlotOptions)
              elif 'decomposition' == self.options['plotSettings']['plot'][pltindex]['SKLtype']:
                if   self.dim == 2:
                  decompositionValues = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 2))
                elif self.dim == 3:
                  decompositionValues = np.zeros(shape = (len(self.xValues[pltindex][key][xIndex]), 3))
                decompositionValues[:, 0] = self.xValues[pltindex][key][xIndex]
                decompositionValues[:, 1] = self.yValues[pltindex][key][yIndex]
                if 'noClusters' in self.options['plotSettings']['plot'][pltindex].get('attributes', {}).keys():
                  clusterDict[pltindex]['noClusters'] = int(self.options['plotSettings']['plot'][pltindex].get('attributes', {})['noClusters'])
                  self.options['plotSettings']['plot'][pltindex].get('attributes', {}).pop('noClusters')
                else:
                  clusterDict[pltindex]['noClusters'] = np.amax(self.clusterValues[pltindex][1][0]) + 1
                if self.clusterValues[pltindex][1][0] is not None:
                  if self.dim == 2:
                    for k, col in zip(range(clusterDict[pltindex]['noClusters']), colors):
                      myMembers = self.clusterValues[pltindex][1][0] == k
                      self.actPLot = self.plt.scatter(decompositionValues[myMembers, 0], decompositionValues[myMembers, 1], color = col, **dataMiningPlotOptions)
                  elif self.dim == 3:
                    dataMiningPlotOptions['rasterized'] = True
                    for zIndex in range(len(self.zValues[pltindex][key])):
                      decompositionValues[:, 2] = self.zValues[pltindex][key][zIndex]
                    for k, col in zip(range(clusterDict[pltindex]['noClusters']), colors):
                      myMembers = self.clusterValues[pltindex][1][0] == k
                      self.actPlot = self.plt3D.scatter(decompositionValues[myMembers, 0], decompositionValues[myMembers, 1], decompositionValues[myMembers, 2], color = col, **dataMiningPlotOptions)
                else:  # no ClusterLabels
                  if self.dim == 2:
                    self.actPLot = self.plt.scatter(decompositionValues[:, 0], decompositionValues[:, 1], **dataMiningPlotOptions)
                  elif self.dim == 3:
                    dataMiningPlotOptions['rasterized'] = True
                    for zIndex in range(len(self.zValues[pltindex][key])):
                      decompositionValues[:, 2] = self.zValues[pltindex][key][zIndex]
                      self.actPlot = self.plt3D.scatter(decompositionValues[:, 0], decompositionValues[:, 1], decompositionValues[:, 2], **dataMiningPlotOptions)
      else:
        # Let's try to "write" the code for the plot on the fly
        self.raiseAWarning('Try to create a not-predifined plot of type ' + self.outStreamTypes[pltindex] + '. If it does not work check manual and/or relavite matplotlib method specification.')
        commandArgs = ' '
        import CustomCommandExecuter as execcommand
        for kk in self.options['plotSettings']['plot'][pltindex]:
          if kk != 'attributes' and kk != self.outStreamTypes[pltindex]:
            if commandArgs != ' ':
              prefix = ','
            else:
              prefix = ''
            try:
              commandArgs = commandArgs + prefix + kk + '=' + str(ast.literal_eval(self.options['plotSettings']['plot'][pltindex][kk]))
            except:
              commandArgs = commandArgs + prefix + kk + '="' + str(self.options['plotSettings']['plot'][pltindex][kk]) + '"'
        try:
          if self.dim == 2:
            execcommand.execCommand('self.actPlot = self.plt3D.' + self.outStreamTypes[pltindex] + '(' + commandArgs + ')', self)
          elif self.dim == 3:
            execcommand.execCommand('self.actPlot = self.plt3D.' + self.outStreamTypes[pltindex] + '(' + commandArgs + ')', self)
        except ValueError as ae:
          self.raiseAnError(RuntimeError, '<' + str(ae) + '> -> in execution custom plot "' + self.outStreamTypes[pltindex] + '" in Plot ' + self.name + '.\nSTREAM MANAGER: ERROR -> command has been called in the following way: ' + 'self.plt.' + self.outStreamTypes[pltindex] + '(' + commandArgs + ')')
    # SHOW THE PICTURE
    self.plt.draw()
    # self.plt3D.draw(self.fig.canvas.renderer)
    if 'screen' in self.options['how']['how'].split(',') and disAvail:
      if platform.system() == 'Linux':
        # XXX For some reason, this is required on Linux, but causes
        # OSX to fail.  Which is correct for windows has not been determined.
        def handle_close(event):
          """
            This method is aimed to handle the closing of figures (overall when in interactive mode)
            @ In, event, instance, the event to close
            @ Out, None
          """
          self.fig.canvas.stop_event_loop()
          self.raiseAMessage('Closed Figure')
        self.fig.canvas.mpl_connect('close_event', handle_close)
      self.fig.show()
      # if blockFigure: self.fig.ginput(n=-1, timeout=-1, show_clicks=False)
    for i in range(len(self.options['how']['how'].split(','))):
      if self.options['how']['how'].split(',')[i].lower() != 'screen':
        if not self.overwrite:
          prefix = str(self.counter) + '-'
        else:
          prefix = ''
        if len(self.filename) > 0:
          name = self.filename
        else:
          name = prefix + self.name + '_' + str(self.outStreamTypes).replace("'", "").replace("[", "").replace("]", "").replace(",", "-").replace(" ", "")
        self.plt.savefig(name + '.' + self.options['how']['how'].split(',')[i], format = self.options['how']['how'].split(',')[i])
