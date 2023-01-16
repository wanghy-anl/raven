#!/usr/bin/env python
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
"""
Created on March 8, 2018

@author: alfoa

External Loader for serialized surrogate model (ROM) for external usage
"""
# This is a class and module used to import serialized ROMs (by RAVEN) into an
# external code.
# It requires to set the path of the RAVEN framework (e.g. ./raven/ravenframework)
# and the path to the serialized ROM (e.g. ./example/ROMpk.pk)
# This script can be run with a standalone input file where these info is inputted
# and some evaluations can be evaluated. For example:
# <?xml version="1.0" ?>
# <external_rom>
#    <RAVENdir>/Users/alfoa/projects/raven_github/raven/ravenframework</RAVENdir>
#    <ROMfile>/Users/alfoa/projects/raven_github/raven/scripts/ROMpk</ROMfile>
#    <evaluate>
#      <x1>0. 1. 0.5</x1>
#      <x2>1.0 0.4 2.1</x2>
#    </evaluate>
#    <inspect>true</inspect>
#    <outputFile>test_output.xml</outputFile>
# </external_rom>
#
# The script can be run as "python externalROMloader.py inputfile.xml"
# or the class ravenROMexternal can be just used


#For future compatibility with Python 3
from __future__ import division, print_function, absolute_import
#End compatibility block for Python 3

#External Modules--------------------begin
import os
import sys
import pickle
import numpy as np
import xml.etree.ElementTree as ET
from xml.dom import minidom
#External Modules--------------------end

class ravenROMexternal(object):
  """
    External ROM loader and user-gate
  """
  def __init__(self, binaryFileName, whereFrameworkIs):
    """
      This constructor un-serializes the ROM generated by RAVEN and
      it makes the ROM available for external usage
      @ In, binaryFileName, str, the location of the serialized (pickled) ROM that needs to be imported
      @ In, whereFrameworkIs, str, the location of RAVEN framework (path)
      @ Out, None
    """
    self._binaryLoc = binaryFileName
    self._frameworkLoc = whereFrameworkIs
    self._load(binaryFileName, whereFrameworkIs)

  def _load(self, binaryFileName, whereFrameworkIs):
    """
      Load the ROM.
      @ In, binaryFileName, str, the location of the serialized (pickled) ROM that needs to be imported
      @ In, whereFrameworkIs, str, the location of RAVEN framework (path)
      @ Out, None
    """
    # find the RAVEN framework
    try:
      import ravenframework
      #If the above succeeded, do not need to do any of the rest.
    except ModuleNotFoundError:
      frameworkDir = os.path.abspath(whereFrameworkIs)
      if not os.path.exists(frameworkDir):
        raise IOError('The RAVEN framework directory does not exist in location "' + str(frameworkDir)+'" !')
      sys.path.append(os.path.dirname(frameworkDir))
      if not os.path.dirname(frameworkDir).endswith("framework"):
        # we import the Driver to load the RAVEN enviroment for the un-pickling
        try:
          from CustomDrivers import DriverUtils
          DriverUtils.doSetup()
        except ImportError:
          # we try to add the framework directory
          pass
      else:
        # we import the Driver to load the RAVEN enviroment for the un-pickling
        sys.path.append(os.path.join(frameworkDir,"ravenframework"))
        import Driver
    # de-serialize the ROM
    serializedROMlocation = os.path.abspath(binaryFileName)
    if not os.path.exists(serializedROMlocation):
      raise IOError('The serialized (binary) file has not been found in location "' + str(serializedROMlocation)+'" !')
    self.rom = pickle.load(open(serializedROMlocation, mode='rb'))

  def __getstate__(self):
    """
      Deep copy.
      @ In, None
      @ Out, d, dict, self representation
    """
    d = {'binaryFileName': self._binaryLoc,
         'whereFrameworkIs': self._frameworkLoc}
    return d

  def __setstate__(self, d):
    """
      Deep paste.
      @ In, d, dict, self representation
      @ Out, None
    """
    self._binaryLoc = d['binaryFileName']
    self._frameworkLoc = d['whereFrameworkIs']
    self._load(self._binaryLoc, self._frameworkLoc)

  def setAdditionalParams(self, nodes):
    """
      Set ROM parameters for external evaluation
      @ In, nodes, list, list of xml nodes for setting parameters of pickleROM
      @ Out, None
    """
    from ravenframework.SupervisedLearning.pickledROM import pickledROM
    spec = pickledROM.getInputSpecification()()
    # Changing parameters for the ROM
    for node in nodes:
      spec.parseNode(node)
    # Matching the index name of the defaul params object
    params = {'paramInput':spec}
    self.rom.setAdditionalParams(params)

  def evaluate(self,request):
    """
      Evaluate the ROM
      @ In, request, dict, dictionary of realization that needs to be evaluated {'varName':numpy.ndarray,'varName':numpy.ndarray, etc.}
      @ Out, output, list, dictionary of the outputs {'output1':np.ndarray,'output2':np.ndarray, etc.}
      the arrays have the shape (NumberOfRequestedEvaluations,)
    """
    output = []
    for index in range(len(list(request.values())[0])):
      output.append(self.rom.evaluate({k:np.asarray(v[index]) for k,v in request.items()}))
    return output

  def getInitParams(self):
    """
      Return the initialization parameter of the pickled ROM
      @ In, None
      @ Out, params, dict, dictionary of init params
    """
    return self.rom.getInitParams()

