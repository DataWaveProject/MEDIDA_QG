from ModelErrorQGarg import ModelErrorQGarg

import os
#try:
# dirsys = '/home/rm99/Mount/jetstream_volume/ModelErrorQGrff_localcopy_endpoint_interp2_newcasev3'
dirsys = '/media/rmojgani/hdd/PostDoc/Projects/test/ModelErrorQGrff_localcopy_endpoint_interp2_newcasev3'
os.chdir(dirsys)
#except:
#print('nochangedir')

args = ModelErrorQGarg()
locals().update(vars(args))
print(args)

IF_TEST_NONOISE = False
if IF_TEST_NONOISE:
    NOISE_MAG = 0.0
    CASE_NO = 1003
    KEEP_RATIO = 1.0 # Spectral filter
    SENSOR_RATIO = 0.95 #1.0
    NOISE_MAG = 0.0
    RFF_SIGMA = 1.0
    # RFF_SIGMA1 = 0.75
    # RFF_SIGMA2 = 1.0
    GAMMA_DIFF=0.00
    GAMMA_LAPL=0.00
    NUM_EPOCHS_ADAM = 200124 #60123#52310
    DEEP = 5

from myfilters import plotfft
#mylabel = 'interp2';
from smoothplot import myplot2
ENDPOINT=False

interp_type = 'griddata' #['rbf', 'griddata', 'mlp']
mylabel = interp_type

# 'rbf' : multiquadric:
if interp_type == 'rbf':
    EPSILON = 0.10
    from scipy.interpolate import Rbf
    rbf_function = 'multiquadric' #['multiquadric': sqrt((r/self.epsilon)**2 + 1),
                                  # 'linear': ,
                                  # 'gaussian': ]
#     from scipy.interpolate import RBFInterpolator as Rbf
elif interp_type == 'griddata':
    from scipy.interpolate import griddata
    interp2d_kind ='cubic'# ['linear', 'cubic']

#%% Settings
# IF_TRAIN_IC, IF_TRAIN_R = True, True
# IF_ANIMATION = False
# IF_LOCAL = False
# IF_SAVEMAT = True
# IF_LOADNET1 = False
# IF_LOADNET2 = False
#%% TO POST
IF_TRAIN_IC, IF_TRAIN_R = False, False
IF_ANIMATION = False
IF_LOCAL = True
IF_SAVEMAT = False
IF_LOADNET1 = True
IF_LOADNET2 = True
#%% Import libraries and path
import numpy as np
# import matplotlib
# matplotlib.use('Agg')
import matplotlib.pylab as plt
plt.rcParams['image.cmap'] = 'bwr_r'
from random import random
#import netCDF4 as nc4
#from saveNCfileQG import savenc
from scipy.io import savemat
import sys
#sys.path.insert(1, '/util/')
#sys.path.insert(1, 'util')
# sys.path.insert(1, '/mnt/hdd/PostDoc/Projects/Closure_Discovery/experiments/case2')
# sys.path.insert(1, '/mnt/hdd/PostDoc/Projects/Closure_Discovery/util')
from rvm_util import rvm_add_noise
from rvm import RVR
import torch
from myfilters import smoother
#%% Declare parameters, arrays, etc.
IF_jac = 'NA'
c_non_linear = 1.0
#
opt = 3 # 1 = just the linear parts, 2 = just the nonlinear parts, 3 = full model

N  = 96  #zonal size of spectral decomposition
N2 = 192 #meridional size of spectral decomposition
Lx = 46. #size of x -- stick to multiples of 10
Ly = 68. #size of y -- stick to multiples of 10

BOUNDARY_CUT = 30
SPIN_UP = int(10e3)#int(60e3)#int(60e3)# spin up time is : 60k*dt, for dt = 0.025  int(1e3)#
#%% Cut and vectorize definition
def cutandvectorize(m, BOUNDARY_CUT):
    N0, N1 = m.shape
    m = m[BOUNDARY_CUT:-BOUNDARY_CUT,BOUNDARY_CUT:-BOUNDARY_CUT]
    m = m.reshape( (N0-2*BOUNDARY_CUT)*(N1-2*BOUNDARY_CUT))
    return m
#%% Initialize problem
from QGlib_v2 import case_select
g = 0.04 #leapfrog filter coefficient
U_1 = 1.
x = np.linspace( -Lx / 2, Lx / 2, N , endpoint=ENDPOINT)
y = np.linspace( -Ly / 2, Ly / 2, N2, endpoint=ENDPOINT)

xx, yy = np.meshgrid(x, y)

CONSTANTS_r, topographicPV_ref  , x_mountain_r, y_mountain_r, H_r,\
CONSTANTS_m, topographicPV_model, x_mountain_m, y_mountain_m, H_m,\
sigma, beta, sx, sy =\
case_select( CASE_NO, CASE_NO_R, xx, yy)

c_me_jac_r = CONSTANTS_r['c_me_jac']
c_me_jac_m = CONSTANTS_m['c_me_jac']
vmin, vmax = -max(H_r), max(H_r)
#%% Initialize solver
from QGlib import operator_gen
kk, ll, Grad, Lapl, Grad8, D_Dx, D_Dy = operator_gen(N, Lx, N2, Ly)

dt = 0.025 #Timestep
ts = int(SPIN_UP*2) # Total timesteps
tot_time = dt*ts    # Length of run
lim = int(SPIN_UP ) # Start saving
st = int( 1. / dt ) # How often to save data
#######################################################
#  Define equilibrium interface height + sponge

sponge = np.zeros( N2)
u_eq = np.zeros( N2)

for i in range( N2 ):
	y1 = float( i - N2 /2) * (y[1] - y[0] )
	y2 = float(min(i, N2 -i - 1)) * (y[1] - y[0] )
	sponge[i] = U_1 / (np.cosh(abs(y2/sigma)))**2
	u_eq[i] = U_1 * ( 1. / (np.cosh(abs(y1/sigma)))**2 - 1. / (np.cosh(abs(y2/sigma)))**2  )

psi_Rc = -np.fft.fft( u_eq ) / 1.j / ll
psi_Rc[0] = 0.
psi_R = np.fft.ifft( psi_Rc )

from QGlib import QGinitialize, QGinitialize2, QGinitialize3
from QGlib import my_load
from QGlib import initialize_psi_to_param
from QGloop_v2 import QGloop

psic_1, psic_2, vorc_1, vorc_2, q_1, q_2, qc_1, qc_2, psi_1, psi_2 =\
    QGinitialize(N, N2, ll, kk, Lapl, CONSTANTS_r['beta'], y, topographicPV_ref)
pv, psiAll, Uall, Vall = QGinitialize2(N, N2, ts, lim, st)
#%% File names
import time
file_name_spunup = str(0000)+CASE_NO_R+'_'+str(IF_jac)#CASE_NO
file_name_spunup = file_name_spunup+"pv_spun"+str(SPIN_UP)
file_r =  file_name_spunup+"pvr"
file_m =  file_name_spunup+"pvm"
file_name_anim = file_name_spunup+"psci.mp4"
#%% Run\load reference baseline
print('File name:', file_name_spunup)
try:
    # pv_M, q_1_M, q_2_M, qc_1_M, qc_2_M, vorc_1_M, vorc_2_M,\
    #             psi_1_M, psi_2_M, psic_1_M, psic_2_M = my_load(file_name_spunup)


    # pv_M, q_1_M, q_2_M, qc_1_M, qc_2_M, vorc_1_M, vorc_2_M,\
    #             psi_1_M, psi_2_M, psic_1_M, psic_2_M = my_load('/mnt/hdd/PostDoc/Projects/v3/'+file_name_spunup)

    # pv_M, q_1_M, q_2_M, qc_1_M, qc_2_M, vorc_1_M, vorc_2_M,\
    #             psi_1_M, psi_2_M, psic_1_M, psic_2_M = my_load('/mnt/hdd/PostDoc/Projects/'+file_name_spunup)
    pv_M, q_1_M, q_2_M, qc_1_M, qc_2_M, vorc_1_M, vorc_2_M,\
                psi_1_M, psi_2_M, psic_1_M, psic_2_M = my_load('/media/rmojgani/hdd/PostDoc/Projects/test/ModelErrorQGrff_localcopy_endpoint_interp2_newcasev3/'+file_name_spunup)
    if IF_LOCAL:
        plt.figure(figsize=(10,2.5))
        plt.subplot(1,3,1)
        plt.pcolor(q_1_M[0,:,:,-1],vmin=-8,vmax=8);plt.colorbar()
        plt.title(r'$q_1$')
        plt.subplot(1,3,2)
        plt.pcolor(psi_1_M[0,:,:,-1]);plt.colorbar()
        plt.title(r'$\psi_1$')
        plt.show()

