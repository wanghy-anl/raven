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
  Created on April 18, 2017
  @author: Matteo D'Onorio (Sapienza University of Rome)
           Andrea Alfonsi (INL)
"""

import os
from ravenframework.CodeInterfaceBaseClass import CodeInterfaceBase
from ravenframework.CodeInterfaceClasses.MELCOR.melcorTools import MCRBin
from ..Generic import GenericParser
import pandas as pd
import shutil

class Melcor(CodeInterfaceBase):
  """
    This class is used a part of a code dictionary to specialize Model. Code for different MELCOR versions
    like MELCOR 2.2x, MELCOR 1.86, MELCOR for fusion applications
  """

  def __init__(self):
    """
      Constructor
      @ In, None
      @ Out, None
    """
    CodeInterfaceBase.__init__(self)
    self.inputExtensions = ['i','inp']
    self.detVars = []

  def _readMoreXML(self,xmlNode):
    """
      Function to read the portion of the xml input that belongs to this specialized class and initialize
      some members based on inputs. This can be overloaded in specialize code interface in order to
      read specific flags.
      Only one option is possible. You can choose here, if multi-deck mode is activated, from which deck you want to load the results
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None.
    """

    melNode = xmlNode.find('MelcorOutput')
    varNode = xmlNode.find('variables')
    plotNode = xmlNode.find('CodePlotFile')
    
    try:
      detNode = xmlNode.find('detNode')
      hackedNode = xmlNode.find('hackedNode')
    except:
      detNode = None
      hackedNode = None  
    
    if detNode != None:
      inpNode = xmlNode.find('InputFile')
      rstNode = xmlNode.find('RestartFile')
      if inpNode is None:
        raise IOError("Please enter MELCOR input name")
      if rstNode is None:
        raise IOError("Please enter MELCOR restart name")
      self.InpFile = [var.strip() for var in inpNode.text.split(",")][0]
      self.RstFile = [var.strip() for var in rstNode.text.split(",")][0]
      self.DetNode = [var.strip() for var in detNode.text.split(",")][0]
    if hackedNode != None:
      self.hackedNode = [var.strip() for var in hackedNode.text.split(",")]    
    
    if varNode is None:
      raise IOError("Melcor variables not found, define variables to print")
    if plotNode is None:
      raise IOError("Please define the name of the MELCOR plot file in the CodePlotFile xml node")
    if melNode is None:
      raise IOError("Please enter MELCOR message file name")

    self.VarList = [var.strip() for var in varNode.text.split("$,")]
    self.MelcorPlotFile = [var.strip() for var in plotNode.text.split(",")][0]
    self.melcorOutFile = [var.strip() for var in melNode.text.split(",")][0]

    return self.VarList, self.MelcorPlotFile, self.melcorOutFile, self.InpFile, self.RstFile, self.DetNode, self.hackedNode

  def findInps(self,currentInputFiles):
    """
      Locates the input files for Melgen, Melcor
      @ In, currentInputFiles, list, list of Files objects
      @ Out, (melgIn,melcIn), tuple, tuple containing Melgen and Melcor input files
    """
    foundMelcorInp = False
    for index, inputFile in enumerate(currentInputFiles):
      if inputFile.getExt() in self.getInputExtension():
        foundMelcorInp = True
        melgIn = currentInputFiles[index]
        melcIn = currentInputFiles[index]
    if not foundMelcorInp:
      raise IOError("Unknown input extensions. Expected input file extensions are "+ ",".join(self.getInputExtension())+" No input file has been found!")
    return melgIn, melcIn


  def generateCommand(self, inputFiles, executable, clargs=None, fargs=None, preExec=None):
    """
      This method is used to retrieve the command (in tuple format) needed to launch the Code.
      See base class.  Collects all the clargs and the executable to produce the command-line call.
      Returns tuple of commands and base file name for run.
      Commands are a list of tuples, indicating parallel/serial and the execution command to use.
      @ In, inputFiles, list, List of input files (length of the list depends on the number of inputs have been added in the Step is running this code)
      @ In, executable, string, executable name with absolute path (e.g. /home/path_to_executable/code.exe)
      @ In, clargs, dict, optional, dictionary containing the command-line flags the user can specify in the input (e.g. under the node < Code >< clargstype =0 input0arg =0 i0extension =0 .inp0/ >< /Code >)
      @ In, fargs, dict, optional, a dictionary containing the auxiliary input file variables the user can specify in the input (e.g. under the node < Code >< fileargstype =0 input0arg =0 aux0extension =0 .aux0/ >< /Code >)
      @ In, preExec, string, optional, a string the command that needs to be pre-executed before the actual command here defined
      @ Out, returnCommand, tuple, tuple containing the generated command. returnCommand[0] is the command to run the code (string), returnCommand[1] is the name of the output root
    """
    
    melcOut = 'OUTPUT_MELCOR'
    if self.DetNode != None:
      melcOut = 'out~'+ self.InpFile[:-2]#prefix ~out needed to create branchinfo.xml
    
    found = False
    for index, inputFile in enumerate(inputFiles):
      if inputFile.getExt() in self.getInputExtension():
        found = True
        break
    if not found:
      raise IOError('None of the input files has one of the following extensions: ' + ' '.join(self.getInputExtension()))

    melcin,melgin = self.findInps(inputFiles)
    if clargs:
      precommand = executable + clargs['text']
    else:
      precommand = executable
      
    melgCommand = str(preExec)+ ' '+melcin.getFilename()
    melcCommand = precommand+ ' '+melcin.getFilename()
    
    if self.DetNode != None:
      found = False
      for index, inputFile in enumerate(inputFiles):
        if inputFile.getPath().endswith("DET_1/"):
          found = True
          break
      if found == True:
        returnCommand = [('serial',melgCommand + ' && ' + melcCommand +' ow=o ')],melcOut	
      else:
        returnCommand = [('serial',melcCommand +' ow=a ')],melcOut
    else:
      returnCommand = [('serial',melgCommand + ' && ' + melcCommand +' ow=o ')],melcOut
    
    return returnCommand

  def createNewInput(self,currentInputFiles,origInputFiles,samplerType,**Kwargs):
    """
      This generates a new input file depending on which sampler is chosen
      @ In, currentInputFiles, list,  list of current input files (input files from last this method call)
      @ In, oriInputFiles, list, list of the original input files
      @ In, samplerType, string, Sampler type (e.g. MonteCarlo, Adaptive, etc. see manual Samplers section)
      @ In, Kwargs, dictionary, kwarded dictionary of parameters. In this dictionary there is another dictionary called "SampledVars"
             where RAVEN stores the variables that got sampled (e.g. Kwargs['SampledVars'] => {'var1':10,'var2':40})
      @ Out, newInputFiles, list, list of newer input files, list of the new input files (modified and not)
    """

    if "dynamicevent" or 'adaptivedynamiceventtree' in samplerType.lower():
      self.Det = str(samplerType).lower()
      workingDir = Kwargs['subDirectory']
      self._samplersDictionary = {}
      isDet = self.DetNode
      if isDet == 'hackedMelcor':
          hacked_node = self.hackedNode
          hacked_var = self.hacked_data(hacked_node)
      subworkingDir = Kwargs['WORKING_DIR']
      firstDir = subworkingDir + "/DET_1"
      melcorInpFile = self.InpFile
    else:
      self.Det = False
    indexes  = []
    inFiles  = []
    origFiles= []
    
    # find input file index
    index = self._findInputFileIndex(currentInputFiles)
    # instanciate the parser
    if self.Det:
      if workingDir != firstDir:
        self.inputAliases = Kwargs.get('alias').get('input')
        self._samplersDictionary[samplerType] = self.dynamicEventTreeForMELCOR
        self.detVars = Kwargs.get('DETVariables')
        if 'None' not in str(samplerType):
          Kwargs['currentPath'] = currentInputFiles[index].getPath()
          modifDict = self._samplersDictionary[samplerType](**Kwargs)
        if isDet != 'olderMelcor':
          if modifDict['happenedEvent']:
            newInput = self.writeNewInput('happenedEvent', melcorInpFile, workingDir)
          else:
            newInput = self.writeNewInput('nothappenedEvent', melcorInpFile, workingDir)
        if isDet == 'hackedMelcor':
          doubleZero = list()
          values = list()
          for var in Kwargs['SampledVars'].items():
            zeroOrNot = self.findZero('empty', workingDir , isDet , melcorInpFile , var[0] )
            doubleZero.append(zeroOrNot)
            values.append([var[0],var[1]])
          for var in Kwargs['SampledVars']:
            if var in hacked_var:
              tripVar = self.messageReader(workingDir[:-2])[0]
              if modifDict['happenedEvent'] and tripVar == var:
                newInput = self.hackedEdf('happenedEvent', workingDir , var  , hacked_var[var] , values)
              else:
                newInput = self.hackedEdf(doubleZero , workingDir , var, hacked_var[var] , values)
        if not self.detVars:
          raise IOError('ERROR in "MELCOR Code Interface": NO DET variables with DET sampler!!!')
      else:
        print("FIRST RUN")
        if isDet == 'hackedMelcor':
            for var in Kwargs['SampledVars']:
                if var in hacked_var:
                  filename = "EDF_" + str(var) + ".TXT"
                  Edf = open(os.open(os.path.join( workingDir , filename ), os.O_CREAT | os.O_WRONLY, 0o777), 'w')
                  Edf.write(" " + "%.5E" %0.0 + " " + "%.5E" %1.0 + "\n" + " " + "%.5E" %100000000.0 + " " + "%.5E" %1.0 + "\n")
                  Edf.close()
    self.__transferMetadata(Kwargs.get("metadataToTransfer",None), currentInputFiles[index].getPath())
    
    for index,inputFile in enumerate(currentInputFiles):
      if inputFile.getExt() in self.getInputExtension():
        indexes.append(index)
        inFiles.append(inputFile)
    for index,inputFile in enumerate(origInputFiles):
      if inputFile.getExt() in self.getInputExtension():
        origFiles.append(inputFile)
    parser = GenericParser.GenericParser(inFiles)
    parser.modifyInternalDictionary(**Kwargs)
    parser.writeNewInput(currentInputFiles,origFiles)

    if isDet == 'olderMelcor': #MELCOR 1.86
      for var in Kwargs['SampledVars']:
        if workingDir != firstDir:
          #tripVar = "%" + self.messageReader(workingDir[:-2])[0] + "%"
          tripVar = self.messageReader(workingDir[:-2])[0]
          if modifDict['happenedEvent'] and var == tripVar:
            newInput = self.writeEdf('happenedEvent' , melcorInpFile , workingDir , var)
          else:
            newInput = self.writeEdf('nothappenedEvent' , melcorInpFile , workingDir , var)
        else:
          newInput = self.writeEdf('nothappenedEvent' , melcorInpFile , workingDir, var)
          
    return currentInputFiles

  def hacked_data(self, hacked_node):
    """
      @ In, hacked_node, list, info on hacked_var and hacked_mode

      @ Out, hacked_var, dictonary, hacked variable and hacked_mode
    """
    
    hacked_var = dict()
    for data in hacked_node:
        hacked_var[data.split('/')[0]] = data.split('/')[1] 
    return hacked_var

  def hackedEdf (self, happenedorNot , workingDir , var , hacked_mode, values):
    """
      @ In, happenedorNot, string, info on whether event happend or not
			@ In , workingDir, string, actual working Directory
			@ In, var, string, name of sampled variables present written as '%var%'
      @ Out, None
    """
    import threading
    mode = hacked_mode.split('-')[0]
    position = int(hacked_mode.split('-')[1])      
    freezeValue = self.last_line( workingDir , position , 'EDF_HACKED.TXT')[1]
    tripVariable = var.replace('%','') #sampled variable without prefix and suffix %
    filename = "EDF_" + str(tripVariable) + ".TXT"
    for objects in values:
      if var in objects:
        firstTime = objects[1]
      else:
        secondTime = objects[1]
    lastTime = secondTime + firstTime
    restartTime = firstTime + 2.0
    if happenedorNot == 'happenedEvent':
      Edf = open(os.open(os.path.join( workingDir , filename ), os.O_CREAT | os.O_WRONLY, 0o777), 'w')
      Edf.write(" " + "%.5E" %0.0 + " " + "%.5E" %1.0 + "\n" + " " + "%.5E" %restartTime + " " + "%.5E" %freezeValue + "\n" ) #+ " " + "%.5E" %lastTime + " " + "%.5E" %freezeValue + "\n" )
      Edf.close()
      if mode == 'freeze':
        t1 = self.do_something(workingDir, filename, mode , freezeValue, restartTime , lastTime)
      if mode == 'random':
        lower_boundary = float((hacked_mode.split('-')[2]).split('!')[0])
        upper_boundary = float((hacked_mode.split('-')[2]).split('!')[1])
        lower_upper = [ lower_boundary , upper_boundary ]
        t1 = self.do_something(workingDir, filename, mode ,  lower_upper, restartTime , lastTime)
    else:
      restartTime = self.last_line( workingDir , position , filename)[0] + 1.0
      if happenedorNot[0] != happenedorNot[1]:
        if mode == 'freeze':
          t2 = self.do_something(workingDir, filename, mode ,  lower_upper, restartTime , lastTime)
        if mode == 'random':
          lower_boundary = float((hacked_mode.split('-')[2]).split('!')[0])
          upper_boundary = float((hacked_mode.split('-')[2]).split('!')[1])
          lower_upper = [ lower_boundary , upper_boundary ]
          t2 = self.do_something(workingDir, filename, mode , lower_upper , restartTime , lastTime)
      if happenedorNot[0] == 0.0 and happenedorNot[1] == 0.0:
        Time = restartTime + 100000.0
        Edf = open(os.path.join( workingDir, filename ),"a")
        Edf.write(" " + "%.5E" %Time + " " + "%.5E" %freezeValue + "\n")
        Edf.close()

  def do_something(self, workingDir, filename, mode , value_changed, Time, lastTime):    #value_changed could be freeze or upper and lower boundary
    
    Edf = open(os.path.join( workingDir, filename ),"a")
    if mode == 'freeze':
      while lastTime > Time:
        Time += 5.0  
        Edf.write(" " + "%.5E" %Time + " " + "%.5E" %value_changed + "\n")
    if mode == 'random':
      import random
      lower_value = value_changed[0]
      higher_value = value_changed[1]
      random_value = random.uniform(lower_value, higher_value)
      while lastTime > Time:
        Time += 5.0  
        random_value = random.uniform(lower_value, higher_value)  
        Edf.write(" " + "%.5E" %Time + " " + "%.5E" %random_value + "\n")
    Edf.close()       

  def last_line( self , workingDir , position , filename):
    
    file = open(os.path.join( workingDir,filename),"r")
    for lastLine in file:
        pass
    lastLine = lastLine.rstrip()
    lastLine = lastLine.split()
    lastTime = float(lastLine[0])
    lastValue = float(lastLine[position])
    file.close()
    return lastTime, lastValue

  def stopDET (self, workingDir):
    """
      @ In, happenedorNot, string, info on whether event happend or not
			@ In, inputFile, string, name of melcor input file
			@ In, workingDir, string, actual working Directory
			@ In, var, string, name of sampled variables present written as '%var%'
      @ Out, None
    """

    found = False
    for var in self.detVars:
      variable = var.replace('%','') #sampled variable without prefix and suffix %
      filename = "EDF_" + str( variable ) + ".TXT"
      if self.DetNode == 'olderMelcor':
        zeroOrNot = self.findZero( filename, workingDir , self.DetNode , self.InpFile, variable)[0]
      else:
        zeroOrNot = self.findZero( filename, workingDir , self.DetNode , self.InpFile, variable)
      if zeroOrNot == 1.0:
        found = False
        break
      else:
        found = True
    return found

  def writeEdf (self, happenedorNot , inputFile , workingDir , var):
    """
      @ In, happenedorNot, string, info on whether event happend or not
			@ In, inputFile, string, name of melcor input file
			@ In , workingDir, string, actual working Directory
			@ In, var, string, name of sampled variables present written as '%var%'
      @ Out, None
    """
    tripVariable = var.replace('%','') #sampled variable without prefix and suffix %
    filename = "EDF_" + str(tripVariable) + ".TXT"
    Edf = open(os.path.join( workingDir , filename), 'a')
    sampledVar = self.ravenSample(inputFile , workingDir , tripVariable)
    if workingDir.endswith("/DET_1"):
      if happenedorNot == 'happenedEvent':
        Edf.write("%.5E" %0.0 + " " + "%.5E" %0.0 + " " + "%.5E" %sampledVar + "\n")
      else:
        Edf.write("%.5E" %0.0 + " " + "%.5E" %1.0 + " " + "%.5E" %sampledVar + "\n")
    else:
      restartTime = self.restartTime(workingDir[:-2])
      previousTime = self.findZero(filename, workingDir[:-2])[1]
      if previousTime > restartTime:
        restartTime = previousTime + 0.1
      restartTimeStep = self.restartTimeStep(workingDir[:-2])
      self.writeNewRestart(inputFile, workingDir, restartTimeStep)
      zeroOrNot = self.findZero(filename, workingDir[:-2])[0]
      if happenedorNot == 'happenedEvent':
        Edf.write("%.5E" %restartTime + " " + "%.5E" %0.0 + " " + "%.5E" %sampledVar + "\n")
      else:
        Edf.write("%.5E" %restartTime + " " + "%.5E" %zeroOrNot + " " + "%.5E" %sampledVar + "\n")
    Edf.close()

  def findZero(self, filename, workingDir , isDet , melcorInpFile, variable):
    """
      @ In, filename, string, EDF_var.TXT file present in previous working Directory
	  @ In, workingDir, string, previous working Directory where EDF.TXT files are present
      @ Out, zeroOrNot, int, returns 0.0 if last line in EDF file has a 0.0 in second column (column numeration starting from 1 while in MELCOR EDF column numeration starts from 0)
    """
    if isDet == 'olderMelcor':
      file = open(os.path.join(workingDir,filename),"r")
      for lastLine in file:
        pass
      lastLine = lastLine.rstrip()
      lastLine = lastLine.split()
      lastTime = float(lastLine[0])
      if float(lastLine[1]) == 0.0:
        zeroOrNot = 0.0
      else:
        zeroOrNot = 1.0
      file.close()
      return zeroOrNot, lastTime
    else:
      counter = -1
      variable = str(variable)
      file = open(os.path.join(workingDir,melcorInpFile),"r")
      for index, line in enumerate(file, 1):
        line = line.rstrip()
        line = line.split()
        if line[0] == 'CF_ID':
          if line[1][1:-1] == variable:
            counter = index + 3
        if index == counter:
          if float(line [2]) == 0.0:
            zeroOrNot = 0.0
          else:
            zeroOrNot = 1.0
            break
      file.close()
      return zeroOrNot

  def changeRestart (self, inputFile, workingDir, restartTimeStep):
    """
      @ In, inputFile, string, name of melcor input file
			@ In , workingDir, string, actual working Directory
			@ In, restartTimeStep, int, last restart cycle present in previous .MES file
      @ Out, newInput, list, container of inputFile with changed RESTART cycle
    """
    file = open(os.path.join(workingDir,inputFile),"r")
    newInput = []
    for index, line in enumerate(file, 1):
      line = line.rstrip()
      line = line.split()
      if line[0] == 'RESTART':
        newLine = [line[0], int(restartTimeStep)]
        newInput.append(newLine)
      else:
        newInput.append(line)
    return newInput

  def writeNewRestart(self, inputFile, workingDir, restartTimeStep):
    """
      This writes a new input file
      @ In, workingDir, string, workingDir where MELCOR output message in generated
      @ In, inputFile, string, MELCOR input
      @ Out, newInput , file, modified MELCOR input
    """
    newInput = self.changeRestart(inputFile, workingDir, restartTimeStep)
    newFile = open(os.path.join(workingDir, inputFile),"w")
    for line in newInput:
      for words in line:
        newFile.write(str(words) + " ")
      newFile.write('\n')
    newFile.close()

  def restartTimeStep(self, workingDir):  #OK   stoppedCF = {} and tripVariable = 'string'
    """
      @ In, workingDir, string, previous working Directory where .MES file is present
      @ Out, restartInfo, list, container of previous restart time (restartInfo[0]) and restart time step (restartInfo[1])
    """
    
    outputToRead = open(os.path.join(workingDir,self.melcorOutFile),"r")
    tripTime = self.messageReader(workingDir)[1][0]
    Message_frm_line = 0
    restartTimeStep = 0
    for index, line in enumerate(outputToRead, 1):
      line = line.rstrip()
      line = line.split()
      if line[0] == '/SMESSAGE/':
        Message_frm_line = index + 1
      if index == Message_frm_line:
        if line[4] == 'CONTROL':
          break
      if line[0] == 'Restart':
        if float(line[3]) == tripTime:
          break
        #if int(line[5]) > oldValue:
        #  restartTimeStep = int(line[5])
        #  oldValue = int(line[5])
        #  continue
        else:
          restartTimeStep = int(line[5])
          continue
    if restartTimeStep == 0: #if previous .MES file doesn't contain info on last restart, therefore restart info searches in two times (or more) previous working directory
      try:
        restartTimeStep = self.restartTimeStep(workingDir[:-2])
      except:
        print("ERROR in time step. In order to restart MELCOR needs a restart dump written in .MES previous to the trip time step. Integrate the new correction in the MELCOR input")
    outputToRead.close()
    return restartTimeStep

  def restartTime(self, workingDir):  #OK   stoppedCF = {} and tripVariable = 'string'
    """
      @ In, workingDir, string, previous working Directory where .MES file is present
      @ Out, restartInfo, list, container of previous restart time (restartInfo[0]) and restart time step (restartInfo[1])
    """

    outputToRead = open(os.path.join(workingDir,self.melcorOutFile),"r")
    tripTime = self.messageReader(workingDir)[1][0]
    oldValue = 1
    restartTime = 0
    for index, line in enumerate(outputToRead, 1):
      line = line.rstrip()
      line = line.split()
      if line[0] == 'Listing':
        if float(line[3]) == tripTime:
          break
        if int(line[5]) > oldValue:
          restartTime = float(line[3])
          oldValue = int(line[5])
          continue
        else:
          continue
    if restartTime == 0: #if previous .MES file doesn't contain info on last restart, therefore restart info searches in two times (or more) previous working directory
      try:
        restartTime = self.restartTime(workingDir[:-2])
      except:
        print("ERROR in time step. In order to restart MELCOR needs a restart dump written in .MES previous to the trip time step. Integrate the new correction in the MELCOR input")
    restartTime = float (restartTime) + 0.001
    outputToRead.close()
    return restartTime

  def ravenSample (self, inputFile , workingDir , variable):
    """
      @ In, inputFile, string, name of MELCOR input
			@ In, workingDir, string, actual working Directory
			@ In, variable, string, sampled variables without prefix and suffix %
      @ Out, sampledVar, float, corresponding sampling of Raven
    """

    file = open(os.path.join(workingDir,inputFile),"r")
    sampledVar = None
    for index, line in enumerate(file, 1):
      line = line.rstrip()
      line = line.split()
      if self.DetNode == 'olderMelcor':
        if line[0] == '*ravenSample' + variable:
          sampledVar = float(line[1])
          break
      if self.DetNode == 'hackedMelcor':
        if line[0] == '!ravenSample' + variable:
          sampledVar = float(line[1])
          break
    if sampledVar == None:
      raise IOError("Issue with wrong input or wrong sampling")
    return sampledVar

  def dynamicEventTreeForMELCOR(self, **Kwargs):
    """
      This generates a new input file depending on which tripCF are found in messageReader
      @ In, Kwargs, dict, container of different infos
      @ Out, modifDict, dict, container
    """

    modifDict = {}
    deckList = {1:{}}
    workingDir = Kwargs['subDirectory'][:-2]
    modifDict['subDirectory'] = Kwargs['subDirectory']
    #melcorInpFile = melcorCombinedInterface.MelcorApp.melcorInpFile
    if self.Det:
      modifDict['happenedEvent'] = Kwargs['happenedEvent']
      modifDict['excludeTrips'] = []
      modifDict['DETvariables'] = self.detVars
      parentID = Kwargs.get("RAVEN_parentID", "none")
      if parentID.lower() != "none":
        # now we can copy the restart file
        sourcePath = Kwargs['subDirectory'][:-2]
        self.__copyRestartFile(sourcePath, Kwargs['currentPath'])
        # now we can check if the event happened and if so, remove the variable fro the det variable list
        if modifDict['happenedEvent']:
          for var in Kwargs['happenedEventVarHistory']:
            aliased = self._returnAliasedVariable(var, False)
            tripVariable = self.messageReader(workingDir)[0]
            modifDict['excludeTrips'] = var
    for keys in Kwargs['SampledVars']:
      tripVariable = self.messageReader(workingDir)[0]
      if tripVariable not in deckList:
        deckList[tripVariable] = {}
      if tripVariable not in deckList[tripVariable]:
        deckList[tripVariable] = [{'value':Kwargs['SampledVars'][keys]}]
      else:
        deckList[tripVariable].append({'value':Kwargs['SampledVars'][keys]})
    modifDict['decks']=deckList
    return modifDict

  def modifyInput(self, melcorInpFile, workingDir):
    """
      This generates a new input file depending on which tripCF are found in messageReader
      @ In, file, string, MELCOR input file
      @ In, workingDir, string, workingDir where MELCOR output message in generated
      @ Out, newInputForHappenedEvent, list, container of newInputFile to run with changed CF that tripped
      @ Out, newInputForNotHappenedEvent, list, container of newInputFile to run with changed CF that tripped
    """

    workingDir = workingDir[:-2]
    tripVariable = self.messageReader(workingDir)[0]
    restartCycle = int(self.messageReaderCycle(workingDir)[1])
    file = open(os.path.join(workingDir,melcorInpFile),"r")
    newInputForHappenedEvent = []
    newInputForNotHappenedEvent = []
    CF_linechange = -1    #line of the value, of a CF that tripped that needs to be changed
    CF_indexLine_UQ = -1
    #CF_number = 'notfound'
    CF_indexLine = -1     #line of the CF that tripped
    for index, line in enumerate(file, 1):
      line = line.rstrip()
      line = line.split()
      if line[0] == 'CF_ID':
        check = line[1][1:-1]
        if check == tripVariable:
          CF_indexLine = index
          newInputForHappenedEvent.append(line)
          newInputForNotHappenedEvent.append(line)
          continue
        if check == 'EQ_' + tripVariable:
          CF_indexLine_UQ = index + 3
          newInputForHappenedEvent.append(line)
          newInputForNotHappenedEvent.append(line)
          continue
        else:
          newInputForHappenedEvent.append(line)
          newInputForNotHappenedEvent.append(line)
          continue
      if (line[0] == 'CF_ARG' or line[0] == 'CF_FORMULA') and (index - CF_indexLine < 5): #controllare per essere generalizzato
        CF_linechange = index + int(line[1])
        CF_firstValue = index + 1
        newInputForHappenedEvent.append(line)
        newInputForNotHappenedEvent.append(line)
        continue
      if CF_linechange - index >= 0:
        if index == CF_firstValue: #qui cambiamo la variabile nel caso di event happened
          newLine = [line[0], line[1], 0.0] #forse da cambiare posizione di newData
          newInputForHappenedEvent.append(newLine)
          newInputForNotHappenedEvent.append(line)
          CF_linechange = -1
          continue
        #else: #qui cambiamo la variabile nel caso di event NOT happened
        #if index == CF_linechange:        
        #  newLine = [line[0],line[1],'$RAVEN-' + str(tripVariable) + ':-1$']
        #  newInputForHappenedEvent.append(line)
        #  newInputForNotHappenedEvent.append(newLine)
        #  CF_linechange = -1
        #  continue
        if index != CF_firstValue and index != CF_linechange: 
          newInputForHappenedEvent.append(line)
          newInputForNotHappenedEvent.append(line)
          continue
      if index == CF_indexLine_UQ: #controllare per essere generalizzato
        newLine = [line[0],line[1],'$RAVEN-' + str(tripVariable) + ':-1$']
        newInputForHappenedEvent.append(line)
        newInputForNotHappenedEvent.append(newLine)
        #index_UQ = -1
        continue
      if line[0] == 'MEL_RESTARTFILE':
        newLine = [ line[0] , line[1] , line[2] , restartCycle]
        oldLine = [ line[0] , line[1] , line[2] , -1]
        newInputForHappenedEvent.append(oldLine)
        newInputForNotHappenedEvent.append(newLine)
      else:
        newInputForHappenedEvent.append(line)
        newInputForNotHappenedEvent.append(line)
    file.close()
    return newInputForHappenedEvent, newInputForNotHappenedEvent

  def writeNewInput(self, happenedorNot, melcorInpFile, workingDir):
    """
      This writes a new input file depending on what event is described
      @ In, happenedorNot, string, description of whether happenedEvent is True or False
      @ In, workingDir, string, workingDir where MELCOR output message in generated
      @ In, melcorInpFile, string, MELCOR input
      @ Out, newInput , file, modified MELCOR input
    """
    newInputForHappenedEvent = self.modifyInput(melcorInpFile, workingDir)[0]
    newInputForNotHappenedEvent = self.modifyInput(melcorInpFile, workingDir)[1]
    newInput = open(os.path.join(workingDir,melcorInpFile),"w")
    if happenedorNot == 'happenedEvent':
      for line in newInputForHappenedEvent:
        for words in line:
          newInput.write(str(words) + " ")
        newInput.write('\n')
    elif happenedorNot == 'nothappenedEvent':
      for line in newInputForNotHappenedEvent:
        for words in line:
          newInput.write(str(words) + " ")
        newInput.write('\n')
    else:
      raise IOError('ERROR in "MELCOR Code Interface": something is wrong with the writeNewInput')
    newInput.close()
    return newInput

  def messageReader(self, workingDir):  #OK   stoppedCF = {} and tripVariable = 'string'
    """
      This def. reades the MELCOR message output generated after a stop
      @ In, workingDir, string, workingDir where MELCOR output message in generated
      @ Out, stoppedCF , dictonary, container of all tripVariable wt corresponding triptime (stoppedCF[tripVariable][0]) and triptimestep (stoppedCF[tripVariable][1])
      @ Out, tripVariable , string, name of the trip variable
      @ Out, stoppedCF , Dict, container of key (string): tripVariable and value (list): [endTime , endTimeStep]
    """

    outputToRead = open(os.path.join(workingDir,self.melcorOutFile),"r")
    CF_line = -1
    stoppedCF = []
    found = False
    Message_frm_line = 0
    for index, line in enumerate(outputToRead, 1):
      line = line.rstrip()
      line = line.split()
      if self.DetNode == 'olderMelcor':
        if line[0] == '/SMESSAGE/':
          Message_frm_line = index + 1
          CF_line = index + 2
          stoppedCF.append(float(line[2])) #triptime
          stoppedCF.append(int(line[4])) #triptimestep
          continue
        if index == Message_frm_line:
          if line[4] == 'CVH':
            CF_line = -1
            stoppedCF = []
            Message_frm_line = 0
        if index == CF_line:
          try:
            if line[4] != 'CENTRAL':
              tripVariable = line[4]
              return tripVariable, stoppedCF
              break
          except:
            continue
        #if index == timeLine:
        #  try:
        #    stoppedCF.append(float(line[3])) #triptime
        #    stoppedCF.append(int(line[5])) #triptimestep
        #    return tripVariable, stoppedCF
        #    break
        #  except:
        #    stoppedCF.append(float(line[2])) #triptime
        #    stoppedCF.append(int(line[4])) #triptimestep
        #    return tripVariable, stoppedCF
        #    break
        else:
          continue
      else:
        if line[0] == '/SMESSAGE/':
          CF_line = index + 2
          continue
        if index == CF_line:
          try:
            if line[2] == 'CENTRAL':
              found = True
            else:
              tripVariable = line[2]
              #timeLine = index + 6
          except:
            continue
        if line [0] == 'Restart' and found == True:
          stoppedCF.append(float(line[4])) #triptime
          stoppedCF.append(int(line[6])) #triptimestep
          return tripVariable, stoppedCF
          break
        else:
          continue

    outputToRead.close()

  def messageReaderCycle(self, workingDir):  #OK   stoppedCF = {} and tripVariable = 'string'
    """
      This def. reades the MELCOR message output generated after a stop
      @ In, workingDir, string, workingDir where MELCOR output message in generated
      @ Out, stoppedCF , dictonary, container of all tripVariable wt corresponding triptime (stoppedCF[tripVariable][0]) and triptimestep (stoppedCF[tripVariable][1])
      @ Out, tripVariable , string, name of the trip variable
      @ Out, stoppedCF , Dict, container of key (string): tripVariable and value (list): [endTime , endTimeStep]
    """

    outputToRead = open(os.path.join(workingDir,self.melcorOutFile),"r")
    CF_line = -1
    CycleRestart = [ 0 , -1 ] #mettere -1
    for index, line in enumerate(outputToRead, 1):
      line = line.rstrip()
      line = line.split()
      if line[0] == '/SMESSAGE/':
        CF_line = index + 2
        continue
      if index == CF_line:
        try:
          if line[2] == 'CENTRAL':
            return CycleRestart
            break
        except:
          continue
      if line [0] == 'Restart':
        CycleRestart[0] = float(line[4])
        CycleRestart[1] = int(line[6]) #triptimestep
      else:
        continue
    outputToRead.close()
 
  def _writeBranchInfo(self, filename, endTime, endTimeStep, tripVariable):

    """
      Method to write the branchInfo
      @ In, filename, str, the file name
      @ In, endTime, float, the end time
      @ In, endTimeStep, float, the end time step
      @ In, tripVariable, str, the variable that caused the stop of the simulation (trip)
      @ Out, None
    """
    from ..Utilities import dynamicEventTreeUtilities as detUtils
    #tripVar = "%" + str(tripVariable) + "%"
    tripVar = str(tripVariable)
    detUtils.writeXmlForDET(filename,tripVar,[],{'end_time': endTime, 'end_ts': endTimeStep})
    
  def writeDict(self,workDir):
    """
      Output the parsed results into a CSV file
      @ In, workDir, str, current working directory
      @ Out, dictionary, dict, dictioanry containing the data generated by MELCOR
    """
    fileDir = os.path.join(workDir,self.MelcorPlotFile)
    time,data,varUdm = MCRBin(fileDir,self.VarList)
    dfTime = pd.DataFrame(time, columns= ["Time"])
    dfData = pd.DataFrame(data, columns = self.VarList)
    df = pd.concat([dfTime, dfData], axis=1, join='inner')
    df.drop_duplicates(subset="Time",keep='first',inplace=True)
    dictionary = df.to_dict(orient='list')
    return dictionary
    
  def writeCsv(self,filen,workDir):
    """
      Output the parsed results into a CSV file
      @ In, filen, str, the file name of the CSV file
      @ In, workDir, str, current working directory
      @ Out, None
    """
    
    IOcsvfile=open(filen,'w+')
    fileDir = os.path.join(workDir,self.MelcorPlotFile)
    Time,Data,VarUdm = MCRBin(fileDir,self.VarList)
    dfTime = pd.DataFrame(Time, columns= ["Time"])
    dfData = pd.DataFrame(Data, columns = self.VarList)
    df = pd.concat([dfTime, dfData], axis=1, join='inner')
    df.drop_duplicates(subset="Time",keep='first',inplace=True)
    df.to_csv(IOcsvfile,index=False, header=True)

  def finalizeCodeOutput(self,command,output,workingDir):
    """
      This method is called by the RAVEN code at the end of each run (if the method is present, since it is optional).
      In this method the MELCOR outputfile is parsed and a CSV is created
      @ In, command, string, the command used to run the just ended job
      @ In, output, string, the Output name root
      @ In, workingDir, string, current working dir
      @ Out, response, dict, the data dictionary {var1:array,var2:array, etc}
    """
    stop_threads = True
    failure = False
    #failure = self.checkForOutputStop(workingDir)
    response = dict()
    outfile = os.path.join(workingDir,output+'.out')
    #outputobj=MELCORdata.MELCORdata(os.path.join(workingDir,output))
    if failure == False:
      response = self.writeCsv(os.path.join(workingDir,output+'.csv'),workingDir)
      #response = self.writeDict(workingDir)
    if self.Det:
      stopDET = self.stopDET ( workingDir )
      if stopDET == True:
        print("RUN ended successfully!!!!!")
        return response
      tripVariable = self.messageReader(workingDir)[0]
      if tripVariable == 'END_SIMULATION':
        print("RUN ended successfully!!!!!")
      else:
        endTime = self.messageReader(workingDir)[1][0]
        endTimeStep = self.messageReader(workingDir)[1][1]
        filename = os.path.join(workingDir,output+"_actual_branch_info.xml")
        self._writeBranchInfo(filename, endTime, endTimeStep, tripVariable)
    return response

  def checkForOutputFailure(self,output,workingDir):
    """
      This method is called by the RAVEN code at the end of each run  if the return code is == 0.
      This method needs to be implemented by the codes that, if the run fails, return a return code that is 0
      This can happen in those codes that record the failure of the job (e.g. not converged, etc.) as normal termination (returncode == 0)
      This method can be used, for example, to parse the outputfile looking for a special keyword that testifies that a particular job got failed
      (e.g. in RELAP5 would be the keyword "********")
      @ In, output, string, the Output name root
      @ In, workingDir, string, current working dir
      @ Out, failure, bool, True if the job is failed, False otherwise
    """
    failure = True
    goodWord  = "Normal termination"   # This is for MELCOR 2.2 (todo: list for other MELCOR versions)
    try:
      outputToRead = open(os.path.join(workingDir,self.melcorOutFile),"r")
    except FileNotFoundError:
      return failure
    readLines = outputToRead.readlines()
    lastRow = readLines[-1]
    if goodWord in lastRow:
      failure = False
    outputToRead.close()
    return failure

  def __copyRestartFile(self, sourcePath, currentPath, restartFileName = None):
    """
      Copy restart file
      @ In, sourcePath, str, the source path where the restart is at
      @ In, currentPath, str, the current location (where the restart will be copied)
      @ In, restartFileName, str, optional, the restart file name if present (otherwise try to find one to copy in sourcePath)
      @ Out, None
    """
    
    edfFile = []
    for fileToCheck in os.listdir(sourcePath):
      if fileToCheck.strip().endswith(".TXT"):
        edfFile.append(fileToCheck)
    if self.RstFile is None:
      raise IOError("no restart file has been found!" + self.RstFile + " not found!")
    sourceFile = os.path.join(sourcePath, self.RstFile)
    sourceFilePlot = os.path.join(sourcePath, self.MelcorPlotFile)
    sourceFileEdf = []
    for files in edfFile:
      sourceFileEdf.append(os.path.join(sourcePath, files))
    try:
      shutil.copy2(sourceFile, currentPath)
      shutil.copy2(sourceFilePlot, currentPath)
      for files in sourceFileEdf:
        shutil.copy2(files, currentPath)
    except:
      raise IOError('not able to copy restart file from "'+sourceFile+'" to "'+currentPath+'"')

  def __transferMetadata(self, metadataToTransfer, currentPath):
    """
      Method to tranfer metadata if present
      @ In, metadataToTransfer, dict, the metadata to transfer
      @ In currentPath, str, the current working path
      @ Out, None
    """
    if metadataToTransfer is not None:
      sourceID = metadataToTransfer.get("sourceID",None)
      if sourceID is not None:
        # search for restrt file
        sourcePath = os.path.join(currentPath,"../",sourceID)
        self.__copyRestartFile(sourcePath, currentPath)
      else:
        raise IOError('the only metadtaToTransfer that is available in MELCOR is "sourceID". Got instad: '+', '.join(metadataToTransfer.keys()))

  def _findInputFileIndex(self, currentInputFiles):
    """
      Find input file index
      @ In, currentInputFiles, list, list of current input files to search from
      @ Out, index, int, the index of the relap input
    """
    found = False
    for index, inputFile in enumerate(currentInputFiles):
      if inputFile.getExt() in self.getInputExtension():
        found = True
        break
    if not found:
      raise IOError('None of the input files has one of the following extensions: ' + ' '.join(self.getInputExtension()))
    return index

  def _returnAliasedVariable(self, var, fromCodeToRaven = True):
    """
      Return the alias for variable in
      @ In, var, str, the variable the alias should return for
      @ Out, aliasVar, str, the aliased variable if found
    """
    aliasVar = var
    if len(self.inputAliases):
      for ravenVar, codeVar in self.inputAliases.items():
        if fromCodeToRaven:
          if codeVar.strip().startswith(var.strip()):
            aliasVar = ravenVar
            break
        else:
          if ravenVar.strip().startswith(var.strip()):
            aliasVar = codeVar
            break
    return aliasVar