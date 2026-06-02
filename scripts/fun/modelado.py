#!/usr/bin/env python
# coding: utf-8


import pandas as pd
import numpy as np
from pvlib import irradiance


def calculaGTImod(inc_deg,az,anguloCenital,azimutSolar,GHI,DHI,DNI,Go,AM,modDict,rho=0.25):
    #Función que devuelve un dataframe "GTI_modelada" con las estimaciones de GTI para cada modelo,
    #proveniente de un diccionario "modDict" con el modelo y su abreviatura. 

    
    GTI_modelada = pd.DataFrame(columns=modDict.keys())
    for modelo in modDict.keys():
        GTIm = (irradiance.get_total_irradiance(inc_deg,az,anguloCenital,azimutSolar,
                            DNI,GHI,DHI,Go,AM,albedo=rho, model=modDict[modelo]))
        
        GTI_modelada[modelo] = GTIm.poa_global
    return GTI_modelada

#----------------------------------------------------------------------------------------------
#Modelos de separación directa-difusa

def ruiz_arias(kt,m,params, simplificado=True):

    if simplificado: #RA2S
        a0 = params[0]; a1 = params[1]; a2 = params[2]; a3 = params[3]; a4 = 0; a5 = params[5]; a6 = 0
    else:
        a0 = params[0]; a1 = params[1]; a2 = params[2]; a3 = params[3]; a4 = params[4]; a5 = params[5]; a6 = params[6]
    
    fd_RA = a0 + a1*np.exp(-np.exp(a2 + (a3*kt) + (a5*m) + (a4*(kt**2)) + (a6*(m**2))))
    fd_RA[fd_RA < 0] = 0
    
    return fd_RA 

def RA1(kt,a1,a2,a3):
    
    fd = 1 + a1*np.exp(-np.exp(a2 + a3*kt))
    fd[fd < 0] = 0
    
    return fd

def RA2(X,a0,a1,a2,a3,a4,a5,a6):
    
    kt,m = X
    fd = a0 + a1*np.exp(-np.exp(a2 + (a3*kt) + (a5*m) + (a4*(kt**2)) + (a6*(m**2))))
    fd[fd < 0] = 0
    
    return fd

def RA2S(X,a0,a1,a2,a3,a5):
    
    kt,m = X
    fd = a0 + a1*np.exp(-np.exp(a2 + (a3*kt) + (a5*m)))
    fd[fd < 0] = 0
    
    return fd

def ERBS(kt,params):
    a1 = params[0]; b0 = params[1]; b1 = params[2]; b2 = params[3]; b3 = params[4];
    b4 = params[5]; c0 = params[6]
    
    msk1 = (kt > 0) & (kt < 0.22)
    msk2 = (kt >= 0.22) & (kt < 0.8)
    msk3 = kt > 0.8
    
    fd_erbs = pd.Series(index = kt.index, dtype='float64')
    fd_erbs.loc[msk1] = 1 + a1*kt[msk1]
    fd_erbs.loc[msk2] = b0 + b1*kt[msk2] + b2*(kt[msk2])**2 + b3*(kt[msk2])**3 + b4*(kt[msk2])**4
    fd_erbs.loc[msk3] = c0 
    
    fd_erbs[fd_erbs < 0] = 0
    
    return fd_erbs

#---------------------------------------------------------------------------------------------
#MODELO ESRA DE CIELO CLARO:

def altSolarCorregida(altSolar):
    num = 0.1594 + 1.1230*(np.pi/180)*altSolar + 0.065656*((np.pi/180)**2)*(altSolar**2)
    den = 1 + 28.9344*(np.pi/180)*altSolar + 277.3971*((np.pi/180)**2)*(altSolar**2)
    gamma_refr = 0.061359*(180/np.pi)*(num/den)
    
    return (altSolar + gamma_refr)
    