except:
    tic = time.time()
    #Timestepping:
    pv, Uall, Vall, psiAll,\
            vorc_1, vorc_2,\
            q_1   , q_2   ,\
            qc_1  , qc_2  ,\
            psic_1, psic_2,\
            psi_1, psi_2   \
            = QGloop(ts, kk, ll, D_Dx, D_Dy, Grad, Lapl, Grad8,
                                   psic_1, vorc_1,
                                   psic_2, vorc_2,
                                   psi_1, psi_2, psi_R, CONSTANTS_r,
                                   sponge, q_1, q_2,
                                   topographicPV_ref,
                                   qc_1, qc_2,
                                   dt, y, g,
                                   opt,lim,st,
                                   pv, psiAll, Uall, Vall,
                                   c_me_jac_r)#,1.0)

    mdic = {"pv": pv       ,
            'q_1': q_1     , 'q_2': q_2,
            'qc_1': qc_1   , 'qc_2': qc_2,
            'vorc_1':vorc_1, 'vorc_2':vorc_2,
            'psic_1':psic_1, 'psic_2':psic_2,
            'psi_1':psi_1  , 'psi_2':psi_2   }

    savemat(file_name_spunup+".mat", mdic)
    toc = time.time()
    print('Elased time: %.2f min' %((toc-tic)/60) )

    if IF_LOCAL:
        plt.figure(figsize=(10,2.5))
        plt.subplot(1,3,1)
        plt.pcolor(q_1[0,:,:,-1],vmin=-8,vmax=8);plt.colorbar()
        plt.subplot(1,3,2)
        plt.pcolor(psi_1[0,:,:,-1]);plt.colorbar()
        plt.show()
