#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 21 11:35:23 2021

@author: inti
"""
#Funciones para determinar el omega que maximiza la medida de GTI (ajustada)
import pandas as pd
import numpy as np
import pvlib as pv
from fun import modelado as md


#Funciones para determinar el omega que maximiza la medida de GTI (ajustada)
def get_solar_noon(times,lon):
    doy = times.dayofyear.unique()
    E = pv.solarposition.equation_of_time_spencer71(doy)
    omega = pd.Series(data= pv.solarposition.hour_angle(times,lon,E), index=times) 
    return abs(omega).idxmin()

def getIntervalGTImax(GTI,deltaT=1): 
    #Devuelve la GTI alrededor del máximo (+- 1h por def)
    t_max = GTI.idxmax()
    t1 = t_max - pd.Timedelta(hours=deltaT)
    t2 = t_max + pd.Timedelta(hours=deltaT)
    return GTI.loc[t1:t2], t1, t2

def ajusteGTI(GTI,grado=2,exp=3):
    #Devuelve la GTI ajustada por un pol. de gr 4 
    GTI = GTI.dropna()    
    x_val = np.linspace(0,1,len(GTI))
    y_val = GTI**exp
    
    coeffs = np.polyfit(x_val,y_val,grado)
    poly_eqn = np.poly1d(coeffs)
    y_hat = pd.Series(poly_eqn(x_val),index=GTI.index)
    
    return y_hat, y_hat**(1/exp)

def getDeltaOmega(GTI_ajustada,omegaDeg):
    tmax = GTI_ajustada.idxmax()
    dw = omegaDeg[tmax]
    
    return dw

def remove_noise_fit(GTI,GTI_fit,tol=5):
    GTI_copy = GTI.copy(deep=True)
    msk_noise_tol = abs(GTI - GTI_fit) > tol
    while msk_noise_tol.sum() > 0:
        GTI_copy[msk_noise_tol] = GTI_fit[msk_noise_tol]
        _,GTI_fit = ajusteGTI(GTI_copy)
        msk_noise_tol = abs(GTI_copy - GTI_fit) > tol

    return GTI_copy

#Funciones para calcular la curva característica omega vs gamma.

def crea_serie_temp_1s(dia,lat_deg, lon_deg,tz,freq='1s'):
    days = pd.date_range(dia,dia,tz=tz)
    sunrise_sunset = pv.solarposition.sun_rise_set_transit_spa(days, lat_deg, lon_deg)
    ti=sunrise_sunset['sunrise'][0].round(freq)
    tf=sunrise_sunset['sunset'][0].round(freq)
    serie_temp_1s = pd.date_range(ti,tf,freq=freq)
    
    return serie_temp_1s

def variables_solares(solar_pos,loc):
    am = loc.get_airmass(solar_pos.index)
    am = am['airmass_absolute']
    hour_angle = pv.solarposition.hour_angle(solar_pos.index,
                                             loc.longitude, solar_pos.equation_of_time)
    hour_angle = pd.Series(hour_angle,index=solar_pos.index)
    Go = pv.irradiance.get_extra_radiation(solar_pos.index)
    
    return am,hour_angle,Go

def curva_caracteristica(beta,solar_pos,am_1s,Go_1s,w_1s,GHI_csk,DHI_csk,DNI_csk,azi_range):
    omega_gamma = np.zeros(len(azi_range))
    j=0
    for surf_azi in azi_range:
        aoi = pv.irradiance.aoi(beta,surf_azi,solar_pos['zenith'],solar_pos['azimuth'])
        GTI_csk,_,_,_ = perez(beta,solar_pos['zenith'],aoi,am_1s,Go_1s,GHI_csk,DHI_csk,DNI_csk,rho=0.25)
        omega_gamma[j] = w_1s[GTI_csk.idxmax()]
        j=j+1
    
    return omega_gamma

#Funciones para ajustar e interpolar en la curva caracteristica

def ajustaCurva(azimuts,dw_azimutal):
    '''Ajusta la curva delta omega en función del azimut por un polinomio de 3º grado, devolviendo los valores
    funcionales del ajuste así como la ecuación del mismo.
    '''
    x_val = azimuts; y_val = dw_azimutal
    coeffs = np.polyfit(x_val,y_val,3)
    poly_eqn = np.poly1d(coeffs)
    y_hat = poly_eqn(x_val)
    
    return y_hat, poly_eqn

def interpola(dwExperimental,poly_eqn,azimuts):
    '''Recibe un delta omega obtenido experimentalmente y el resultado del ajuste de la curva, interpola
    y devuelve el resultado, que corresponde a la estimación del azimut (dado que es el corte de una recta
    con un polinomio de 3º grado, son 3 soluciones y hay que elegir la que está en el intervalo (-az,az))
    '''
    raices = np.roots(poly_eqn - dwExperimental)
    raiz = raices[(raices<azimuts[-1])&(raices>(azimuts[0]))]
    
    return raiz

#Funciones extra (PEREZ, interpolar TL, etc)
def getTL(ciclosTL,est,doy):
    TL = ciclosTL[est]
    doy_medio = [15, 45, 75, 105, 136, 166, 197, 228, 258, 289, 319, 350] #doy del centro de cada mes
    TLinterp = np.interp(doy , doy_medio, TL, period = 366)
    
    return TLinterp

def perez(surface_inc,zenith,aoi,airmass,Go,GHI,DHI,DNI,rho=0.25):
    
    beta = np.deg2rad(surface_inc)
    z = np.radians(zenith)
    
    
    
    delta = DHI * airmass / Go
    
    F1c, F2c = pv.irradiance._get_perez_coefficients('allsitescomposite1990')
    
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


#Funciones para realizar el cálculo analítico en base al modelo ESRA

def get_m_from_omega(w,DOY,beta,lat): #(w, beta, lat) en deg todos!
    sinDelta = np.sin(pv.solarposition.declination_spencer71(DOY)) #dec en rad, de acuerdo a PVLIB
    cosDelta = np.cos(pv.solarposition.declination_spencer71(DOY))
    sinPhi = np.sin(np.deg2rad(lat)); cosPhi = np.cos(np.deg2rad(lat))
    sinBeta = np.sin(np.deg2rad(beta)); cosBeta = np.cos(np.deg2rad(beta))
    
    cosz = sinDelta*sinPhi + cosDelta*cosPhi*np.cos(np.deg2rad(w))
    return 1/cosz  

def get_m_dot(w,DOY,beta,lat): #(w, beta, lat) en deg todos!
    m = get_m_from_omega(w,DOY,beta,lat)
    cosDelta = np.cos(pv.solarposition.declination_spencer71(DOY))
    cosPhi = np.cos(np.deg2rad(lat))
    
    return (m**2)*cosDelta*cosPhi*np.sin(np.deg2rad(w))

    
# def get_mkr(w,DOY,beta,lat):
#     m = get_m_from_omega(w,DOY,beta,lat)
#     P4 = (6.62960 + 1.75130*m - 0.12020*(m**2) + 0.00650*(m**3) - 0.00013*(m**4))
#     mkr = m/P4

#     return mkr

def get_d_mkr(w,DOY,beta,lat):
    m = get_m_from_omega(w,DOY,beta,lat)
    m_dot = get_m_dot(w,DOY,beta,lat)
    P4 = (6.62960 + 1.75130*m - 0.12020*(m**2) + 0.00650*(m**3) - 0.00013*(m**4))
    P3 = (1.75130 - 2*0.12020*m + 3*0.00650*(m**2) - 4*0.00013*(m**3))
    
    return (m_dot/P4**2)*(P4 - m*P3)

def get_xi(beta,fd,rho_g=0.20):
    Fb = (1+np.cos(np.deg2rad(beta)))*0.5
    Kb = (1-np.cos(np.deg2rad(beta)))*0.5
    xi = fd*Fb + rho_g*Kb
    return xi


# def eqn(x,DOY,LATdeg,BETAdeg,w_ast,m,d_mkr,TL,xi,fd):
#     #x = azim_sup en radianes!
#     sinDelta = np.sin(pv.solarposition.declination_spencer71(DOY))
#     cosDelta = np.cos(pv.solarposition.declination_spencer71(DOY))
#     sinPhi = np.sin(np.deg2rad(LATdeg)); cosPhi = np.cos(np.deg2rad(LATdeg))
#     sinBeta = np.sin(np.deg2rad(BETAdeg)); cosBeta = np.cos(np.deg2rad(BETAdeg))
#     sinw = np.sin(np.deg2rad(w_ast)); cosw = np.cos(np.deg2rad(w_ast))

    
#     a0 = sinDelta*sinPhi*cosBeta + sinDelta*cosPhi*sinBeta*np.cos(x)
#     a1 = cosDelta*cosPhi*cosBeta - cosDelta*sinPhi*sinBeta*np.cos(x)
#     a2 = cosDelta*sinBeta*np.sin(x)

#     cos_theta = a0 + a1*cosw + a2*sinw
#     dcos_theta = -a1*sinw + a2*cosw
    
#     B = cosDelta*cosPhi
    
#     rb = m*cos_theta
#     rb_dot  = m*(dcos_theta + m*B*sinw*cos_theta) 
    
#     return rb_dot - (TL*d_mkr + m*B*sinw)*(rb + xi/(1-fd)) 

def eqn(x,DOY,LATdeg,BETAdeg,w_ast,m,d_mkr,TL,xi,fd):
    #x = cos(azim_sup). Mejora la resolución de la ecuación.
    sinDelta = np.sin(pv.solarposition.declination_spencer71(DOY))
    cosDelta = np.cos(pv.solarposition.declination_spencer71(DOY))
    sinPhi = np.sin(np.deg2rad(LATdeg)); cosPhi = np.cos(np.deg2rad(LATdeg))
    sinBeta = np.sin(np.deg2rad(BETAdeg)); cosBeta = np.cos(np.deg2rad(BETAdeg))
    sinw = np.sin(np.deg2rad(w_ast)); cosw = np.cos(np.deg2rad(w_ast))

    
    a0 = sinDelta*sinPhi*cosBeta + sinDelta*cosPhi*sinBeta*x
    a1 = cosDelta*cosPhi*cosBeta - cosDelta*sinPhi*sinBeta*x
    a2 = cosDelta*sinBeta*np.sqrt(1-x**2)

    cos_theta = a0 + a1*cosw + a2*sinw
    dcos_theta = -a1*sinw + a2*cosw
    
    B = cosDelta*cosPhi
    
    rb = m*cos_theta
    rb_dot  = m*(dcos_theta + m*B*sinw*cos_theta) 
    
    return rb_dot - (TL*d_mkr + m*B*sinw)*(rb + xi/(1-fd)) 

#ver función cos_theta = f(x) 


