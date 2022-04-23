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
#***************************************
#* Simple analytic test ExternalModule *
#***************************************
#
# Simulates time-dependent track of a projectile through the air from start to 0,
#     assuming no air resistance.
#     Inputs:
#       (x0,y0) - initial position
#       v0 - initial total velocity
#       ang - angle of initial motion, in degrees, with respect to flat ground
#     Outputs:
#       (x,y) - vector positions of projectile in time
#       t - corresponding time steps
#
import numpy as np

in_vars = ['x0', 'y0', 'v0', 'ang', 'timeOption']
out_vars = ['x', 'y', 'r', 't', 'v', 'a']

def prange(v0,th,x0=0,y0=0,g=9.8):
  """
    Calculates the analytic horizontal range.
    @ In, v0, float, initial velocity of the projectile
    @ In, th, float, angle to the ground for initial projectile motion (i.e., firing angle)
    @ In, x0, float, optional, initial horizontal location of firing point
    @ In, y0, float, optional, initial height of firing point
    @ In, g, float, optional, gravitational constant (m/s/s)
    @ Out, prange, float, horizontal range
  """
  return v0**2*np.sin(2*th)/2/g + v0 * np.cos(th)/g * np.sqrt(v0**2 *np.sin(th)**2+2*g*y0)+ x0


def time_to_ground(v0,th,y0=0,g=9.8):
  """
    Calculates the analytic time of flight
    @ In, v0, float, initial velocity of the projectile
    @ In, th, float, angle to the ground for initial projectile motion
    @ In, y0, float, optional, initial height of projectile
    @ In, g, float, optional, gravitational constant (m/s/s)
    @ Out, time_to_ground, float, time projectile is above the ground
  """
  return v0*np.sin(th)/g + np.sqrt(v0**2 * np.sin(th)**2 + 2*g*y0)/g

def x_pos(v0,th,t,x0=0):
  """
    Calculates the x position in time
    @ In, v0, float, initial velocity of the projectile in [m/s]
    @ In, th, float, initial firing angle of the projectile in [radians]
    @ In, t, float, time instance (at which the horizontal position is sought) in [sec]
    @ In, x0, float, initial horizontal position in [m]
    @ Out, x_pos, float, horizontal position at instance t in [m]
  """
  return x0 + v0 * np.cos(th) * t

def y_pos(v0,th,t,y0=0,g=8.8):
  """
    Calculates the analytic vertical position in time
    @ In, v0, float, velocity of the projectile
    @ In, th, float, initial firing angle of the projectile in [radians]
    @ In, t, float, time of flight
    @ In, y0, float, initial vertical position
    @ In, g, float, optional, gravitational constant (m/s/s)
    @ Out, y_pos, float, vertical position
  """
  return y0 + v0 * np.sin(th) * t - 0.5 * g * t**2

def calc_vel(y0, y, v0, ang, g=9.8):
  """
    Calculates the velocity given the current vertical position
    @ In, y0, float, initial vertical position
    @ In, y, float, current vertical position
    @ In, v0, float, initial velocity of the projectile
    @ In, ang, float, firing angle
    @ In, g, float, optional, gravitational constant (m/s/s)
    @ Out, vel, float, total velocity at the given vertical position
    @ Out, x_vel, float, horizontal component of the velocity at any instance
    @ Out, y_vel, float, vertical velocity at the given vertical position
  """
  vel = np.sqrt(v0**2 - 2*g*(y-y0))
  x_vel = v0 * np.cos(ang)
  y_vel = np.sqrt(vel*vel - x_vel*x_vel)
  return x_vel, y_vel, vel

def calc_vel_t(t, v0, ang, g=9.8):
  """
    Calculates the velocity given the current vertical position
    @ In, t, float, time instance at which the velocities are sought
    @ In, v0, float, initial velocity of the projectile
    @ In, ang, float, firing angle
    @ In, g, float, optional, gravitational constant (m/s/s)
    @ Out, vel, float, total velocity at the given vertical position
    @ Out, x_vel, float, horizontal component of the velocity at any instance
    @ Out, y_vel, float, vertical velocity at the given vertical position
  """
  x_vel = v0 * np.cos(ang)
  y_vel = v0 * np.sin(ang) - g * t
  vel = np.sqrt(x_vel**2 + y_vel**2)
  return x_vel, y_vel, vel

def current_angle(v0, ang, vel):
  return np.arccos(v0 * np.cos(ang) / vel)

def run(raven, inputs):
  vars = {'x0': get_from_raven(raven,'x0', 0),
          'y0': get_from_raven(raven,'y0', 0),
          'v0': get_from_raven(raven,'v0', 1),
          'ang': get_from_raven(raven,'angle', 45),
          'timeOption': get_from_raven(raven,'timeOption', 0)}
  res = main(vars)
  raven.x = res['x']
  raven.y = res['y']
  raven.t = res['t']
  raven.r = res['r'] * np.ones(len(raven.x))
  raven.v = res['v']
  raven.a = res['a']
  raven.timeOption = vars['timeOption']

def get_from_raven(raven, attr, default=None):
  return np.squeeze(getattr(raven, attr, default))

def main(Input):
  x0 = Input.get('x0', 0)
  y0 = Input.get('y0', 0)
  v0 = Input.get('v0', 1)
  ang = Input.get('ang', 45)
  g = Input.get('g', 9.8)
  timeOption = Input.get('timeOption', 0)
  ang = ang * np.pi / 180
  if timeOption == 0:
    ts = np.linspace(0,1,10)
  else:
    # due to numpy library update, the return shape of np.linspace
    # is changed when an array-like input is provided, i.e. return from time_to_ground
    ts = np.linspace(0,time_to_ground(v0,ang,y0),10)

  vx0 = np.cos(ang)*v0
  vy0 = np.sin(ang)*v0
  r = prange(v0,ang,y0)

  x = np.zeros(len(ts))
  y = np.zeros(len(ts))
  v = np.zeros(len(ts))
  a = np.zeros(len(ts))
  for i,t in enumerate(ts):
    x[i] = x_pos(x0,vx0,t)
    y[i] = y_pos(y0,vy0,t)
    vx, vy, vm = calc_vel(y0, y[i], v0, ang, g)
    v[i] = vm
    a[i] = current_angle(v0, ang, vm)
  t = ts
  return {'x': x, 'y': y, 'r': r, 't': ts, 'v': v, 'a': a,
    'x0': x0, 'y0': y0, 'v0': v0, 'ang': ang, 'timeOption': timeOption}

#can be used as a code as well
if __name__=="__main__":
  import sys
  inFile = sys.argv[sys.argv.index('-i')+1]
  outFile = sys.argv[sys.argv.index('-o')+1]
  #construct the input
  Input = {}
  for line in open(inFile,'r'):
    arg, val = (a.strip() for a in line.split('='))
    Input[arg] = float(val)
  #run the code
  res = main(Input)
  #write output
  outFile = open(outFile+'.csv','w')
  outFile.writelines(','.join(in_vars) + ',' + ','.join(out_vars) + '\n')
  template = ','.join('{{}}'.format(v) for v in in_vars + out_vars) + '\n'
  print('template:', template)
  for i in range(len(res['t'])):
    this = [(res[v][i] if len(np.shape(res[v])) else res[v]) for v in in_vars + out_vars]
    outFile.writelines(template.format(*this))
  outFile.close()