#%% Save animation
# from QGlib import record_anim
# record_anim(file_name_anim, q_1_M, psi_1_M, q_2_M, psi_2_M ) if IF_ANIMATION else print('No Animation created')
#%%
#dt = 0.025 #Timestep
ts = 1              # Total timesteps
tot_time = dt*ts    # Length of run
lim = 1             # Start saving
st = 1             # How often to save data
print( (ts+1 - lim) // st)
for i in range( 0, ts+1 ):
    print(i,':', i >= lim and i % st == 0)
#%%
from QGlib_v2 import psi_lib
#%%
XXt   = np.array([])   # XX
XXjac = np.array([])   # XXjac

from untitled0 import XXlib_gen, XXjac_gen
#%% EnKF: Run and save reference + model
len_ = LEN_LOOP# psi_1_M.shape[-1]#
loop_range = range(len_) #  range(len_), [len_-1],

dq1 = np.array([])
dq2 = np.array([])
jj1 = 0  #0 working
jj = jj1

vorc_1_r_all, vorc_2_r_all, q_1_r_all, q_2_r_all, qc_1_r_all, qc_2_r_all,\
psic_1_r_all, psic_2_r_all, psi_1_r_all, psi_2_r_all =\
QGinitialize3(N2, N, 49, len_)

vorc_1_m_all, vorc_2_m_all, q_1_m_all, q_2_m_all, qc_1_m_all, qc_2_m_all,\
psic_1_m_all, psic_2_m_all, psi_1_m_all, psi_2_m_all =\
QGinitialize3(N2, N, 49, len_)

pvr, psiAllr, Uallr, Vallr = QGinitialize2(N, N2, ts, lim, st)
pvm, psiAllm, Uallm, Vallm = QGinitialize2(N, N2, ts, lim, st)
#%%
folder_path='save/rff/'+'H'+str(HIDDEN)+'/'

# file_name = str(CASE_NO)+CASE_NO_R+'_D'+str(DEEP)+'_RVM_NOISE_MAG='+str(NOISE_MAG)+'_N_ENS='+str(0)+'_sr'+str(SENSOR_RATIO)+'_len'+str(len_)+'ADAM'+str(NUM_EPOCHS_ADAM)+\
#     '_RFFs'+str(RFF_SIGMA)

file_name = str(CASE_NO)+CASE_NO_R+'_D'+str(DEEP)+'_RVM_NOISE_MAG='+str(NOISE_MAG)+\
    '_N_ENS='+str(0)+'_sr'+str(SENSOR_RATIO)+'_len'+str(len_)+'ADAM'+str(NUM_EPOCHS_ADAM)+\
    '_LAMBDAREG'+str(LAMBDA_REG)+'_RFFs'+str(RFF_SIGMA)
# file_name1 = str(CASE_NO)+CASE_NO_R+'_D'+str(DEEP)+'_RVM_NOISE_MAG='+str(NOISE_MAG)+\
#     '_N_ENS='+str(0)+'_sr'+str(SENSOR_RATIO)+'_len'+str(len_)+'ADAM'+str(NUM_EPOCHS_ADAM)+\
#     '_LAMBDAREG'+str(LAMBDA_REG)+'_RFFs'+str(RFF_SIGMA1)
# file_name2 = str(CASE_NO)+CASE_NO_R+'_D'+str(DEEP)+'_RVM_NOISE_MAG='+str(NOISE_MAG)+\
#     '_N_ENS='+str(0)+'_sr'+str(SENSOR_RATIO)+'_len'+str(len_)+'ADAM'+str(NUM_EPOCHS_ADAM)+\
#     '_LAMBDAREG'+str(LAMBDA_REG)+'_RFFs'+str(RFF_SIGMA2)
myiter = '_contd200123'#'_iter4'#'_iter4'#_iter4

# file_name = file_name + '_Gdiff' +str(GAMMA_DIFF) + '_Glapl' + str(GAMMA_LAPL)

from pathlib import Path
Path(folder_path).mkdir(parents=True, exist_ok=True)

folder_path_load='save/rff/'+'H'+str(HIDDEN)+'/'
file_name_load = file_name


try:
    checkpoint = torch.load(folder_path_load+file_name_load+myiter+'.pth')
    # checkpoint1 = torch.load(folder_path_load+file_name1+myiter+'.pth')
    # checkpoint2 = torch.load(folder_path_load+file_name2+myiter+'.pth')

except:
    print('no checkpoint')

# from mynet2D import Net

if interp_type =='mlp':
    from init_net import init_net
else:
    from init_interp2 import init_net

#Timestepping:
for n in loop_range:
    print('tcount: ', n)
    i_save = n
    SENSOR_RATIO = 0.7
    xx_torch, yy_torch, x_train, y_train, scale, ix, iy, ind_unmask =\
        init_net(SENSOR_RATIO, N, N2, D_Dx, D_Dy, Lx, Ly)
    #%%
    #----------------------------------
    # Initialize                      |REVISION: [jj1 and jj2 ]
    #----------------------------------
    psi_1 , psi_2  = psi_1_M[jj1,:,:,n].copy() , psi_2_M[jj1,:,:,n].copy()
    #%%
    import matplotlib.patches as patches
    DPI = 250
    plt.rcParams['figure.dpi'] = DPI
    plt.rcParams.update({
        'font.size': 10,
        'text.usetex': True,
        'text.latex.preamble': r'\usepackage{amsfonts}'
    })
#%%
    arr = psi_1
    mask = np.ones_like(arr, dtype=bool)
    mask.flat[ind_unmask] = False
    masked_arr =np.ma.masked_where(mask, arr)
    unmasked_arr =np.ma.masked_where(~mask, arr)

    fig = plt.figure(figsize=(10,2.5),dpi=250)

    ax = plt.subplot(1,3,1)
    plt.contourf(xx,yy, masked_arr)
    # plt.scatter(xx,yy, s=~mask*0.1, marker='+', c="black",lw=0)
    # plt.scatter(xx,yy, s=mask*0.1, marker='o', c="black",lw=0)

    rect = patches.Rectangle((-5, -5), 10, 10, linewidth=3, edgecolor='k', facecolor='none')
    ax.add_patch(rect)

    plt.ylim([-20,20])
    plt.tight_layout()

    ax.set_aspect('equal', 'box')

    ax = plt.subplot(1,3,2)

    plt.pcolor(xx,yy, masked_arr)
    plt.scatter(xx,yy, s=mask*5, marker='o', c="white",ec='black',lw=0.5)
    plt.scatter(xx,yy, s=~mask*5, marker='o', c="black",lw=0)

    plt.xlim([-5,5])
    plt.ylim([-5,5])

    ax.set_aspect('equal', 'box')
    # plt.tight_layout()

    ax.axes.xaxis.set_ticklabels([])
    ax.axes.yaxis.set_ticklabels([])
    ax.set_xticks([])
    ax.set_yticks([])


    ax2 = plt.subplot(1,3,3)

    ax2.pcolor(xx,yy, unmasked_arr)
    plt.scatter(xx,yy, s=mask*5, marker='o', c=unmasked_arr,ec='black',lw=0.5)
    plt.scatter(xx,yy, s=~mask*5, marker='o', c="black",lw=0)

    plt.xlim([-5,5])
    plt.ylim([-5,5])

    ax2.set_aspect('equal', 'box')

    ax2.axes.xaxis.set_ticklabels([])
    ax2.axes.yaxis.set_ticklabels([])
    ax2.set_xticks([])
    ax2.set_yticks([])

    plt.tight_layout()




    fig.savefig("xxxa.png", dpi=350)

    #%%
    fig = plt.figure(figsize=(10,2.5),dpi=250)
    ax2 = plt.subplot(1,3,3)

    ax2.pcolor(xx,yy, arr)
    plt.scatter(xx,yy, s=mask*5, marker='o', c=unmasked_arr,ec='black',lw=0.5)
    plt.scatter(xx,yy, s=~mask*5, marker='o', c="black",lw=0)

    plt.xlim([-5,5])
    plt.ylim([-5,5])

    ax2.set_aspect('equal', 'box')

    ax2.axes.xaxis.set_ticklabels([])
    ax2.axes.yaxis.set_ticklabels([])
    ax2.set_xticks([])
    ax2.set_yticks([])

    plt.tight_layout()

    fig.savefig("xxxb.png", dpi=350)

    #%%
    stop
    psic_1, psic_2,\
    vorc_1, vorc_2,\
    q_1   , q_2,\
    qc_1  , qc_2 =\
    initialize_psi_to_param(psi_1, psi_2,\
                            N2, N, beta, Lapl, y, topographicPV_ref)

    psi_1 = np.array((psi_1,psi_1,0*psi_1))
    psi_2 = np.array((psi_2,psi_2,0*psi_2))

    psic_1 = np.array((psic_1,psic_1,0*psic_1))
    psic_2 = np.array((psic_2,psic_2,0*psic_2))
    vorc_1 = np.array((vorc_1,vorc_1,0*vorc_1))
    vorc_2 = np.array((vorc_2,vorc_2,0*vorc_2))
    q_1 = np.array((q_1,q_1,0*q_1))
    q_2 = np.array((q_2,q_2,0*q_2))
    qc_1 = np.array((qc_1,qc_1,0*qc_1))
    qc_2 = np.array((qc_2,qc_2,0*qc_2))
    #%%
    #----------------------------------------------
    # Evolve the system (reference), IC: unmasked |
    #----------------------------------------------
    _, _, _, _,_, _, _, _, _, _, _, _,\
    psi_1_r, psi_2_r  = QGloop(ts, kk, ll, D_Dx, D_Dy, Grad, Lapl, Grad8,
                                psic_1, vorc_1, psic_2, vorc_2,
                                psi_1, psi_2, psi_R, CONSTANTS_r,
                                sponge, q_1, q_2,
                                topographicPV_ref,
                                qc_1, qc_2,
                                dt, y, g,
                                opt,lim,st ,
                                pvm, psiAllm, Uallm, Vallm,
                                c_me_jac_r)#, 1.0)
    #%% Masking the IC to evolve the model and construct dq vector
    psi_1 , psi_2  = psi_1_M[jj1,:,:,n].copy() , psi_2_M[jj1,:,:,n].copy()
    import scipy as sp

    if IF_TRAIN_IC:
        print('Train IC network ... ')

        psi_1 += np.random.normal(0,NOISE_MAG*np.std(psi_1),psi_1.shape)
        psi_2 += np.random.normal(0,NOISE_MAG*np.std(psi_2),psi_1.shape)

        w1 = psi_1[iy,:][:,ix].reshape(-1,1)[ind_unmask]
        w2 = psi_2[iy,:][:,ix].reshape(-1,1)[ind_unmask]

        if interp_type =='mlp':
            w = np.concatenate((w1,w2),axis=1)
            w = torch.from_numpy(w).float()
            w = torch.tensor(w,requires_grad=True)

            net11 = Net(HIDDEN, DEEP, LAMBDA_REG, LOSS_FFT_CUT, RFF_SIGMA).cuda()
            net11.optimize_ADAM(x_train, y_train, w, 0,\
                                NUM_EPOCHS_ADAM, LR0, GAMMA_DIFF, GAMMA_LAPL)#ind_unmask

            psi_1020 = net11.forward(xx_torch.cuda(), yy_torch.cuda() )
            # MLP Interpolated data from the masked data
            psi_10 = psi_1020.detach().cpu().numpy()[:,0].reshape(N2,N)
            psi_20 = psi_1020.detach().cpu().numpy()[:,1].reshape(N2,N)
            print('IC network Trained.')

            # tck1 = sp.interpolate.bisplrep(x_train, y_train, w1, s=0)
            # tck2 = sp.interpolate.bisplrep(x_train, y_train, w2, s=0)

            # psi_10 = sp.interpolate.bisplev(xx_torch, yy_torch, tck1)
            # psi_20 = sp.interpolate.bisplev(xx_torch, yy_torch, tck2)
        #%% Radial Basis
        elif interp_type =='rbf':
            rbf1 = Rbf(x_train, y_train, w1, epsilon=EPSILON, function=rbf_function)
            rbf2 = Rbf(x_train, y_train, w2, epsilon=EPSILON, function=rbf_function)
            psi_10 = rbf1(xx_torch, yy_torch).reshape(N2,N)
            psi_20 = rbf2(xx_torch, yy_torch).reshape(N2,N)
        #%% Interp2d
        # f1 = sp.interpolate.interp2d(x_train, y_train, w1, kind=interp2d_kind)
        # f2 = sp.interpolate.interp2d(x_train, y_train, w2, kind=interp2d_kind)
        # psi_10 = f1(x, y)
        # psi_20 = f2(x, y)
        #%%
        elif interp_type=='griddata':
            points = np.stack([x_train,y_train],axis=1).reshape(-1,2)
            # psi_10 = griddata(points, w1, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method=interp2d_kind, fill_value=0).reshape(N2,N)

            psi_10_z0 = griddata(points, w1, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method='nearest')
            psi_10_z1 = griddata(points, w1, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method=interp2d_kind)
            psi_10_z1[np.isnan(psi_10_z1)] = psi_10_z0[np.isnan(psi_10_z1)]
            psi_10 = psi_10_z1[:,:,0]
            # plt.pcolor(psi_10_z1.reshape(N2,N))
            # stop
            # psi_20 = griddata(points, w2, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method=interp2d_kind, fill_value=0).reshape(N2,N)

            psi_20_z0 = griddata(points, w2, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method='nearest')
            psi_20_z1 = griddata(points, w2, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method=interp2d_kind)
            psi_20_z1[np.isnan(psi_20_z1)] = psi_20_z0[np.isnan(psi_20_z1)]
            psi_20 = psi_20_z1[:,:,0]

    else:
        #%%
        if IF_LOADNET1:
            print('Load IC network ... ')

            net11 = Net(HIDDEN, DEEP, LAMBDA_REG, LOSS_FFT_CUT, RFF_SIGMA).cuda()
            net11.load_state_dict(checkpoint['model11_state_dict'])
            psi_1020 = net11.forward(xx_torch.cuda(), yy_torch.cuda() )
            # Interpolated data from the masked data
            psi_10 = psi_1020.detach().cpu().numpy()[:,0].reshape(N2,N)
            psi_20 = psi_1020.detach().cpu().numpy()[:,1].reshape(N2,N)
            del net11
            torch.cuda.empty_cache()

            # Debug tester
            # psi_10 = psi_1
            # psi_20 = psi_2
            print('IC network loaded.')
        else:
            psi_10 = psi_1
            psi_20 = psi_2
            print('Exact IC copied.')

        from smoothplot import myplot2
        #%%
        if KEEP_RATIO != 1.0:
            psi_10 = smoother(psi_10, KEEP_RATIO)
            psi_20 = smoother(psi_20, KEEP_RATIO)
            print('filtered')

    if IF_LOCAL:
        mylabel = str(LAMBDA_REG)
        plotfft(psi_1, psi_10, r'$\psi_{1}$,'+mylabel+r' $\sigma_r=$'+str(RFF_SIGMA))
        plotfft(psi_2, psi_20, r'$\psi_{2}$,'+mylabel+r' $\sigma_r=$'+str(RFF_SIGMA))
        myplot2(psi_10,psi_1,label=mylabel, IF_SAVE=False)
        myplot2(psi_20,psi_2,label=mylabel, IF_SAVE=False)

    # stop
    #%%
    # =========================================================================
    #----------------------------------
    # Forwarding the model            |
    #----------------------------------
    psic_1, psic_2,\
    vorc_1, vorc_2,\
    q_1   , q_2,\
    qc_1  , qc_2 =\
    initialize_psi_to_param(psi_10, psi_20,\
                                N2, N, beta, Lapl, y, topographicPV_model)

    psi_1 = np.array((psi_10,psi_10,0*psi_10))
    psi_2 = np.array((psi_20,psi_20,0*psi_20))

    psic_1 = np.array((psic_1,psic_1,0*psic_1))
    psic_2 = np.array((psic_2,psic_2,0*psic_2))
    vorc_1 = np.array((vorc_1,vorc_1,0*vorc_1))
    vorc_2 = np.array((vorc_2,vorc_2,0*vorc_2))
    q_1 = np.array((q_1,q_1,0*q_1))
    q_2 = np.array((q_2,q_2,0*q_2))
    qc_1 = np.array((qc_1,qc_1,0*qc_1))
    qc_2 = np.array((qc_2,qc_2,0*qc_2))
    #%%
    _, _, _, _,_, _, _, _, _, _, _, _,\
    psi_1_m, psi_2_m  = QGloop(ts, kk, ll, D_Dx, D_Dy, Grad, Lapl, Grad8,
                                psic_1, vorc_1, psic_2, vorc_2,
                                psi_1, psi_2, psi_R, CONSTANTS_m,
                                sponge, q_1, q_2,
                                topographicPV_model,
                                qc_1, qc_2,
                                dt, y, g,
                                opt,lim,st ,
                                pvm, psiAllm, Uallm, Vallm,
                                c_me_jac_m)#, c_me_jac_m)
    #%% Estimation of state from IC using the model
    _, _, _, _, q_1_m , q_2_m, _, _ =\
    initialize_psi_to_param(psi_1_m[jj1,:,:,0], psi_2_m[jj1,:,:,0],\
                                N2, N, beta, Lapl, y, topographicPV_model)
    #%% Mask the observation data (emulation of sensor mask)
    psi_1_r =  psi_1_r[0,:,:,0]
    psi_2_r =  psi_2_r[0,:,:,0]
    ###%%
    if IF_TRAIN_R:
        print('Train second time step network ... ')

        psi_10_r = psi_1_r+np.random.normal(0,NOISE_MAG*np.std(psi_1_r),psi_1_r.shape)
        psi_20_r = psi_2_r+np.random.normal(0,NOISE_MAG*np.std(psi_2_r),psi_2_r.shape)

        w1 = psi_10_r[iy,:][:,ix].reshape(-1,1)[ind_unmask]
        w2 = psi_20_r[iy,:][:,ix].reshape(-1,1)[ind_unmask]

        if interp_type =='mlp':
            w = np.concatenate((w1,w2),axis=1)
            w = torch.from_numpy(w).float()
            w = torch.tensor(w,requires_grad=True)

            net22 = Net(HIDDEN, DEEP, LAMBDA_REG, LOSS_FFT_CUT, RFF_SIGMA).cuda()
            net22.optimize_ADAM(x_train, y_train, w, 0, NUM_EPOCHS_ADAM, LR0, GAMMA_DIFF, GAMMA_LAPL)#ind_unmask

            psi_1020 = net22.forward(xx_torch.cuda(), yy_torch.cuda() )
            psi_10 = psi_1020.detach().cpu().numpy()[:,0].reshape(N2,N)
            psi_20 = psi_1020.detach().cpu().numpy()[:,1].reshape(N2,N)

            torch.save({
                        'model11_state_dict': net11.state_dict(),
                        'model22_state_dict': net22.state_dict()
                        }, folder_path+file_name+'.pth')
            print('first and second time step networks saved.')
        #%%
        elif interp_type =='rbf':
            rbf1 = Rbf(x_train, y_train, w1, epsilon=EPSILON, function=rbf_function)
            rbf2 = Rbf(x_train, y_train, w2, epsilon=EPSILON, function=rbf_function)
            psi_10 = rbf1(xx_torch, yy_torch).reshape(N2,N)
            psi_20 = rbf2(xx_torch, yy_torch).reshape(N2,N)
        #%%
        # f1 = sp.interpolate.interp2d(x_train, y_train, w1, kind=interp2d_kind)
        # f2 = sp.interpolate.interp2d(x_train, y_train, w2, kind=interp2d_kind)
        # psi_10 = f1(x, y)
        # psi_20 = f2(x, y)
        elif interp_type=='griddata':
            points = np.stack([x_train,y_train],axis=1).reshape(-1,2)
            # psi_10 = griddata(points, w1, (xx_torch.reshape(N2,N)  , yy_torch.reshape(N2,N)  ), method=interp2d_kind, fill_value=0).reshape(N2,N)

            psi_10_z0 = griddata(points, w1, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method='nearest')
            psi_10_z1 = griddata(points, w1, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method=interp2d_kind)
            psi_10_z1[np.isnan(psi_10_z1)] = psi_10_z0[np.isnan(psi_10_z1)]
            psi_10 = psi_10_z1[:,:,0]

            # psi_20 = griddata(points, w2, (xx_torch.reshape(N2,N)  , yy_torch.reshape(N2,N)  ), method=interp2d_kind, fill_value=0).reshape(N2,N)
            psi_20_z0 = griddata(points, w2, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method='nearest')
            psi_20_z1 = griddata(points, w2, (xx_torch.reshape(N2,N), yy_torch.reshape(N2,N)), method=interp2d_kind)
            psi_20_z1[np.isnan(psi_20_z1)] = psi_20_z0[np.isnan(psi_20_z1)]
            psi_20 = psi_20_z1[:,:,0]

        print('second time step network trained.')
    else:
        #%%
        if IF_LOADNET2:
            print('Load second time step network ... ')

            net22 = Net(HIDDEN, DEEP).cuda()
            net22.load_state_dict(checkpoint['model22_state_dict'])
            psi_1020 = net22.forward(xx_torch.cuda(), yy_torch.cuda() )
            # Interpolated data from the masked data
            psi_10 = psi_1020.detach().cpu().numpy()[:,0].reshape(N2,N)
            psi_20 = psi_1020.detach().cpu().numpy()[:,1].reshape(N2,N)
            if KEEP_RATIO != 1.0:
                psi_10 = smoother(psi_10, KEEP_RATIO)
                psi_20 = smoother(psi_20, KEEP_RATIO)

            # Debug tester
            # psi_10 = psi_1_r
            # psi_20 = psi_2_r
            print('second time step network loaded.')

        else:
            psi_10 = psi_1_r
            psi_20 = psi_2_r
            print('Exact next time step copied.')

        if KEEP_RATIO != 1.0:
            psi_10 = smoother(psi_10, KEEP_RATIO)
            psi_20 = smoother(psi_20, KEEP_RATIO)

            print('filtered')

    if IF_LOCAL:
        plotfft(psi_1_r, psi_10, r'$\psi_{1}$,'+mylabel)
        plotfft(psi_2_r, psi_20, r'$\psi_{2}$,'+mylabel)
        myplot2(psi_10,psi_1_r,label=mylabel+r' $\sigma_r=$'+str(RFF_SIGMA), IF_SAVE=False)
        myplot2(psi_20,psi_2_r,label=mylabel+r' $\sigma_r=$'+str(RFF_SIGMA), IF_SAVE=False)
    #%%
    _, _, _, _, q_1_r , q_2_r, _, _ =\
    initialize_psi_to_param(psi_10, psi_20,\
                                N2, N, beta, Lapl, y, topographicPV_ref)
    #%%
    #--------------------------------------------------------------------------
    # Build cost function (1/tot_time) * ( q_1_r[jj1,:,:,n]-  q_1_m[jj1,:,:,n] )
    #-------------------
    # q_1_r = smoother(q_1_r,KEEP_RATIO)
    # q_2_r = smoother(q_2_r,KEEP_RATIO)
    # q_1_m = smoother(q_1_m,KEEP_RATIO)
    # q_2_m = smoother(q_2_m,KEEP_RATIO)


    dq1M = (1/tot_time) * ( q_1_r -  q_1_m )# to check the 0th index
    dq1n = cutandvectorize(dq1M, BOUNDARY_CUT)
    dq1 = np.hstack((dq1,dq1n))

    dq2M = (1/tot_time) * ( q_2_r -  q_2_m )# to check the 0th index
    dq2n = cutandvectorize(dq2M, BOUNDARY_CUT)
    dq2 = np.hstack((dq2,dq2n))

    X_labels, XX_2D = psi_lib(N2, N,
                                Grad  , Lapl  , Grad8,
                                D_Dx  , D_Dy  ,
                                psic_1[jj1,:,:], psic_2[jj1,:,:], psi_R,
                                vorc_1[jj1,:,:], vorc_2[jj1,:,:],
                                qc_1[jj1,:,:]  , qc_2[jj1,:,:]  ,
                                psi_1_m[jj1,:,:,0] , psi_2_m[jj1,:,:,0],
                                y, beta)
    #%%
#    if n == 0:
#    XXR, X_labels, x_lib, y_lib = XXlib_gen(N2, N, xx, yy, sx, sy, X_labels_0)
    ##%%
#    XXjac = XXjac_gen(x_lib, y_lib, N2, N, XXR, D_Dx, D_Dy, psic_2_r_all[jj1, :, :, n] )
    ##%%
    XXn = np.zeros( ((N2-2*BOUNDARY_CUT)*(96-2*BOUNDARY_CUT), XX_2D.shape[0]+XXjac.shape[0] ) )#

    # Library of the derivatives of the state variables
    for icount in range(XX_2D.shape[0]):
#        print(icount)
        XXn[:,icount] = cutandvectorize(XX_2D[icount], BOUNDARY_CUT)

    # Library based on state variables
    for jcount in range(XXjac.shape[0]):
#        print(jcount,':',1+icount+jcount)
        XXn[:,1+icount+jcount] = cutandvectorize(XXjac[jcount], BOUNDARY_CUT)

    ##%% is this used anywhere?
    xx_cut = xx[BOUNDARY_CUT:-BOUNDARY_CUT,BOUNDARY_CUT:-BOUNDARY_CUT]
    yy_cut = yy[BOUNDARY_CUT:-BOUNDARY_CUT,BOUNDARY_CUT:-BOUNDARY_CUT]
    #XX =  np.stack((XX0,XX1,XX2,XX3,XX4,XX5),axis=1)
    #XXjac = XX1
    ##%% Stack
    if XXt.shape[0]==0:
        XXt = XXn
    else:
        XXt = np.vstack((XXt,XXn))

#plt.show()
#%%
# from pathlib import Path
# Path(folder_path).mkdir(parents=True, exist_ok=True)

# print('/ Saving the RVM elements, start ... ')

# mdic = {'args': args,
#         'XXt': XXt,
#         'dq1': dq1,
#         'dq2': dq2,
#         'q_1_r': q_1_r,
#         'q_1_m': q_1_m,
#         'q_2_r': q_2_r,
#         'q_2_m': q_2_m,
#         'psi_10':psi_10,
#         'psi_20':psi_20
#         }

# if IF_SAVEMAT==True:
#     savemat(folder_path+'/'+file_name+".mat", mdic)

# print('/ ... Saving the RVM elements, end. ')
#%%
# from scipy.io import loadmat
# #mat_contents = loadmat(folder_path+"3A_RVM_NOISE_MAG=0.0_N_ENS=0_casper")
# #mat_contents = loadmat(folder_path+"3Ald_RVM_NOISE_MAG=0.0_N_ENS=0")
# #mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0rand0d75")
# #mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0rand0d50")
# #mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0rand0d25")
# #mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0rand0d75_4net")

# #folder_path='save/Onenet/'
# #file_name_load = '3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr0.95_len1ADAM200000'
# #mat_contents = loadmat(folder_path+file_name_load)

# #folder_path='save/'
# #mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0rand0d75_4net")

# # folder_path='save/Onenet2/'
# #mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr0.95_len1ADAM100000")
# # mat_contents = loadmat(folder_path+"3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr0.95_len1ADAM500000")

# #folder_path_load ='save/Onenet3/'
# #file_name_load = '3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr0.95_len1ADAM10000'
# #
# folder_path_load='save/Onenet4/'
# # file_name_load = '3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr'+'0.95'+'_len1ADAM'+str(NUM_EPOCHS_ADAM)+'_Gdiff'+str(GAMMA_DIFF)+'_Glapl'+str(GAMMA_LAPL)
# file_name_load = '3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr'+'1.0'+'_len1ADAM'+str(NUM_EPOCHS_ADAM)+'_Gdiff'+str(GAMMA_DIFF)+'_Glapl'+str(GAMMA_LAPL)

# mat_contents = loadmat(folder_path_load+file_name_load)

# dq1s = mat_contents["dq1"].T[:,0]
# dq2s = mat_contents["dq2"].T[:,0]
# XXts = mat_contents["XXt"]

# q_1_rs = mat_contents["q_1_r"]
# q_2_rs = mat_contents["q_2_r"]
# q_1_ms = mat_contents["q_1_m"]
# q_2_ms = mat_contents["q_2_m"]
# psi_10s = mat_contents["psi_10"]
# psi_20s = mat_contents["psi_20"]

# _, _, _, _, q_1_rss , q_2_rss, _, _ =\
# initialize_psi_to_param(psi_10s, psi_20s,\
#                             N2, N, beta, Lapl, y, topographicPV_ref*0)
# #%%
# N2_cut, N1_cut = N2-2*BOUNDARY_CUT, 96-2*BOUNDARY_CUT
# N1N2_cut = N1_cut*N2_cut
# for icount in range(9):
#     XXt[:,icount] = smoother( XXt[:,icount].reshape((N2_cut,N1_cut)),KEEP_RATIO).reshape(N1N2_cut,)
#%% Choose Layer
TOL = 1e14
THRESHOLD_ALPHA_M = np.hstack(([1e-12],10**np.linspace(-7,7,15),[1e12]))
mse_m = np.full((len(THRESHOLD_ALPHA_M),2),np.inf);
len_fit = np.full((len(THRESHOLD_ALPHA_M),2),np.inf);

LAYER_M = [1,2]

for LAYER in LAYER_M:
    print('=======Case: '+str(CASE_NO)+CASE_NO_R+'\n')


    print('LAYER:', LAYER, '\n')
    if LAYER == 1:
        dq = dq1
    elif LAYER == 2:
        dq = dq2
    ##%% Pseudo-inverse
    # pXX = np.linalg.pinv(XXt)
    # c_jac = np.dot(pXX,dq)
    #dR_jac = np.dot(XXt,c_jac).reshape(*xx_cut.shape+(len_,), order='F')#%%
    #dR_jac = np.dot(XXt,c_jac).reshape(*xx_cut.shape, order='F')#%%
    ##%% DUMMY
    print('\n DUMMY \n')
    THRESHOLD_ALPHA = THRESHOLD_ALPHA_M[0]
    iloc = THRESHOLD_ALPHA_M==THRESHOLD_ALPHA
    clfnotfit = RVR(threshold_alpha=1e-50, tol=1e10, verbose=False, standardise=True)
    nofitted = clfnotfit.fit(XXt, dq, X_labels);
    nofitted.m_=0*nofitted.m_
    len_fit[iloc,LAYER-1]=0

    mse_m[iloc,LAYER-1] = nofitted.score_MSE(XXt, dq)
    mse_m[iloc,LAYER-1] = nofitted.score_MSE(XXt, dq)/mse_m[0,LAYER-1]
    print('Score, MSE:', mse_m[iloc,LAYER-1][0] )
    ##%% RVM
    for THRESHOLD_ALPHA in THRESHOLD_ALPHA_M[1:]:
        print('----------------------------------\n')
        print('CASE:', CASE_NO, ', Layer:', str(LAYER),', alpha:', THRESHOLD_ALPHA, '\n')
        #X_labels = range( XX.shape[1])
        clf = RVR(threshold_alpha=THRESHOLD_ALPHA, tol=TOL, verbose=False, standardise=True)
        fitted = clf.fit(XXt, dq, X_labels);
        try:
            iloc = THRESHOLD_ALPHA_M==THRESHOLD_ALPHA
            mse_m[iloc,LAYER-1] = fitted.score_MSE(XXt, dq)/ nofitted.score_MSE(XXt, dq)
            len_fit[iloc,LAYER-1]=len(fitted.m_)
            print('....................................')
            print('Score, MSE:', mse_m[iloc,LAYER-1][0] )

        except:
            print('pass')
        # fitted = clf.fit(XXts, dq1, X_labels);
        # fitted = clf.fit(XXts, dq1s, X_labels );
        # fitted = clf.fit(XXt[:,4:7], dq1, X_labels[4:7]);
        c_rvm_jac = fitted.m_
##%%
def orderOfMagnitude(number):
    return np.floor(np.log10(number))

##%%
#plt.figure(figsize=(10,4))
fig, ax= plt.subplots(nrows=1, ncols=2, figsize=(15,4), dpi=500)

fig.subplots_adjust(right=0.75)

for LAYER in LAYER_M:

    twin1 = ax[LAYER-1].twinx()

    p1, = ax[LAYER-1].loglog(THRESHOLD_ALPHA_M,mse_m[:,LAYER-1], '<-k', label=LAYER_M[LAYER-1])
    #p1, = ax[LAYER-1].loglog(THRESHOLD_ALPHA_M,mse_m[:,1],'>-k',  label=LAYER_M[1])
    #p1, = ax.legend()

    p2, = twin1.semilogx(THRESHOLD_ALPHA_M,len_fit[:,LAYER-1], '<--r', label=LAYER_M[LAYER-1])
    #p2, = twin1.semilogx(THRESHOLD_ALPHA_M,len_fit[:,1],'>--r',  label=LAYER_M[1])
    #p2, = twin1.legend()

    ax[LAYER-1].yaxis.label.set_color(p1.get_color())
    twin1.yaxis.label.set_color(p2.get_color())

    tkw = dict(size=4, width=1.5)
    ax[LAYER-1].tick_params(axis='y', colors=p1.get_color(), **tkw)
    twin1.tick_params(axis='y', colors=p2.get_color(), **tkw)
    ax[LAYER-1].tick_params(axis='x', **tkw)


    YMIN = orderOfMagnitude(mse_m[len_fit!=np.inf].min())-1
    YMAX = orderOfMagnitude(mse_m[len_fit!=np.inf].max())+1

    #ax[LAYER-1].set_ylim([10**YMIN,1])

    twin1.set_ylim([0, len_fit[len_fit!=np.inf].max()+1])

    #ax[LAYER-1].legend(['1', '2'], loc='center left', frameon=False)

    ax[LAYER-1].set_xlabel(r"$\alpha$")
    if LAYER==1:
        ax[LAYER-1].set_ylabel(r"Normalized (MSE) Error ($\%$)")
    if LAYER==2:
        twin1.set_ylabel("$\|c\|_{0}$")
    ax[LAYER-1].grid(which='major', linestyle=':', linewidth='1.0', alpha=0.5, color='k')
    #ax[LAYER-1].set_aspect('equal')

    ax[LAYER-1].yaxis.grid(False)
    #ax[LAYER-1].set_xlim([1e-7,1e7])

    plt.title('CASE:'+str(CASE_NO)+', SR='+str(SENSOR_RATIO)+', interp:'+ interp_type+', Layer:'+str(LAYER))

# plt.savefig(file_name_load+'.png', dpi=300, format=None, metadata=None,
#         bbox_inches=None, pad_inches=0.1,
#         facecolor='auto', edgecolor='auto',
#        )

stop_fitted
#%% Pseudo-inverse
pXX = np.linalg.pinv(XXt)
c_jac = np.dot(pXX,dq)
dR_jac = np.dot(XXt,c_jac).reshape(*xx_cut.shape+(len_,), order='F')#%%
dR_jac = np.dot(XXt,c_jac).reshape(*xx_cut.shape, order='F')#%%
#%%
print('Score, MSE:', fitted.score_MSE(XXt, dq) )
dR_rvm_jac = np.dot(fitted.phi,c_rvm_jac).reshape(*xx_cut.shape+(len_,), order='F')#%%
dR_rvm_jac = np.dot(fitted.phi,c_rvm_jac).reshape(*xx_cut.shape, order='F')#%%
print('Score, MSE:', fitted.score_MSE(XXt, dq) )
dR_rvm_jac = np.dot(fitted.phi,c_rvm_jac).reshape(*xx_cut.shape+(len_,), order='F')#%%
dR_rvm_jac = np.dot(fitted.phi,c_rvm_jac).reshape(*xx_cut.shape, order='F')#%%
#%% Plot
fig = plt.figure(figsize=(17,5))
ax = fig.add_subplot(1, 1, 1)

plt.bar(X_labels, 0*c_jac, 0.15, alpha=0.5)
plt.bar(np.where(fitted.retained_)[0]-0.15, c_rvm_jac, 0.15, alpha=0.5)
#plt.scatter(X_labels, c_exact, s=abs(c_exact*5), marker="+", c="black")
plt.xlabel(r'$\phi_i$', fontsize=20)
plt.ylabel('c', fontsize=20)

plt.tick_params(axis='both', which='major', labelsize=12)

#ax.set_yscale('log')
ax.tick_params(axis='x', rotation=90)

ax.grid(which='minor', alpha=0.2)
ax.grid(which='major', alpha=0.5)
plt.title( file_m+'aa_LAYER='+str(LAYER)+' | '+r'$\epsilon_{tol}=$'+str(TOL)+r', $\alpha=$'+str(THRESHOLD_ALPHA) )

# plt.savefig(file_m+'aa_LAYER='+str(LAYER)+'.png', bbox_inches='tight' , pad_inches = 0)

plt.show()
#%% Plot Bases : Run with exact for XXt and load for XXts
N2_cut, N1_cut = N2-2*BOUNDARY_CUT, 96-2*BOUNDARY_CUT
N1N2_cut = N1_cut*N2_cut

plt.figure(figsize=(12,20))

for ii in range(6):
    plt.subplot(6,3,ii*3+1)
    plt.title(X_labels[ii]);plt.pcolor((XXt[:N1N2_cut,ii]).reshape(N2_cut,N1_cut));plt.colorbar()
    plt.subplot(6,3,ii*3+2)
    plt.title('NN: '+X_labels[ii]);plt.pcolor((XXts[:N1N2_cut,ii]).reshape(N2_cut,N1_cut));plt.colorbar()
    plt.subplot(6,3,ii*3+3)
    plt.title(X_labels[ii]+'|'+str(round(np.linalg.norm(XXt[:N1N2_cut,ii]-XXts[:N1N2_cut,ii]),2)));
    plt.pcolor((XXt[:N1N2_cut,ii]-XXts[:N1N2_cut,ii]).reshape(N2_cut,N1_cut));plt.colorbar()

plt.show()
#%%
plt.figure(figsize=(16,8))

plt.subplot(2,3,1)
plt.pcolor(q_1_r.reshape( N2, 96 ), vmin=-5, vmax=5);plt.colorbar()
plt.subplot(2,3,2)
plt.pcolor(q_1_m.reshape( N2, 96 ), vmin=-5, vmax=5);plt.colorbar()
plt.subplot(2,3,3)
plt.pcolor((q_1_r-q_1_m).reshape( N2, 96 ), vmin=-0.007, vmax=0.007);plt.colorbar()

plt.subplot(2,3,4)
plt.pcolor(q_1_rs.reshape( N2, 96 ), vmin=-5, vmax=5);plt.colorbar()
plt.subplot(2,3,5)
plt.pcolor(q_1_ms.reshape( N2, 96 ), vmin=-5, vmax=5);plt.colorbar()
plt.subplot(2,3,6)
plt.pcolor((q_1_rs -  q_1_ms ).reshape( N2, 96 ), vmin=-0.007, vmax=0.007);plt.colorbar()
#plt.pcolor((q_1_rs -  q_1_ms ).reshape( N2, 96 ));plt.colorbar()
#    plt.colorbar()
#%%
plt.figure(figsize=(16,8))

plt.subplot(2,3,3)
plt.pcolor((q_1_r-q_1_rs).reshape( N2, 96 ));plt.colorbar()

plt.subplot(2,3,6)
plt.pcolor((q_1_m -  q_1_ms ).reshape( N2, 96 ));plt.colorbar()
#    plt.colorbar()

#%%
dq1Mnn = (1/tot_time) * ( q_1_rs -  q_1_ms )# to check the 0th index
dq1nn = cutandvectorize(dq1Mnn, BOUNDARY_CUT)

dq2Mnn = (1/tot_time) * ( q_2_rs -  q_2_ms )# to check the 0th index
dq2nn = cutandvectorize(dq2Mnn, BOUNDARY_CUT)
#%%
plt.figure(figsize=(9,4))
plt.subplot(2,3,1)
plt.pcolor( (1/tot_time)*dq1[:N1N2_cut].reshape( N2_cut, N1_cut ));plt.colorbar();
plt.subplot(2,3,2)
plt.pcolor( (1/tot_time)*dq1s[:N1N2_cut].reshape( N2_cut, N1_cut ));plt.colorbar();
plt.subplot(2,3,3)
plt.pcolor( (1/tot_time)*dq1nn[:N1N2_cut].reshape( N2_cut, N1_cut ));plt.colorbar();
#%%
#    _, _, _, _, q_1_rz , q_2_rz, _, _ =\
#    initialize_psi_to_param(psi_10, psi_20,\
#                                N2, 96, beta, Lapl, y, topographicPV_ref)
#%% p to q, and q to p
from QGlib import ptq
def ptq1(ps1, ps2, Lapl):
    """Calculate PV"""
    q1 = Lapl * ps1 - 1*(ps1 - ps2) # -(k^2 + l^2) * psi_1 -(psi_1-psi_2)
    q2 = Lapl * ps2 + 1*(ps1 - ps2) # -(k^2 + l^2) * psi_2 +(psi_1-psi_2)
    return q1, q2

def ptq2(ps1, ps2, Lapl):
    """Calculate PV"""
    q1 = Lapl * ps1*1 - (ps1 - ps2) # -(k^2 + l^2) * psi_1 -(psi_1-psi_2)
    q2 = Lapl * ps2*1 + (ps1 - ps2) # -(k^2 + l^2) * psi_2 +(psi_1-psi_2)
    return q1, q2

psic_1 = np.fft.rfft2(psi_10)
psic_2 = np.fft.rfft2(psi_20)

vorc_1, vorc_2 = ptq(psic_1, psic_2, Lapl)
qq_1  = np.fft.irfft2( vorc_1) + beta * y[:, np.newaxis]

psic_1s = np.fft.rfft2(psi_10s)
psic_2s = np.fft.rfft2(psi_20s)
#psic_1s = np.fft.rfft2(u_list[0].reshape(N2,N))
#psic_2s = np.fft.rfft2(w_list[0].reshape(N2,N))

vorc_1s, vorc_2s = ptq(psic_1s, psic_2s, Lapl)
qq_1s  = np.fft.irfft2( vorc_1s) + beta * y[:, np.newaxis]

#u_list= net22.lib_DP(xx_torch.cuda(), yy_torch.cuda(), 0, scale)
#w_list= net22.lib_DP(xx_torch.cuda(), yy_torch.cuda(), 1, scale)
#qq_1s = ((u_list[3]+u_list[4]) - (u_list[0] - w_list[0])).reshape(N2,N) + beta * y[:, np.newaxis]
#%%
plt.figure(figsize=(15,4))
plt.subplot(1,3,1)
plt.pcolor(qq_1);plt.colorbar()
plt.subplot(1,3,2)
plt.pcolor(qq_1s);plt.colorbar()
plt.subplot(1,3,3)
plt.pcolor(qq_1-qq_1s, vmin=-1,vmax=1);plt.colorbar()
plt.title(str(round(np.linalg.norm(qq_1s-qq_1),2)));
#%%
VMIN=-5/10
VMAX=-VMIN
plt.figure(figsize=(15,10))

plt.subplot(2,2,1)
plt.pcolor(xxv,yyv, np.fft.irfft2( vorc_1 - vorc_1s), vmin=VMIN,vmax=VMAX);plt.colorbar()
plt.scatter(xv1,yv1,marker='.',color='k',s=1.0)
#plt.xlim([-1,1]);plt.ylim([-1,1])

plt.subplot(2,2,2)
plt.pcolor(xxv,yyv,  np.fft.irfft2( vorc_2 - vorc_2s), vmin=VMIN,vmax=VMAX);plt.colorbar()
plt.scatter(xv1,yv1,marker='.',color='k',s=1.0)
#plt.xlim([-1,1]);plt.ylim([-1,1])

plt.subplot(2,2,3)
plt.pcolor(xxv,yyv,  np.fft.irfft2( vorc_1 - vorc_1s), vmin=-0.5,vmax=0.5);plt.colorbar()
plt.scatter(xv1,yv1,marker='.',color='k',s=0.2)
plt.subplot(2,2,4)
plt.pcolor(xxv,yyv,  np.fft.irfft2( vorc_1) -  np.fft.irfft2( vorc_1s), vmin=-0.5,vmax=0.5);plt.colorbar()
plt.scatter(xv1,yv1,marker='+',color='k',s=5.0)
plt.xlim([-1,1]);plt.ylim([-1,1])
#%%
plt.scatter(np.diag(vorc_1s).real, np.diag(vorc_1s).imag,marker='*')
plt.scatter(np.diag(vorc_1).real,np.diag(vorc_1).imag,marker='+')
#%%
uxxpuyy = (u_list[3]+u_list[4]).reshape(N2,N)
uxxpuyy = cutandvectorize(uxxpuyy, BOUNDARY_CUT)
plt.figure(figsize=(15,4))
plt.subplot(1,3,1)
plt.pcolor( (uxxpuyy ).reshape(N2_cut,N1_cut));plt.colorbar()
plt.subplot(1,3,2)
plt.pcolor( (XXt[:N1N2_cut,0]).reshape(N2_cut,N1_cut));plt.colorbar()
plt.subplot(1,3,3)
plt.pcolor( (uxxpuyy -XXt[:N1N2_cut,0]).reshape(N2_cut,N1_cut),vmin=-0.21,vmax=0.21);plt.colorbar()
#%%
uxxpuyy = (u_list[0]).reshape(N2,N)
uxxpuyy = cutandvectorize(uxxpuyy, BOUNDARY_CUT)

plt.figure(figsize=(15,4))
plt.subplot(1,3,1)
plt.pcolor( (uxxpuyy ).reshape(N2_cut,N1_cut) , vmin=-5, vmax=5);plt.colorbar();
plt.subplot(1,3,2)
plt.pcolor( (XXt[:N1N2_cut,4]).reshape(N2_cut,N1_cut), vmin=-5, vmax=5);plt.colorbar();
plt.subplot(1,3,3)
plt.pcolor( (uxxpuyy -XXt[:N1N2_cut,4]).reshape(N2_cut,N1_cut),vmin=-0.1,vmax=0.1);plt.colorbar();
#%%
from myfilters import smoother
for KEEP_RATIO in [1.0, 0.75, 0.5, 0.25,0.10,0.05]:
    # checkpoint = torch.load('save/Onenet2/3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr0.95_len1ADAM500000.pth')
    # checkpoint = torch.load('save/Onenet3/3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr0.95_len1ADAM10000.pth')
    NUM_EPOCHS_ADAM = int(300e3)
    GAMMA_DIFF = 0.0
    GAMMA_LAPL = 0.0
    DEEP = 4
    HIDDEN = 1000
    folder_path_load='save/Onenet4/'
    file_name_load = '3A_D'+str(DEEP)+'_RVM_NOISE_MAG=0.0_N_ENS=0_sr'+'1.0'+'_len1ADAM'+str(NUM_EPOCHS_ADAM)+'_Gdiff'+str(GAMMA_DIFF)+'_Glapl'+str(GAMMA_LAPL)
    # file_name_load = '3A_D4_RVM_NOISE_MAG=0.0_N_ENS=0_sr1.0_len1ADAM300000_Gdiff0.1_Glapl0.0'
    checkpoint = torch.load(folder_path_load+file_name_load+'.pth')

    net11 = Net(HIDDEN, DEEP).cuda()
    # net22 = Net(HIDDEN, DEEP).cuda()

    net11.load_state_dict(checkpoint['model11_state_dict'])
    # net22.load_state_dict(checkpoint['model22_state_dict'])

    u_list= net11.lib_DP(xx_torch.cuda(), yy_torch.cuda(), 0, scale)
    w_list= net11.lib_DP(xx_torch.cuda(), yy_torch.cuda(), 1, scale)
    ##%%
    u_list_r = net22.lib_DP(xx_torch.cuda(), yy_torch.cuda(), 0, scale)
    w_list_r = net22.lib_DP(xx_torch.cuda(), yy_torch.cuda(), 1, scale)

    psi_1_r_NN = u_list_r[0].reshape(*psi_10.shape)
    psi_2_r_NN = w_list_r[0].reshape(*psi_20.shape)

    psi_1_r_NN= smoother(psi_1_r_NN,KEEP_RATIO)
    psi_2_r_NN = smoother(psi_2_r_NN,KEEP_RATIO)

    _, _, _, _, q_1_r_NN , q_2_r_NN, _, _ =\
    initialize_psi_to_param(psi_1_r_NN, psi_2_r_NN,\
                                N2, N, beta, Lapl, y, topographicPV_ref)

    psic_1 = np.fft.rfft2(psi_10)
    psic_2 = np.fft.rfft2(psi_20)

    # vorc_1s, vorc_2s = ptq(psic_1s, psic_2s, Lapl)
    # qq_1_net1  = np.fft.irfft2( vorc_1s) + beta * y[:, np.newaxis]
    ##%%
    plt.figure(figsize=(12,12))
    plt.subplot(4,3,1)
    plt.pcolor(psi_1_r_NN);plt.colorbar();
    plt.title(X_labels[4]+', NN')
    plt.subplot(4,3,2)
    plt.pcolor(psi_1_r);plt.colorbar();
    plt.title(X_labels[4])
    plt.subplot(4,3,3)
    plt.pcolor(psi_1_r_NN-psi_1_r);plt.colorbar();
    error_psi_1 = np.linalg.norm( psi_1_r_NN-psi_1_r ) /  np.linalg.norm( psi_1_r )*100
    plt.title(str(round(error_psi_1,2))+"%")

    plt.subplot(4,3,4)
    plt.pcolor(psi_2_r_NN);plt.colorbar();
    plt.title(X_labels[5])
    plt.subplot(4,3,5)
    plt.pcolor(psi_2_r);plt.colorbar();
    plt.subplot(4,3,6)
    plt.pcolor(psi_2_r_NN-psi_2_r);plt.colorbar();
    error_psi_2 = np.linalg.norm( psi_2_r_NN-psi_2_r )/  np.linalg.norm( psi_2_r )*100
    plt.title(str(round(error_psi_2,2))+"%")

    plt.subplot(4,3,7)
    plt.pcolor(np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r_NN) ));plt.colorbar();
    plt.title(X_labels[0])

    plt.subplot(4,3,8)
    plt.pcolor(np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r) ));plt.colorbar();
    plt.subplot(4,3,9)
    plt.pcolor(np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r_NN) ) -
               np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r) )  ,vmin=-2,vmax=2);plt.colorbar();
    error = np.linalg.norm( np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r_NN) ) -
                           np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r) ) )
    plt.title(str(round(error,2)))


    plt.subplot(4,3,10)
    plt.pcolor(np.fft.irfft2(Lapl *np.fft.rfft2(psi_2_r_NN) ));plt.colorbar();
    plt.title(X_labels[1])

    plt.subplot(4,3,11)
    plt.pcolor(np.fft.irfft2(Lapl *np.fft.rfft2(psi_2_r) ));plt.colorbar();
    plt.subplot(4,3,12)
    plt.pcolor(np.fft.irfft2(Lapl *np.fft.rfft2(psi_2_r_NN) ) -
               np.fft.irfft2(Lapl *np.fft.rfft2(psi_2_r) )  ,vmin=-2,vmax=2);plt.colorbar();
    error = np.linalg.norm( np.fft.irfft2(Lapl *np.fft.rfft2(psi_1_r_NN) ) -
                           np.fft.irfft2(Lapl *np.fft.rfft2(psi_2_r) ) )
    plt.title(str(round(error,2))+'__'+str(KEEP_RATIO))
    #%%
    plt.figure(figsize=(10,3))
    plt.subplot(1,3,1)
    plt.pcolor(psi_10);plt.colorbar()
    plt.subplot(1,3,2)
    plt.pcolor(psi_1_r);plt.colorbar()
    plt.subplot(1,3,3)
    plt.pcolor(psi_10-psi_1_r);plt.colorbar()

