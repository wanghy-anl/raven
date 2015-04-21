'''
Created on Apr 20, 2015

@author: talbpaul
'''
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
if not 'xrange' in dir(__builtins__):
  xrange = range
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------
from BaseClasses import BaseType
import platform
import os
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
#Internal Modules End--------------------------------------------------------------------------------

# set a global variable for backend default setting
if platform.system() == 'Windows': disAvail = True
else:
  if os.getenv('DISPLAY'): disAvail = True
  else:                    disAvail = False

class MessageHandler(BaseType):
  '''
  Class for handling messages, warnings, and errors in RAVEN.  One instance of this
  class should be created at the start of the Simulation and propagated through
  the readMoreXML function of the BaseClass.  The utils handlers for raiseAMessage,
  raiseAWarning, raiseAnError, and raiseDebug will access this handler.
  '''
  def __init__(self):
    '''
      Init of class
      @In, None
      @Out, None
    '''
    BaseType.__init__(self)
    self.printTag     = 'MESSAGE HANDLER'
    self.verbosity    = 'all'
    self.suppressErrs = True
    self.verbCode     = {'silent':0, 'quiet':1, 'all':2, 'debug':3}

  def initialize(self,initDict):
    self.verbosity     = initDict['verbosity'   ] if 'verbosity'    in initDict.keys() else 'all'
    self.callerLength  = initDict['callerLength'] if 'callerLength' in initDict.keys() else 25
    self.tagLength     = initDict['tagLength'   ] if 'tagLength'    in initDict.keys() else 15
    self.suppressErrs  = initDict['suppressErrs'] in utils.stringsThatMeanTrue() if 'suppressErrs' in initDict.keys() else True

  def getStringFromCaller(self,obj):
    try: obj.printTag
    except AttributeError: tag = str(obj)
    else: tag = str(obj.printTag)
    return tag
  
  def getDesiredVerbosity(self,caller):
    localVerb = caller.getLocalVerbosity()
    if localVerb == None: localVerb = self.verbosity
    return localVerb

  def checkVerbosity(self,verb):
    if str(verb).strip().lower() not in self.verbCode.keys():
      self.raiseError(self,IOError,'Verbosity key '+str(verb)+' not recognized!  Options are '+str(self.verbCode.keys()))
    return self.verbCode[str(verb).strip().lower()]

  def error(self,caller,etype,message,tag,verbosity):
    verbval = self.checkVerbosity(verbosity)
    okay,msg = _printMessage(caller,message,tag,verbval)
    if okay:
      if not self.suppressErrs: raise etype(msg)
      else: print(msg)

  def message(self,caller,message,tag,verbosity):
    verbval = self.checkVerbosity(verbosity)
    okay,msg = __printMessage(caller,message,tag,verbval)
    if okay: print(msg)

  def _printMessage(self,caller,message,verbval):
    #allows raising standardized messages
    ctag = self.getStringFromCaller(caller)
    shouldIPrint = False
    if verbval <= self.getDesiredVerbosity(caller): shouldIPrint=True
    msg=self.stdMessage(ctag,tag,message)
    return shouldIPrint,msg

  def stdMessage(self,pre,tag,post):
    msg = ''
    msg+=pre.ljust(self.callerLength)[0:self.callerLength] + ': '
    msg+=tag.ljust(self.tagLength)[0:self.tagLength]+' -> '
    msg+=post
    return msg