if __name__ == '__main__':
  arguments = sys.argv
  if len(arguments) == 2:
    # we expect an input file
    if not os.path.exists(arguments[1]):
      raise IOError('Not found input file "' + str(os.path.basename(arguments[1]) )+'" in location "' +os.path.dirname(arguments[1])+  '"!')
    if not arguments[1].endswith("xml"):
      raise IOError('The input file "' + str(arguments[1])+'" is not an XML!')
    if os.path.exists(arguments[1]):
      tree = ET.parse(arguments[1])
      root = tree.getroot()
      ravenDir     = root.find(".//RAVENdir")
      pickledFile  = root.find(".//ROMfile")
      evaluateData = root.find(".//evaluate")
      inspectROM   = root.find(".//inspect")
      outputFilename = root.find(".//outputFile")
      outputFilename = outputFilename.text if outputFilename is not None else '.'.join(os.path.basename(arguments[1]).split(".")[:-1])+"_out.xml"
      if ravenDir is None:
        raise IOError('Not found XML node <RAVENdir>!')
      ravenDir = ravenDir.text
      if pickledFile is None:
        raise IOError('Not found XML node <ROMfile>!')
      if evaluateData is None:
        raise IOError('Not found XML node <evaluate>!')
      pickledFile = pickledFile.text

      if evaluateData is None and inspectROM is None:
        raise IOError('Not found either XML node <evaluate> nor <inspect>! At least one of them needs to be inputted!')
      if evaluateData is not None:
        evalDict = {}
        for child in evaluateData:
          evalDict[child.tag] = [float(val) for val in child.text.split()]
      if inspectROM is not None:
        inspROM = True if inspectROM.text.lower() in ['true','t','yes',"y"] else False
      else:
        inspROM = False
  else:
    raise IOError('An input file must be provided!')
  rom = ravenROMexternal(pickledFile, ravenDir)
  if evaluateData is not None:
    output = rom.evaluate(evalDict)
  if inspROM:
    settings = rom.getInitParams()
  # create the output
  outElement = ET.Element(rom.rom.name)
  if inspROM:
    sett = ET.Element("settings")
    for el,val in settings.items():
      element      = ET.Element(el)
      element.text = str(np.asarray(val))
      sett.append(element)
    outElement.append(sett)
  if evaluateData is not None:
    evalData = ET.Element("evaluations")
    for cnt,out in enumerate(output):
      realizationData = ET.Element("evaluation", attrib={'realization':str(cnt+1)})
      for el,val in evalDict.items():
        element      = ET.Element(el)
        element.text = str(val[cnt])
        realizationData.append(element)
      evalData.append(realizationData)
      for el,val in out.items():
        element      = ET.Element(el)
        element.text = str(val)
        realizationData.append(element)
      evalData.append(realizationData)
    outElement.append(evalData)
  with open (outputFilename,"w") as fileObject:
    fileObject.write(minidom.parseString(ET.tostring(outElement)).toprettyxml(indent="  "))