def am_kastenYoung(Zsnm,altSolar):
    Zh = 8434.5
    gamma_deg = altSolarCorregida(altSolar)
    gamma_rad = np.deg2rad(gamma_deg)
    num = np.exp(-Zsnm/Zh)
    denom = np.sin(gamma_rad) + 0.50572*(gamma_deg + 6.07995)**(-1.6364)
    
    return num/denom

def generaComponentesESRA(alt_solar,Go,Zsnm,TL=2.0):
    #Vía PVLIB calculo Gscf y AM para luego usar el modelo ESRA de cielo claro
    
    gamma_s = altSolarCorregida(alt_solar)

    am = am_kastenYoung(Zsnm,gamma_s)
    
    delta_r = 1/(6.62960 + 1.75130*am - 0.12020*(am**2) + 0.00650*(am**3) - 0.00013*(am**4))
    delta_r[am > 20] = 1/(10.4 + 0.718*am[am > 20])
    

    BHI = Go*np.sin(np.deg2rad(alt_solar))*np.exp(-0.8662*TL*am*delta_r) #componente directa
    BHI[BHI<0] = 0
    
    Trd = -1.5843e-2 + 3.0543e-2*TL + 3.797e-4*(TL**2)
    
    A0 = 2.6463e-1 - TL*6.1581e-2 + (TL**2)*3.1408e-3
    A1 = 2.0402 + TL*1.8945e-2 - (TL**2)*1.1161e-2
    A2 = -1.3025 + TL*3.9231e-2 + (TL**2)*8.5079e-2
    

    #Modificación de A0, depende del type(TL). Puede ser float o series
    
    if isinstance(TL, (np.floating, float)):
        if A0*Trd < 2e-3:
            A0 = (2e-3)/Trd
    else:
        A0[A0*Trd < 2e-3] = (2e-3)/Trd 
    
    Fd = A0 + A1*np.sin(np.deg2rad(alt_solar)) + A2*((np.sin(np.deg2rad(alt_solar)))**2) 

    DHI = Go*Trd*Fd #Componente difusa
    DHI[DHI<0] = 0
    
    DNI = BHI/np.sin(np.deg2rad(alt_solar))
    DNI[DNI<0] = 0
    
    GHI = BHI + DHI
    
    return GHI, DHI, DNI

#---------------------------------------------------------------------------------------------
#MODELO PEREZ DE TRANSPOSICION:
def perez(surface_inc,zenith,aoi,airmass,Go,GHI,DHI,DNI,rho=0.25):
    
    beta = np.deg2rad(surface_inc)
    z = np.radians(zenith)
    
    
    
    delta = DHI * airmass / Go
    
    F1c, F2c = irradiance._get_perez_coefficients('allsitescomposite1990')
    
    nans = np.array([np.nan, np.nan, np.nan])
    F1c = np.vstack((F1c, nans))
    F2c = np.vstack((F2c, nans))
   
    a = np.maximum(0,np.cos(np.radians(aoi)))
    c = np.maximum(np.cos(np.radians(85)),np.cos(z))
    
    eps = ((DHI + DNI)/DHI + (1.041*z**3))/(1 + 1.041*z**3)
    
    if isinstance(eps,pd.Series):
        eps = eps.values
    
    ebin = np.digitize(max(eps), (0., 1.065, 1.23, 1.5, 1.95, 2.8, 4.5, 6.2))
    # ebin = np.array(ebin)  # GH 642
    # ebin[np.isnan(eps)] = 0
    
    F1 = np.maximum(0,F1c[ebin-1,0] + delta*F1c[ebin-1,1] + z*F1c[ebin-1,2])
    F2 = F2c[ebin-1,0] + delta*F2c[ebin-1,1] + z*F2c[ebin-1,2]

    Rd = (1-F1)*(1+np.cos(beta))*0.5 + F1*(a/c) + F2*np.sin(beta)
    
    direct = DNI*np.maximum(0,np.cos(np.radians(aoi)))
    diffuse = DHI*Rd
    reflected = rho*GHI*0.5*(1-np.cos(beta))
    total = direct + diffuse + reflected
    
    return total, direct, diffuse, reflected


    
