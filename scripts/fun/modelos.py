#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 17 14:19:39 2021

@author: inti
"""

import numpy as np

#%%
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

def generaComponentesESRA(alt_solar,Go,Zsnm,TL=2):
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
#%%
#Interpolación para obtener los ciclos TL
def getTL(ciclosTL,est,doy):
    TL = ciclosTL[est]
    doy_medio = [15, 45, 75, 105, 136, 166, 197, 228, 258, 289, 319, 350] #doy del centro de cada mes
    TLinterp = np.interp(doy , doy_medio, TL, period = 366)
    
    return TLinterp